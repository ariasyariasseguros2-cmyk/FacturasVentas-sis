import os
import re
import traceback
from typing import List, Dict, Any, Optional, Tuple, Set
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from utils.validacion_grandias_bd import (
    validar_filas_contra_grandias_bd,
    COLOR_VERDE,
    COLOR_AMARILLO,
    COLOR_ROJO,
)


TWO_PLACES_G = Decimal("0.01")
IGV_PORCENTAJE_G = Decimal("0.18")
MONEDA_GRANDIA = "S/."


def _to_decimal_g(val: Any) -> Decimal:
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
        return Decimal(m.group(0)).quantize(TWO_PLACES_G, rounding=ROUND_HALF_UP)
    except (InvalidOperation, Exception):
        return Decimal("0")


def _round2_g(v: Decimal) -> Decimal:
    if not isinstance(v, Decimal):
        v = _to_decimal_g(v)
    return v.quantize(TWO_PLACES_G, rounding=ROUND_HALF_UP)


# ============================================================
#   EXPRESIONES REGEX — CORREGIDAS PARA GRANDIA
# ============================================================
# Formato dual: DD/MM/AAAA y AAAA-MM-DD (formato ISO usado por Grandia)
_FECHA_RE_G = re.compile(
    r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b"
    r"|\b(\d{4})[\-](\d{1,2})[\-](\d{1,2})\b"
)

# Orden comisión INCLUYE MINÚSCULAS (ej: 2337-LQ-092026ef2c tiene "ef" hex minúsculas)
_NRO_DOC_RE_G = re.compile(r"\b((?:[A-Za-z0-9]{1,8}-){1,6}[A-Za-z0-9\-\/]{3,})\b")
_FACTURA_MOV_RE_G = re.compile(r"\b(F\d{2,3}-[A-Za-z0-9\-]{5,})\b")
_CONTRATO_RE_G = re.compile(r"\b(\d{6,12})\b")

# Porcentaje: acepta TANTO "(25.00%)" COMO el número solo "25.00"
#   - En Grandia el header se llama "Comision(%)" PERO los datos son 25.00 (sin %)
_PORCENTAJE_SOLO_NUM_RE = re.compile(
    r"^\s*\(?\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:%|%)?\s*\)?\s*$"
)

_MONTO_RE_G = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{3})*\.\d{2})(?!\d)")


def _normalizar_fecha(val: str) -> str:
    """Normaliza fecha DD/MM/AAAA o AAAA-MM-DD a DD/MM/AAAA."""
    val = (val or "").strip()
    if not val:
        return ""
    # YYYY-MM-DD
    m_iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", val)
    if m_iso:
        y, mo, d = m_iso.group(1), m_iso.group(2), m_iso.group(3)
        return f"{int(d):02d}/{int(mo):02d}/{y}"
    # DD/MM/AAAA  o DD-MM-AAAA  o DD.MM.AA
    m_dmy = re.match(r"^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})$", val)
    if m_dmy:
        d, mo, a = m_dmy.group(1), m_dmy.group(2), m_dmy.group(3)
        if len(a) == 2:
            a = "20" + a
        return f"{int(d):02d}/{int(mo):02d}/{a}"
    return val


# ============================================================
#   EXTRACCIÓN POR RANGOS X (ESTRATEGIA MÁS ROBUSTA)
#   Detecta el header real, toma los X0/X1 de cada columna,
#   y asigna cada palabra a la columna por su coordenada X.
# ============================================================

_HEADER_MARKERS_G = [
    ("nro_orden",           ["n°", "n° "]),
    ("nro_contrato",        ["n° contrato", "nro contrato", "contrato"]),
    ("grupo_rmi",           ["grupo rmi", "grupo"]),
    ("contratante",         ["contratante"]),
    ("producto",            ["producto"]),
    ("agente",              ["agente"]),
    ("factura_movimiento",  ["factura de movimien", "factura mov", "factura de", "factura"]),
    ("fecha_emision",       ["na emision", "a emision", "emision", "emisió", "emisión"]),
    ("facturada_soles",     ["factcturada s/", "facturada s/.", "facturada soles", "facturada"]),
    ("porcentaje_comision", ["comision(%", "comision (%", "comisión(%", "comisión (%,", "%sión", "porcentaje"]),
    ("comision_soles",      ["isión(s/)", "comisión(s/)", "comision s/.", "comisión s/.", "comision soles", "comisión soles"]),
    ("fecha_disponible",    ["a de disponibil", "fecha disponibil", "de disponibil", "disponible"]),
    ("orden_comision",      ["orden comisi", "orden comisión", "orden"]),
    ("estado_comision",     ["estado comisi", "estado comisión", "estado"]),
    ("fecha_registro",      ["fecha registro", "registro"]),
]

# Orden correcto de columnas en el PDF Grandia (para fallback de posición)
_COLUMNAS_ORDEN_GRANDIA = [
    "nro_orden", "nro_contrato", "grupo_rmi", "contratante",
    "producto", "agente", "factura_movimiento", "fecha_emision",
    "facturada_soles", "porcentaje_comision", "comision_soles",
    "fecha_disponible", "orden_comision", "estado_comision", "fecha_registro",
]


def _tokenizar_header(texto: str) -> str:
    return re.sub(r"\s{2,}", " ", texto.replace("\n", " ").strip().lower())


def _encontrar_header_y_columnas(page) -> Optional[List[Tuple[str, float, float, float]]]:
    """
    Busca la línea de encabezado en la página (con coordenadas).
    Devuelve lista de tuplas (nombre_campo, x0, x1, centro_y)
    o None si no se encontró.
    """
    palabras = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
    if not palabras:
        return None

    def _y(p):
        return (p["top"] + p["bottom"]) / 2

    # Agrupar palabras por fila (mismo centro-y)
    filas: List[Tuple[float, List[Any]]] = []
    tol_y = 8.0
    for p in palabras:
        yp = _y(p)
        puesta = False
        for ref_y, palabras_fila in filas:
            if abs(ref_y - yp) <= tol_y:
                palabras_fila.append(p)
                puesta = True
                break
        if not puesta:
            filas.append((yp, [p]))

    # Para cada fila, ver si es HEADER (contiene markers suficientes)
    for ref_y, pals_fila in filas:
        pals_fila.sort(key=lambda p: (p["x0"], p["top"]))
        texto_fila = _tokenizar_header(" ".join(p["text"] for p in pals_fila if p["text"].strip()))
        if not texto_fila:
            continue

        hits = 0
        for _, keys in _HEADER_MARKERS_G:
            for k in keys:
                if k in texto_fila:
                    hits += 1
                    break
        if hits < 5:
            continue

        # ES HEADER. Ahora asignar cada palabra/sublista a una columna.
        # Estrategia: juntar tokens adyacentes hasta que se encuentre
        # un nuevo marker de columna distinto.
        columnas_detectadas: List[Tuple[str, float, float, float]] = []
        # Construir texto corrido con coordenadas: por cada token, buscar qué marker le corresponde
        # por substring match acumulado desde izquierda.
        # Método más simple: expandir una ventana de tokens acumulados y ver a qué campo match.
        i = 0
        n = len(pals_fila)
        while i < n:
            # Buscar el campo que MATCHEE con el acumulado empezando en i
            mejor_campo = None
            mejor_hasta = i  # al menos 1 token
            acumulado = ""
            for j in range(i, min(i + 8, n)):
                if acumulado:
                    acumulado += " "
                acumulado += pals_fila[j]["text"]
                acum_norm = _tokenizar_header(acumulado)
                matched = None
                for campo, keys in _HEADER_MARKERS_G:
                    for k in keys:
                        if k in acum_norm:
                            matched = campo
                            break
                    if matched:
                        break
                if matched:
                    mejor_campo = matched
                    mejor_hasta = j
            if mejor_campo is None:
                # Token no identificado → asignar al último campo (continuación)
                if columnas_detectadas:
                    columnas_detectadas[-1] = (
                        columnas_detectadas[-1][0],
                        columnas_detectadas[-1][1],
                        pals_fila[mejor_hasta]["x1"],
                        ref_y,
                    )
                i += 1
                continue
            # Evitar duplicados (mismo campo dos veces)
            if columnas_detectadas and columnas_detectadas[-1][0] == mejor_campo:
                # extender x1 del último
                columnas_detectadas[-1] = (
                    mejor_campo,
                    columnas_detectadas[-1][1],
                    pals_fila[mejor_hasta]["x1"],
                    ref_y,
                )
            else:
                columnas_detectadas.append((
                    mejor_campo,
                    pals_fila[i]["x0"],
                    pals_fila[mejor_hasta]["x1"],
                    ref_y,
                ))
            i = mejor_hasta + 1

        if len(columnas_detectadas) >= 6:
            return columnas_detectadas
    return None


def _extraer_por_xranges(page, columnas_header: List[Tuple[str, float, float, float]]) -> List[Dict[str, Any]]:
    """
    A partir de columnas detectadas (campo, x0, x1, y_ref),
    mapea cada palabra de las filas de datos a su columna por coordenada X.
    """
    if not columnas_header:
        return []

    header_y = columnas_header[0][3]

    # Expandir ligeramente los rangos y construir (campo, x0, x1) ordenados por x0
    rangos: List[Tuple[str, float, float]] = []
    col_x_centers = sorted(
        [(c[0], c[1], c[2], (c[1] + c[2]) / 2) for c in columnas_header],
        key=lambda t: t[3],
    )
    # Rellenar gaps entre columnas: fin de i = mitad entre fin_i y centro_{i+1}
    for idx, (campo, x0, x1, xc) in enumerate(col_x_centers):
        if idx + 1 < len(col_x_centers):
            next_xc = col_x_centers[idx + 1][3]
            x1_ext = (x1 + next_xc) / 2
        else:
            x1_ext = x1 + 60
        if idx > 0:
            prev_x1 = col_x_centers[idx - 1][2]
            x0_ext = (prev_x1 + x0) / 2
        else:
            x0_ext = max(0, x0 - 10)
        rangos.append((campo, x0_ext, x1_ext))

    # Extraer todas las palabras y agrupar por fila (sólo las que están ABAJO del header)
    palabras = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
    if not palabras:
        return []

    def _y(p):
        return (p["top"] + p["bottom"]) / 2

    filas_pals: List[Tuple[float, List[Any]]] = []
    tol_y_filas = 7.5
    for p in sorted(palabras, key=lambda w: (_y(w), w["x0"])):
        if _y(p) <= header_y + 6:  # header o superior
            continue
        yp = _y(p)
        puesta = False
        for ref_y, pf in filas_pals:
            if abs(ref_y - yp) <= tol_y_filas:
                pf.append(p)
                puesta = True
                break
        if not puesta:
            filas_pals.append((yp, [p]))

    # Para cada fila, asignar tokens a columnas
    filas_procesadas: List[Dict[str, Any]] = []
    for y_fila, pals in filas_pals:
        pals.sort(key=lambda p: (p["x0"], p["top"]))
        celda_por_campo: Dict[str, List[str]] = {c: [] for c, _, _ in rangos}
        for p in pals:
            t = p["text"].strip()
            if not t:
                continue
            xc_p = (p["x0"] + p["x1"]) / 2
            # Asignar a la columna cuyo rango contenga xc_p,
            # o al más cercano por distancia
            idx_mejor = -1
            dist_mejor = 1e9
            for idx, (campo, xr0, xr1) in enumerate(rangos):
                if xr0 <= xc_p <= xr1:
                    idx_mejor = idx
                    dist_mejor = 0
                    break
                d = min(abs(xc_p - xr0), abs(xc_p - xr1))
                if d < dist_mejor:
                    dist_mejor = d
                    idx_mejor = idx
            if idx_mejor >= 0 and dist_mejor < 80:
                campo = rangos[idx_mejor][0]
                celda_por_campo[campo].append(t)

        # Unir tokens de cada celda y limpiar
        out: Dict[str, Any] = {
            "nro_orden": "", "nro_contrato": "", "grupo_rmi": "", "contratante": "",
            "producto": "", "agente": "", "factura_movimiento": "", "fecha_emision": "",
            "facturada_soles": Decimal("0"), "comision_soles": Decimal("0"),
            "porcentaje_comision": Decimal("0"), "fecha_disponible": "",
            "orden_comision": "", "estado_comision": "", "fecha_registro": "",
        }
        for campo, tokens in celda_por_campo.items():
            if not tokens:
                continue
            joined = " ".join(tokens).strip()
            if campo in ("facturada_soles", "comision_soles"):
                out[campo] = _to_decimal_g(joined)
            elif campo == "porcentaje_comision":
                # En Grandia es 25.00 sin símbolo %
                pm = _PORCENTAJE_SOLO_NUM_RE.match(joined)
                if pm:
                    out[campo] = _round2_g(Decimal(pm.group(1)))
                else:
                    out[campo] = _to_decimal_g(joined)
            elif campo.startswith("fecha_"):
                out[campo] = _normalizar_fecha(joined)
            else:
                out[campo] = re.sub(r"\s{2,}", " ", joined).strip(" .,-()")

        # Limpiar valores: filtrar filas basura
        if (out["facturada_soles"] == 0 and out["comision_soles"] == 0):
            continue
        if (
            not out["factura_movimiento"] and not out["orden_comision"]
            and not out["contratante"] and not out["nro_contrato"]
        ):
            continue

        # Si porcentaje está vacío pero hay facturado y comision, calcularlo
        if out["porcentaje_comision"] == 0 and out["facturada_soles"] > 0 and out["comision_soles"] > 0:
            pct_calc = _round2_g(out["comision_soles"] * Decimal("100") / out["facturada_soles"])
            out["porcentaje_comision"] = pct_calc
        # Si porcentaje sigue 0, asumir 25% (estándar Grandia EPS)
        if out["porcentaje_comision"] == 0 and out["facturada_soles"] > 0:
            out["porcentaje_comision"] = Decimal("25.00")
            out["comision_soles"] = _round2_g(out["facturada_soles"] * Decimal("25.00") / Decimal("100"))

        # Normalizar factura movimiento y orden comisión por regex
        if out["factura_movimiento"]:
            fm = _FACTURA_MOV_RE_G.search(out["factura_movimiento"])
            if fm:
                out["factura_movimiento"] = fm.group(1)
        if out["orden_comision"]:
            odm = _NRO_DOC_RE_G.search(out["orden_comision"])
            if odm:
                # Quitar cualquier paréntesis/guion residual
                out["orden_comision"] = re.sub(r"[()]+", "", odm.group(1)).strip("-")

        # Eliminar N° contrato si se coló una fecha/monto
        if out["nro_contrato"]:
            nc_limpio = re.sub(r"\D", "", out["nro_contrato"])
            if len(nc_limpio) < 6:
                out["nro_contrato"] = ""
            else:
                out["nro_contrato"] = nc_limpio

        filas_procesadas.append(out)
    return filas_procesadas


_ANCLA_NRO_CONTRATO_RE = re.compile(r"^\d{6,11}$")
_ANCLA_FACTURA_MOV_RE = re.compile(r"^F\d{2,3}\-\d{5,10}$")
_ANCLA_FECHA_SOLO_RE = re.compile(r"^(?:\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{4}\-\d{1,2}\-\d{1,2})$")
_ANCLA_MONTO_SOLO_RE = re.compile(r"^\-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?$")
_ANCLA_ORDEN_COMISION_RE = re.compile(r"^[\-A-Za-z0-9]{4,}\-LQ(?:\-LQ)?\-(?:[\-A-Za-z0-9]{4,})$")


def _construir_rangos_globales(page):
    columnas_header = _encontrar_header_y_columnas(page)
    if not columnas_header:
        return None
    col_x_centers = sorted(
        [(c[0], c[1], c[2], (c[1] + c[2]) / 2) for c in columnas_header],
        key=lambda t: t[3],
    )
    rangos: List[Tuple[str, float, float]] = []
    for idx, (campo, x0, x1, xc) in enumerate(col_x_centers):
        if idx + 1 < len(col_x_centers):
            next_xc = col_x_centers[idx + 1][3]
            x1_ext = (x1 + next_xc) / 2
        else:
            x1_ext = x1 + 60
        if idx > 0:
            prev_x1 = col_x_centers[idx - 1][2]
            x0_ext = (prev_x1 + x0) / 2
        else:
            x0_ext = max(0, x0 - 10)
        rangos.append((campo, x0_ext, x1_ext))
    header_y = columnas_header[0][3]
    return (rangos, header_y)


def _asignar_palabras_a_campos_por_rangos(
    pals: List[Any],
    rangos: List[Tuple[str, float, float]],
) -> Dict[str, List[str]]:
    celda_por_campo: Dict[str, List[str]] = {c: [] for c, _, _ in rangos}
    for p in pals:
        t = p["text"].strip()
        if not t:
            continue
        xc_p = (p["x0"] + p["x1"]) / 2
        idx_mejor = -1
        dist_mejor = 1e9
        for idx, (campo, xr0, xr1) in enumerate(rangos):
            if xr0 <= xc_p <= xr1:
                idx_mejor = idx
                dist_mejor = 0
                break
            d = min(abs(xc_p - xr0), abs(xc_p - xr1))
            if d < dist_mejor:
                dist_mejor = d
                idx_mejor = idx
        if idx_mejor >= 0 and dist_mejor < 120:
            campo = rangos[idx_mejor][0]
            celda_por_campo[campo].append(t)
    return celda_por_campo


def _finalizar_fila_dict(celda_por_campo: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
    out: Dict[str, Any] = {
        "nro_orden": "", "nro_contrato": "", "grupo_rmi": "", "contratante": "",
        "producto": "", "agente": "", "factura_movimiento": "", "fecha_emision": "",
        "facturada_soles": Decimal("0"), "comision_soles": Decimal("0"),
        "porcentaje_comision": Decimal("0"), "fecha_disponible": "",
        "orden_comision": "", "estado_comision": "", "fecha_registro": "",
    }
    for campo, tokens in celda_por_campo.items():
        if not tokens:
            continue
        joined = " ".join(tokens).strip()
        if campo in ("facturada_soles", "comision_soles"):
            out[campo] = _to_decimal_g(joined)
        elif campo == "porcentaje_comision":
            pm = _PORCENTAJE_SOLO_NUM_RE.match(joined)
            if pm:
                out[campo] = _round2_g(Decimal(pm.group(1)))
            else:
                out[campo] = _to_decimal_g(joined)
        elif campo.startswith("fecha_"):
            out[campo] = _normalizar_fecha(joined)
        else:
            out[campo] = re.sub(r"\s{2,}", " ", joined).strip(" .,-()")

    if out["porcentaje_comision"] == 0 and out["facturada_soles"] > 0 and out["comision_soles"] > 0:
        out["porcentaje_comision"] = _round2_g(out["comision_soles"] * Decimal("100") / out["facturada_soles"])
    if out["porcentaje_comision"] == 0 and out["facturada_soles"] > 0:
        out["porcentaje_comision"] = Decimal("25.00")
        out["comision_soles"] = _round2_g(out["facturada_soles"] * Decimal("25.00") / Decimal("100"))
    if out["factura_movimiento"]:
        fm = _FACTURA_MOV_RE_G.search(out["factura_movimiento"])
        if fm:
            out["factura_movimiento"] = fm.group(1)
    if out["orden_comision"]:
        odm = _NRO_DOC_RE_G.search(out["orden_comision"])
        if odm:
            out["orden_comision"] = re.sub(r"[()]+", "", odm.group(1)).strip("-")
    if out["nro_contrato"]:
        nc_limpio = re.sub(r"\D", "", out["nro_contrato"])
        if len(nc_limpio) < 6:
            out["nro_contrato"] = ""
        else:
            out["nro_contrato"] = nc_limpio

    if out["facturada_soles"] == 0 and out["comision_soles"] == 0:
        return None
    if (
        not out["factura_movimiento"] and not out["orden_comision"]
        and not out["contratante"] and not out["nro_contrato"]
    ):
        return None
    return out


def _extraer_filas_por_anclas(
    page,
    rangos_globales: Optional[List[Tuple[str, float, float]]],
    header_y_primera_pag: Optional[float],
    page_idx: int,
) -> List[Dict[str, Any]]:
    palabras = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
    if not palabras:
        return []

    def _y(p):
        return (p["top"] + p["bottom"]) / 2

    filas_pals: List[Tuple[float, List[Any]]] = []
    tol_y_filas = 8.0
    min_y = 0.0
    if page_idx == 0 and header_y_primera_pag is not None:
        min_y = header_y_primera_pag + 6
    for p in sorted(palabras, key=lambda w: (_y(w), w["x0"])):
        yp = _y(p)
        if yp < min_y:
            continue
        puesta = False
        for ref_y, pf in filas_pals:
            if abs(ref_y - yp) <= tol_y_filas:
                pf.append(p)
                puesta = True
                break
        if not puesta:
            filas_pals.append((yp, [p]))

    filas_procesadas: List[Dict[str, Any]] = []
    for y_fila, pals in filas_pals:
        if not pals:
            continue
        pals_sorted = sorted(pals, key=lambda pp: (pp["x0"], pp["top"]))
        textos = [pp["text"].strip() for pp in pals_sorted if pp["text"].strip()]
        if not textos:
            continue

        tiene_nro_contrato = False
        tiene_fact_mov = False
        tiene_fecha = False
        tiene_monto = False
        tiene_orden_comision = False
        tiene_guion_nro_cto = False
        cant_numeros = 0
        for t in textos:
            if _ANCLA_NRO_CONTRATO_RE.match(t):
                tiene_nro_contrato = True
            if t == "-":
                tiene_guion_nro_cto = True
            if _ANCLA_FACTURA_MOV_RE.match(t):
                tiene_fact_mov = True
            if _ANCLA_FECHA_SOLO_RE.match(t):
                tiene_fecha = True
            if _ANCLA_ORDEN_COMISION_RE.match(t):
                tiene_orden_comision = True
            if _ANCLA_MONTO_SOLO_RE.match(t):
                num_limpio = t.replace(",", "").replace(".", "")
                if num_limpio.lstrip("-").isdigit():
                    cant_numeros += 1
                    if "." in t or "," in t:
                        tiene_monto = True

        nro_cto_ok = tiene_nro_contrato or (tiene_guion_nro_cto and tiene_fact_mov)
        fila_valida = False
        if nro_cto_ok and (tiene_fact_mov or tiene_fecha or tiene_orden_comision):
            fila_valida = True
        elif tiene_fact_mov and (tiene_fecha or nro_cto_ok or tiene_orden_comision):
            fila_valida = True
        elif tiene_fecha and tiene_monto and cant_numeros >= 3:
            fila_valida = True
        elif tiene_orden_comision and cant_numeros >= 2 and len(textos) >= 6:
            fila_valida = True
        elif (nro_cto_ok or tiene_fact_mov) and cant_numeros >= 2:
            fila_valida = True
        elif nro_cto_ok and tiene_monto:
            fila_valida = True
        elif tiene_fact_mov and tiene_monto:
            fila_valida = True

        if not fila_valida:
            continue

        if rangos_globales:
            celdas = _asignar_palabras_a_campos_por_rangos(pals_sorted, rangos_globales)
        else:
            celdas: Dict[str, List[str]] = {
                "nro_orden": [], "nro_contrato": [], "grupo_rmi": [], "contratante": [],
                "producto": [], "agente": [], "factura_movimiento": [], "fecha_emision": [],
                "facturada_soles": [], "porcentaje_comision": [], "comision_soles": [],
                "fecha_disponible": [], "orden_comision": [], "estado_comision": [], "fecha_registro": [],
            }
            resto = textos
            if resto:
                celdas["nro_orden"] = [resto[0]]
                resto = resto[1:]
            montos_encontrados: List[str] = []
            fechas_encontradas: List[str] = []
            for tk in resto:
                if _ANCLA_NRO_CONTRATO_RE.match(tk) and not celdas["nro_contrato"]:
                    celdas["nro_contrato"] = [tk]
                elif tk == "-" and not celdas["nro_contrato"]:
                    celdas["nro_contrato"] = [""]
                elif _ANCLA_FACTURA_MOV_RE.match(tk):
                    celdas["factura_movimiento"] = [tk]
                elif _ANCLA_FECHA_SOLO_RE.match(tk):
                    fechas_encontradas.append(tk)
                elif _ANCLA_MONTO_SOLO_RE.match(tk) and ("." in tk or "," in tk):
                    montos_encontrados.append(tk)
                elif _ANCLA_ORDEN_COMISION_RE.match(tk):
                    celdas["orden_comision"] = [tk]
                elif re.match(r"^(?:EN\s+LIQUIDACION|LIQUIDADO|PENDIENTE|EN\s+PROCESO|ANULADO|PAGADO)$", tk, re.IGNORECASE):
                    celdas["estado_comision"] = [tk]
                elif re.match(r"^(?:SCTR|VIDA|SALUD|INCENDIO|VEHICULAR|AUTOMOTRIZ)$", tk, re.IGNORECASE):
                    celdas["producto"] = [tk]
                elif not celdas["contratante"]:
                    celdas["contratante"] = [tk]
                elif not celdas["producto"]:
                    celdas["producto"] = [tk]
                elif not celdas["agente"]:
                    celdas["agente"] = [tk]
                else:
                    if not celdas["grupo_rmi"]:
                        celdas["grupo_rmi"] = [tk]
                    else:
                        celdas["contratante"].append(tk)
            if len(fechas_encontradas) >= 1:
                celdas["fecha_emision"] = [fechas_encontradas[0]]
            if len(fechas_encontradas) >= 2:
                celdas["fecha_disponible"] = [fechas_encontradas[1]]
            if len(fechas_encontradas) >= 3:
                celdas["fecha_registro"] = [fechas_encontradas[-1]]
            if len(montos_encontrados) >= 1:
                celdas["facturada_soles"] = [montos_encontrados[0]]
            if len(montos_encontrados) >= 3:
                celdas["porcentaje_comision"] = [montos_encontrados[1]]
                celdas["comision_soles"] = [montos_encontrados[2]]
            elif len(montos_encontrados) == 2:
                pct_candidato = _to_decimal_g(montos_encontrados[1])
                if Decimal("1") <= pct_candidato <= Decimal("60"):
                    celdas["porcentaje_comision"] = [montos_encontrados[1]]
                    if len(montos_encontrados) >= 3:
                        celdas["comision_soles"] = [montos_encontrados[2]]
                else:
                    celdas["comision_soles"] = [montos_encontrados[1]]

        row_dict = _finalizar_fila_dict(celdas)
        if row_dict is None:
            continue
        filas_procesadas.append(row_dict)
    return filas_procesadas


_LINEA_INICIO_ITEM_RE = re.compile(r"^\s*(\d{1,3})\s+(.*)$")
_LINEA_INICIO_TOTAL_RE = re.compile(r"^\s*TOTAL\s*[:：]?", re.IGNORECASE)
_ESTADO_COMISION_RE = re.compile(
    r"(EN\s+LIQUIDACION|LIQUIDADO|PENDIENTE|EN\s+PROCESO|ANULADO|PAGADO|OBSERVADO)",
    re.IGNORECASE,
)
_NRO_DOC_FINAL_RE = re.compile(
    r"(\d{3,6}\-LQ(?:\-LQ)?\-(?:[\-A-Za-z0-9]{4,}))",
)


def _split_tokens_respetando_fechas_estados(linea: str) -> List[str]:
    tokens: List[str] = []
    i = 0
    s = linea.strip()
    n = len(s)
    while i < n:
        if s[i].isspace():
            i += 1
            continue
        j = i
        if s[i].isdigit() and (i + 2 < n):
            m1 = re.match(r"\d{4}\-\d{1,2}\-\d{1,2}", s[i:])
            m2 = re.match(r"\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}", s[i:])
            if m1:
                tokens.append(m1.group(0))
                i += len(m1.group(0))
                continue
            if m2:
                tokens.append(m2.group(0))
                i += len(m2.group(0))
                continue
        if s[i:i + 2].upper() == "EN":
            m3 = re.match(r"EN\s+LIQUIDACION|EN\s+PROCESO", s[i:], re.IGNORECASE)
            if m3:
                tokens.append(m3.group(0))
                i += len(m3.group(0))
                continue
        while j < n and not s[j].isspace():
            j += 1
        if j > i:
            tokens.append(s[i:j])
        i = j
    return tokens


def _parsear_fila_tokens_grandia(tokens: List[str]) -> Optional[Dict[str, Any]]:
    if not tokens:
        return None
    celdas: Dict[str, List[str]] = {
        "nro_orden": [], "nro_contrato": [], "grupo_rmi": [], "contratante": [],
        "producto": [], "agente": [], "factura_movimiento": [], "fecha_emision": [],
        "facturada_soles": [], "porcentaje_comision": [], "comision_soles": [],
        "fecha_disponible": [], "orden_comision": [], "estado_comision": [], "fecha_registro": [],
    }
    if tokens and tokens[0].isdigit():
        celdas["nro_orden"] = [tokens[0]]
        resto_tokens = tokens[1:]
    else:
        resto_tokens = list(tokens)

    montos: List[str] = []
    fechas: List[str] = []

    for idx_tk, tk in enumerate(resto_tokens):
        if _ANCLA_NRO_CONTRATO_RE.match(tk) and not celdas["nro_contrato"]:
            celdas["nro_contrato"] = [tk]
            continue
        if tk == "-" and not celdas["nro_contrato"]:
            celdas["nro_contrato"] = [""]
            continue
        if _ANCLA_FACTURA_MOV_RE.match(tk):
            celdas["factura_movimiento"] = [tk]
            continue
        if _ANCLA_FECHA_SOLO_RE.match(tk):
            fechas.append(tk)
            continue
        if _ANCLA_MONTO_SOLO_RE.match(tk):
            if "." in tk or "," in tk:
                montos.append(tk)
            continue
        if _ANCLA_ORDEN_COMISION_RE.match(tk) or _NRO_DOC_FINAL_RE.match(tk):
            celdas["orden_comision"] = [tk]
            continue
        m_est = _ESTADO_COMISION_RE.fullmatch(tk.upper().replace("  ", " "))
        if m_est:
            celdas["estado_comision"] = [tk]
            continue
        if re.match(r"^(?:SCTR|VIDA|SALUD|INCENDIO|VEHICULAR|AUTOMOTRIZ|FAP|VIDA\s*LEY|SALUD\s*EPS)$", tk, re.IGNORECASE):
            celdas["producto"] = [tk]
            continue
        if not celdas["contratante"]:
            celdas["contratante"] = [tk]
            continue
        hay_factura_antes = any(_ANCLA_FACTURA_MOV_RE.match(x) for x in resto_tokens[:idx_tk])
        if hay_factura_antes and not celdas["agente"]:
            celdas["agente"] = [tk]
        elif hay_factura_antes:
            celdas["agente"].append(tk)
        elif not celdas["producto"]:
            celdas["contratante"].append(tk)
        elif not celdas["agente"]:
            celdas["agente"] = [tk]
        else:
            celdas["contratante"].append(tk)

    if len(fechas) >= 1:
        celdas["fecha_emision"] = [fechas[0]]
    if len(fechas) >= 2:
        celdas["fecha_disponible"] = [fechas[1]]
    if len(fechas) >= 3:
        celdas["fecha_registro"] = [fechas[-1]]
    if len(montos) >= 1:
        celdas["facturada_soles"] = [montos[0]]
    if len(montos) >= 3:
        celdas["porcentaje_comision"] = [montos[1]]
        celdas["comision_soles"] = [montos[2]]
    elif len(montos) == 2:
        pct = _to_decimal_g(montos[1])
        if Decimal("1") <= pct <= Decimal("60"):
            celdas["porcentaje_comision"] = [montos[1]]
        else:
            celdas["comision_soles"] = [montos[1]]
    return _finalizar_fila_dict(celdas)


def _extraer_por_texto_plano_paginas(pdf) -> List[Dict[str, Any]]:
    resultado: List[Dict[str, Any]] = []
    todas_lineas: List[str] = []
    for page in pdf.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt:
            todas_lineas.extend(txt.split("\n"))

    lineas_normalizadas: List[str] = []
    for raw in todas_lineas:
        linea = raw.strip()
        if not linea:
            continue
        if _LINEA_INICIO_TOTAL_RE.match(linea):
            break
        norm = re.sub(r"\s{2,}", " ", linea)
        lineas_normalizadas.append(norm)

    bloques: List[Tuple[int, List[str]]] = []
    acum: List[str] = []
    item_actual: Optional[int] = None
    for linea in lineas_normalizadas:
        m = _LINEA_INICIO_ITEM_RE.match(linea)
        if m:
            n_item = int(m.group(1))
            resto = m.group(2)
            if 1 <= n_item <= 5000:
                if item_actual is not None and acum:
                    bloques.append((item_actual, acum))
                item_actual = n_item
                acum = [resto] if resto else []
                continue
        if item_actual is not None:
            if len(linea) < 3:
                continue
            acum.append(linea)
    if item_actual is not None and acum:
        bloques.append((item_actual, acum))

    for n_item, pedazos in bloques:
        linea_completa = " ".join(pedazos).strip()
        if not linea_completa:
            continue
        tokens = _split_tokens_respetando_fechas_estados(f"{n_item} {linea_completa}")
        fila = _parsear_fila_tokens_grandia(tokens)
        if fila is None:
            continue
        fila["nro_orden"] = str(n_item)
        resultado.append(fila)
    return resultado


def _clave_fila_unica(f: Dict[str, Any]) -> Tuple[str, str, str, str]:
    fm = (f.get("factura_movimiento") or "").strip()
    nc = (f.get("nro_contrato") or "").strip()
    fe = (f.get("fecha_emision") or "").strip()
    monto = f"{_round2_g(f.get('facturada_soles') or Decimal('0')):.2f}"
    return (nc, fm, fe, monto)


# ============================================================
#   FUNCIÓN PRINCIPAL DE EXTRACCIÓN
# ============================================================

def extraer_tablas_grandia(pdf_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except Exception:
        raise RuntimeError("Se requiere la librería 'pdfplumber' para extraer datos del PDF.")

    filas: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        estrategia_texto = _extraer_por_texto_plano_paginas(pdf)
        if estrategia_texto and len(estrategia_texto) >= 20:
            filas.extend(estrategia_texto)

        rangos_globales: Optional[List[Tuple[str, float, float]]] = None
        header_y_ppal: Optional[float] = None
        if pdf.pages:
            info_rg = _construir_rangos_globales(pdf.pages[0])
            if info_rg:
                rangos_globales, header_y_ppal = info_rg

        if len(filas) < 100:
            for page_idx, page in enumerate(pdf.pages):
                page_filas: List[Dict[str, Any]] = []
                extraido = False

                anclas_result = _extraer_filas_por_anclas(page, rangos_globales, header_y_ppal, page_idx)
                if anclas_result:
                    page_filas.extend(anclas_result)
                    extraido = True

                if not extraido:
                    columnas_header = _encontrar_header_y_columnas(page)
                    if columnas_header:
                        xr = _extraer_por_xranges(page, columnas_header)
                        if xr:
                            page_filas.extend(xr)
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
                        rows_page = _procesar_tabla_grandia_con_encabezado(t)
                        if rows_page:
                            page_filas.extend(rows_page)
                            extraido = True
                            break

                if not extraido:
                    rows_legacy = _extraer_grandia_por_patrones_page(page)
                    if rows_legacy:
                        page_filas.extend(rows_legacy)
                        extraido = True

                filas.extend(page_filas)

    vistas: Set[Tuple[str, str, str, str]] = set()
    unicas: List[Dict[str, Any]] = []
    for f in filas:
        clave = _clave_fila_unica(f)
        if clave in vistas:
            continue
        vistas.add(clave)
        unicas.append(f)
    filas = unicas

    for f in filas:
        if f["facturada_soles"] > 0:
            if f["porcentaje_comision"] == 0:
                f["porcentaje_comision"] = Decimal("25.00")
                f["comision_soles"] = _round2_g(f["facturada_soles"] * Decimal("25.00") / Decimal("100"))
            elif f["comision_soles"] == 0:
                f["comision_soles"] = _round2_g(f["facturada_soles"] * f["porcentaje_comision"] / Decimal("100"))
    return filas


# ============================================================
#   MAPEO DE COLUMNAS POR ENCABEZADO (fallback)
# ============================================================

_CAMPO_GRANDIA_POR_PALABRAS = [
    ("nro_orden",           ["n°", "n° fila", "n° ", "n", "item"]),
    ("nro_contrato",        ["n° contrato", "nro contrato", "contrato n°", "contrato"]),
    ("grupo_rmi",           ["grupo rmi", "grupo", "rmi"]),
    ("contratante",         ["contratante", "cliente", "razon social", "razón social", "nombre"]),
    ("producto",            ["producto", "product", "prod.", "ramo"]),
    ("agente",              ["agente", "intermediario", "broker"]),
    ("factura_movimiento",  ["factura de movimien", "factura mov.", "factura de", "factura", "n° factura", "nro factura"]),
    ("fecha_emision",       ["na emision", "a emision", "emision", "emisió", "emisión"]),
    ("facturada_soles",     ["factcturada s/", "facturada s/.", "facturada soles", "facturada", "monto facturado", "importe facturado"]),
    # Header truncado en PDF: "Comision(%" y "isión(S/) si" son 2 columnas distintas
    ("porcentaje_comision", ["comision(%", "comisión(%", "comision (%,", "comisión (%,", "%sión", "porcentaje comision", "porcent. comisi", "pct comision"]),
    ("comision_soles",      ["isión(s/)", "comisión(s/)", "comision s/.", "comisión s/.", "comision soles", "comisión soles", "importe comision", "monto comision", "comision si"]),
    ("fecha_disponible",    ["a de disponibil", "fecha disponibil", "fecha disponible", "de disponibil", "fec disponible", "disponible"]),
    ("orden_comision",      ["orden comisi", "orden comisión", "nro orden", "orden"]),
    ("estado_comision",     ["estado comisi", "estado comisión", "estado"]),
    ("fecha_registro",      ["fecha registro", "registro"]),
]


def _detectar_columnas_grandia_por_encabezado(fila_encabezado) -> Optional[Dict[str, int]]:
    if not fila_encabezado:
        return None
    norm_cells = []
    for i, c in enumerate(fila_encabezado):
        s = "" if c is None else str(c).replace("\n", " ").strip().lower()
        s = re.sub(r"\s{2,}", " ", s)
        norm_cells.append(s)
    joined = " ".join(norm_cells)
    if not any(k in joined for k in (
        "contratante", "factura de", "factcturada", "comision", "orden comisi",
    )):
        return None
    mapa: Dict[str, int] = {}
    for idx, s in enumerate(norm_cells):
        matched = None
        for campo, palabras in _CAMPO_GRANDIA_POR_PALABRAS:
            for palabra in palabras:
                if palabra in s:
                    matched = campo
                    break
            if matched:
                break
        if matched and matched not in mapa:
            mapa[matched] = idx
    # Fallback: si no se detectó porcentaje_comision por nombre, detectar por POSICIÓN RELATIVA
    # Entre facturada_soles y comision_soles debería estar el porcentaje
    if "porcentaje_comision" not in mapa and "facturada_soles" in mapa and "comision_soles" in mapa:
        fi = mapa["facturada_soles"]
        ci = mapa["comision_soles"]
        # Si hay exactamente 1 columna entre ambas, esa es el %
        if ci - fi == 2:
            mapa["porcentaje_comision"] = fi + 1
        elif ci - fi >= 1:
            # % es adyacente antes de comision_soles
            mapa["porcentaje_comision"] = ci - 1
    checks = [
        ("facturada_soles" in mapa or "comision_soles" in mapa),
        ("contratante" in mapa or "nro_contrato" in mapa),
        ("factura_movimiento" in mapa or "orden_comision" in mapa),
    ]
    if sum(checks) >= 2:
        return mapa
    return None


def _procesar_tabla_grandia_con_encabezado(tabla) -> List[Dict[str, Any]]:
    if not tabla:
        return []
    filas = list(tabla)
    header_row_idx = None
    mapa = None
    for start in range(min(6, len(filas))):
        mapa = _detectar_columnas_grandia_por_encabezado(filas[start])
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
            if cur and not cur.endswith((" ", "-", "/", "&", ".")) and not ext.startswith((" ", "-", "/", "&", ".")):
                sep = " "
            destino[k] = re.sub(r"\s{2,}", " ", (cur + sep + ext).strip())

    def _commit(acum: Optional[Dict[str, Any]]):
        if acum is None:
            return
        fs = _to_decimal_g(acum.get("facturada_soles"))
        cs = _to_decimal_g(acum.get("comision_soles"))
        pct_raw = acum.get("porcentaje_comision", "")
        pct_val = Decimal("0")
        if isinstance(pct_raw, Decimal):
            pct_val = pct_raw
        else:
            str_pct = str(pct_raw).replace("%", "").replace("(", "").replace(")", "").strip()
            if _PORCENTAJE_SOLO_NUM_RE.match(str_pct):
                m_pct = _PORCENTAJE_SOLO_NUM_RE.match(str_pct)
                if m_pct:
                    pct_val = _to_decimal_g(m_pct.group(1))
            else:
                pct_val = _to_decimal_g(str_pct)
        acum["facturada_soles"] = _round2_g(fs)
        acum["comision_soles"] = _round2_g(cs)
        acum["porcentaje_comision"] = _round2_g(pct_val)

        if acum["porcentaje_comision"] == 0 and acum["facturada_soles"] > 0 and acum["comision_soles"] > 0:
            acum["porcentaje_comision"] = _round2_g(acum["comision_soles"] * Decimal("100") / acum["facturada_soles"])
        if acum["comision_soles"] == 0 and acum["facturada_soles"] > 0:
            pct_apply = acum["porcentaje_comision"] if acum["porcentaje_comision"] > 0 else Decimal("25.00")
            acum["comision_soles"] = _round2_g(acum["facturada_soles"] * pct_apply / Decimal("100"))
            if acum["porcentaje_comision"] == 0:
                acum["porcentaje_comision"] = Decimal("25.00")

        for k in (
            "nro_contrato", "grupo_rmi", "contratante", "producto", "agente",
            "factura_movimiento", "fecha_disponible",
            "orden_comision", "estado_comision",
        ):
            acum[k] = re.sub(r"\s{2,}", " ", str(acum.get(k, "")).strip())
        # Normalizar fechas
        for k in ("fecha_emision", "fecha_disponible", "fecha_registro"):
            acum[k] = _normalizar_fecha(str(acum.get(k, "")))
        # Normalizar orden comisión (regex con minúsculas)
        if acum["orden_comision"]:
            odm = _NRO_DOC_RE_G.search(acum["orden_comision"])
            if odm:
                acum["orden_comision"] = re.sub(r"[()]+", "", odm.group(1)).strip("-")
        if acum["factura_movimiento"]:
            fm = _FACTURA_MOV_RE_G.search(acum["factura_movimiento"])
            if fm:
                acum["factura_movimiento"] = fm.group(1)

        if acum["facturada_soles"] == 0 and acum["comision_soles"] == 0:
            return
        if not acum["factura_movimiento"] and not acum["orden_comision"] and not acum["contratante"] and not acum["nro_contrato"]:
            return
        out.append(acum)

    for row in filas[header_row_idx + 1:]:
        if row is None:
            continue
        cells = ["" if c is None else str(c).replace("\n", " ").strip() for c in row]
        if all(not c for c in cells):
            continue
        joined = " ".join(cells).lower()
        if any(k in joined for k in ["liquidaci", "n° contrato", "contratante", "producto", "factura de", "orden comisi", "estado comisi", "fecha registro"]) and sum(1 for c in cells if c.strip()) > 4:
            continue
        if re.search(r"(totales?|total\s+(comision|general|facturado)|i\.?g\.?v\.?)", joined):
            continue
        if re.search(r"p[aá]gina\s+\d+\s+(de|/)\s+\d+", joined):
            continue
        if re.match(r"^(liquidaci|fecha de generaci|número de operaci|agente|código|moneda|ruc:|codigo|grandia|número ruc|código susalud|moneda)", joined):
            continue

        nueva: Dict[str, Any] = {
            "nro_orden": "", "nro_contrato": "", "grupo_rmi": "", "contratante": "",
            "producto": "", "agente": "", "factura_movimiento": "", "fecha_emision": "",
            "facturada_soles": Decimal("0"), "comision_soles": Decimal("0"),
            "porcentaje_comision": Decimal("0"), "fecha_disponible": "",
            "orden_comision": "", "estado_comision": "", "fecha_registro": "",
        }
        for campo, idx in mapa.items():
            if 0 <= idx < len(cells):
                valor = cells[idx]
                nueva[campo] = valor

        # Reforzar: backup por parser patrones
        backup = parsear_fila_grandia_por_patrones(cells)
        if backup:
            for k in (
                "nro_contrato", "grupo_rmi", "contratante", "producto", "agente",
                "factura_movimiento", "fecha_emision", "fecha_disponible",
                "orden_comision", "estado_comision", "fecha_registro",
            ):
                actual = str(nueva.get(k, "")).strip()
                if actual == "" or actual == "0":
                    relleno = str(backup.get(k, "")).strip()
                    if relleno and relleno != "0":
                        nueva[k] = relleno
            for k in ("facturada_soles", "porcentaje_comision", "comision_soles"):
                if _to_decimal_g(nueva.get(k)) == 0 and _to_decimal_g(backup.get(k)) > 0:
                    nueva[k] = backup[k]

        tiene_fecha = bool(str(nueva.get("fecha_emision", "")).strip() or str(nueva.get("fecha_registro", "")).strip())
        tiene_monto = _to_decimal_g(nueva.get("facturada_soles")) > 0 or _to_decimal_g(nueva.get("comision_soles")) > 0
        tiene_doc = bool(str(nueva.get("factura_movimiento", "")).strip() or str(nueva.get("orden_comision", "")).strip())

        if not tiene_fecha and not tiene_monto and not tiene_doc:
            if acumulada is not None:
                _mergear_texto(acumulada, nueva, ("contratante", "producto", "agente", "estado_comision"))
            continue
        if acumulada is not None and not tiene_monto and not tiene_fecha and not tiene_doc:
            _mergear_texto(acumulada, nueva, ("contratante", "producto", "agente", "estado_comision"))
            continue
        _commit(acumulada)
        acumulada = nueva
    _commit(acumulada)
    return out


# ============================================================
#   FALLBACK: extracción regex por coordenadas (legacy)
# ============================================================

def _extraer_grandia_por_patrones_page(page) -> List[Dict[str, Any]]:
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
                    and re.match(r"^[A-Za-z0-9]", nxt)
                    and not nxt.startswith("-")
                    and not (len(t) == 1 and t == "-" and re.match(r"^\d{8,}", nxt))
                ):
                    glued = t + nxt
                if glued is None and (t.startswith("(") and re.match(r"\d", t.lstrip("("))) and (nxt == "%)" or nxt == "%" or nxt == ")"):
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

        if header_y is None:
            if any(k in low for k in ("contratante", "factura de", "facturada", "comision", "orden comisi", "n° contrato")) and \
               any(k in low for k in ("producto", "agente", "emision", "%sión", "fecha", "disponible")):
                header_y = y_ref
                continue
        if header_y is None:
            continue
        if re.search(r"p[aá]gina\s+\d+\s+(de|/)\s+\d+", low):
            continue
        if re.match(r"^(liquidaci|fecha de generaci|número de operaci|agente|código|moneda|ruc:|codigo|grandia)", low):
            continue
        if re.search(r"(totales?|total\s+(comision|general|facturado)|i\.?g\.?v\.?)", low):
            continue
        if not re.search(r"[A-Za-z0-9]", texto):
            continue
        grupos_texto.append((y_ref, texto, tokens))

    salidas: List[Dict[str, Any]] = []
    ultima_con_doc: Optional[Tuple[float, Dict[str, Any]]] = None
    for y_ref, texto, tokens in grupos_texto:
        tiene_doc_here = bool(_FACTURA_MOV_RE_G.search(texto) or _NRO_DOC_RE_G.search(texto))
        tiene_monto_here = bool(_MONTO_RE_G.search(texto) or re.search(r"\b\d{1,3}\.\d{2}\b", texto))
        if not tiene_doc_here and not tiene_monto_here:
            es_garbage = True
            if len(tokens) >= 3:
                if any(k in texto for k in ("SCTR", "VIDA", "SALUD", "ARIAS", "GRANDIA", "EN LIQUIDACI", "F099-", "F001-")):
                    es_garbage = False
            if es_garbage:
                continue
        if not tiene_doc_here and ultima_con_doc is not None and abs(y_ref - ultima_con_doc[0]) <= 24.0:
            raw_prev = ultima_con_doc[1].get("_raw", texto)
            merged = raw_prev + " " + texto
            parsed = parsear_fila_grandia_por_patrones([merged])
            if parsed is not None:
                parsed["_raw"] = merged
                salidas[-1] = parsed
                ultima_con_doc = (y_ref, parsed)
                continue
        parsed = parsear_fila_grandia_por_patrones([texto])
        if parsed is None:
            continue
        parsed["_raw"] = texto
        salidas.append(parsed)
        if tiene_doc_here or tiene_monto_here:
            ultima_con_doc = (y_ref, parsed)
    clean = []
    for s in salidas:
        s.pop("_raw", None)
        clean.append(s)
    return clean


# ============================================================
#   PARSER POR PATRONES (REGEX) GRANDIA — FALLBACK
# ============================================================

def parsear_fila_grandia_por_patrones(celdas) -> Optional[Dict[str, Any]]:
    out: Dict[str, Any] = {
        "nro_orden": "", "nro_contrato": "", "grupo_rmi": "", "contratante": "",
        "producto": "", "agente": "", "factura_movimiento": "", "fecha_emision": "",
        "facturada_soles": Decimal("0"), "comision_soles": Decimal("0"),
        "porcentaje_comision": Decimal("0"), "fecha_disponible": "",
        "orden_comision": "", "estado_comision": "", "fecha_registro": "",
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

    # 1) FECHAS — con soporte YYYY-MM-DD
    fechas_encontradas: List[str] = []
    for fm in _FECHA_RE_G.finditer(texto_global):
        if fm.group(1):
            d, mo, a = fm.group(1), fm.group(2), fm.group(3)
            if len(a) == 2:
                a = "20" + a
            fechas_encontradas.append(f"{int(d):02d}/{int(mo):02d}/{a}")
        elif fm.group(4):
            y, mo, d = fm.group(4), fm.group(5), fm.group(6)
            fechas_encontradas.append(f"{int(d):02d}/{int(mo):02d}/{y}")
    if fechas_encontradas:
        if len(fechas_encontradas) >= 1:
            out["fecha_emision"] = fechas_encontradas[0]
        if len(fechas_encontradas) >= 3:
            out["fecha_disponible"] = fechas_encontradas[1]
            out["fecha_registro"] = fechas_encontradas[-1]
        elif len(fechas_encontradas) == 2:
            out["fecha_registro"] = fechas_encontradas[-1]

    # 2) PORCENTAJE: valor "25.00" sin %, detectar por TOKENS numéricos en rango 1-30
    #    Buscar tokens que sean exactamente "XX.XX" y estén entre 1 y 40
    pct_candidatos: List[Decimal] = []
    for tok in raw_tokens:
        m_pct = re.match(r"^\s*\(?\s*(\d{1,2}(?:\.\d{1,2})?)\s*%?\s*\)?\s*$", tok)
        if m_pct:
            try:
                v = Decimal(m_pct.group(1))
                if Decimal("1") <= v <= Decimal("50"):
                    pct_candidatos.append(v)
            except Exception:
                pass
    if pct_candidatos:
        # El porcentaje más frecuente (25% se repite en todas las filas)
        from collections import Counter
        cnt = Counter(pct_candidatos)
        out["porcentaje_comision"] = _round2_g(cnt.most_common(1)[0][0])

    # 3) MONTOS — todos los XX.XX de 2 decimales
    montos_todos: List[Decimal] = []
    spans_montos: List[Tuple[int, int, Decimal]] = []
    for m in _MONTO_RE_G.finditer(texto_global):
        try:
            v = _to_decimal_g(m.group(1))
            montos_todos.append(v)
            spans_montos.append((m.start(), m.end(), v))
        except Exception:
            pass
    # Añadir también montos detectados sin separador de miles
    for m in re.finditer(r"(?<!\d)(\d{2,5}\.\d{2})(?!\d)", texto_global):
        try:
            v = _to_decimal_g(m.group(1))
            if v not in montos_todos:
                montos_todos.append(v)
        except Exception:
            pass

    montos_unicos = list(dict.fromkeys(montos_todos))
    montos_desc = sorted(montos_unicos, reverse=True)

    # 4) Determinar Facturado, Comisión
    facturada = Decimal("0")
    comision = Decimal("0")
    # Heurística Grandia: 3 columnas numéricas = [Facturado, Porcentaje(25), Comisión]
    # La columna % es 25.00 siempre.
    if len(montos_desc) >= 3 and out["porcentaje_comision"] > 0:
        pct = out["porcentaje_comision"]
        # Quitar el porcentaje de la lista (valor 25.00)
        no_pct = [m for m in montos_desc if abs(float(m - pct)) > 0.05]
        if len(no_pct) >= 2:
            facturada = no_pct[0]
            comision = no_pct[1]
        elif len(no_pct) >= 1:
            facturada = no_pct[0]
    elif len(montos_desc) >= 2:
        pares = []
        for v_f in montos_desc:
            for v_c in montos_desc:
                if v_f == v_c:
                    continue
                if out["porcentaje_comision"] > 0:
                    esp = _round2_g(v_f * out["porcentaje_comision"] / Decimal("100"))
                    if abs(float(v_c - esp)) < 0.1:
                        pares.append((abs(float(v_c - esp)), v_f, v_c))
                if v_c <= v_f * Decimal("0.8") and v_c > 0:
                    pct_esp = v_c * Decimal("100") / v_f if v_f > 0 else Decimal("0")
                    if Decimal("15") <= pct_esp <= Decimal("40"):
                        pares.append((0.1, v_f, v_c))
        if pares:
            pares.sort(key=lambda x: x[0])
            _, facturada, comision = pares[0]
        else:
            facturada, comision = montos_desc[0], montos_desc[1]
    elif len(montos_desc) >= 1:
        facturada = montos_desc[0]

    if comision == 0 and facturada > 0:
        pct_def = out["porcentaje_comision"] if out["porcentaje_comision"] > 0 else Decimal("25.00")
        comision = _round2_g(facturada * pct_def / Decimal("100"))
        if out["porcentaje_comision"] == 0:
            out["porcentaje_comision"] = Decimal("25.00")
    if out["porcentaje_comision"] == 0 and facturada > 0 and comision > 0:
        out["porcentaje_comision"] = _round2_g(comision * Decimal("100") / facturada)

    out["facturada_soles"] = _round2_g(facturada)
    out["comision_soles"] = _round2_g(comision)

    # 5) FACTURA MOVIMIENTO (F099-XXXXXXX, F001-XXXXXXX)
    facturas_mov: List[str] = []
    for m in _FACTURA_MOV_RE_G.finditer(texto_global):
        n = m.group(1).strip("-")
        facturas_mov.append(n)
    fm_uniq = list(dict.fromkeys(facturas_mov))
    if fm_uniq:
        out["factura_movimiento"] = fm_uniq[0]

    # 6) N° CONTRATO
    contratos: List[str] = []
    for m in _CONTRATO_RE_G.finditer(texto_global):
        cn = m.group(1)
        fechas_ya = {out["fecha_emision"].replace("/", ""),
                    out["fecha_disponible"].replace("/", ""),
                    out["fecha_registro"].replace("/", "")}
        if cn in fechas_ya:
            continue
        ya_usado = False
        for sv in spans_montos:
            ss = f"{sv[2]:.2f}".replace(".", "")
            if cn in ss or ss.endswith(cn):
                ya_usado = True
                break
        if ya_usado:
            continue
        if len(cn) >= 6:
            contratos.append(cn)
    contratos_uniq = list(dict.fromkeys(contratos))
    # Quitar los que ya se usaron en factura movimiento
    if fm_uniq:
        fm_sin_guion = re.sub(r"\D", "", fm_uniq[0])
        limpio = []
        for c in contratos_uniq:
            if not c:
                continue
            if c == fm_sin_guion[-len(c):]:
                continue
            limpio.append(c)
        contratos_uniq = limpio
    if contratos_uniq:
        out["nro_contrato"] = contratos_uniq[0]

    # 7) ORDEN COMISIÓN — CON MINÚSCULAS (ej: 2337-LQ-092026ef2c)
    ordenes: List[str] = []
    for m in _NRO_DOC_RE_G.finditer(texto_global):
        n = re.sub(r"[()]+", "", m.group(1)).strip("-")
        if n == out["factura_movimiento"]:
            continue
        if n == out["nro_contrato"]:
            continue
        ordenes.append(n)
    ordenes_uniq = list(dict.fromkeys(ordenes))
    ordenes_priorizadas = sorted(ordenes_uniq, key=lambda n: (
        0 if ("LQ" in n.upper() or "lq" in n) else 1,
        -n.count("-"),
        -len(n),
    ))
    if ordenes_priorizadas:
        candidato = ordenes_priorizadas[0]
        if not out["factura_movimiento"] and re.match(r"^F\d", candidato.upper()):
            out["factura_movimiento"] = candidato
        else:
            out["orden_comision"] = candidato

    # 8) ESTADO COMISIÓN
    if "EN LIQUIDACION" in texto_global.upper() or "EN LIQUIDACI" in texto_global.upper():
        out["estado_comision"] = "EN LIQUIDACIÓN"
    elif re.search(r"PAGADO", texto_global.upper()):
        out["estado_comision"] = "PAGADO"
    elif re.search(r"PENDIENTE", texto_global.upper()):
        out["estado_comision"] = "PENDIENTE"

    # 9) PRODUCTO
    known = {"SCTR", "VIDA", "SALUD", "VEHICULOS", "SOAT", "HOGAR", "EMPRESARIAL", "SCTR SALUD", "SCTR VIDA"}
    p_tokens: List[str] = []
    for tok in raw_tokens:
        up = tok.upper().strip(".,-():;")
        if up in known:
            p_tokens.append(up)
    if p_tokens:
        out["producto"] = " ".join(list(dict.fromkeys(p_tokens)))
    elif "SCTR" in texto_global.upper():
        out["producto"] = "SCTR"

    # 10) AGENTE
    agente_match = re.search(
        r"(ARIAS\s*[&\s]\s*ARIAS\s+CORREDORES\s+DE\s+SEGUROS\s*S\.?A\.?C\.?)",
        texto_global,
        re.IGNORECASE,
    )
    if agente_match:
        out["agente"] = agente_match.group(1).upper().strip()

    # 11) CONTRATANTE
    blocked: set = set()
    for b in (
        out["fecha_emision"], out["fecha_disponible"], out["fecha_registro"],
        out["factura_movimiento"], out["orden_comision"], out["nro_contrato"],
        out["agente"], out["estado_comision"], out["producto"],
    ):
        if b:
            blocked.add(b)
            blocked.add(b.strip("-.,"))
    for _, _, v in spans_montos:
        blocked.add(f"{v:.2f}")
        blocked.add(f"{v:,.2f}")
        blocked.add(str(v))
    if out["porcentaje_comision"] > 0:
        blocked.add(f"{float(out['porcentaje_comision']):.2f}")
    blocked_low = {x.lower() for x in blocked if x}

    idx_agente_end = -1
    for i, tok in enumerate(raw_tokens):
        low = tok.lower().strip(".,-():;")
        if low == "agente" and idx_agente_end == -1:
            idx_agente_end = i + 5
            continue

    stop_low = {"calle", "urb", "urbanizacion", "av", "avenida", "jr", "jiron",
                "lima", "peru", "perú", "s.a.", "s.a", "sac", "eirl", "e.i.r.l.",
                "s.r.l.", "srl", "sa", "empresa", "individual", "responsabilidad", "limitada"}

    contratante_tokens: List[str] = []
    for i, tok in enumerate(raw_tokens):
        if not tok:
            continue
        ts = tok.strip(".,-–—/:;()%")
        tl = ts.lower()
        if not ts:
            continue
        if idx_agente_end > 0 and i <= idx_agente_end:
            continue
        if not re.search(r"[A-Za-zÑñÁÉÍÓÚáéíóú0-9&]", ts):
            continue
        if re.fullmatch(r"[0-9\(\)\.\%\,\ ]+", ts):
            continue
        if tl in blocked_low or ts in blocked:
            continue
        if any(u and len(u) >= 3 and u in tl for u in blocked_low):
            continue
        if tl in ("ruc", "dni", "nro", "s/", "$", "s", "por", "comision", "comisión", "factura", "%"):
            continue
        if tl in ("en", "liquidación", "liquidacion", "pagado", "pendiente", "orden", "emision", "emisió", "disponible", "registro", "contrato", "grupo", "rmi", "facturado", "soles", "movimiento"):
            continue
        if tl in stop_low and len(contratante_tokens) >= 3:
            contratante_tokens.append(ts)
            break
        contratante_tokens.append(ts)

    raw_cli = " ".join(contratante_tokens).strip(" .,-–—/:;()%")
    for doc_val in (out["factura_movimiento"], out["orden_comision"], out["nro_contrato"], out["agente"]):
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
    out["contratante"] = raw_cli

    if out["facturada_soles"] == 0 and out["comision_soles"] == 0:
        return None
    if not out["factura_movimiento"] and not out["orden_comision"] and not out["contratante"] and not out["nro_contrato"]:
        return None
    return out


# ============================================================
#   COMPONENTE TKINTER GRANDIA
# ============================================================

class TableroFacturacionGrandias(tk.Frame):
    COLUMNS = (
        ("nro_item",             "N°",                   55),
        ("nro_contrato",         "N° Contrato",          100),
        ("contratante",          "Contratante",          280),
        ("producto",             "Producto",              90),
        ("factura_movimiento",   "Factura Mov.",         130),
        ("fecha_emision",        "Emisión",              100),
        ("facturada_soles",      "Facturada S/.",        120, "moneda"),
        ("comision_soles",       "Comisión S/.",         120, "moneda"),
        ("porcentaje_comision",  "% Comisión",            95, "porcentaje"),
        ("orden_comision",       "Orden Comisión",       180),
        ("estado_comision",      "Estado Comisión",      120),
        ("fecha_registro",       "Fecha Registro",       110),
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

        self.lbl_estado = tk.Label(inner, text="Listo. Cargue un PDF de Grandia para empezar →",
                                   bg="#ffffff", fg="#64748b", font=("Segoe UI", 9), anchor="w")
        self.lbl_estado.pack(fill="x")

    def _crear_encabezado(self, parent):
        title_box = tk.Frame(parent, bg="#ffffff")
        title_box.pack(side="left")
        tk.Label(title_box, text="Liquidación de Comisiones — Grandia EPS",
                 bg="#ffffff", fg="#0f172a", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Extraiga datos desde el PDF de Liquidación de Grandia EPS. Columnas adaptadas al formato oficial.",
                 bg="#ffffff", fg="#64748b", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(parent, bg="#ffffff")
        btns.pack(side="right")
        self._mkbtn(btns, "Cargar PDF Grandia", "#2563eb", self._cargar_pdf).pack(side="left", padx=3)
        self._mkbtn(btns, "Validar BD", "#16a34a", self._validar_contra_bd).pack(side="left", padx=3)
        self._mkbtn(btns, "Nueva fila", "#0ea5e9", self._agregar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Eliminar fila", "#ef4444", self._eliminar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "Recalcular comisiones (25%)", "#0f766e", self._recalcular_comisiones_25).pack(side="left", padx=3)
        self._mkbtn(btns, "Limpiar todo", "#475569", self._limpiar).pack(side="left", padx=3)

    def _mkbtn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, bg=color, fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                         cursor="hand2", activebackground="#1e293b", activeforeground="#ffffff",
                         padx=12, pady=7, command=cmd)

    def _construir_totales(self, parent):
        cards = [
            ("Total Facturado S/.",        "facturado_total",  "#2563eb", "#eff6ff"),
            ("Total Comisión Broker",      "comision_total",   "#0891b2", "#ecfeff"),
            ("Base IGV (sólo comisión)",   "base_igv",         "#475569", "#f8fafc"),
            ("Total IGV (18%)",            "igv_total",        "#f59e0b", "#fffbeb"),
            ("Total a cobrar",             "total_cobrar",     "#16a34a", "#f0fdf4"),
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
            sv = tk.StringVar(value=f"{MONEDA_GRANDIA} 0.00")
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
            ("verde",    COLOR_VERDE,    "#166534", "Poliza + Factura"),
            ("amarillo", COLOR_AMARILLO, "#92400e", "Solo hay Poliza"),
            ("rojo",     COLOR_ROJO,     "#991b1b", "Sin Poliza ni Factura"),
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
            if cid == "nro_item":
                anchor = "center"
            elif align in ("moneda", "porcentaje", "e"):
                anchor = "e"
            else:
                anchor = "w"
            stretch = (cid == "contratante")
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
            title="Seleccionar PDF de Liquidación Grandia",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            filas = extraer_tablas_grandia(path)
        except Exception as e:
            messagebox.showerror("Error al leer PDF",
                                 f"No se pudo leer el PDF de Grandia.\n\n{str(e)}\n\n{traceback.format_exc(limit=1)}",
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

        self._renumerar()
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(
            text=f"Importado: {len(filas)} filas desde {os.path.basename(path)}  |  Total registros: {len(self._rows)}",
            fg="#059669")
        messagebox.showinfo(
            "PDF importado correctamente",
            f"Se insertaron {len(filas)} filas correctamente desde:\n"
            f"{os.path.basename(path)}\n\n"
            f"Total de registros en la tabla: {len(self._rows)}",
            parent=self,
        )

    def _agregar_fila(self):
        fila = {
            "nro_orden": "", "nro_contrato": "", "grupo_rmi": "", "contratante": "",
            "producto": "SCTR", "agente": "ARIAS & ARIAS CORREDORES DE SEGUROS S.A.C.",
            "factura_movimiento": "", "fecha_emision": "",
            "facturada_soles": Decimal("0"), "comision_soles": Decimal("0"),
            "porcentaje_comision": Decimal("25.00"), "fecha_disponible": "",
            "orden_comision": "", "estado_comision": "EN LIQUIDACIÓN", "fecha_registro": "",
        }
        self._append_row(fila)
        self._renumerar()
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    def _append_row(self, f: Dict[str, Any]):
        self._uid_counter += 1
        uid = f"r{self._uid_counter}"
        data = dict(f)
        data["facturada_soles"] = _round2_g(_to_decimal_g(data.get("facturada_soles")))
        data["comision_soles"] = _round2_g(_to_decimal_g(data.get("comision_soles")))
        data["porcentaje_comision"] = _round2_g(_to_decimal_g(data.get("porcentaje_comision")))
        self._rows.append(data)
        self.tree.insert("", "end", iid=uid, values=self._valores_tabla(data, len(self._rows)))

    def _renumerar(self):
        """
        Vuelve a asignar los valores de la columna N° (primera columna) en toda
        la tabla para que coincidan con el orden visual del Treeview (1..N).
        """
        iids = self.tree.get_children()
        for pos, iid in enumerate(iids, start=1):
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

    def _recalcular_comisiones_25(self):
        pct = Decimal("25.00")
        for i, row in enumerate(self._rows):
            md = _to_decimal_g(row.get("facturada_soles"))
            if md > 0:
                row["porcentaje_comision"] = pct
                row["comision_soles"] = _round2_g(md * pct / Decimal("100"))
                iid = self.tree.get_children()[i]
                self.tree.item(iid, values=self._valores_tabla(row))
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(text=f"Comisiones recalculadas al 25% sobre Facturado S/. ({len(self._rows)} filas).", fg="#0f766e")

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
                "nro_contrato": r.get("nro_contrato", ""),
                "factura_movimiento": r.get("factura_movimiento", ""),
                "contratante": r.get("contratante", ""),
                "producto": r.get("producto", "") or "Grandia EPS",
                "fecha": r.get("fecha_emision", "") or r.get("fecha_registro", ""),
                "monto_doc": _to_decimal_g(r.get("facturada_soles")),
                "monto_comision": _to_decimal_g(r.get("comision_soles")),
                "porcentaje_comision": _to_decimal_g(r.get("porcentaje_comision")),
            }
            filas_para_validar.append(r_norm)

        try:
            resultados, cant_existe, cant_no_existe = validar_filas_contra_grandias_bd(filas_para_validar)
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
            detalles_unicos.append(f"Verde (Poliza + Factura): {cant_verde}")
        if cant_amarillo > 0:
            detalles_unicos.append(f"Amarillo (Solo Poliza): {cant_amarillo}")
        if cant_rojo > 0:
            detalles_unicos.append(f"Rojo (Sin Poliza ni Factura): {cant_rojo}")
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
                f"Todas las {total} filas tienen Poliza y Factura en la BD.\n"
                "Todas las filas están en VERDE.",
                parent=self,
            )
        else:
            detalles_msg = []
            if cant_verde > 0:
                detalles_msg.append(f"🟢 VERDE (Poliza + Factura): {cant_verde}")
            if cant_amarillo > 0:
                detalles_msg.append(f"🟡 AMARILLO (Solo Poliza): {cant_amarillo}")
            if cant_rojo > 0:
                detalles_msg.append(f"🔴 ROJO (Sin Poliza ni Factura): {cant_rojo}")
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
            justify="right" if col_id in {"facturada_soles", "comision_soles", "porcentaje_comision"} else "left"
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
        if col_id in {"facturada_soles", "comision_soles", "porcentaje_comision"}:
            row[col_id] = _round2_g(_to_decimal_g(valor_nuevo))
        elif col_id.startswith("fecha_"):
            row[col_id] = _normalizar_fecha(valor_nuevo)
        elif col_id != "nro_item":
            row[col_id] = valor_nuevo
        self.tree.item(iid, values=self._valores_tabla(row, index + 1))
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    # --- Helpers
    def _valores_tabla(self, row: Dict[str, Any], nro_item: int = 0) -> Tuple[str, ...]:
        values: List[str] = []
        for item in self.COLUMNS:
            cid = item[0]
            tipo = item[3] if len(item) > 3 else "text"
            if cid == "nro_item":
                values.append(f"{int(nro_item)}")
                continue
            raw = row.get(cid, "")
            if tipo == "moneda":
                v = _to_decimal_g(raw)
                values.append(f"{MONEDA_GRANDIA} {self._fmt_money(v)}")
            elif tipo == "porcentaje":
                v = _to_decimal_g(raw)
                values.append(f"{_round2_g(v):.2f} %")
            else:
                values.append("" if raw is None else str(raw))
        return tuple(values)

    def _actualizar_totales(self):
        facturado_total = Decimal("0")
        comision_total = Decimal("0")
        for r in self._rows:
            facturado_total += _to_decimal_g(r.get("facturada_soles"))
            comision_total += _to_decimal_g(r.get("comision_soles"))
        facturado_total = _round2_g(facturado_total)
        comision_total = _round2_g(comision_total)
        base_igv = comision_total
        igv_total = _round2_g(base_igv * IGV_PORCENTAJE_G)
        total_cobrar = _round2_g(base_igv + igv_total)
        self._total_vars["facturado_total"].set(f"{MONEDA_GRANDIA} {self._fmt_money(facturado_total)}")
        self._total_vars["comision_total"].set(f"{MONEDA_GRANDIA} {self._fmt_money(comision_total)}")
        self._total_vars["base_igv"].set(f"{MONEDA_GRANDIA} {self._fmt_money(base_igv)}")
        self._total_vars["igv_total"].set(f"{MONEDA_GRANDIA} {self._fmt_money(igv_total)}")
        self._total_vars["total_cobrar"].set(f"{MONEDA_GRANDIA} {self._fmt_money(total_cobrar)}")

    def _fmt_money(self, v: Decimal) -> str:
        s = f"{_round2_g(v):,.2f}"
        return s.replace(",", "¤").replace(".", ",").replace("¤", ".")
