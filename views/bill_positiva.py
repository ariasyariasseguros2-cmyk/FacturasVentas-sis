import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from utils.validacion_bd import (
    validar_filas_contra_bd,
    COLOR_VERDE,
    COLOR_AMARILLO,
    COLOR_ROJO,
)


TWO_PLACES_P = Decimal("0.01")
IGV_PORCENTAJE_P = Decimal("0.18")
MONEDA_POSITIVA = "$"

_FECHA_RE_P = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b"
)
_DOC_RE_P = re.compile(r"\b[A-Z]{1,3}\d{6,}[A-Z0-9\-]*\b")
_MONTO_RE_P = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})(?!\d)")


def _to_decimal_p(val: Any) -> Decimal:
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
        return Decimal(m.group(0)).quantize(TWO_PLACES_P, rounding=ROUND_HALF_UP)
    except (InvalidOperation, Exception):
        return Decimal("0")


def _round2_p(v: Decimal) -> Decimal:
    if not isinstance(v, Decimal):
        v = _to_decimal_p(v)
    return v.quantize(TWO_PLACES_P, rounding=ROUND_HALF_UP)


def _normalizar_fecha_p(valor: str) -> str:
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


def _simplificar_texto(texto: str) -> str:
    s = (texto or "").strip().lower()
    tabla = str.maketrans(
        {
            "a": "a",
            "e": "e",
            "i": "i",
            "o": "o",
            "u": "u",
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u",
            "ñ": "n",
        }
    )
    s = s.translate(tabla)
    s = re.sub(r"\s{2,}", " ", s)
    return s


def _norm_token(token: str) -> str:
    s = _simplificar_texto(token)
    return re.sub(r"[^a-z0-9%]+", "", s)


def _agrupar_palabras_por_fila(palabras, tolerancia_y: float = 4.5):
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


def _texto_fila(palabras_fila) -> str:
    return " ".join(str(p["text"]).strip() for p in palabras_fila if str(p["text"]).strip())


def _contar_hits_header(texto: str) -> int:
    s = _simplificar_texto(texto)
    claves = ("ramo", "poliza", "doc", "fecha", "descripcion", "p.neta", "%com", "comision", "dscto")
    return sum(1 for clave in claves if clave in s)


def _mapear_header_desde_fila(palabras_fila) -> Optional[List[Tuple[str, float]]]:
    tokens = [_norm_token(p["text"]) for p in palabras_fila]
    campos: List[Tuple[str, float]] = []
    i = 0
    while i < len(palabras_fila):
        tok = tokens[i]
        campo = None
        if tok == "ramo":
            campo = "ramo"
        elif tok.startswith("poliza"):
            campo = "poliza"
        elif tok == "doc" or tok.startswith("doc"):
            campo = "documento"
        elif tok.startswith("fecha"):
            campo = "fecha"
        elif tok.startswith("descrip"):
            campo = "descripcion"
        elif tok == "pneta" or (tok == "p" and i + 1 < len(tokens) and tokens[i + 1] == "neta"):
            campo = "prima_neta"
        elif tok.startswith("%com") or (tok == "%" and i + 1 < len(tokens) and tokens[i + 1].startswith("com")):
            campo = "porcentaje_comision"
        elif tok.startswith("comision"):
            campo = "comision"
        elif tok.startswith("dscto") or tok.startswith("dcto"):
            campo = "descuento"

        if campo:
            cx = (palabras_fila[i]["x0"] + palabras_fila[i]["x1"]) / 2
            campos.append((campo, cx))
        i += 1

    dedup: Dict[str, float] = {}
    for campo, centro in campos:
        if campo not in dedup:
            dedup[campo] = centro
    ordenados = sorted(dedup.items(), key=lambda item: item[1])
    if len(ordenados) >= 7 and "descripcion" in dedup and "comision" in dedup:
        return ordenados
    return None


def _rangos_desde_header(campos_header: List[Tuple[str, float]]) -> List[Tuple[str, float, float]]:
    rangos: List[Tuple[str, float, float]] = []
    for idx, (campo, centro) in enumerate(campos_header):
        if idx == 0:
            izquierda = centro - 70
        else:
            izquierda = (campos_header[idx - 1][1] + centro) / 2
        if idx + 1 < len(campos_header):
            derecha = (centro + campos_header[idx + 1][1]) / 2
        else:
            derecha = centro + 90
        rangos.append((campo, izquierda, derecha))
    return rangos


def _campo_por_x(x: float, rangos: List[Tuple[str, float, float]]) -> str:
    for campo, izquierda, derecha in rangos:
        if izquierda <= x < derecha:
            return campo
    if rangos:
        return rangos[-1][0]
    return ""


def _es_meta_positiva(texto: str) -> bool:
    s = _simplificar_texto(texto)
    if not s:
        return True
    patrones = (
        "la positiva",
        "boleta de liquidacion",
        "boleta ",
        "oficina",
        "broker",
        "igv",
        "moneda",
        "ruc",
        "direccion",
        "responsable",
    )
    return any(p in s for p in patrones)


def _es_total_positiva(texto: str) -> bool:
    s = _simplificar_texto(texto)
    return "total oficina" in s or s.startswith("total ")


def _es_oficina_positiva(texto: str) -> bool:
    bruto = (texto or "").strip()
    if not bruto:
        return False
    s = _simplificar_texto(bruto)
    if _contar_hits_header(s) >= 3 or _es_meta_positiva(s) or _es_total_positiva(s):
        return False
    if any(ch.isdigit() for ch in bruto):
        return False
    if len(bruto.split()) > 4:
        return False
    limpio = re.sub(r"[^A-Za-z/\-\s]", "", bruto).strip()
    if not limpio:
        return False
    return bruto.upper() == bruto


def _parsear_fila_asignada(campos: Dict[str, str], oficina_actual: str) -> Optional[Dict[str, Any]]:
    descripcion = re.sub(r"\s{2,}", " ", campos.get("descripcion", "").strip())
    fila = {
        "oficina": oficina_actual,
        "ramo": campos.get("ramo", "").strip(),
        "poliza": fields_poliza if (fields_poliza := campos.get("poliza", "").strip()) else "",
        "documento": fields_doc if (fields_doc := campos.get("documento", "").strip()) else "",
        "fecha": _normalizar_fecha_p(campos.get("fecha", "").strip()),
        "descripcion": descripcion,
        "prima_neta": _round2_p(_to_decimal_p(campos.get("prima_neta", "0"))),
        "porcentaje_comision": _round2_p(_to_decimal_p(campos.get("porcentaje_comision", "0"))),
        "comision": _round2_p(_to_decimal_p(campos.get("comision", "0"))),
        "descuento": _round2_p(_to_decimal_p(campos.get("descuento", "0"))),
    }

    if not fila["fecha"]:
        m_fecha = _FECHA_RE_P.search(" ".join(campos.values()))
        if m_fecha:
            fila["fecha"] = _normalizar_fecha_p(m_fecha.group(0))
    if not fila["documento"]:
        m_doc = _DOC_RE_P.search(" ".join(campos.values()))
        if m_doc:
            fila["documento"] = m_doc.group(0)

    if fila["comision"] == 0 and fila["prima_neta"] > 0 and fila["porcentaje_comision"] > 0:
        fila["comision"] = _round2_p(
            fila["prima_neta"] * fila["porcentaje_comision"] / Decimal("100")
        )

    if fila["prima_neta"] == 0 and fila["comision"] == 0:
        return None
    if not fila["poliza"] and not fila["documento"] and not fila["descripcion"]:
        return None
    return fila


def _extraer_por_xranges_positiva(page) -> List[Dict[str, Any]]:
    palabras = page.extract_words(keep_blank_chars=False, x_tolerance=2, y_tolerance=3)
    if not palabras:
        return []

    filas = _agrupar_palabras_por_fila(palabras)
    resultados: List[Dict[str, Any]] = []
    oficina_actual = ""
    header_rangos: List[Tuple[str, float, float]] = []
    ultima_fila: Optional[Dict[str, Any]] = None

    for _, palabras_fila in filas:
        texto = _texto_fila(palabras_fila).strip()
        if not texto:
            continue

        if _es_oficina_positiva(texto):
            oficina_actual = re.sub(r"\s{2,}", " ", texto).strip()
            continue

        if _contar_hits_header(texto) >= 5:
            campos_header = _mapear_header_desde_fila(palabras_fila)
            if campos_header:
                header_rangos = _rangos_desde_header(campos_header)
            continue

        if not header_rangos:
            continue

        if _es_meta_positiva(texto) or _es_total_positiva(texto):
            continue

        celdas: Dict[str, List[str]] = {}
        for palabra in palabras_fila:
            token = str(palabra["text"]).strip()
            if not token:
                continue
            cx = (palabra["x0"] + palabra["x1"]) / 2
            campo = _campo_por_x(cx, header_rangos)
            if not campo:
                continue
            celdas.setdefault(campo, []).append(token)

        if not celdas:
            continue

        campos = {campo: " ".join(tokens).strip() for campo, tokens in celdas.items()}
        fila = _parsear_fila_asignada(campos, oficina_actual)
        if fila:
            resultados.append(fila)
            ultima_fila = fila
            continue

        texto_restante = re.sub(r"\s{2,}", " ", texto).strip()
        if (
            ultima_fila is not None
            and texto_restante
            and not _MONTO_RE_P.search(texto_restante)
            and not _FECHA_RE_P.search(texto_restante)
        ):
            descripcion_actual = ultima_fila.get("descripcion", "").strip()
            if texto_restante not in descripcion_actual:
                ultima_fila["descripcion"] = (descripcion_actual + " " + texto_restante).strip()

    return resultados


def _detectar_columnas_tabla_positiva(fila_encabezado) -> Optional[Dict[str, int]]:
    if not fila_encabezado:
        return None
    mapa: Dict[str, int] = {}
    for idx, celda in enumerate(fila_encabezado):
        s = _simplificar_texto("" if celda is None else str(celda).replace("\n", " ").strip())
        if "ramo" in s:
            mapa.setdefault("ramo", idx)
        elif "poliza" in s:
            mapa.setdefault("poliza", idx)
        elif s.startswith("doc"):
            mapa.setdefault("documento", idx)
        elif "fecha" in s:
            mapa.setdefault("fecha", idx)
        elif "descripcion" in s:
            mapa.setdefault("descripcion", idx)
        elif "p.neta" in s or "pneta" in s:
            mapa.setdefault("prima_neta", idx)
        elif "%com" in s:
            mapa.setdefault("porcentaje_comision", idx)
        elif "comision" in s:
            mapa.setdefault("comision", idx)
        elif "dscto" in s or "dcto" in s:
            mapa.setdefault("descuento", idx)
    if len(mapa) >= 7 and "descripcion" in mapa and "comision" in mapa:
        return mapa
    return None


def _procesar_tabla_positiva(tabla) -> List[Dict[str, Any]]:
    if not tabla:
        return []
    filas = list(tabla)
    header_idx = None
    mapa = None
    oficina_actual = ""
    for idx, fila in enumerate(filas[:6]):
        joined = " ".join("" if c is None else str(c) for c in fila)
        if _es_oficina_positiva(joined):
            oficina_actual = joined.strip()
        posible = _detectar_columnas_tabla_positiva(fila)
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
        if not joined:
            continue
        if _es_oficina_positiva(joined):
            oficina_actual = joined
            continue
        if _es_meta_positiva(joined) or _es_total_positiva(joined):
            continue

        campos = {
            campo: celdas[idx_celda] if idx_celda < len(celdas) else ""
            for campo, idx_celda in mapa.items()
        }
        fila_parseada = _parsear_fila_asignada(campos, oficina_actual)
        if fila_parseada:
            resultados.append(fila_parseada)
    return resultados


def extraer_tablas_positiva(pdf_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except Exception:
        raise RuntimeError("Se requiere la libreria 'pdfplumber' para extraer datos del PDF.")

    filas: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_filas = _extraer_por_xranges_positiva(page)
            if page_filas:
                filas.extend(page_filas)
                continue

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
                page_filas = _procesar_tabla_positiva(tabla)
                if page_filas:
                    filas.extend(page_filas)
                    break

    return filas


class TableroFacturacionPositiva(tk.Frame):
    COLUMNS = (
        ("nro_item", "N°", 55),
        ("oficina", "Oficina", 130),
        ("ramo", "Ramo", 170),
        ("poliza", "Poliza", 105),
        ("documento", "Doc.", 135),
        ("fecha", "Fecha", 100),
        ("descripcion", "Descripcion", 320),
        ("prima_neta", "P.Neta", 110, "moneda"),
        ("porcentaje_comision", "% Com.", 90, "porcentaje"),
        ("comision", "Comision", 110, "moneda"),
        ("descuento", "Dscto.", 95, "moneda"),
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
            text="Listo. Cargue un PDF de La Positiva para empezar ->",
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
            text="Boleta de Liquidacion de Comisiones - La Positiva",
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="Extraiga datos desde el PDF de La Positiva. Se mantiene oficina, poliza, documento, descripcion y valores.",
            bg="#ffffff",
            fg="#64748b",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(parent, bg="#ffffff")
        btns.pack(side="right")
        self._mkbtn(btns, "Cargar PDF Positiva", "#2563eb", self._cargar_pdf).pack(side="left", padx=3)
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
            sv = tk.StringVar(value=f"{MONEDA_POSITIVA} 0.00")
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
            stretch = cid in {"descripcion"}
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

    def _cargar_pdf(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar PDF de La Positiva",
            filetypes=[("Archivos PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            filas = extraer_tablas_positiva(path)
        except Exception as e:
            messagebox.showerror(
                "Error al leer PDF",
                f"No se pudo leer el PDF de La Positiva.\n\n{str(e)}\n\n{traceback.format_exc(limit=1)}",
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
            "oficina": "",
            "ramo": "",
            "poliza": "",
            "documento": "",
            "fecha": "",
            "descripcion": "",
            "prima_neta": Decimal("0"),
            "porcentaje_comision": Decimal("0"),
            "comision": Decimal("0"),
            "descuento": Decimal("0"),
        }
        self._append_row(fila)
        self._renumerar()
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

    def _append_row(self, fila: Dict[str, Any]):
        self._uid_counter += 1
        uid = f"r{self._uid_counter}"
        data = dict(fila)
        data["prima_neta"] = _round2_p(_to_decimal_p(data.get("prima_neta")))
        data["porcentaje_comision"] = _round2_p(_to_decimal_p(data.get("porcentaje_comision")))
        data["comision"] = _round2_p(_to_decimal_p(data.get("comision")))
        data["descuento"] = _round2_p(_to_decimal_p(data.get("descuento")))
        data["fecha"] = _normalizar_fecha_p(str(data.get("fecha", "")))
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
            prima = _to_decimal_p(row.get("prima_neta"))
            pct = _to_decimal_p(row.get("porcentaje_comision"))
            if prima > 0 and pct > 0:
                row["comision"] = _round2_p(prima * pct / Decimal("100"))
                iid = self.tree.get_children()[i]
                self.tree.item(iid, values=self._valores_tabla(row, i + 1))
                actualizadas += 1
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()
        self.lbl_estado.configure(
            text=f"Comision recalculada en {actualizadas} fila(s) usando Prima Neta y % Com.",
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
                    "fecha": r.get("fecha", ""),
                    "tipo_doc": r.get("ramo", "") or "COMI",
                    "nro_documento": r.get("poliza", ""),
                    "doc_legal": r.get("documento", ""),
                    "monto_doc": _to_decimal_p(r.get("prima_neta")),
                    "monto_comision": _to_decimal_p(r.get("comision")),
                    "porcentaje_comision": _to_decimal_p(r.get("porcentaje_comision")),
                    "identificacion": "",
                    "cliente": r.get("descripcion", ""),
                }
            )

        try:
            resultados, _, _ = validar_filas_contra_bd(filas_para_validar)
        except Exception as e:
            messagebox.showerror(
                "Error de validacion",
                f"Ocurrio un error al validar contra la BD:\n\n{str(e)}\n\n{traceback.format_exc(limit=2)}",
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
        detalles = []
        if cant_verde > 0:
            detalles.append(f"Verde (Poliza + Factura): {cant_verde}")
        if cant_amarillo > 0:
            detalles.append(f"Amarillo (Solo Poliza): {cant_amarillo}")
        if cant_rojo > 0:
            detalles.append(f"Rojo (Sin Poliza ni Factura): {cant_rojo}")
        resumen = "  |  ".join(detalles)

        if cant_rojo == 0 and cant_amarillo == 0:
            fg_estado = "#0f766e"
        elif cant_rojo > 0:
            fg_estado = "#dc2626"
        else:
            fg_estado = "#b45309"

        self.lbl_estado.configure(
            text=f"Validacion completada - {total} filas  |  {resumen}",
            fg=fg_estado,
        )

        if cant_rojo == 0 and cant_amarillo == 0:
            messagebox.showinfo(
                "Validacion exitosa",
                f"Todas las {total} filas tienen Poliza y Factura en la BD.\nTodas las filas estan en VERDE.",
                parent=self,
            )
        else:
            detalles_msg = []
            if cant_verde > 0:
                detalles_msg.append(f"VERDE (Poliza + Factura): {cant_verde}")
            if cant_amarillo > 0:
                detalles_msg.append(f"AMARILLO (Solo Poliza): {cant_amarillo}")
            if cant_rojo > 0:
                detalles_msg.append(f"ROJO (Sin Poliza ni Factura): {cant_rojo}")
            messagebox.showwarning(
                "Validacion con inconsistencias",
                "Resultado de la validacion:\n\n" + "\n".join(detalles_msg),
                parent=self,
            )

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
            justify="right" if col_id in {"prima_neta", "porcentaje_comision", "comision", "descuento"} else "left",
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
        editor, iid, _, col_id = self._editor
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
        if col_id in {"prima_neta", "porcentaje_comision", "comision", "descuento"}:
            row[col_id] = _round2_p(_to_decimal_p(valor_nuevo))
        elif col_id == "fecha":
            row[col_id] = _normalizar_fecha_p(valor_nuevo)
        elif col_id != "nro_item":
            row[col_id] = valor_nuevo
        self.tree.item(iid, values=self._valores_tabla(row, index + 1))
        self._actualizar_leyenda_conteos(0, 0, 0)
        self._actualizar_totales()

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
                values.append(f"{MONEDA_POSITIVA} {self._fmt_money(_to_decimal_p(raw))}")
            elif tipo == "porcentaje":
                values.append(f"{_round2_p(_to_decimal_p(raw)):.2f} %")
            else:
                values.append("" if raw is None else str(raw))
        return tuple(values)

    def _actualizar_totales(self):
        prima_total = Decimal("0")
        comision_total = Decimal("0")
        for r in self._rows:
            prima_total += _to_decimal_p(r.get("prima_neta"))
            comision_total += _to_decimal_p(r.get("comision"))
        prima_total = _round2_p(prima_total)
        comision_total = _round2_p(comision_total)
        base_igv = comision_total
        igv_total = _round2_p(base_igv * IGV_PORCENTAJE_P)
        total_cobrar = _round2_p(base_igv + igv_total)
        self._total_vars["prima_total"].set(f"{MONEDA_POSITIVA} {self._fmt_money(prima_total)}")
        self._total_vars["comision_total"].set(f"{MONEDA_POSITIVA} {self._fmt_money(comision_total)}")
        self._total_vars["base_igv"].set(f"{MONEDA_POSITIVA} {self._fmt_money(base_igv)}")
        self._total_vars["igv_total"].set(f"{MONEDA_POSITIVA} {self._fmt_money(igv_total)}")
        self._total_vars["total_cobrar"].set(f"{MONEDA_POSITIVA} {self._fmt_money(total_cobrar)}")

    def _fmt_money(self, v: Decimal) -> str:
        s = f"{_round2_p(v):,.2f}"
        return s
