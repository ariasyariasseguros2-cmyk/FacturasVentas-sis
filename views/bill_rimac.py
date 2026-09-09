import os
import re
import traceback
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from utils.validacion_bd import (
    validar_filas_contra_bd,
    COLOR_VERDE,
    COLOR_AMARILLO,
    COLOR_ROJO,
)


TWO_PLACES = Decimal("0.01")
IGV_PORCENTAJE = Decimal("0.18")
MONEDA_RIMAC = "$"


def _to_decimal_rimac(val: Any) -> Decimal:
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    try:
        s = str(val).strip()
        if not s:
            return Decimal("0")
        s = s.replace("S/", "").replace("S/.", "").replace("$", "").replace("USD", "")
        s = s.replace(",", "").replace("%", "").strip()
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return Decimal("0")
        return Decimal(m.group(0)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, Exception):
        return Decimal("0")


def _round2_rimac(v: Decimal) -> Decimal:
    if not isinstance(v, Decimal):
        v = _to_decimal_rimac(v)
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ============================================================
#   EXTRACCIÓN DE DATOS DE PDF RÍMAC — PRELIQUIDACIÓN
# ============================================================

_FECHA_RE_R = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")
_NRO_DOC_RE_R = re.compile(r"\b((?:[A-Z0-9]{1,6}-){1,4}[A-Z0-9\-\/]{3,})\b")
_CODIGO_SUNAT_RE_R = re.compile(r"\b(FA?-[A-Z0-9\-]{5,}|F\d{3}-[A-Z0-9\-]{5,})\b")
_POLIZA_RE_R = re.compile(r"\b(\d{6,12})\b")
_MONTO_RE_R = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})*\.\d{2})(?!\d)|(?<!\d)(\d{3,}\.\d{2})(?!\d)")
_PORCENTAJE_RE_R = re.compile(r"\b(\d{1,3}(?:\.\d{1,2})?)\s*(?:%\s*)?\b")

_RIMAC_HEADER_TOKENS = (
    "producto", "poliza", "póliza", "cliente", "documento",
    "doc.sunat", "doc. sunat", "tipo", "fecha pago", "prima total",
    "porcent. comisi", "porcentaje comisi", "comision", "comisión",
)


def extraer_tablas_rimac(pdf_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except Exception:
        raise RuntimeError("Se requiere la librería 'pdfplumber' para extraer datos del PDF.")

    filas: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_filas: List[Dict[str, Any]] = []
            extraido = False

            rows_text = _extraer_rimac_por_coordenadas(page)
            if rows_text and len(rows_text) >= 1:
                page_filas.extend(rows_text)
                extraido = True

            if not extraido:
                estrategias = [
                    {
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "text",
                        "join_tolerance": 5,
                        "edge_min_length": 2,
                        "snap_tolerance": 8,
                        "snap_x_tolerance": 8,
                        "snap_y_tolerance": 6,
                        "min_words_vertical": 1,
                        "min_words_horizontal": 1,
                        "intersection_tolerance": 6,
                    },
                    {
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                        "intersection_tolerance": 12,
                        "snap_tolerance": 8,
                        "min_words_vertical": 1,
                        "min_words_horizontal": 1,
                    },
                    {
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "join_tolerance": 4,
                        "edge_min_length": 2,
                        "snap_tolerance": 6,
                        "min_words_vertical": 1,
                        "min_words_horizontal": 1,
                    },
                ]

                for settings in estrategias:
                    try:
                        t = page.extract_table(table_settings=settings)
                    except Exception:
                        t = None
                    if not t:
                        continue

                    rows_page = _procesar_tabla_rimac_con_encabezado(t)
                    if rows_page:
                        page_filas.extend(rows_page)
                        extraido = True
                        break

            filas.extend(page_filas)
    return filas


# ============================================================
#   MAPEO DE COLUMNAS POR ENCABEZADO REAL RÍMAC
# ============================================================

_CAMPO_RIMAC_POR_PALABRAS = [
    ("producto",           ["producto", "product", "prod."]),
    ("poliza",             ["poliza", "póliza", "pólizas", "poliza nro", "nro poliza"]),
    ("cliente",            ["cliente", "razon social", "razón social", "nombre", "asegurado"]),
    ("documento",          ["documento", "nro documento", "n° documento", "cupon", "cupón", "recibo"]),
    ("doc_sunat",          ["doc.sunat", "doc. sunat", "doc sunat", "factura sunat", "codigo sunat", "código sunat", "doc.legal", "doc. legal"]),
    ("tipo",               ["tipo", "tipo doc", "tipo de", "clase"]),
    ("fecha_pago",         ["fecha pago", "fechapago", "fecha de pago", "fecha emision", "fecha emisión", "fecha"]),
    ("prima_total",        ["prima total", "prima", "monto prima", "importe prima", "prima bruta"]),
    ("porcentaje_comision",["porcent. comisi", "porcentaje comisi", "% comisi", "porcent comisión", "pct comision"]),
    ("comision",           ["comision", "comisión", "monto comision", "importe comision", "comision total"]),
]


def _detectar_columnas_rimac_por_encabezado(fila_encabezado) -> Optional[Dict[str, int]]:
    if not fila_encabezado:
        return None
    norm_cells = []
    for i, c in enumerate(fila_encabezado):
        s = "" if c is None else str(c).replace("\n", " ").strip().lower()
        s = re.sub(r"\s{2,}", " ", s)
        norm_cells.append(s)
    joined = " ".join(norm_cells)
    if not any(k in joined for k in ("poliza", "póliza", "prima", "comision", "comisión", "doc.sunat", "doc. sunat")):
        return None
    mapa: Dict[str, int] = {}
    for idx, s in enumerate(norm_cells):
        matched = None
        for campo, palabras in _CAMPO_RIMAC_POR_PALABRAS:
            for palabra in palabras:
                if palabra in s:
                    matched = campo
                    break
            if matched:
                break
        if matched and matched not in mapa:
            mapa[matched] = idx
    checks = [
        "comision" in mapa,
        ("poliza" in mapa or "documento" in mapa or "cliente" in mapa),
        ("prima_total" in mapa or "fecha_pago" in mapa),
    ]
    if sum(checks) >= 2:
        return mapa
    return None


def _procesar_tabla_rimac_con_encabezado(tabla) -> List[Dict[str, Any]]:
    if not tabla:
        return []
    filas = list(tabla)
    header_row_idx = None
    mapa = None
    for start in range(min(5, len(filas))):
        mapa = _detectar_columnas_rimac_por_encabezado(filas[start])
        if mapa is not None:
            header_row_idx = start
            break
    if mapa is None or header_row_idx is None:
        return []

    out: List[Dict[str, Any]] = []
    acumulada: Optional[Dict[str, Any]] = None

    def _mergear_texto(destino: Dict[str, Any], origen: Dict[str, Any], campos):
        for k in campos:
            ext = str(origen.get(k, "")).strip()
            if not ext:
                continue
            cur = str(destino.get(k, "")).strip()
            sep = ""
            if cur and not cur.endswith((" ", "-", "/", "&")) and not ext.startswith((" ", "-", "/", "&", ".")):
                sep = " "
            destino[k] = re.sub(r"\s{2,}", " ", (cur + sep + ext).strip())

    def _commit(acum: Optional[Dict[str, Any]]):
        if acum is None:
            return
        pt = _to_decimal_rimac(acum.get("prima_total"))
        co = _to_decimal_rimac(acum.get("comision"))
        pct_raw = acum.get("porcentaje_comision", "")
        pct_val = Decimal("0")
        if isinstance(pct_raw, Decimal):
            pct_val = pct_raw
        else:
            pm = re.search(r"(\d{1,3}(?:\.\d{1,2})?)", str(pct_raw).replace("%", ""))
            if pm:
                pct_val = _to_decimal_rimac(pm.group(1))
        acum["prima_total"] = _round2_rimac(pt)
        acum["comision"] = _round2_rimac(co)
        acum["porcentaje_comision"] = _round2_rimac(pct_val)

        if acum["comision"] == 0 and pt > 0 and pct_val > 0:
            acum["comision"] = _round2_rimac(pt * pct_val / Decimal("100"))

        for k in ("producto", "poliza", "cliente", "documento", "doc_sunat", "tipo", "fecha_pago"):
            acum[k] = re.sub(r"\s{2,}", " ", str(acum.get(k, "")).strip())

        if acum["prima_total"] == 0 and acum["comision"] == 0:
            return
        if not acum["poliza"] and not acum["documento"] and not acum["cliente"]:
            return
        out.append(acum)

    for row in filas[header_row_idx + 1:]:
        if row is None:
            continue
        cells = ["" if c is None else str(c).replace("\n", " ").strip() for c in row]
        if all(not c for c in cells):
            continue
        joined = " ".join(cells).lower()
        if any(k in joined for k in _RIMAC_HEADER_TOKENS) and any(k in joined for k in ("producto", "poliza", "póliza", "fecha", "prima")):
            continue
        if re.search(r"(totales?|total\s+(comision|igv|general)|i\.?g\.?v\.?)", joined):
            continue
        if re.search(r"p[aá]gina\s+\d+\s+(de|/)\s+\d+", joined):
            continue
        if re.match(r"^(lima|preliquidaci|fecha|hora|usuario|moneda|nro-?preliquid|intermedi|paguese)", joined):
            continue

        nueva: Dict[str, Any] = {
            "producto": "", "poliza": "", "cliente": "", "documento": "",
            "doc_sunat": "", "tipo": "", "fecha_pago": "",
            "prima_total": Decimal("0"), "porcentaje_comision": Decimal("0"),
            "comision": Decimal("0"),
        }
        for campo, idx in mapa.items():
            if 0 <= idx < len(cells):
                nueva[campo] = cells[idx]

        backup = parsear_fila_rimac_por_patrones(cells)
        if backup:
            for k in ("producto", "poliza", "cliente", "documento", "doc_sunat", "tipo", "fecha_pago"):
                actual = str(nueva.get(k, "")).strip()
                if actual == "" or actual == "0":
                    relleno = str(backup.get(k, "")).strip()
                    if relleno and relleno != "0":
                        nueva[k] = relleno
            for k in ("prima_total", "porcentaje_comision", "comision"):
                if _to_decimal_rimac(nueva.get(k)) == 0 and _to_decimal_rimac(backup.get(k)) > 0:
                    nueva[k] = backup[k]

        tiene_fecha = bool(str(nueva.get("fecha_pago", "")).strip())
        tiene_monto = (
            _to_decimal_rimac(nueva.get("prima_total")) > 0
            or _to_decimal_rimac(nueva.get("comision")) > 0
        )
        tiene_poliza_doc = bool(str(nueva.get("poliza", "")).strip() or str(nueva.get("documento", "")).strip())

        if not tiene_fecha and not tiene_monto and not tiene_poliza_doc:
            if acumulada is not None:
                _mergear_texto(acumulada, nueva, ("cliente", "producto", "documento", "doc_sunat", "tipo"))
            continue

        if acumulada is not None and not tiene_monto and not tiene_fecha:
            _mergear_texto(acumulada, nueva, ("cliente", "producto", "documento", "doc_sunat", "tipo"))
            continue

        _commit(acumulada)
        acumulada = nueva
    _commit(acumulada)
    return out


def _extraer_rimac_por_coordenadas(page) -> List[Dict[str, Any]]:
    palabras = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
    if not palabras:
        return []

    def _y(p):
        return (p["top"] + p["bottom"]) / 2

    palabras_ordenadas = sorted(palabras, key=lambda p: (_y(p), p["x0"]))

    filas_agrupadas: List[List[Any]] = []
    tol_y = 9.0
    for p in palabras_ordenadas:
        yp = _y(p)
        puesta = False
        for fila in filas_agrupadas:
            if abs(fila[0] - yp) <= tol_y:
                fila[1].append(p)
                puesta = True
                break
        if not puesta:
            filas_agrupadas.append([yp, [p]])

    grupos_texto = []
    header_y = None
    for y_ref, palabras_fila in filas_agrupadas:
        if not palabras_fila:
            continue
        palabras_fila.sort(key=lambda p: (p["x0"], p["top"]))
        raw_ts = [p["text"].strip() for p in palabras_fila if p["text"].strip()]

        merged: List[str] = []
        i = 0
        while i < len(raw_ts):
            t = raw_ts[i]
            if i + 1 < len(raw_ts):
                nxt = raw_ts[i + 1]
                glued = None
                if (
                    t.endswith("-")
                    and len(t.rstrip("-")) >= 2
                    and re.match(r"^[A-Z0-9]", nxt)
                    and not nxt.startswith("-")
                ):
                    glued = t + nxt
                if glued is None and t.startswith("FA-") and re.match(r"^\d", nxt):
                    glued = t + nxt
                if glued is None and re.fullmatch(r"\d{1,2}", t) and re.fullmatch(r"\d{4}", nxt):
                    glued = t + "/" + nxt
                if glued is not None:
                    merged.append(glued)
                    i += 2
                    continue
            merged.append(t)
            i += 1
        tokens = merged
        texto = " ".join(tokens).strip()
        if not texto:
            continue
        low = texto.lower()

        if header_y is None:
            if any(k in low for k in ("producto", "poliza", "póliza", "prima total", "porcent. comisi", "comision")) and \
               any(k in low for k in ("cliente", "documento", "doc.sunat", "doc. sunat", "fecha pago", "tipo")):
                header_y = y_ref
                continue

        if header_y is None:
            continue
        if re.search(r"p[aá]gina\s+\d+\s+(de|/)\s+\d+", low):
            continue
        if re.match(r"^(moneda|nro-?preliquid|intermedi|paguese|lima|preliquidaci|fecha|hora|usuario)", low):
            continue
        if re.search(r"(totales?|total\s+(comision|igv|general)|i\.?g\.?v\.?)", low):
            continue
        if not re.search(r"[A-Za-z0-9]", texto):
            continue

        grupos_texto.append((y_ref, texto, tokens))

    salidas: List[Dict[str, Any]] = []
    for y_ref, texto, tokens in grupos_texto:
        parsed = parsear_fila_rimac_por_patrones([texto])
        if parsed is None:
            continue
        salidas.append(parsed)
    return salidas


# ============================================================
#   PARSER POR PATRONES (REGEX) RÍMAC
# ============================================================

def parsear_fila_rimac_por_patrones(celdas) -> Optional[Dict[str, Any]]:
    out: Dict[str, Any] = {
        "producto": "",
        "poliza": "",
        "cliente": "",
        "documento": "",
        "doc_sunat": "",
        "tipo": "",
        "fecha_pago": "",
        "prima_total": Decimal("0"),
        "porcentaje_comision": Decimal("0"),
        "comision": Decimal("0"),
    }

    raw_tokens: List[str] = []
    for c in celdas:
        if c is None:
            continue
        s = str(c).replace("\n", " ").replace("·", " ").strip()
        if not s:
            continue
        raw_tokens.extend(s.split())
    texto_global = " ".join(raw_tokens)
    if not texto_global.strip():
        return None

    fm = _FECHA_RE_R.search(texto_global)
    if fm:
        d, mo, a = fm.group(1), fm.group(2), fm.group(3)
        if len(a) == 2:
            a = "20" + a
        out["fecha_pago"] = f"{int(d):02d}/{int(mo):02d}/{a}"

    pct_match = re.search(r"\b(\d{1,3}(?:\.\d{1,2})?)\s*%", texto_global)
    if pct_match:
        try:
            out["porcentaje_comision"] = _round2_rimac(Decimal(pct_match.group(1)))
        except Exception:
            pass

    montos_todos: List[Decimal] = []
    spans_montos: List[Tuple[int, int, Decimal]] = []
    for m in _MONTO_RE_R.finditer(texto_global):
        val_str = m.group(1) or m.group(2)
        try:
            v = _to_decimal_rimac(val_str)
            montos_todos.append(v)
            spans_montos.append((m.start(), m.end(), v))
        except Exception:
            pass
    montos_unicos = list(dict.fromkeys(montos_todos))
    montos_desc = sorted(montos_unicos, reverse=True)

    prima = Decimal("0")
    comision = Decimal("0")
    if out["porcentaje_comision"] > 0 and len(montos_unicos) >= 2:
        pct = out["porcentaje_comision"] / Decimal("100")
        pares = []
        for v1 in montos_unicos:
            for v2 in montos_unicos:
                if v1 == v2:
                    continue
                esp = _round2_rimac(v1 * pct)
                if abs(float(v2 - esp)) < 0.05:
                    pares.append((abs(float(v2 - esp)), v1, v2))
        if pares:
            pares.sort(key=lambda x: x[0])
            _, prima, comision = pares[0]

    if prima == 0 and comision == 0 and len(montos_desc) >= 2:
        prima = montos_desc[0]
        comision = montos_desc[1]
        if out["porcentaje_comision"] > 0:
            esp_from_pct = _round2_rimac(prima * out["porcentaje_comision"] / Decimal("100"))
            if esp_from_pct > 0 and abs(float(comision - esp_from_pct)) > 1.0:
                for v in montos_desc[1:]:
                    if abs(float(v - esp_from_pct)) <= 1.0:
                        comision = v
                        break
    elif prima == 0 and len(montos_desc) >= 1:
        prima = montos_desc[0]

    if comision == 0 and prima > 0 and out["porcentaje_comision"] > 0:
        comision = _round2_rimac(prima * out["porcentaje_comision"] / Decimal("100"))

    out["prima_total"] = _round2_rimac(prima)
    out["comision"] = _round2_rimac(comision)

    nros_doc: List[str] = []
    for m in _NRO_DOC_RE_R.finditer(texto_global):
        n = m.group(1).strip("-")
        nros_doc.append(n)
    seen = set()
    nros_uniq = []
    for n in nros_doc:
        if n not in seen:
            seen.add(n)
            nros_uniq.append(n)
    nros_doc = nros_uniq

    docs_sunat_candidatos: List[str] = []
    docs_poliza_documento: List[str] = []
    for n in nros_doc:
        if re.match(r"^(FA?-|F\d{3}-|B\d{3}-)", n):
            docs_sunat_candidatos.append(n)
        elif re.match(r"^(CP-|LQ-|REC-|CUO-)", n):
            docs_poliza_documento.append(n)
        else:
            docs_poliza_documento.append(n)

    if docs_sunat_candidatos:
        out["doc_sunat"] = docs_sunat_candidatos[0]

    polizas_numeros: List[str] = []
    for m in _POLIZA_RE_R.finditer(texto_global):
        pn = m.group(1)
        if any(pn in (out["fecha_pago"].replace("/", ""),) for _ in [0]):
            continue
        ya_usado = False
        for sv in spans_montos:
            ss = f"{sv[2]:.2f}".replace(".", "")
            if pn in ss or ss.endswith(pn):
                ya_usado = True
                break
        if ya_usado:
            continue
        polizas_numeros.append(pn)
    polizas_uniq = list(dict.fromkeys(polizas_numeros))

    documento_asignado = False
    if docs_poliza_documento:
        out["documento"] = docs_poliza_documento[0]
        documento_asignado = True
        if len(docs_poliza_documento) > 1 and not out["poliza"]:
            candidato_poliza = docs_poliza_documento[1]
            if re.fullmatch(r"\d{6,}", candidato_poliza):
                out["poliza"] = candidato_poliza
            elif not documento_asignado:
                pass

    if not out["poliza"] and polizas_uniq:
        out["poliza"] = polizas_uniq[0]
        if len(polizas_uniq) > 1 and not out["documento"]:
            for pn in polizas_uniq[1:]:
                if pn != out["poliza"]:
                    out["documento"] = pn
                    break

    usado = set()
    usado.add(out["fecha_pago"])
    usado.add(out["poliza"])
    usado.add(out["documento"])
    usado.add(out["doc_sunat"])
    for _, _, v in spans_montos:
        usado.add(f"{v:.2f}")
        usado.add(f"{v:,.2f}")
    if out["porcentaje_comision"] > 0:
        usado.add(f"{float(out['porcentaje_comision']):.2f}%")
        usado.add(f"{float(out['porcentaje_comision']):.0f}%")
    usado_low = {x.lower() for x in usado if x}

    stop_tokens_low = {
        "calle", "urb", "urbanizacion", "av", "avenida", "jr", "jiron",
        "lima", "peru", "perú", "s.a.", "s.a", "sac", "eirl", "e.i.r.l.",
        "s.r.l.", "srl", "sa", "eirl.",
    }

    tipo_tokens: List[str] = []
    cliente_tokens: List[str] = []
    producto_tokens: List[str] = []

    known_tipos = {"COMI", "COM", "COMI.", "FACT", "FAC", "NOTA", "ABON", "REC", "BOLETA"}
    known_productos = {
        "VEHICULOS", "VEHICULO", "AUTO", "AUTOS", "SOAT",
        "VIDA", "SALUD", "SCTR", "SCTR", "TREC", "INCENDIO",
        "INCENDIOS", "TERREMOTO", "MULTIRIESGO", "RESPONSABILIDAD",
        "RESP. CIVIL", "RC", "TRANSPORTE", "CARGA", "HOGAR",
        "CASERO", "EMPRESARIAL", "PYME", "EMPRESAS",
        "INTEGRAL", "FAMILIAR", "PERSONAL", "ACCIDENTES",
        "ENFERMEDAD", "ONCOLOGICO", "ONCOLÓGICO", "RENTA",
        "EDUCATIVO", "COLEGIO", "UNIVERSITARIO", "MASCOTAS",
        "WEB", "EQUIPO", "MAQUINARIA", "ROBO", "HURTO",
    }

    for tok in raw_tokens:
        if not tok:
            continue
        low = tok.lower().strip(".,-():;")
        t_strip = tok.strip(".,-–—/:;()%")
        t_strip_low = t_strip.lower()

        if not t_strip:
            continue
        if not re.search(r"[A-Za-zÑñÁÉÍÓÚáéíóú0-9&]", t_strip):
            continue
        if re.fullmatch(r"[0-9\(\)\.\%\,\ ]+", t_strip):
            continue
        if t_strip_low in usado_low or t_strip in usado:
            continue
        if any(u and len(u) >= 3 and u in t_strip_low for u in usado_low):
            continue
        if _MONTO_RE_R.fullmatch(t_strip.replace(",", "")):
            continue
        if _FECHA_RE_R.fullmatch(t_strip):
            continue
        if low in ("ruc", "dni", "nro", "s/", "$", "usd", "por", "pago", "prima", "total", "comision", "comisión", "%"):
            continue

        up = t_strip.upper()
        if up in known_tipos and not tipo_tokens:
            tipo_tokens.append(t_strip.upper())
            continue
        if up in known_productos:
            producto_tokens.append(t_strip.upper())
            continue

        if t_strip_low in stop_tokens_low and len(cliente_tokens) >= 3:
            break
        cliente_tokens.append(t_strip)

    out["producto"] = " ".join(producto_tokens[:3]).strip(" .,-–—/:;()")
    out["tipo"] = " ".join(tipo_tokens[:2]).strip(" .,-–—/:;()")

    raw_cli = " ".join(cliente_tokens).strip(" .,-–—/:;()%")
    for doc_val in (out["poliza"], out["documento"], out["doc_sunat"]):
        if not doc_val:
            continue
        raw_cli = re.sub(r"[\s\-\–\—\(\)\%\.\,]+" + re.escape(doc_val) + r"[\s\-\–\—\(\)\%\.\,]+", " ", raw_cli)
        raw_cli = re.sub(re.escape(doc_val), " ", raw_cli)
    m_first = re.search(r"[A-Za-z0-9ÑñÁÉÍÓÚáéíóú&]", raw_cli)
    if m_first:
        raw_cli = raw_cli[m_first.start():]
    m_last = re.search(r"[A-Za-z0-9ÑñÁÉÍÓÚáéíóú&]", raw_cli[::-1])
    if m_last:
        raw_cli = raw_cli[:len(raw_cli) - m_last.start()]
    raw_cli = re.sub(r"\s{2,}", " ", raw_cli).strip()
    out["cliente"] = raw_cli

    if out["prima_total"] == 0 and out["comision"] == 0:
        return None
    if not out["poliza"] and not out["documento"] and not out["cliente"] and not out["producto"]:
        return None
    return out


# ============================================================
#   COMPONENTE TKINTER RÍMAC
# ============================================================

class TableroFacturacionRimac(tk.Frame):
    COLUMNS = (
        ("producto",            "Producto",          130),
        ("poliza",              "Póliza",            110),
        ("cliente",             "Cliente",           260),
        ("documento",           "Documento",         140),
        ("doc_sunat",           "Doc.Sunat",         150),
        ("tipo",                "Tipo",               70),
        ("fecha_pago",          "Fecha Pago",        100),
        ("prima_total",         "Prima Total",       110, "moneda"),
        ("porcentaje_comision", "Porcent. Comisión", 110, "porcentaje"),
        ("comision",            "Comisión",          110, "moneda"),
    )

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._editor: Optional[Tuple[ttk.Entry, str, int, str]] = None
        self._rows: List[Dict[str, Any]] = []
        self._uid_counter = 0
        self.configure(bg="#f1f5f9")
        self._construir()

    def _construir(self):
        wrap = tk.Frame(self, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=2, pady=2)
        inner = tk.Frame(wrap, bg="#ffffff")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        header = tk.Frame(inner, bg="#ffffff")
        header.pack(fill="x")
        self._crear_encabezado(header)

        tot_row = tk.Frame(inner, bg="#ffffff")
        tot_row.pack(fill="x", pady=(12, 10))
        self._construir_totales(tot_row)

        ley_row = tk.Frame(inner, bg="#ffffff")
        ley_row.pack(fill="x", pady=(0, 8))
        self._construir_leyenda(ley_row)

        t_frame = tk.Frame(inner, bg="#ffffff")
        t_frame.pack(fill="both", expand=True, pady=(0, 8))
        self._construir_tabla(t_frame)

        self.lbl_estado = tk.Label(inner, text="Listo. Cargue un PDF de Rímac para empezar →",
                                   bg="#ffffff", fg="#64748b", font=("Segoe UI", 9), anchor="w")
        self.lbl_estado.pack(fill="x")

    def _crear_encabezado(self, parent):
        title_box = tk.Frame(parent, bg="#ffffff")
        title_box.pack(side="left")
        tk.Label(title_box, text="Prelíquidación de Comisiones — Rímac",
                 bg="#ffffff", fg="#0f172a", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Extraiga datos desde el PDF de Prelíquidación Rímac. Las columnas coinciden con el formato del documento.",
                 bg="#ffffff", fg="#64748b", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(parent, bg="#ffffff")
        btns.pack(side="right")
        self._mkbtn(btns, "Cargar PDF Rímac", "#2563eb", self._cargar_pdf).pack(side="left", padx=3)
        self._mkbtn(btns, "Validar BD", "#16a34a", self._validar_contra_bd).pack(side="left", padx=3)
        self._mkbtn(btns, "Nueva fila", "#0ea5e9", self._agregar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Eliminar fila", "#ef4444", self._eliminar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Limpiar todo", "#475569", self._limpiar).pack(side="left", padx=3)

    def _mkbtn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, bg=color, fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                         cursor="hand2", activebackground="#1e293b", activeforeground="#ffffff",
                         padx=12, pady=7, command=cmd)

    def _construir_totales(self, parent):
        cards = [
            ("Total Comisión",  "comision_total",  "#0891b2", "#ecfeff"),
            ("I.G.V. (18%)",    "igv_total",       "#f59e0b", "#fffbeb"),
            ("Total",           "total_final",     "#16a34a", "#f0fdf4"),
        ]
        self._total_vars: Dict[str, tk.StringVar] = {}
        for i, (label, key, color, bgcard) in enumerate(cards):
            card = tk.Frame(parent, bg="#e2e8f0")
            card.grid(row=0, column=i, padx=(0 if i == 0 else 6, 0), sticky="nsew")
            parent.grid_columnconfigure(i, weight=1)
            inner = tk.Frame(card, bg=bgcard)
            inner.pack(fill="both", expand=True, padx=1, pady=1)
            pad = tk.Frame(inner, bg=bgcard)
            pad.pack(fill="both", expand=True, padx=12, pady=10)
            tk.Label(pad, text=label, bg=bgcard, fg="#475569",
                     font=("Segoe UI", 9)).pack(anchor="w")
            sv = tk.StringVar(value=f"{MONEDA_RIMAC} 0.00")
            self._total_vars[key] = sv
            tk.Label(pad, textvariable=sv, bg=bgcard, fg=color,
                     font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(4, 0))

    def _construir_leyenda(self, parent):
        wrap = tk.Frame(parent, bg="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1)
        wrap.pack(fill="x", padx=0, pady=0)
        inner = tk.Frame(wrap, bg="#f8fafc")
        inner.pack(fill="x", padx=10, pady=6)

        tk.Label(
            inner,
            text="Leyenda:",
            bg="#f8fafc", fg="#334155",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        reglas = [
            ("verde",    COLOR_VERDE,    "#166534", "Recibo + Factura"),
            ("amarillo", COLOR_AMARILLO, "#92400e", "Solo hay Recibo"),
            ("rojo",     COLOR_ROJO,     "#991b1b", "Sin Recibo ni Factura"),
        ]
        self._leyenda_vars: Dict[str, tk.StringVar] = {}
        for i, (key, bg, fg, texto) in enumerate(reglas):
            if i > 0:
                tk.Frame(inner, bg="#cbd5e1", width=1, height=18).pack(side="left", padx=10)
            item = tk.Frame(inner, bg="#f8fafc")
            item.pack(side="left", padx=(6 if i == 0 else 0, 0))
            cuadro = tk.Label(item, text="  ", bg=bg, fg=fg,
                              font=("Segoe UI", 9, "bold"),
                              highlightbackground=fg, highlightthickness=1, width=2)
            cuadro.pack(side="left")
            tk.Label(item, text=f" {texto} ", bg="#f8fafc", fg=fg,
                     font=("Segoe UI", 9)).pack(side="left")
            sv = tk.StringVar(value="(0)")
            self._leyenda_vars[key] = sv
            tk.Label(item, textvariable=sv, bg="#f8fafc", fg=fg,
                     font=("Segoe UI", 9, "bold")).pack(side="left")

    def _actualizar_leyenda_conteos(self, verde: int = 0, amarillo: int = 0, rojo: int = 0):
        if hasattr(self, "_leyenda_vars"):
            self._leyenda_vars["verde"].set(f"({verde})")
            self._leyenda_vars["amarillo"].set(f"({amarillo})")
            self._leyenda_vars["rojo"].set(f"({rojo})")

    def _construir_tabla(self, parent):
        tv_frame = tk.Frame(parent, bg="#ffffff")
        tv_frame.pack(fill="both", expand=True)

        cols = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(tv_frame, columns=cols, show="headings", selectmode="browse", height=18)

        for item in self.COLUMNS:
            cid = item[0]
            text = item[1]
            width = item[2]
            align = item[3] if len(item) > 3 else "w"
            self.tree.heading(cid, text=text)
            anchor = "e" if align in ("moneda", "porcentaje", "e") else "w"
            stretch = (cid == "cliente")
            self.tree.column(cid, width=width, anchor=anchor, stretch=stretch)

        scrollbar_y = ttk.Scrollbar(tv_frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tv_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 9), background="#ffffff",
                        fieldbackground="#ffffff", foreground="#0f172a", bordercolor="#e2e8f0")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                        background="#f8fafc", foreground="#334155", relief="flat",
                        bordercolor="#e2e8f0", padding=4)
        style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#1e3a8a")])

        self.tree.tag_configure("verde", background=COLOR_VERDE, foreground="#166534")
        self.tree.tag_configure("amarillo", background=COLOR_AMARILLO, foreground="#92400e")
        self.tree.tag_configure("rojo", background=COLOR_ROJO, foreground="#991b1b")

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        tv_frame.grid_rowconfigure(0, weight=1)
        tv_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Delete>", lambda e: self._eliminar_fila())
        self.tree.bind("<Button-3>", lambda e: "break")

    # --- Acciones
    def _cargar_pdf(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar PDF de Prelíquidación Rímac",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            filas = extraer_tablas_rimac(path)
        except Exception as e:
            messagebox.showerror("Error al leer PDF",
                                 f"No se pudo leer el PDF de Rímac.\n\n{str(e)}\n\n{traceback.format_exc(limit=1)}",
                                 parent=self)
            return

        if not filas:
            messagebox.showwarning("Sin datos",
                                   "El PDF se leyó pero no se detectaron filas de detalle.\n"
                                   "Puede agregar filas manualmente con Nueva fila.",
                                   parent=self)
            self._actualizar_totales()
            return

        for f in filas:
            self._append_row(f)

        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(
            text=f"Importado: {len(filas)} filas desde {os.path.basename(path)}  |  Total registros: {len(self._rows)}",
            fg="#059669")

    def _agregar_fila(self):
        fila = {
            "producto": "",
            "poliza": "",
            "cliente": "",
            "documento": "",
            "doc_sunat": "",
            "tipo": "COMI",
            "fecha_pago": "",
            "prima_total": Decimal("0"),
            "porcentaje_comision": Decimal("23.00"),
            "comision": Decimal("0"),
        }
        self._append_row(fila)
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    def _append_row(self, f: Dict[str, Any]):
        self._uid_counter += 1
        uid = f"r{self._uid_counter}"
        data = dict(f)
        data["prima_total"] = _round2_rimac(_to_decimal_rimac(data.get("prima_total")))
        data["comision"] = _round2_rimac(_to_decimal_rimac(data.get("comision")))
        data["porcentaje_comision"] = _round2_rimac(_to_decimal_rimac(data.get("porcentaje_comision")))
        self._rows.append(data)
        self.tree.insert("", "end", iid=uid, values=self._valores_tabla(data))

    def _eliminar_fila(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Eliminar fila", f"¿Seguro que desea eliminar {len(sel)} fila(s)?", parent=self):
            return
        idxs = []
        for iid in sel:
            try:
                idx = self.tree.index(iid)
                idxs.append(idx)
            except Exception:
                pass
            try:
                self.tree.delete(iid)
            except Exception:
                pass
        for idx in sorted(idxs, reverse=True):
            if 0 <= idx < len(self._rows):
                del self._rows[idx]
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    def _limpiar(self):
        if not self._rows:
            return
        if not messagebox.askyesno("Limpiar", "¿Borrar todos los registros de la tabla?", parent=self):
            return
        for iid in list(self.tree.get_children()):
            self.tree.delete(iid)
        self._rows.clear()
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(text="Tabla limpiada.", fg="#64748b")

    def _validar_contra_bd(self):
        if not self._rows:
            messagebox.showinfo(
                "Validar BD",
                "No hay filas en la tabla para validar.\nCargue un PDF primero o agregue filas manualmente.",
                parent=self,
            )
            return

        self.lbl_estado.configure(text="Validando contra base de datos...", fg="#0284c7")
        self.update_idletasks()

        filas_para_validar = []
        for r in self._rows:
            r_norm = {
                "fecha": r.get("fecha_pago", ""),
                "tipo_doc": r.get("tipo", "") or "COMI",
                "nro_documento": r.get("documento", "") or r.get("poliza", ""),
                "doc_legal": r.get("doc_sunat", ""),
                "monto_doc": _to_decimal_rimac(r.get("prima_total")),
                "monto_comision": _to_decimal_rimac(r.get("comision")),
                "porcentaje_comision": _to_decimal_rimac(r.get("porcentaje_comision")),
                "identificacion": "",
                "cliente": r.get("cliente", ""),
            }
            filas_para_validar.append(r_norm)

        try:
            resultados, cant_existe, cant_no_existe = validar_filas_contra_bd(filas_para_validar)
        except Exception as e:
            messagebox.showerror(
                "Error de validación",
                f"Ocurrió un error al validar contra la BD:\n\n{str(e)}\n\n{traceback.format_exc(limit=2)}",
                parent=self,
            )
            self.lbl_estado.configure(text="Error al validar.", fg="#dc2626")
            return

        iids = self.tree.get_children()
        cant_verde = 0
        cant_amarillo = 0
        cant_rojo = 0

        for i, res in enumerate(resultados):
            if i >= len(iids):
                break
            existe_recibo = res.get("existe_recibo", False)
            existe_factura = res.get("existe_factura", False)

            if existe_recibo and existe_factura:
                tag = "verde"
                cant_verde += 1
            elif existe_recibo and not existe_factura:
                tag = "amarillo"
                cant_amarillo += 1
            else:
                tag = "rojo"
                cant_rojo += 1

            self.tree.item(iids[i], tags=(tag,))

        self._actualizar_leyenda_conteos(cant_verde, cant_amarillo, cant_rojo)

        total = len(self._rows)
        detalles_unicos = []
        if cant_verde > 0:
            detalles_unicos.append(f"Verde (R+F): {cant_verde}")
        if cant_amarillo > 0:
            detalles_unicos.append(f"Amarillo (R): {cant_amarillo}")
        if cant_rojo > 0:
            detalles_unicos.append(f"Rojo (---): {cant_rojo}")
        resumen = "  |  ".join(detalles_unicos)

        if cant_rojo == 0 and cant_amarillo == 0:
            fg_estado = "#0f766e"
        elif cant_rojo > 0:
            fg_estado = "#dc2626"
        else:
            fg_estado = "#b45309"

        self.lbl_estado.configure(
            text=f"Validación completada — {total} filas  |  {resumen}",
            fg=fg_estado,
        )

        if cant_rojo == 0 and cant_amarillo == 0:
            messagebox.showinfo(
                "Validación exitosa",
                f"Todas las {total} filas tienen RECIBO y FACTURA en la BD.\n"
                "Todas las filas están en VERDE.",
                parent=self,
            )
        else:
            detalles_msg = []
            if cant_verde > 0:
                detalles_msg.append(f"🟢 VERDE (Recibo + Factura): {cant_verde}")
            if cant_amarillo > 0:
                detalles_msg.append(f"🟡 AMARILLO (Solo Recibo): {cant_amarillo}")
            if cant_rojo > 0:
                detalles_msg.append(f"🔴 ROJO (Sin Recibo ni Factura): {cant_rojo}")
            messagebox.showwarning(
                "Validación con inconsistencias",
                "Resultado de la validación:\n\n"
                + "\n".join(detalles_msg),
                parent=self,
            )

    # --- Celdas editables
    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not iid or not col:
            return
        try:
            col_index = int(str(col).replace("#", "")) - 1
        except Exception:
            return
        if col_index < 0 or col_index >= len(self.COLUMNS):
            return
        col_id = self.COLUMNS[col_index][0]
        self._cerrar_editor(commit=False)
        x, y, w, h = self.tree.bbox(iid, col)
        try:
            value = self.tree.set(iid, col_id)
        except Exception:
            value = ""
        editor = ttk.Entry(self.tree, font=("Segoe UI", 9))
        editor.insert(0, value)
        editor.focus_set()
        editor.select_range(0, "end")
        editor.configure(
            background="#fef9c3",
            foreground="#0f172a",
            justify="right" if col_id in {"prima_total", "porcentaje_comision", "comision"} else "left"
        )
        editor.place(x=x, y=y, width=w, height=h)
        self._editor = (editor, iid, col_index, col_id)
        editor.bind("<Return>", lambda e: self._cerrar_editor(commit=True))
        editor.bind("<Escape>", lambda e: self._cerrar_editor(commit=False))
        editor.bind("<FocusOut>", lambda e: self._cerrar_editor(commit=True))
        editor.bind("<Tab>", lambda e: (self._cerrar_editor(commit=True), "break"))

    def _cerrar_editor(self, commit: bool):
        if self._editor is None:
            return
        editor, iid, col_index, col_id = self._editor
        self._editor = None
        valor_nuevo = ""
        if commit:
            try:
                valor_nuevo = editor.get().strip()
            except Exception:
                valor_nuevo = ""
        try:
            editor.destroy()
        except Exception:
            pass
        if not commit:
            return
        try:
            index = self.tree.index(iid)
        except Exception:
            return
        if not (0 <= index < len(self._rows)):
            return
        row = self._rows[index]
        if col_id in {"prima_total", "porcentaje_comision", "comision"}:
            row[col_id] = _round2_rimac(_to_decimal_rimac(valor_nuevo))
        else:
            row[col_id] = valor_nuevo
        self.tree.item(iid, values=self._valores_tabla(row))
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    # --- Helpers
    def _valores_tabla(self, row: Dict[str, Any]) -> Tuple[str, ...]:
        values: List[str] = []
        for item in self.COLUMNS:
            cid = item[0]
            tipo = item[3] if len(item) > 3 else "text"
            raw = row.get(cid, "")
            if tipo == "moneda":
                v = _to_decimal_rimac(raw)
                values.append(f"{MONEDA_RIMAC} {self._fmt_money(v)}")
            elif tipo == "porcentaje":
                v = _to_decimal_rimac(raw)
                values.append(f"{_round2_rimac(v):.2f} %")
            else:
                values.append("" if raw is None else str(raw))
        return tuple(values)

    def _actualizar_totales(self):
        comision_total = Decimal("0")
        for r in self._rows:
            comision_total += _to_decimal_rimac(r.get("comision"))
        comision_total = _round2_rimac(comision_total)
        base_igv = comision_total
        igv_total = _round2_rimac(base_igv * IGV_PORCENTAJE)
        total_final = _round2_rimac(base_igv + igv_total)
        self._total_vars["comision_total"].set(f"{MONEDA_RIMAC} {self._fmt_money(comision_total)}")
        self._total_vars["igv_total"].set(f"{MONEDA_RIMAC} {self._fmt_money(igv_total)}")
        self._total_vars["total_final"].set(f"{MONEDA_RIMAC} {self._fmt_money(total_final)}")

    def _fmt_money(self, v: Decimal) -> str:
        s = f"{_round2_rimac(v):,.2f}"
        return s.replace(",", "¤").replace(".", ",").replace("¤", ".")
