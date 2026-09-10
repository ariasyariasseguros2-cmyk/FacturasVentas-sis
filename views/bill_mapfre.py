import os
import re
import traceback
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from utils.validacion_bd import (
    COLOR_AMARILLO,
    COLOR_ROJO,
    COLOR_VERDE,
    validar_filas_contra_bd,
)


TWO_PLACES_M = Decimal("0.01")
IGV_PORCENTAJE_M = Decimal("0.18")
MONEDA_MAPFRE = "S/."

_FECHA_RE_M = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b"
)
_MONTO_RE_M = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?!\d)")


def _parsear_linea_texto_mapfre(linea: str) -> Optional[Dict[str, str]]:
    """Fallback robusto de texto para una línea tipo MAPFRE PERU.

    Acepta una secuencia donde el primer token del bloque es la compañía,
    el tercero es la póliza y el resto del bloque se reparte entre cliente,
    ramo, recibo, estado, fecha y montos. La lógica separa la parte numérica
    inicial de la póliza de la cola alfabética si el PDF fusionó ambos tokens
    en un solo texto sin espacio.
    """
    linea = (linea or "").strip()
    if not linea:
        return None
    if "DUPLICADO DE LIQUIDACION" in linea.upper():
        return None
    if linea.upper().startswith("FECHA PROCESO") or linea.upper().startswith("MONEDA"):
        return None
    if "MAPFRE PERU" not in linea.upper():
        return None

    tokens = re.findall(r"\S+", linea)
    if len(tokens) < 12:
        return None
    if tokens[0].upper() != "MAPFRE" or tokens[1].upper() != "PERU":
        return None

    # Fecha: cualquier formato común del PDF (dd/mm/yyyy o yyyy-mm-dd).
    fecha_idx = None
    for i, tok in enumerate(tokens):
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", tok) or re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", tok):
            fecha_idx = i
            break
    if fecha_idx is None:
        return None

    # Antes de la fecha se espera: estado y nro_recibo.
    # Tomamos el último token del lado izquierdo como estado, y el anterior como recibo.
    izq = tokens[:fecha_idx]
    if len(izq) < 3:
        return None

    estado_recibo = izq[-1].strip().upper()
    nro_recibo = izq[-2].strip()
    if not re.fullmatch(r"\d+", nro_recibo):
        # Si el recibo fue colapsado con la poliza/cliente, aún intentamos recuperar el
        # valor numérico del token anterior al estado.
        nro_recibo = ""
        for t in reversed(izq[:-1]):
            if re.fullmatch(r"\d+", t):
                nro_recibo = t
                break
    if not nro_recibo:
        return None

    # Campos monetarios a la derecha de la fecha.
    derecho = tokens[fecha_idx + 1:]
    amount_tokens = []
    for tok in derecho:
        limpio = tok.replace("S/", "").replace("S/.", "")
        if re.fullmatch(r"\d{1,3}(?:,\d{3})*\.\d{2}|\d+(?:\.\d{2})?", limpio):
            amount_tokens.append(tok)
    if len(amount_tokens) < 3:
        return None

    prima_neta = amount_tokens[0]
    porcentaje_comision = amount_tokens[1]
    importe_comision = amount_tokens[2]

    # La póliza se dibuja como el token luego de MAPFRE PERU. A veces el token
    # trae también sufijo alfabético pegado al número (ej. 1012630201159PAN).
    poliza_token = tokens[2].strip()
    m_pol = re.match(r"^(\d+)", poliza_token)
    if m_pol:
        poliza_val = m_pol.group(1)
    else:
        poliza_val = poliza_token

    # El cliente es lo que queda entre la póliza y el par (estado, recibo, fecha).
    # Se toma el tramo de texto desde el índice 3 con corte justo antes de los tokens
    # del recibo/estado y la fecha.
    cliente_tokens = []
    for idx in range(3, fecha_idx - 2):
        t = tokens[idx]
        if t.upper() in {"CT", "CO", "AC", "PE", "SI", "SC", "FA", "LL"}:
            continue
        cliente_tokens.append(t)
    cliente = " ".join(cliente_tokens)

    # Ramo: se puede inferir como el bloque alfabético justo antes del recibo.
    nombre_ramo = ""
    if len(izq) >= 4:
        # Captura el tramo de letras antes del recibo y del estado, descartando la póliza.
        ramo_candidato = []
        for tok in izq[-4:-2]:
            if re.fullmatch(r"[A-ZÁÉÍÓÚÑa-záéíóúñ\-\s]+", tok):
                ramo_candidato.append(tok)
        if ramo_candidato:
            nombre_ramo = " ".join(ramo_candidato)

    campos = {
        "compania": "MAPFRE PERU",
        "poliza": poliza_val,
        "cliente": re.sub(r"\s{2,}", " ", cliente.strip()),
        "nro_referido": "",
        "nombre_ramo": re.sub(r"\s{2,}", " ", nombre_ramo.strip()),
        "nro_recibo": nro_recibo,
        "estado_recibo": estado_recibo,
        "fecha_movimiento": _normalizar_fecha_m(tokens[fecha_idx]),
        "prima_neta": prima_neta,
        "porcentaje_comision": porcentaje_comision,
        "importe_comision": importe_comision,
    }
    return campos


def _extraer_por_texto_mapfre(page) -> List[Dict[str, Any]]:
    """Fallback seguro si pdfplumber no encuentra tablas ni palabras alineadas por x-ranges."""
    texto = page.extract_text() or ""
    if not texto:
        return []

    resultados = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        campos = _parsear_linea_texto_mapfre(linea)
        if not campos:
            continue
        fila = _parsear_fila_mapfre(campos)
        if fila:
            resultados.append(fila)
    return resultados


def _to_decimal_m(val: Any) -> Decimal:
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    try:
        s = str(val).strip()
        if not s:
            return Decimal("0")
        s = s.replace("S/", "").replace("S/.", "").replace("$", "").replace("%", "").strip()
        s = s.replace(",", "")
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return Decimal("0")
        return Decimal(m.group(0)).quantize(TWO_PLACES_M, rounding=ROUND_HALF_UP)
    except (InvalidOperation, Exception):
        return Decimal("0")


def _round2_m(v: Decimal) -> Decimal:
    if not isinstance(v, Decimal):
        v = _to_decimal_m(v)
    return v.quantize(TWO_PLACES_M, rounding=ROUND_HALF_UP)


def _normalizar_fecha_m(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        return ""
    m_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", valor)
    if m_iso:
        y, mo, d = m_iso.groups()
        return f"{int(d):02d}/{int(mo):02d}/{y}"
    m_dmy = re.match(r"^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})$", valor)
    if m_dmy:
        d, mo, y = m_dmy.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{int(d):02d}/{int(mo):02d}/{y}"
    return valor


def _simplificar_texto_m(texto: str) -> str:
    s = (texto or "").strip().lower()
    s = (
        s.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )
    s = re.sub(r"\s{2,}", " ", s)
    return s


def _norm_token_m(token: str) -> str:
    return re.sub(r"[^a-z0-9%]+", "", _simplificar_texto_m(token))


def _agrupar_palabras_por_fila_m(palabras, tolerancia_y: float = 4.5):
    filas: List[Tuple[float, List[Any]]] = []
    for palabra in palabras:
        cy = (palabra["top"] + palabra["bottom"]) / 2
        colocado = False
        for i, (ref_y, items) in enumerate(filas):
            if abs(ref_y - cy) <= tolerancia_y:
                items.append(palabra)
                nuevo_y = ((ref_y * (len(items) - 1)) + cy) / len(items)
                filas[i] = (nuevo_y, items)
                colocado = True
                break
        if not colocado:
            filas.append((cy, [palabra]))

    filas.sort(key=lambda item: item[0])
    for _, items in filas:
        items.sort(key=lambda item: (item["x0"], item["top"]))
    return filas


def _texto_fila_m(palabras_fila) -> str:
    return " ".join(str(p["text"]).strip() for p in palabras_fila if str(p["text"]).strip())


def _contar_hits_header_m(texto: str) -> int:
    s = _simplificar_texto_m(texto)
    claves = (
        "compania",
        "poliza",
        "cliente",
        "referido",
        "ramo",
        "recibo",
        "estado",
        "movimiento",
        "prima neta",
        "%comision",
        "importe comision",
    )
    return sum(1 for clave in claves if clave in s)


def _mapear_header_desde_fila_m(palabras_fila) -> Optional[List[Tuple[str, float]]]:
    tokens = [_norm_token_m(p["text"]) for p in palabras_fila]
    campos: List[Tuple[str, float]] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        campo = None
        avanzar = 1

        if tok.startswith("comp"):
            campo = "compania"
        elif tok == "nro" and i + 1 < len(tokens) and tokens[i + 1].startswith("poliza"):
            campo = "poliza"
            avanzar = 2
        elif tok.startswith("poliza"):
            campo = "poliza"
        elif tok.startswith("cliente"):
            campo = "cliente"
        elif tok == "nro" and i + 1 < len(tokens) and tokens[i + 1].startswith("refer"):
            campo = "nro_referido"
            avanzar = 2
        elif tok.startswith("refer"):
            campo = "nro_referido"
        elif tok == "nombre" and i + 1 < len(tokens) and tokens[i + 1].startswith("ramo"):
            campo = "nombre_ramo"
            avanzar = 2
        elif tok.startswith("ramo"):
            campo = "nombre_ramo"
        elif tok == "nro" and i + 1 < len(tokens) and tokens[i + 1].startswith("recibo"):
            campo = "nro_recibo"
            avanzar = 2
        elif tok.startswith("recibo"):
            campo = "nro_recibo"
        elif tok.startswith("estado"):
            campo = "estado_recibo"
        elif tok == "fecha" and i + 1 < len(tokens) and tokens[i + 1].startswith("mov"):
            campo = "fecha_movimiento"
            avanzar = 2
        elif tok.startswith("mov"):
            campo = "fecha_movimiento"
        elif tok == "prima" and i + 1 < len(tokens) and tokens[i + 1].startswith("neta"):
            campo = "prima_neta"
            avanzar = 2
        elif tok == "primaneta":
            campo = "prima_neta"
        elif tok.startswith("%com") or (tok == "%" and i + 1 < len(tokens) and tokens[i + 1].startswith("com")):
            campo = "porcentaje_comision"
            avanzar = 2 if tok == "%" else 1
        elif tok == "importe" and i + 1 < len(tokens) and tokens[i + 1].startswith("comision"):
            campo = "importe_comision"
            avanzar = 2
        elif tok.startswith("comision") and i > 0 and tokens[i - 1].startswith("importe"):
            campo = "importe_comision"

        if campo:
            cx = (palabras_fila[i]["x0"] + palabras_fila[min(i + avanzar - 1, len(palabras_fila) - 1)]["x1"]) / 2
            campos.append((campo, cx))
        i += avanzar

    dedup: Dict[str, float] = {}
    for campo, centro in campos:
        if campo not in dedup:
            dedup[campo] = centro
    ordenados = sorted(dedup.items(), key=lambda item: item[1])
    
    # Se remueve "cliente" de los requeridos por venir pegado con "poliza"
    requeridos = {"poliza", "nro_recibo", "prima_neta", "importe_comision"}
    if requeridos.issubset(dedup.keys()):
        return ordenados
    return None


def _rangos_desde_header_m(campos_header: List[Tuple[str, float]]) -> List[Tuple[str, float, float]]:
    rangos: List[Tuple[str, float, float]] = []
    for idx, (campo, centro) in enumerate(campos_header):
        if idx == 0:
            izquierda = centro - 60
        else:
            izquierda = (campos_header[idx - 1][1] + centro) / 2
        if idx + 1 < len(campos_header):
            derecha = (centro + campos_header[idx + 1][1]) / 2
        else:
            derecha = centro + 80
        rangos.append((campo, izquierda, derecha))
    return rangos


def _campo_por_x_m(x: float, rangos: List[Tuple[str, float, float]]) -> str:
    for campo, izquierda, derecha in rangos:
        if izquierda <= x < derecha:
            return campo
    if rangos:
        return rangos[-1][0]
    return ""


def _es_meta_mapfre(texto: str) -> bool:
    s = _simplificar_texto_m(texto)
    if not s:
        return True
    patrones = (
        "duplicado de liquidacion",
        "fecha proceso",
        "moneda",
        "nroop",
        "fecha reporte",
        "agente",
        "razon social",
        "nro. ruc",
        "nro ruc",
        "fecha pago",
        "medio de pago",
    )
    return any(p in s for p in patrones)


def _es_total_mapfre(texto: str) -> bool:
    s = _simplificar_texto_m(texto)
    return s.startswith("total ") or "saldo anterior" in s or "total bono" in s


def _parsear_fila_mapfre(campos: Dict[str, str]) -> Optional[Dict[str, Any]]:
    poliza_val = campos.get("poliza", "").strip()
    cliente_val = campos.get("cliente", "").strip()

    # Si poliza contiene el numero y el cliente juntos (ej: "1012630201159 PANDURO TORRES...")
    if poliza_val and not cliente_val:
        m_pol = re.match(r"^(\d+)\s+(.+)$", poliza_val)
        if m_pol:
            poliza_val = m_pol.group(1)
            cliente_val = m_pol.group(2)

    fila = {
        "compania": re.sub(r"\s{2,}", " ", campos.get("compania", "").strip()),
        "poliza": poliza_val,
        "cliente": re.sub(r"\s{2,}", " ", cliente_val),
        "nro_referido": campos.get("nro_referido", "").strip(),
        "nombre_ramo": re.sub(r"\s{2,}", " ", campos.get("nombre_ramo", "").strip()),
        "nro_recibo": campos.get("nro_recibo", "").strip(),
        "estado_recibo": campos.get("estado_recibo", "").strip(),
        "fecha_movimiento": _normalizar_fecha_m(campos.get("fecha_movimiento", "").strip()),
        "prima_neta": _round2_m(_to_decimal_m(campos.get("prima_neta", "0"))),
        "porcentaje_comision": _round2_m(_to_decimal_m(campos.get("porcentaje_comision", "0"))),
        "importe_comision": _round2_m(_to_decimal_m(campos.get("importe_comision", "0"))),
    }

    if not fila["fecha_movimiento"]:
        m_fecha = _FECHA_RE_M.search(" ".join(campos.values()))
        if m_fecha:
            fila["fecha_movimiento"] = _normalizar_fecha_m(m_fecha.group(0))

    if fila["importe_comision"] == 0 and fila["prima_neta"] > 0 and fila["porcentaje_comision"] > 0:
        fila["importe_comision"] = _round2_m(
            fila["prima_neta"] * fila["porcentaje_comision"] / Decimal("100")
        )

    if fila["prima_neta"] == 0 and fila["importe_comision"] == 0:
        return None
    if not fila["poliza"] and not fila["nro_recibo"] and not fila["cliente"]:
        return None
    return fila


def _extraer_por_xranges_mapfre(page) -> List[Dict[str, Any]]:
    palabras = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
    if not palabras:
        return []

    filas = _agrupar_palabras_por_fila_m(palabras)
    header_rangos: List[Tuple[str, float, float]] = []
    resultados: List[Dict[str, Any]] = []
    ultima_fila: Optional[Dict[str, Any]] = None

    for _, palabras_fila in filas:
        texto = _texto_fila_m(palabras_fila).strip()
        if not texto:
            continue

        if _contar_hits_header_m(texto) >= 4:
            campos_header = _mapear_header_desde_fila_m(palabras_fila)
            if campos_header:
                header_rangos = _rangos_desde_header_m(campos_header)
            continue

        if not header_rangos:
            continue

        if _es_meta_mapfre(texto) or _es_total_mapfre(texto):
            continue

        celdas: Dict[str, List[str]] = {}
        for palabra in palabras_fila:
            token = str(palabra["text"]).strip()
            if not token:
                continue
            cx = (palabra["x0"] + palabra["x1"]) / 2
            campo = _campo_por_x_m(cx, header_rangos)
            if not campo:
                continue
            celdas.setdefault(campo, []).append(token)

        if not celdas:
            continue

        campos = {campo: " ".join(tokens).strip() for campo, tokens in celdas.items()}
        fila = _parsear_fila_mapfre(campos)
        if fila:
            resultados.append(fila)
            ultima_fila = fila
            continue

        texto_restante = re.sub(r"\s{2,}", " ", texto).strip()
        if (
            ultima_fila is not None
            and texto_restante
            and not _MONTO_RE_M.search(texto_restante)
            and not _FECHA_RE_M.search(texto_restante)
            and len(texto_restante.split()) <= 6
        ):
            ramo_actual = ultima_fila.get("nombre_ramo", "").strip()
            if texto_restante not in ramo_actual:
                ultima_fila["nombre_ramo"] = (ramo_actual + " " + texto_restante).strip()

    return resultados


def _detectar_columnas_tabla_mapfre(fila_encabezado) -> Optional[Dict[str, int]]:
    if not fila_encabezado:
        return None
    mapa: Dict[str, int] = {}
    for idx, celda in enumerate(fila_encabezado):
        s = _simplificar_texto_m("" if celda is None else str(celda).replace("\n", " ").strip())
        if "compania" in s:
            mapa.setdefault("compania", idx)
        elif "poliza" in s:
            mapa.setdefault("poliza", idx)
        elif "cliente" in s:
            mapa.setdefault("cliente", idx)
        elif "referido" in s:
            mapa.setdefault("nro_referido", idx)
        elif "ramo" in s:
            mapa.setdefault("nombre_ramo", idx)
        elif "recibo" in s and "estado" not in s:
            mapa.setdefault("nro_recibo", idx)
        elif "estado" in s:
            mapa.setdefault("estado_recibo", idx)
        elif "movimiento" in s:
            mapa.setdefault("fecha_movimiento", idx)
        elif "prima" in s:
            mapa.setdefault("prima_neta", idx)
        elif "%com" in s or "comision" in s and "%" in s:
            mapa.setdefault("porcentaje_comision", idx)
        elif "importe" in s:
            mapa.setdefault("importe_comision", idx)
            
    requeridos = {"poliza", "nro_recibo", "prima_neta", "importe_comision"}
    if requeridos.issubset(mapa.keys()):
        return mapa
    return None


def _procesar_tabla_mapfre(tabla) -> List[Dict[str, Any]]:
    if not tabla:
        return []
    filas = list(tabla)
    header_idx = None
    mapa = None
    for idx, fila in enumerate(filas[:6]):
        posible = _detectar_columnas_tabla_mapfre(fila)
        if posible is not None:
            header_idx = idx
            mapa = posible
            break
    if mapa is None or header_idx is None:
        return []

    resultados: List[Dict[str, Any]] = []
    for fila in filas[header_idx + 1:]:
        if fila is None:
            continue
        celdas = ["" if c is None else str(c).replace("\n", " ").strip() for c in fila]
        joined = " ".join(celdas).strip()
        if not joined or _es_meta_mapfre(joined) or _es_total_mapfre(joined):
            continue
        campos = {
            campo: celdas[idx_celda] if idx_celda < len(celdas) else ""
            for campo, idx_celda in mapa.items()
        }
        fila_parseada = _parsear_fila_mapfre(campos)
        if fila_parseada:
            resultados.append(fila_parseada)
    return resultados


def _fusionar_filas_para_pagina(filas_xranges: List[Dict[str, Any]], filas_tabla: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  
    if not filas_xranges:
        return filas_tabla
    if not filas_tabla:
        return filas_xranges

    # evitar duplicados por clave de poliza + recibo + cliente + fecha
    vistos = set()
    fusion = []
    for fila in filas_xranges + filas_tabla:
        clave = (
            str(fila.get("poliza", ""))
            + "|"
            + str(fila.get("nro_recibo", ""))
            + "|"
            + str(fila.get("cliente", ""))
            + "|"
            + str(fila.get("fecha_movimiento", ""))
        )
        if clave in vistos:
            continue
        vistos.add(clave)
        fusion.append(fila)
    return fusion


def _deduplicar_filas_mapfre(filas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    vistos = set()
    salida = []
    for fila in filas:
        clave = (
            str(fila.get("poliza", ""))
            + "|"
            + str(fila.get("nro_recibo", ""))
            + "|"
            + str(fila.get("cliente", ""))
            + "|"
            + str(fila.get("fecha_movimiento", ""))
            + "|"
            + str(fila.get("nombre_ramo", ""))
        )
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(fila)
    return salida


def extraer_tablas_mapfre(pdf_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except Exception:
        raise RuntimeError("Se requiere la libreria 'pdfplumber' para extraer datos del PDF.")

    filas: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_xrange = _extraer_por_xranges_mapfre(page)
            page_texto = _extraer_por_texto_mapfre(page)

            page_tabla = []
            try:
                tablas = page.extract_tables()
            except Exception:
                tablas = []

            if not tablas:
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
                ]
                for settings in estrategias:
                    try:
                        tabla = page.extract_table(table_settings=settings)
                    except Exception:
                        tabla = None
                    if not tabla:
                        continue
                    page_tabla_parcial = _procesar_tabla_mapfre(tabla)
                    if page_tabla_parcial:
                        page_tabla.extend(page_tabla_parcial)
            else:
                for tabla in tablas:
                    page_tabla_parcial = _procesar_tabla_mapfre(tabla)
                    if page_tabla_parcial:
                        page_tabla.extend(page_tabla_parcial)

            page_filas = _fusionar_filas_para_pagina(page_xrange, page_tabla)
            page_filas = _fusionar_filas_para_pagina(page_filas, page_texto)
            if page_filas:
                filas.extend(page_filas)

    return _deduplicar_filas_mapfre(filas)


class TableroFacturacionMapfre(tk.Frame):
    COLUMNS = (
        ("nro_item", "N°", 55),
        ("compania", "Compañia", 120),
        ("poliza", "Nro. Poliza", 110),
        ("cliente", "Cliente", 290),
        ("nro_referido", "Nro. Referido", 120),
        ("nombre_ramo", "Nombre Ramo", 170),
        ("nro_recibo", "Nro. Recibo", 110),
        ("estado_recibo", "Estado", 80),
        ("fecha_movimiento", "Fecha Movimiento", 115),
        ("prima_neta", "Prima Neta", 105, "moneda"),
        ("porcentaje_comision", "% Comision", 95, "porcentaje"),
        ("importe_comision", "Importe Comision", 120, "moneda"),
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

        self.lbl_estado = tk.Label(
            inner,
            text="Listo. Cargue un PDF de Mapfre para empezar ->",
            bg="#ffffff",
            fg="#64748b",
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.lbl_estado.pack(fill="x")

    def _crear_encabezado(self, parent):
        title_box = tk.Frame(parent, bg="#ffffff")
        title_box.pack(side="left")
        tk.Label(
            title_box,
            text="Liquidacion de Comisiones - Mapfre",
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="Extraiga datos del PDF de Mapfre con columnas alineadas al formato del documento oficial.",
            bg="#ffffff",
            fg="#64748b",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(parent, bg="#ffffff")
        btns.pack(side="right")
        self._mkbtn(btns, "Cargar PDF Mapfre", "#2563eb", self._cargar_pdf).pack(side="left", padx=3)
        self._mkbtn(btns, "Validar BD", "#16a34a", self._validar_contra_bd).pack(side="left", padx=3)
        self._mkbtn(btns, "Nueva fila", "#0ea5e9", self._agregar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Eliminar fila", "#ef4444", self._eliminar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Recalcular comision", "#0f766e", self._recalcular_comision).pack(side="left", padx=3)
        self._mkbtn(btns, "Limpiar todo", "#475569", self._limpiar).pack(side="left", padx=3)

    def _mkbtn(self, parent, text, color, cmd):
        return tk.Button(
            parent,
            text=text,
            bg=color,
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            activebackground="#1e293b",
            activeforeground="#ffffff",
            padx=12,
            pady=7,
            command=cmd,
        )

    def _construir_totales(self, parent):
        cards = [
            ("Total Prima Neta", "prima_total", "#2563eb", "#eff6ff"),
            ("Total Comision", "comision_total", "#0891b2", "#ecfeff"),
            ("Base IGV (solo comision)", "base_igv", "#475569", "#f8fafc"),
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
            tk.Label(pad, text=label, bg=bgcard, fg="#475569", font=("Segoe UI", 9)).pack(anchor="w")
            sv = tk.StringVar(value=f"{MONEDA_MAPFRE} 0.00")
            self._total_vars[key] = sv
            tk.Label(
                pad,
                textvariable=sv,
                bg=bgcard,
                fg=color,
                font=("Segoe UI", 16, "bold"),
            ).pack(anchor="w", pady=(4, 0))

    def _construir_leyenda(self, parent):
        wrap = tk.Frame(parent, bg="#f8fafc", highlightbackground="#e2e8f0", highlightthickness=1)
        wrap.pack(fill="x", padx=0, pady=0)
        inner = tk.Frame(wrap, bg="#f8fafc")
        inner.pack(fill="x", padx=10, pady=6)

        tk.Label(inner, text="Leyenda:", bg="#f8fafc", fg="#334155", font=("Segoe UI", 9, "bold")).pack(side="left")

        reglas = [
            ("verde", COLOR_VERDE, "#166534", "Poliza + Factura"),
            ("amarillo", COLOR_AMARILLO, "#92400e", "Solo hay Poliza"),
            ("rojo", COLOR_ROJO, "#991b1b", "Sin Poliza ni Factura"),
        ]
        self._leyenda_vars: Dict[str, tk.StringVar] = {}
        for i, (key, bg, fg, texto) in enumerate(reglas):
            if i > 0:
                tk.Frame(inner, bg="#cbd5e1", width=1, height=18).pack(side="left", padx=10)
            item = tk.Frame(inner, bg="#f8fafc")
            item.pack(side="left", padx=(6 if i == 0 else 0, 0))
            tk.Label(
                item,
                text="  ",
                bg=bg,
                fg=fg,
                font=("Segoe UI", 9, "bold"),
                highlightbackground=fg,
                highlightthickness=1,
                width=2,
            ).pack(side="left")
            tk.Label(item, text=f" {texto} ", bg="#f8fafc", fg=fg, font=("Segoe UI", 9)).pack(side="left")
            sv = tk.StringVar(value="(0)")
            self._leyenda_vars[key] = sv
            tk.Label(item, textvariable=sv, bg="#f8fafc", fg=fg, font=("Segoe UI", 9, "bold")).pack(side="left")

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
            if cid == "nro_item":
                anchor = "center"
            elif align in ("moneda", "porcentaje", "e"):
                anchor = "e"
            else:
                anchor = "w"
            stretch = cid in {"cliente", "nombre_ramo"}
            self.tree.column(cid, width=width, anchor=anchor, stretch=stretch)

        scrollbar_y = ttk.Scrollbar(tv_frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tv_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Treeview",
            rowheight=24,
            font=("Segoe UI", 9),
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#0f172a",
            bordercolor="#e2e8f0",
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#f8fafc",
            foreground="#334155",
            relief="flat",
            bordercolor="#e2e8f0",
            padding=4,
        )
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

    def _valores_tabla(self, fila: Dict[str, Any], pos: int) -> Tuple[Any, ...]:
        return (
            pos,
            fila.get("compania", ""),
            fila.get("poliza", ""),
            fila.get("cliente", ""),
            fila.get("nro_referido", ""),
            fila.get("nombre_ramo", ""),
            fila.get("nro_recibo", ""),
            fila.get("estado_recibo", ""),
            fila.get("fecha_movimiento", ""),
            f"{_to_decimal_m(fila.get('prima_neta')):.2f}",
            f"{_to_decimal_m(fila.get('porcentaje_comision')):.2f}",
            f"{_to_decimal_m(fila.get('importe_comision')):.2f}",
        )

    def _actualizar_totales(self):
        prima_total = sum((_to_decimal_m(r.get("prima_neta")) for r in self._rows), Decimal("0"))
        comision_total = sum((_to_decimal_m(r.get("importe_comision")) for r in self._rows), Decimal("0"))
        base_igv = comision_total
        igv_total = _round2_m(base_igv * IGV_PORCENTAJE_M)
        total_cobrar = _round2_m(base_igv + igv_total)

        self._total_vars["prima_total"].set(f"{MONEDA_MAPFRE} {prima_total:.2f}")
        self._total_vars["comision_total"].set(f"{MONEDA_MAPFRE} {comision_total:.2f}")
        self._total_vars["base_igv"].set(f"{MONEDA_MAPFRE} {base_igv:.2f}")
        self._total_vars["igv_total"].set(f"{MONEDA_MAPFRE} {igv_total:.2f}")
        self._total_vars["total_cobrar"].set(f"{MONEDA_MAPFRE} {total_cobrar:.2f}")

    def _on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        if not item or not column:
            return

        col_idx = int(column.replace("#", "")) - 1
        if col_idx == 0:  # No editar N° de orden
            return

        col_key = self.COLUMNS[col_idx][0]
        row_idx = self.tree.index(item)
        if row_idx >= len(self._rows):
            return

        x, y, w, h = self.tree.bbox(item, column)
        value = str(self.tree.item(item, "values")[col_idx])

        entry = ttk.Entry(self.tree)
        entry.insert(0, value)
        entry.select_range(0, tk.END)
        entry.focus()
        entry.place(x=x, y=y, width=w, height=h)

        def save_edit(e=None):
            new_val = entry.get().strip()
            row_data = self._rows[row_idx]

            if col_key in ("prima_neta", "porcentaje_comision", "importe_comision"):
                row_data[col_key] = _round2_m(_to_decimal_m(new_val))
            elif col_key == "fecha_movimiento":
                row_data[col_key] = _normalizar_fecha_m(new_val)
            else:
                row_data[col_key] = new_val

            entry.destroy()
            self._editor = None
            self.tree.item(item, values=self._valores_tabla(row_data, row_idx + 1))
            self._actualizar_totales()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", lambda e: entry.destroy())
        entry.bind("<Escape>", lambda e: entry.destroy())

    def _cargar_pdf(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar PDF de Mapfre",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            filas = extraer_tablas_mapfre(path)
        except Exception as e:
            messagebox.showerror(
                "Error al leer PDF",
                f"No se pudo leer el PDF de Mapfre.\n\n{str(e)}\n\n{traceback.format_exc(limit=1)}",
                parent=self,
            )
            return

        if not filas:
            messagebox.showwarning(
                "Sin datos",
                "El PDF se leyo pero no se detectaron filas de detalle.\nPuede agregar filas manualmente con Nueva fila.",
                parent=self,
            )
            self._actualizar_totales()
            return

        for fila in filas:
            self._append_row(fila)

        self._renumerar()
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(
            text=f"Importado: {len(filas)} filas desde {os.path.basename(path)}  |  Total registros: {len(self._rows)}",
            fg="#059669",
        )
        messagebox.showinfo(
            "PDF importado correctamente",
            f"Se insertaron {len(filas)} filas correctamente desde:\n{os.path.basename(path)}\n\n"
            f"Total de registros en la tabla: {len(self._rows)}",
            parent=self,
        )

    def _agregar_fila(self):
        fila = {
            "compania": "MAPFRE PERU",
            "poliza": "",
            "cliente": "",
            "nro_referido": "",
            "nombre_ramo": "",
            "nro_recibo": "",
            "estado_recibo": "CT",
            "fecha_movimiento": "",
            "prima_neta": Decimal("0"),
            "porcentaje_comision": Decimal("0"),
            "importe_comision": Decimal("0"),
        }
        self._append_row(fila)
        self._renumerar()
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    def _append_row(self, fila: Dict[str, Any]):
        self._uid_counter += 1
        uid = f"r{self._uid_counter}"
        data = dict(fila)
        data["prima_neta"] = _round2_m(_to_decimal_m(data.get("prima_neta")))
        data["porcentaje_comision"] = _round2_m(_to_decimal_m(data.get("porcentaje_comision")))
        data["importe_comision"] = _round2_m(_to_decimal_m(data.get("importe_comision")))
        data["fecha_movimiento"] = _normalizar_fecha_m(str(data.get("fecha_movimiento", "")))
        self._rows.append(data)
        self.tree.insert("", "end", iid=uid, values=self._valores_tabla(data, len(self._rows)))

    def _renumerar(self):
        for pos, iid in enumerate(self.tree.get_children(), start=1):
            idx = pos - 1
            if 0 <= idx < len(self._rows):
                self.tree.item(iid, values=self._valores_tabla(self._rows[idx], pos))

    def _eliminar_fila(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Eliminar fila", f"¿Seguro que desea eliminar {len(sel)} fila(s)?", parent=self):
            return
        idxs = []
        for iid in sel:
            try:
                idxs.append(self.tree.index(iid))
            except Exception:
                pass
            try:
                self.tree.delete(iid)
            except Exception:
                pass
        for idx in sorted(idxs, reverse=True):
            if 0 <= idx < len(self._rows):
                del self._rows[idx]
        self._renumerar()
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

    def _recalcular_comision(self):
        actualizadas = 0
        for i, row in enumerate(self._rows):
            prima = _to_decimal_m(row.get("prima_neta"))
            pct = _to_decimal_m(row.get("porcentaje_comision"))
            if prima > 0 and pct > 0:
                row["importe_comision"] = _round2_m(prima * pct / Decimal("100"))
                iid = self.tree.get_children()[i]
                self.tree.item(iid, values=self._valores_tabla(row, i + 1))
                actualizadas += 1
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(
            text=f"Comision recalculada en {actualizadas} fila(s) usando Prima Neta y % Comision.",
            fg="#0f766e",
        )

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
            filas_para_validar.append(
                {
                    "fecha": r.get("fecha_movimiento", ""),
                    "tipo_doc": r.get("nombre_ramo", "") or "COMI",
                    "nro_documento": r.get("nro_recibo", "") or r.get("poliza", ""),
                    "doc_legal": r.get("nro_referido", ""),
                    "monto_doc": _to_decimal_m(r.get("prima_neta")),
                    "monto_comision": _to_decimal_m(r.get("importe_comision")),
                    "porcentaje_comision": _to_decimal_m(r.get("porcentaje_comision")),
                    "identificacion": "",
                    "cliente": r.get("cliente", ""),
                }
            )

        try:
            resultados, cant_existe, cant_no_existe = validar_filas_contra_bd(filas_para_validar)
        except Exception as e:
            messagebox.showerror(
                "Error de validacion",
                f"Ocurrio un error al validar contra la BD:\n\n{str(e)}\n\n{traceback.format_exc(limit=2)}",
                parent=self,
            )
            self.lbl_estado.configure(text="Error durante la validacion BD.", fg="#dc2626")
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
        self.lbl_estado.configure(
            text=f"Validacion completada: {cant_verde} verdes, {cant_amarillo} amarillos, {cant_rojo} rojos.",
            fg="#16a34a",
        )