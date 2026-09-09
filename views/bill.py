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
MONEDA = "S/."


def _to_decimal(val: Any) -> Decimal:
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    try:
        s = str(val).strip()
        if not s:
            return Decimal("0")
        s = s.replace("S/", "").replace("S/.", "").replace("$", "")
        s = s.replace(",", "").replace("%", "").strip()
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return Decimal("0")
        return Decimal(m.group(0)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, Exception):
        return Decimal("0")


def _round2(v: Decimal) -> Decimal:
    if not isinstance(v, Decimal):
        v = _to_decimal(v)
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ============================================================
#   EXTRACCIÓN DE DATOS DE PDF SANITAS / LIQUIDACIÓN
# ============================================================

_FECHA_RE = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")
_NRO_DOC_RE = re.compile(r"\b((?:[A-Z0-9]{1,6}-){1,4}[A-Z0-9\-\/]{3,})\b")
_CODIGO_SUNAT_RE = re.compile(r"\b(F\d{3}-[A-Z0-9\-]{5,})\b")
_RUC_RE = re.compile(r"\b(20\d{9}|10\d{7}|[0-9]{11})\b")
_DNI_RE = re.compile(r"\b(\d{8})\b")
_PORCENTAJE_RE = re.compile(r"\(\s*([0-9]{1,3}(?:\.\d{1,2})?)\s*(?:[^\)]*?)\s*%\s*\)")
_MONTO_RE_F = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})*\.\d{2})(?!\d)")

_HEADER_TOKENS = (
    "liquidaci", "nro. documento", "nro de documento", "fecha inicio",
    "tipo de documento", "monto doc", "comision", "doc. legal",
    "broker", "identificacion", "cliente",
)


def extraer_tablas_sanitas(pdf_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except Exception:
        raise RuntimeError("Se requiere la librería 'pdfplumber' para extraer datos del PDF.")

    filas: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_filas: List[Dict[str, Any]] = []
            extraido = False

            rows_text = _extraer_por_coordenadas(page)
            if rows_text and len(rows_text) >= 3:
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
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "text",
                        "join_tolerance": 8,
                        "edge_min_length": 1,
                        "snap_tolerance": 12,
                        "snap_x_tolerance": 10,
                        "snap_y_tolerance": 10,
                        "min_words_vertical": 1,
                        "min_words_horizontal": 1,
                        "intersection_tolerance": 10,
                    },
                    {
                        "vertical_strategy": "lines_strict",
                        "horizontal_strategy": "text",
                        "join_tolerance": 5,
                        "edge_min_length": 1,
                        "snap_tolerance": 8,
                        "min_words_vertical": 1,
                        "min_words_horizontal": 1,
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

                    if len(t) < 4:
                        continue
                    if t and t[0] and len(t[0]) > 14:
                        continue

                    rows_page = _procesar_tabla_con_encabezado(t)
                    if rows_page:
                        page_filas.extend(rows_page)
                        extraido = True
                        break

                    rows_page = []
                    for row in t:
                        if row is None:
                            continue
                        cells = ["" if c is None else str(c).replace("\n", " ").strip() for c in row]
                        if len([c for c in cells if c]) < 3:
                            continue
                        if _es_encabezado(cells):
                            continue
                        if _es_total(cells):
                            continue
                        parsed = parsear_fila_por_patrones(cells)
                        if parsed:
                            rows_page.append(parsed)
                    if rows_page:
                        page_filas.extend(rows_page)
                        extraido = True
                        break

            filas.extend(page_filas)
    return filas


# ============================================================
#   MÉTODO RECOMENDADO: mapear columnas POR ENCABEZADO REAL
#   (detectado en la 1ª fila del extract_table con bordes)
# ============================================================

_CAMPO_POR_PALABRAS_CLAVE = [
    ("fecha",          ["fecha inicio", "fecha", "fec ini"]),
    ("tipo_doc",       ["tipo de documento", "tipo documento", "tipo doc", "tipo"]),
    ("nro_documento",  ["nro. documento", "nro de documento", "nro documento", "n° documento", "documento", "nro doc"]),
    ("doc_legal",      ["doc. legal", "doc legal", "codigo legal", "doc leg"]),
    ("monto_doc",      ["monto doc. s/imp.", "monto doc s/imp", "monto doc", "monto s/imp", "monto documento"]),
    ("monto_comision", ["monto comision broker", "monto comision", "comision broker", "comisión", "comision"]),
    ("porcentaje_comision", ["porcentaje comision", "porcentaje", "% comision", "comision %"]),
    ("identificacion", ["nro de identificacion", "nro identificacion", "identificacion", "n° identificación", "ruc/dni", "ruc", "dni"]),
    ("cliente",        ["cliente", "razon social", "razón social", "nombre", "asegurado"]),
]


def _detectar_columnas_por_encabezado(fila_encabezado) -> Optional[Dict[str, int]]:
    if not fila_encabezado:
        return None
    norm_cells = []
    for i, c in enumerate(fila_encabezado):
        s = "" if c is None else str(c).replace("\n", " ").strip().lower()
        s = re.sub(r"\s{2,}", " ", s)
        norm_cells.append(s)
    if not any(any(k in s for k in ["fecha", "nro", "monto", "cliente", "doc"]) for s in norm_cells):
        return None
    mapa: Dict[str, int] = {}
    for idx, s in enumerate(norm_cells):
        matched = None
        for campo, palabras in _CAMPO_POR_PALABRAS_CLAVE:
            for palabra in palabras:
                if palabra in s:
                    matched = campo
                    break
            if matched:
                break
        if matched and matched not in mapa:
            mapa[matched] = idx
    # Mínimos campos requeridos para considerar el encabezado válido: fecha + (monto o comision) + nro_doc o doc_legal
    checks = [
        "fecha" in mapa,
        ("monto_doc" in mapa or "monto_comision" in mapa),
        ("nro_documento" in mapa or "doc_legal" in mapa or "identificacion" in mapa),
    ]
    if sum(checks) >= 3:
        return mapa
    return None


def _procesar_tabla_con_encabezado(tabla) -> List[Dict[str, Any]]:
    if not tabla:
        return []
    filas = list(tabla)
    # Buscar la primera fila que sea encabezado (en algunas páginas está en fila 1)
    header_row_idx = None
    mapa = None
    for start in range(min(4, len(filas))):
        mapa = _detectar_columnas_por_encabezado(filas[start])
        if mapa is not None:
            header_row_idx = start
            break
    if mapa is None or header_row_idx is None:
        return []

    out: List[Dict[str, Any]] = []
    acumulada: Optional[Dict[str, Any]] = None
    pre_acum: Optional[Dict[str, Any]] = None

    def _mergear_en(destino: Dict[str, Any], origen: Dict[str, Any]):
        for k in ("tipo_doc", "cliente"):
            ext = str(origen.get(k, "")).strip()
            if not ext:
                continue
            cur = str(destino.get(k, "")).strip()
            sep = ""
            if cur and not cur.endswith((" ", "-", "/")) and not ext.startswith((" ", "-", "/")):
                sep = " "
            destino[k] = re.sub(r"\s{2,}", " ", (cur + sep + ext).strip())

    def _backup_final(acum: Dict[str, Any]):
        md_s = f"{_round2(_to_decimal(acum.get('monto_doc'))):.2f}"
        mc_s = f"{_round2(_to_decimal(acum.get('monto_comision'))):.2f}"
        pct_s = f"{_round2(_to_decimal(acum.get('porcentaje_comision'))):.2f} %"
        texto = " ".join([
            str(acum.get("fecha", "")),
            str(acum.get("tipo_doc", "")),
            str(acum.get("nro_documento", "")),
            str(acum.get("doc_legal", "")),
            md_s,
            mc_s + " (" + pct_s + ")",
            "RUC - " + str(acum.get("identificacion", "")),
            str(acum.get("cliente", "")),
        ])
        b = parsear_fila_por_patrones([texto])
        if b:
            for k in ("tipo_doc", "doc_legal", "cliente", "nro_documento", "identificacion"):
                actual = str(acum.get(k, "")).strip()
                if actual == "" or actual == "0":
                    relleno = str(b.get(k, "")).strip()
                    if relleno and relleno != "0":
                        acum[k] = relleno

    def _commit(acum: Optional[Dict[str, Any]]):
        if acum is None:
            return
        md = _to_decimal(acum.get("monto_doc"))
        mc = _to_decimal(acum.get("monto_comision"))
        pct_raw = acum.get("porcentaje_comision", "")
        pct_val = Decimal("0")
        if isinstance(pct_raw, Decimal):
            pct_val = pct_raw
        else:
            pm = _PORCENTAJE_RE.search(str(pct_raw))
            if pm:
                pct_val = _to_decimal(pm.group(1))
            else:
                pct_val = _to_decimal(str(pct_raw).replace("%", ""))
        acum["monto_doc"] = _round2(md)
        acum["monto_comision"] = _round2(mc)
        acum["porcentaje_comision"] = _round2(pct_val)

        if acum["monto_comision"] == 0 and acum["monto_doc"] > 0:
            pct_def = acum["porcentaje_comision"] if acum["porcentaje_comision"] > 0 else Decimal("23.00")
            acum["monto_comision"] = _round2(acum["monto_doc"] * pct_def / Decimal("100"))
            if acum["porcentaje_comision"] == 0:
                acum["porcentaje_comision"] = Decimal("23.00")

        for k in ("identificacion",):
            v = str(acum.get(k, "")).strip()
            if v:
                for pref in ("RUC", "DNI", "R.U.C.", "D.N.I.", "-", "—"):
                    if v.upper().startswith(pref):
                        v = v[len(pref):].lstrip(" .-:")
                        break
                m = re.search(r"(20\d{9}|10\d{7}|\d{11}|\d{8})", v)
                if m:
                    v = m.group(1)
            acum[k] = v.strip()

        for k in ("fecha", "tipo_doc", "nro_documento", "doc_legal", "cliente"):
            acum[k] = re.sub(r"\s{2,}", " ", str(acum.get(k, "")).strip())

        _backup_final(acum)

        for k in ("fecha", "tipo_doc", "nro_documento", "doc_legal", "cliente", "identificacion"):
            acum[k] = re.sub(r"\s{2,}", " ", str(acum.get(k, "")).strip())

        if acum["monto_doc"] == 0 and acum["monto_comision"] == 0:
            return
        if not acum["nro_documento"] and not acum["doc_legal"] and not acum["cliente"]:
            return
        out.append(acum)

    for row in filas[header_row_idx + 1:]:
        if row is None:
            continue
        cells = ["" if c is None else str(c).replace("\n", " ").strip() for c in row]
        if all(not c for c in cells):
            continue
        if _es_encabezado(cells) or _es_total(cells):
            continue
        if re.search(r"p[aá]gina\s+\d+\s+(de|/)\s+\d+", " ".join(cells).lower()):
            continue

        nueva: Dict[str, Any] = {
            "fecha": "", "tipo_doc": "", "nro_documento": "", "doc_legal": "",
            "monto_doc": Decimal("0"), "monto_comision": Decimal("0"),
            "porcentaje_comision": Decimal("0"), "identificacion": "", "cliente": "",
        }
        pct_desde_celda = Decimal("0")
        for campo, idx in mapa.items():
            if 0 <= idx < len(cells):
                valor = cells[idx]
                if campo == "monto_comision":
                    pm = _PORCENTAJE_RE.search(str(valor))
                    if pm:
                        pct_desde_celda = _to_decimal(pm.group(1))
                        valor_limpio = _PORCENTAJE_RE.sub("", str(valor)).strip()
                        valor = valor_limpio if valor_limpio else valor
                nueva[campo] = valor
        if pct_desde_celda > 0 and (
            nueva["porcentaje_comision"] == 0 or _to_decimal(nueva["porcentaje_comision"]) == 0
        ):
            nueva["porcentaje_comision"] = pct_desde_celda

        # === FIX 3: mezclar con parser por patrones para rellenar VACÍOS ===
        backup = parsear_fila_por_patrones(cells)
        if backup:
            for k in ("tipo_doc", "doc_legal", "cliente", "nro_documento", "identificacion"):
                actual = str(nueva.get(k, "")).strip()
                if actual == "" or actual == "0":
                    relleno = str(backup.get(k, "")).strip()
                    if relleno and relleno != "0":
                        nueva[k] = relleno
            # Si aún no hay porcentaje pero backup sí lo tiene
            if _to_decimal(nueva.get("porcentaje_comision")) == 0 and _to_decimal(backup.get("porcentaje_comision")) > 0:
                nueva["porcentaje_comision"] = backup["porcentaje_comision"]

        tiene_fecha = bool(str(nueva.get("fecha", "")).strip())
        tiene_monto = (
            _to_decimal(nueva.get("monto_doc")) > 0
            or _to_decimal(nueva.get("monto_comision")) > 0
        )
        tiene_campos_clave = tiene_fecha or tiene_monto
        tiene_solo_texto = (
            not tiene_campos_clave
            and (
                str(nueva.get("tipo_doc", "")).strip()
                or str(nueva.get("cliente", "")).strip()
                or str(nueva.get("nro_documento", "")).strip()
                or str(nueva.get("doc_legal", "")).strip()
                or str(nueva.get("identificacion", "")).strip()
            )
        )

        if tiene_solo_texto:
            if pre_acum is not None:
                _mergear_en(pre_acum, nueva)
                # También mergear campos numéricos/documentos (nro_doc/doc_legal/id)
                for k in ("nro_documento", "doc_legal", "identificacion"):
                    if not str(pre_acum.get(k, "")).strip() and str(nueva.get(k, "")).strip():
                        pre_acum[k] = str(nueva[k]).strip()
            elif acumulada is not None:
                _mergear_en(acumulada, nueva)
                for k in ("nro_documento", "doc_legal", "identificacion"):
                    if not str(acumulada.get(k, "")).strip() and str(nueva.get(k, "")).strip():
                        acumulada[k] = str(nueva[k]).strip()
            else:
                pre_acum = nueva
            continue

        if tiene_campos_clave and pre_acum is not None:
            _mergear_en(nueva, pre_acum)
            for k in ("nro_documento", "doc_legal", "identificacion"):
                if not str(nueva.get(k, "")).strip() and str(pre_acum.get(k, "")).strip():
                    nueva[k] = str(pre_acum[k]).strip()
            pre_acum = None

        if (
            acumulada is not None
            and not tiene_campos_clave
            and (str(nueva.get("tipo_doc", "")).strip() or str(nueva.get("cliente", "")).strip() or str(nueva.get("nro_documento", "")).strip())
        ):
            _mergear_en(acumulada, nueva)
            for k in ("nro_documento", "doc_legal", "identificacion"):
                if not str(acumulada.get(k, "")).strip() and str(nueva.get(k, "")).strip():
                    acumulada[k] = str(nueva[k]).strip()
            continue

        _commit(acumulada)
        acumulada = nueva
    _commit(pre_acum)
    _commit(acumulada)
    return out


def _es_encabezado(cells) -> bool:
    joined = " ".join(cells).lower()
    return any(k in joined for k in _HEADER_TOKENS)


def _es_total(cells) -> bool:
    joined = " ".join(cells).lower()
    if "totales" in joined or "total sin impuestos" in joined or "total igv" in joined or "total a cobrar" in joined:
        return True
    return False


def _extraer_por_coordenadas(page) -> List[Dict[str, Any]]:
    palabras = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
    if not palabras:
        return []

    def _y(p):
        return (p["top"] + p["bottom"]) / 2

    palabras_ordenadas = sorted(palabras, key=lambda p: (_y(p), p["x0"]))

    filas_agrupadas: List[List[Any]] = []
    tol_y = 10.0
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
    for y_ref, palabras_fila in filas_agrupadas:
        if not palabras_fila:
            continue
        palabras_fila.sort(key=lambda p: (p["x0"], p["top"]))
        raw_ts = [p["text"].strip() for p in palabras_fila if p["text"].strip()]

        # === PEGADO INTELIGENTE DE TOKENS VERTICALES (misma X, 2 líneas) ===
        merged: List[str] = []
        i = 0
        while i < len(raw_ts):
            t = raw_ts[i]
            if i + 1 < len(raw_ts):
                nxt = raw_ts[i + 1]
                glued = None
                # 1) "CC-PF-SCTR-" + "003507623/1" o "F002-" + "02301677" (termina -, empieza dígito)
                #    PERO NO pegar guion-suelto "-" con dígitos (es "RUC - 20604865655")
                if (
                    t.endswith("-")
                    and len(t.rstrip("-")) >= 2
                    and re.match(r"^[A-Z0-9]", nxt)
                    and not nxt.startswith("-")
                    and not (len(t) == 1 and t == "-" and re.match(r"^\d{8,}", nxt))
                ):
                    glued = t + nxt
                # 2) "(23.00" + "%)"  →  "(23.00 %)"
                if glued is None and t.startswith("(") and re.match(r"\d", t.lstrip("(")) and (nxt == "%)" or nxt == "%"):
                    glued = t + " " + nxt
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

        if _es_encabezado(tokens) or _es_total(tokens):
            continue
        if re.search(r"p[aá]gina\s+\d+\s+(de|/)\s+\d+", low):
            continue
        if low.startswith("liquidaci"):
            continue
        if re.match(r"^(broker|liquidaci[oó]n (n[uú]mero|fecha)|fecha y hora)", low):
            continue
        if low.startswith("broker:") or low.startswith("fecha y hora"):
            continue
        if re.match(r"^(calle|urb\.?|av(enida)?\.?|jir[oó]n|jr\.?) ", low):
            continue
        if low.startswith("calle ") or low.startswith("urb. ") or low.startswith("av. "):
            continue
        if not re.search(r"[A-Za-z]", texto):
            continue
        if re.fullmatch(r"[\d\s\.\,\:\-]+", texto):
            continue

        grupos_texto.append((y_ref, texto, tokens))

    salidas: List[Dict[str, Any]] = []
    ultima_con_fecha: Optional[Tuple[float, Dict[str, Any]]] = None

    for y_ref, texto, tokens in grupos_texto:
        tiene_fecha_here = bool(_FECHA_RE.search(texto))
        tiene_monto_here = bool(_MONTO_RE_F.search(texto) or _PORCENTAJE_RE.search(texto))

        if not tiene_fecha_here and not tiene_monto_here:
            es_garbage = True
            if len(tokens) >= 3:
                if any(k in texto for k in ("SCTR", "VIDA", "Salud", "SANITAS", "Sanitas", "CUOTA", "Cuota", "F002", "Boleta", "Factura", "CC-", "PF-")):
                    es_garbage = False
            if es_garbage:
                continue

        if not tiene_fecha_here and ultima_con_fecha is not None and abs(y_ref - ultima_con_fecha[0]) <= 22.0:
            raw_prev = ultima_con_fecha[1].get("_raw", texto)
            merged = raw_prev + " " + texto
            parsed = parsear_fila_por_patrones([merged])
            if parsed is not None:
                parsed["_raw"] = merged
                salidas[-1] = parsed
                ultima_con_fecha = (y_ref, parsed)
                continue

        parsed = parsear_fila_por_patrones([texto])
        if parsed is None:
            continue
        parsed["_raw"] = texto
        salidas.append(parsed)
        if tiene_fecha_here:
            ultima_con_fecha = (y_ref, parsed)

    clean: List[Dict[str, Any]] = []
    for s in salidas:
        s.pop("_raw", None)
        clean.append(s)
    return clean


# ============================================================
#   NUEVO PARSER POR PATRONES (REGEX) — ORDEN INDEPENDIENTE
# ============================================================

def parsear_fila_por_patrones(celdas) -> Optional[Dict[str, Any]]:
    """
    Pega todas las celdas/tokens en un solo string y extrae cada campo con REGEX.
    Ventaja: no importa en qué columna X se haya imprimido, reconoce el PATRÓN.
    """
    out: Dict[str, Any] = {
        "fecha": "",
        "tipo_doc": "",
        "nro_documento": "",
        "doc_legal": "",
        "monto_doc": Decimal("0"),
        "monto_comision": Decimal("0"),
        "porcentaje_comision": Decimal("0"),
        "identificacion": "",
        "cliente": "",
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

    # 1) FECHA
    fm = _FECHA_RE.search(texto_global)
    if fm:
        d, mo, a = fm.group(1), fm.group(2), fm.group(3)
        if len(a) == 2:
            a = "20" + a
        out["fecha"] = f"{int(d):02d}/{int(mo):02d}/{a}"
    else:
        return None

    # 2) PORCENTAJE (23.00 %)
    pm = _PORCENTAJE_RE.search(texto_global)
    if pm:
        try:
            out["porcentaje_comision"] = _round2(Decimal(pm.group(1)))
        except Exception:
            pass

    # 3) MONTOS — todos los números 99.99 (incluyendo miles 1.234.56)
    montos_todos: List[Decimal] = []
    spans_montos: List[Tuple[int, int, Decimal]] = []
    for m in _MONTO_RE_F.finditer(texto_global):
        try:
            v = _to_decimal(m.group(1))
            montos_todos.append(v)
            spans_montos.append((m.start(), m.end(), v))
        except Exception:
            pass
    montos_unicos = list(dict.fromkeys(montos_todos))
    # ordenamos los montos únicos de mayor a menor (monto doc > comisión)
    montos_desc = sorted(montos_unicos, reverse=True)

    # 4) Determinar Monto Doc y Comisión (usando porcentaje si está)
    md = Decimal("0")
    mc = Decimal("0")
    if out["porcentaje_comision"] > 0 and montos_unicos:
        pct = out["porcentaje_comision"] / Decimal("100")
        candidatos_md = []
        for v_md in montos_unicos:
            mc_esp = _round2(v_md * pct)
            coincide = False
            for v2 in montos_unicos:
                if abs(float(v2 - mc_esp)) < 0.011:
                    coincide = True
                    break
            if coincide:
                candidatos_md.append((v_md, mc_esp))
        if candidatos_md:
            candidatos_md.sort(key=lambda x: x[0], reverse=True)
            md, mc = candidatos_md[0]

    if md == 0 and mc == 0 and len(montos_desc) >= 2:
        # Heurística: monto doc = mayor, comisión = segundo mayor (80% de los casos)
        #   PERO: si el 2º/3º no es pareja del mayor con 23%, probar todas las parejas
        pares = []
        for i in range(len(montos_desc)):
            for j in range(len(montos_desc)):
                if i == j:
                    continue
                v_md, v_mc = montos_desc[i], montos_desc[j]
                if out["porcentaje_comision"] > 0:
                    esp = _round2(v_md * out["porcentaje_comision"] / Decimal("100"))
                    if abs(float(v_mc - esp)) < 0.02:
                        pares.append((abs(float(v_mc - esp)), v_md, v_mc))
                if v_mc <= v_md * Decimal("0.7") and v_mc > 0:
                    diff = abs(float(v_md * Decimal("0.23") - v_mc))
                    pares.append((diff, v_md, v_mc))
        if pares:
            pares.sort(key=lambda x: x[0])
            _, md, mc = pares[0]

    if md == 0 and mc == 0 and len(montos_desc) >= 2:
        md, mc = montos_desc[0], montos_desc[1]
    if md == 0 and len(montos_desc) >= 1:
        md = montos_desc[0]

    # Regla final SANITAS: si hay Monto Doc pero NO se halló Comisión, se asume 23%.
    if mc == 0 and md > 0:
        pct_def = out["porcentaje_comision"] if out["porcentaje_comision"] > 0 else Decimal("23.00")
        mc = _round2(md * pct_def / Decimal("100"))
        if out["porcentaje_comision"] == 0:
            out["porcentaje_comision"] = Decimal("23.00")

    out["monto_doc"] = _round2(md)
    out["monto_comision"] = _round2(mc)

    # 5) NRO DOCUMENTO principal — puede ser 2, 3 o 4 segmentos:
    #    CC-PF-SCTR-003507623/1, PF-SCTR-003780149, F002-02471469
    nros_doc: List[str] = []
    for m in _NRO_DOC_RE.finditer(texto_global):
        n = m.group(1).strip("-")
        if re.fullmatch(r"F\d{3}-[A-Z0-9\-]{3,}", n):
            continue  # es doc legal (Sunat), no documento de póliza
        nros_doc.append(n)

    # Quitar duplicados preservando orden
    seen = set()
    nros_doc_unique = []
    for n in nros_doc:
        if n not in seen:
            seen.add(n)
            nros_doc_unique.append(n)
    nros_doc = nros_doc_unique

    # Prioridad: el que tenga más segmentos (CC-PF-SCTR > PF-SCTR > SCTR-...)
    nros_doc.sort(key=lambda n: (-n.count("-"), n))

    if nros_doc:
        out["nro_documento"] = nros_doc[0]
        # Si hay más de 1 documento póliza, unir con /
        if len(nros_doc) > 1 and not out["doc_legal"]:
            if not any(d in ("SCTR", "VIDA", "SALUD") for d in nros_doc[1:3]):
                # nros_doc[1:] podría ser doc legal? es Fxxx-?
                pass

    # 6) DOC LEGAL (F002-XXXXX / B001-XXXXX / 001-...-XXXX) — separado
    codigos_sunat: List[str] = []
    for m in _CODIGO_SUNAT_RE.finditer(texto_global):
        c = m.group(1).strip("-")
        if c == out["nro_documento"]:
            continue
        # Además no debe ser un documento SCTR/Póliza
        if any(k in c for k in ("SCTR", "VIDA", "SALUD", "CC-")):
            # lo registramos como póliza, no como doc legal
            if not out["nro_documento"]:
                out["nro_documento"] = c
            continue
        codigos_sunat.append(c)
    # Quitar duplicados preservando orden
    seen = set()
    cods_uniq = []
    for c in codigos_sunat:
        if c not in seen:
            seen.add(c)
            cods_uniq.append(c)
    if cods_uniq and not out["doc_legal"]:
        out["doc_legal"] = cods_uniq[0]

    # === NORMALIZACIÓN NRO DOCUMENTO: quitar prefijo "CC-" y sufijo "/N" ===
    #   CC-PF-SCTR-003507623/1  →  PF-SCTR-003507623
    if out["nro_documento"]:
        nd = out["nro_documento"]
        if nd.upper().startswith("CC-"):
            nd = nd[3:]
        nd = re.sub(r"\/\d+\s*$", "", nd)
        out["nro_documento"] = nd.strip("-")

    # 7) IDENTIFICACIÓN RUC / DNI — 11 dígitos (RUC 20xx / 10xx) o 8 dígitos
    rucs: List[str] = []
    for m in _RUC_RE.finditer(texto_global):
        r = m.group(1)
        if len(r) == 11 and r[:2] in ("20", "10", "17", "15", "18"):
            rucs.append(r)
        if len(r) == 8:
            rucs.append(r)
    # Quitar montos o códigos F002 que colaron
    rucs2 = []
    for r in rucs:
        if any(r in cod for cod in (out["nro_documento"], out["doc_legal"])):
            continue
        rucs2.append(r)
    rucs2 = list(dict.fromkeys(rucs2))
    if rucs2:
        out["identificacion"] = rucs2[0]

    # 8) TIPO DE DOCUMENTO — tokens que empiecen con "Cuota", "Proforma", "Factura",
    #    "Boleta", "Sanitas", "Perú S.A.", etc. NO incluya RUC, doc legal ni montos
    usado = set()
    usado.add(out["fecha"])
    usado.add(out["nro_documento"])
    usado.add(out["doc_legal"])
    usado.add(out["identificacion"])
    for _, _, v in spans_montos:
        usado.add(f"{v:.2f}")
        usado.add(f"{v:,.2f}")
    usado_low = {x.lower() for x in usado if x}
    tipo_tokens: List[str] = []
    for tok in raw_tokens:
        if not tok:
            continue
        low = tok.lower().strip(".,-()")
        if any(low == u for u in usado_low):
            continue
        if any(u in low for u in usado_low if u):
            continue
        if _MONTO_RE_F.fullmatch(tok.replace(",", "")):
            continue
        if re.fullmatch(r"[0-9\(\)\.\% ]+", low):
            continue
        if _FECHA_RE.fullmatch(tok):
            continue
        if low.startswith("ruc") or low == "dni" or low == "nro":
            continue
        if any(k in low for k in (
            "cuota", "proforma", "factura", "boleta", "sanitas", "nota de",
            "liquidaci", "eps", "sctrvida", "sctr", "vida", "salud", "perú",
            "peru", "s.a.", "s.a",
        )):
            tipo_tokens.append(tok)
        if tok in ("Sanitas", "Perú", "Peru", "CUOTA", "Cuota", "SCTR", "VIDA", "SALUD", "EPS"):
            if tok not in tipo_tokens:
                tipo_tokens.append(tok)
    # Limitar a 10 tokens para incluir "Sanitas Perú S.A." completo sin mezclar cliente
    out["tipo_doc"] = " ".join(tipo_tokens[:10]).strip(" .,-–—/:;()")

    # 9) CLIENTE — Algoritmo robusto basado en tokens (no en _quitar frágil)
    #    Construimos un SET de "bloqueados" = todo lo que NO es cliente.
    blocked: set = set()
    for b in (out["fecha"], out["nro_documento"], out["doc_legal"], out["identificacion"]):
        if b:
            blocked.add(b)
            blocked.add(b.strip("-"))
    for _, _, v in spans_montos:
        blocked.add(f"{v:.2f}")
        blocked.add(f"{v:,.2f}")
        blocked.add(str(v))
    for tok in tipo_tokens:
        blocked.add(tok)
        blocked.add(tok.strip(".,-()"))
    blocked_low = {x.lower() for x in blocked if x}

    # Buscamos el índice donde TERMINA el bloque "RUC - XXXXXXXXXX" (cliente empieza DESPUÉS)
    idx_ruc_end = -1
    for i, tok in enumerate(raw_tokens):
        low = tok.lower().strip(".,-():;")
        if low in ("ruc", "dni") and idx_ruc_end == -1:
            if i + 2 < len(raw_tokens):
                idx_ruc_end = i + 2
            continue

    cliente_tokens: List[str] = []
    for i, tok in enumerate(raw_tokens):
        if not tok:
            continue
        # Antes del fin de RUC: skippeamos
        if idx_ruc_end > 0 and i <= idx_ruc_end:
            continue
        t_strip = tok.strip(".,-–—/:;()%")
        t_low = t_strip.lower()
        if not t_strip:
            continue
        # Filtros básicos
        if not re.search(r"[A-Za-zÑñÁÉÍÓÚáéíóú0-9&]", t_strip):
            continue
        if re.fullmatch(r"[0-9\(\)\.\%\, ]+", t_strip):
            continue
        if _FECHA_RE.fullmatch(t_strip):
            continue
        if _MONTO_RE_F.fullmatch(t_strip.replace(",", "")):
            continue
        if t_low in blocked_low or t_strip in blocked:
            continue
        if any(t_low == u for u in blocked_low):
            continue
        if any(u and u in t_low for u in blocked_low if len(u) >= 3):
            continue
        if t_low in ("ruc", "dni", "nro", "s/", "$"):
            continue
        # Stop words: cortamos cuando aparecen y hay suficientes tokens
        if t_low in ("calle", "urbanizacion", "urb", "avenida", "av",
                     "jiron", "jr.", "lima", "perú", "peru") and len(cliente_tokens) >= 3:
            break
        cliente_tokens.append(tok)

    raw_cli = " ".join(cliente_tokens).strip(" .,-–—/:;()%")

    # === LIMPIEZA FINAL DE RUC/DOCUMENTOS ID PEGADOS ===
    for doc_val in (out["identificacion"], out["nro_documento"], out["doc_legal"]):
        if not doc_val:
            continue
        raw_cli = re.sub(r"[\s\-\–\—\(\)\%\.\,]+" + re.escape(doc_val) + r"[\s\-\–\—\(\)\%\.\,]+", " ", raw_cli)
        raw_cli = re.sub(re.escape(doc_val), " ", raw_cli)

    # === LIMPIEZA TOTAL: 1er carácter VÁLIDO hasta el último válido ===
    m_first = re.search(r"[A-Za-z0-9ÑñÁÉÍÓÚáéíóú&]", raw_cli)
    if m_first:
        raw_cli = raw_cli[m_first.start():]
    m_last = re.search(r"[A-Za-z0-9ÑñÁÉÍÓÚáéíóú&]", raw_cli[::-1])
    if m_last:
        raw_cli = raw_cli[:len(raw_cli) - m_last.start()]
    raw_cli = re.sub(r"\s{2,}", " ", raw_cli).strip()
    out["cliente"] = raw_cli

    # Si el cliente se quedó demasiado corto: intentar unir desde las celdas últimas del raw_tokens
    if len(out["cliente"].split()) < 2 and len(raw_tokens) >= 6:
        usado_set_low = set(x.lower() for x in usado if x)
        extra = []
        for tok in raw_tokens:
            if tok.lower() in usado_set_low:
                continue
            low = tok.lower().strip(".,()")
            if _MONTO_RE_F.fullmatch(tok.replace(",", "")):
                continue
            if _FECHA_RE.fullmatch(tok):
                continue
            if low in ("ruc", "dni", "nro"):
                continue
            extra.append(tok)
        # cliente son los últimos tokens
        if len(extra) >= 2:
            prop = " ".join(extra[max(0, len(extra) - 8):]).strip()
            if prop and not out["cliente"]:
                out["cliente"] = prop

    # Validaciones mínimas: debe haber monto doc o comisión o algún doc identificador
    if out["monto_doc"] == 0 and out["monto_comision"] == 0:
        return None
    if not out["nro_documento"] and not out["doc_legal"] and not out["cliente"]:
        return None
    return out


# ============================================================
#   COMPONENTE TKINTER
# ============================================================

class TableroFacturacion(tk.Frame):
    COLUMNS = (
        ("fecha", "Fecha Inicio", 90),
        ("tipo_doc", "Tipo de Documento", 170),
        ("nro_documento", "Nro. Documento", 180),
        ("doc_legal", "Doc. Legal", 120),
        ("monto_doc", f"Monto Doc. s/imp.", 120, "moneda"),
        ("monto_comision", f"Monto Comisión Broker", 140, "moneda"),
        ("porcentaje_comision", "% Comisión", 85, "porcentaje"),
        ("identificacion", "Nro Identificación", 130),
        ("cliente", "Cliente", 260),
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

        self.lbl_estado = tk.Label(inner, text="Listo. Cargue un PDF para empezar →",
                                   bg="#ffffff", fg="#64748b", font=("Segoe UI", 9), anchor="w")
        self.lbl_estado.pack(fill="x")

    def _crear_encabezado(self, parent):
        title_box = tk.Frame(parent, bg="#ffffff")
        title_box.pack(side="left")
        tk.Label(title_box, text="Gestión de Comisiones — Facturas",
                 bg="#ffffff", fg="#0f172a", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Extraiga datos desde el PDF de Sanitas. Los valores se pueden editar.",
                 bg="#ffffff", fg="#64748b", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(parent, bg="#ffffff")
        btns.pack(side="right")
        self._mkbtn(btns, "Cargar PDF", "#2563eb", self._cargar_pdf).pack(side="left", padx=3)
        self._mkbtn(btns, "Validar BD", "#16a34a", self._validar_contra_bd).pack(side="left", padx=3)
        self._mkbtn(btns, "Nueva fila", "#0ea5e9", self._agregar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Eliminar fila", "#ef4444", self._eliminar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Recalcular comisiones (23%)", "#0f766e", self._recalcular_comisiones_23).pack(side="left", padx=3)
        self._mkbtn(btns, "Limpiar todo", "#475569", self._limpiar).pack(side="left", padx=3)

    def _mkbtn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, bg=color, fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                         cursor="hand2", activebackground="#1e293b", activeforeground="#ffffff",
                         padx=12, pady=7, command=cmd)

    def _construir_totales(self, parent):
        cards = [
            ("Total Monto Doc. s/imp.", "monto_doc_total", "#2563eb", "#eff6ff"),
            ("Total Comisión Broker", "comision_total", "#0891b2", "#ecfeff"),
            ("Total sin impuestos (Base IGV)", "base_igv", "#475569", "#f8fafc"),
            ("Total IGV (18%)", "igv_total", "#f59e0b", "#fffbeb"),
            ("Total a cobrar", "total_cobrar", "#16a34a", "#f0fdf4"),
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
            sv = tk.StringVar(value=f"{MONEDA} 0.00")
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
            ("verde", COLOR_VERDE,    "#166534", "Recibo + Factura"),
            ("amarillo", COLOR_AMARILLO, "#92400e", "Solo hay Recibo"),
            ("rojo", COLOR_ROJO,     "#991b1b", "Sin Recibo ni Factura"),
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
            self.tree.column(cid, width=width, anchor=anchor, stretch=False if cid != "cliente" else True)

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
            title="Seleccionar PDF con detalle de Sanitas",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            filas = extraer_tablas_sanitas(path)
        except Exception as e:
            messagebox.showerror("Error al leer PDF",
                                 f"No se pudo leer el PDF.\n\n{str(e)}\n\n{traceback.format_exc(limit=1)}",
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
            "fecha": "",
            "tipo_doc": "Cuota - Sanitas Perú S.A.",
            "nro_documento": "",
            "doc_legal": "",
            "monto_doc": Decimal("0"),
            "monto_comision": Decimal("0"),
            "porcentaje_comision": Decimal("23.00"),
            "identificacion": "",
            "cliente": "",
        }
        self._append_row(fila)
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    def _append_row(self, f: Dict[str, Any]):
        self._uid_counter += 1
        uid = f"r{self._uid_counter}"
        data = dict(f)
        data["monto_doc"] = _round2(_to_decimal(data.get("monto_doc")))
        data["monto_comision"] = _round2(_to_decimal(data.get("monto_comision")))
        data["porcentaje_comision"] = _round2(_to_decimal(data.get("porcentaje_comision")))
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

    def _recalcular_comisiones_23(self):
        pct = Decimal("23.00")
        for i, row in enumerate(self._rows):
            md = _to_decimal(row.get("monto_doc"))
            if md > 0:
                row["porcentaje_comision"] = pct
                row["monto_comision"] = _round2(md * pct / Decimal("100"))
                iid = self.tree.get_children()[i]
                self.tree.item(iid, values=self._valores_tabla(row))
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(text=f"Comisiones recalculadas al 23% sobre Monto Doc. ({len(self._rows)} filas).", fg="#0f766e")

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

        try:
            resultados, cant_existe, cant_no_existe = validar_filas_contra_bd(self._rows)
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
            justify="right" if col_id in {"monto_doc", "monto_comision", "porcentaje_comision"} else "left"
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
        if col_id in {"monto_doc", "monto_comision", "porcentaje_comision"}:
            row[col_id] = _round2(_to_decimal(valor_nuevo))
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
                v = _to_decimal(raw)
                values.append(f"{MONEDA} {self._fmt_money(v)}")
            elif tipo == "porcentaje":
                v = _to_decimal(raw)
                values.append(f"{_round2(v):.2f} %")
            else:
                values.append("" if raw is None else str(raw))
        return tuple(values)

    def _actualizar_totales(self):
        monto_doc_total = Decimal("0")
        comision_total = Decimal("0")
        for r in self._rows:
            monto_doc_total += _to_decimal(r.get("monto_doc"))
            comision_total += _to_decimal(r.get("monto_comision"))
        monto_doc_total = _round2(monto_doc_total)
        comision_total = _round2(comision_total)
        base_igv = comision_total
        igv_total = _round2(base_igv * IGV_PORCENTAJE)
        total_cobrar = _round2(base_igv + igv_total)
        self._total_vars["monto_doc_total"].set(f"{MONEDA} {self._fmt_money(monto_doc_total)}")
        self._total_vars["comision_total"].set(f"{MONEDA} {self._fmt_money(comision_total)}")
        self._total_vars["base_igv"].set(f"{MONEDA} {self._fmt_money(base_igv)}")
        self._total_vars["igv_total"].set(f"{MONEDA} {self._fmt_money(igv_total)}")
        self._total_vars["total_cobrar"].set(f"{MONEDA} {self._fmt_money(total_cobrar)}")

    def _fmt_money(self, v: Decimal) -> str:
        s = f"{_round2(v):,.2f}"
        return s.replace(",", "¤").replace(".", ",").replace("¤", ".")
