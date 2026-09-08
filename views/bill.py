import os
import re
import traceback
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


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
        s = s.replace("S/", "").replace("S/.", "").replace("$", "").replace(",", "")
        s = s.replace("%", "").strip()
        return Decimal(s).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, Exception):
        return Decimal("0")


def _round2(v: Decimal) -> Decimal:
    if not isinstance(v, Decimal):
        v = _to_decimal(v)
    return v.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def extraer_tablas_sanitas(pdf_path: str) -> List[Dict[str, Any]]:
    try:
        import pdfplumber
    except Exception:
        raise RuntimeError("Se requiere la librería 'pdfplumber' para extraer datos del PDF.")

    filas: List[Dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                t = page.extract_table(table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "join_tolerance": 3,
                    "edge_min_length": 3,
                })
            except Exception:
                t = None
            if t:
                for row in t:
                    if row is None:
                        continue
                    cells = ["" if c is None else str(c).strip() for c in row]
                    if len(cells) < 5:
                        continue
                    if _es_encabezado(cells):
                        continue
                    if _es_total(cells):
                        continue
                    parsed = _parsear_fila(cells)
                    if parsed:
                        filas.append(parsed)
                continue

            try:
                t2 = page.extract_table(table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "intersection_tolerance": 6,
                })
            except Exception:
                t2 = None
            if t2:
                for row in t2:
                    if row is None:
                        continue
                    cells = ["" if c is None else str(c).strip() for c in row]
                    if len(cells) < 5:
                        continue
                    if _es_encabezado(cells):
                        continue
                    if _es_total(cells):
                        continue
                    parsed = _parsear_fila(cells)
                    if parsed:
                        filas.append(parsed)
    return filas


def _es_encabezado(cells: List[str]) -> bool:
    joined = " ".join(cells).lower()
    return any(k in joined for k in ("fecha inicio", "nro. documento", "monto doc", "comision broker", "tipo de documento", "documento", "cliente"))


def _es_total(cells: List[str]) -> bool:
    joined = " ".join(cells).lower()
    if "totales" in joined or "total sin impuestos" in joined or "total igv" in joined or "total a cobrar" in joined:
        return True
    return False


_FECHA_RE = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b")
_MONTO_RE = re.compile(r"(?<!\d)\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?(?!\d)")
_PORCENTAJE_RE = re.compile(r"\(([0-9]{1,3}(?:\.\d{1,2})?)\s*%\)")


def _parsear_fila(cells: List[str]) -> Optional[Dict[str, Any]]:
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

    remaining = [c for c in cells]

    fecha_candidata = ""
    for c in cells:
        m = _FECHA_RE.search(c)
        if m:
            d, mo, a = m.group(1), m.group(2), m.group(3)
            if len(a) == 2:
                a = "20" + a
            fecha_candidata = f"{int(d):02d}/{int(mo):02d}/{a}"
            break
    out["fecha"] = fecha_candidata
    remaining = [c for c in remaining if _FECHA_RE.search(c) is None]

    montos: List[Decimal] = []
    porc: Decimal = Decimal("0")
    for c in cells:
        mm = _MONTO_RE.findall(c)
        for m in mm:
            try:
                montos.append(_to_decimal(m))
            except Exception:
                pass
        pm = _PORCENTAJE_RE.search(c)
        if pm:
            try:
                porc = Decimal(pm.group(1))
            except Exception:
                pass

    documentos_so = []
    for c in cells:
        for m in re.findall(r"[A-Z]{2}-[A-Z]{2,6}-[A-Z0-9]{6,}", c):
            documentos_so.append(m)
        for m in re.findall(r"\bF\d{3}-[A-Z0-9\-]{5,}\b", c):
            documentos_so.append(m)
    if documentos_so:
        out["nro_documento"] = documentos_so[0]
        if len(documentos_so) > 1:
            out["doc_legal"] = documentos_so[1]

    montos_sorted = sorted(set(montos), reverse=True)
    if porc > 0 and len(montos_sorted) >= 2:
        md = montos_sorted[0]
        esperado = _round2(md * (porc / Decimal("100")))
        match = None
        for m in montos_sorted[1:]:
            if abs(float(m) - float(esperado)) < 0.02:
                match = m
                break
        if match is not None:
            out["monto_doc"] = md
            out["monto_comision"] = match
            out["porcentaje_comision"] = porc
            montos_sorted = [x for x in montos_sorted if x != md and x != match]
        else:
            if len(montos_sorted) >= 2:
                out["monto_doc"] = montos_sorted[0]
                out["monto_comision"] = montos_sorted[1]
                out["porcentaje_comision"] = porc
                montos_sorted = montos_sorted[2:]
            elif len(montos_sorted) == 1:
                out["monto_doc"] = montos_sorted[0]
    else:
        if len(montos_sorted) >= 2:
            out["monto_doc"] = montos_sorted[0]
            out["monto_comision"] = montos_sorted[1]
            montos_sorted = montos_sorted[2:]
        elif len(montos_sorted) == 1:
            out["monto_doc"] = montos_sorted[0]
        if porc > 0:
            out["porcentaje_comision"] = porc

    rucs = []
    for c in cells:
        for m in re.findall(r"\b\d{11}\b", c):
            rucs.append(m)
        for m in re.findall(r"\b\d{8}\b", c):
            rucs.append(m)
    if rucs:
        out["identificacion"] = rucs[0]

    # Tipo documento: tokens que contengan 'Proforma', 'Sanitas', etc.
    tipo_tokens = []
    for c in cells:
        if not c:
            continue
        low = c.lower()
        if low in (fecha_candidata, out["nro_documento"], out["doc_legal"]):
            continue
        if any(k in low for k in ("proforma", "factura", "boleta", "nota", "sanitas", "eps")):
            tipo_tokens.append(c)
    if tipo_tokens:
        out["tipo_doc"] = " ".join(tipo_tokens).strip()

    # Cliente: la última celda no-vacía que no coincida con campos ya detectados
    usadas = {
        fecha_candidata.lower() if fecha_candidata else "",
        out["nro_documento"].lower(),
        out["doc_legal"].lower(),
    }
    usadas.update({str(x) for x in (out["monto_doc"], out["monto_comision"], out["porcentaje_comision"])})
    usadas.update({x.lower() for x in rucs})
    usadas.update({"", "%"})
    rem = [c for c in cells if c and c.lower() not in usadas and not _MONTO_RE.fullmatch(c.replace(",", ""))]
    if rem:
        candidato_cliente = []
        for c in rem:
            low = c.lower()
            if low == out["tipo_doc"].lower():
                continue
            if "%" in low and any(x.isdigit() for x in low):
                continue
            if _FECHA_RE.search(c):
                continue
            if re.fullmatch(r"[A-Z]{2}-[A-Z]{2,6}-[A-Z0-9]{6,}", c):
                continue
            candidato_cliente.append(c)
        if candidato_cliente:
            out["cliente"] = " ".join(candidato_cliente).strip()

    if not out["doc_legal"] and len(documentos_so) > 1:
        out["doc_legal"] = documentos_so[1]

    if not out["cliente"] and out["identificacion"]:
        out["cliente"] = ""

    if out["monto_doc"] == 0 and out["monto_comision"] == 0 and not out["nro_documento"] and not out["cliente"]:
        return None

    return out


class TableroFacturacion(tk.Frame):
    COLUMNS = (
        ("fecha", "Fecha Inicio", 90),
        ("tipo_doc", "Tipo de Documento", 170),
        ("nro_documento", "Nro. Documento", 160),
        ("doc_legal", "Doc. Legal", 130),
        ("monto_doc", f"Monto Doc. s/imp.", 125, "moneda"),
        ("monto_comision", f"Monto Comisión Broker", 140, "moneda"),
        ("porcentaje_comision", "% Comisión", 85, "porcentaje"),
        ("identificacion", "Nro de Identificación", 150),
        ("cliente", "Cliente", 240),
    )

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._editor: Optional[Tuple[ttk.Entry, str, int, str]] = None
        self._rows: List[Dict[str, Any]] = []
        self._uid_counter = 0
        self.configure(bg="#f1f5f9")
        self._construir()

    # --- Construcción UI
    def _construir(self):
        wrap = tk.Frame(self, bg="#ffffff", highlightbackground="#e2e8f0", highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=2, pady=2)

        inner = tk.Frame(wrap, bg="#ffffff")
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        # Barra superior
        header = tk.Frame(inner, bg="#ffffff")
        header.pack(fill="x")

        self._crear_encabezado(header)

        # Totales (resumen superior para que sea visible rapido)
        tot_row = tk.Frame(inner, bg="#ffffff")
        tot_row.pack(fill="x", pady=(12, 10))
        self._construir_totales(tot_row)

        # Tabla
        t_frame = tk.Frame(inner, bg="#ffffff")
        t_frame.pack(fill="both", expand=True, pady=(0, 8))
        self._construir_tabla(t_frame)

        # Pie
        self.lbl_estado = tk.Label(inner, text="Listo. Cargue un PDF para empezar →",
                                   bg="#ffffff", fg="#64748b", font=("Segoe UI", 9), anchor="w")
        self.lbl_estado.pack(fill="x")

    def _crear_encabezado(self, parent: tk.Frame):
        title_box = tk.Frame(parent, bg="#ffffff")
        title_box.pack(side="left")
        tk.Label(title_box, text="🧾  Gestión de Comisiones — Facturas",
                 bg="#ffffff", fg="#0f172a", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Extraiga datos desde el PDF de Sanitas. Los valores se pueden editar.",
                 bg="#ffffff", fg="#64748b", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(parent, bg="#ffffff")
        btns.pack(side="right")

        self._mkbtn(btns, "📂  Cargar PDF", "#2563eb", self._cargar_pdf).pack(side="left", padx=3)
        self._mkbtn(btns, "➕  Nueva fila", "#0ea5e9", self._agregar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "🗑️  Eliminar fila", "#ef4444", self._eliminar_fila).pack(side="left", padx=3)
        self._mkbtn(btns, "🔄  Recalcular comisiones (23%)", "#0f766e", self._recalcular_comisiones_23).pack(side="left", padx=3)
        self._mkbtn(btns, "🧹  Limpiar todo", "#475569", self._limpiar).pack(side="left", padx=3)

    def _mkbtn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, bg=color, fg="#ffffff",
                         font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                         cursor="hand2", activebackground="#1e293b", activeforeground="#ffffff",
                         padx=12, pady=7, command=cmd)

    def _construir_totales(self, parent: tk.Frame):
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

    def _construir_tabla(self, parent: tk.Frame):
        tv_frame = tk.Frame(parent, bg="#ffffff")
        tv_frame.pack(fill="both", expand=True)

        cols = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(tv_frame, columns=cols, show="headings", selectmode="browse", height=18)

        for item in self.COLUMNS:
            cid = item[0]
            text = item[1]
            width = item[2]
            align = "e" if len(item) > 3 else "w"
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=width, anchor=("e" if align == "moneda" or align == "e" else "w"), stretch=False if cid != "cliente" else True)

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
            messagebox.showerror("Error al leer PDF", f"No se pudo leer el PDF.\n\n{str(e)}\n\n{traceback.format_exc(limit=1)}", parent=self)
            return

        if not filas:
            messagebox.showwarning("Sin datos",
                                   "El PDF se leyó pero no se detectaron filas de detalle.\n"
                                   "Puede agregar filas manualmente con ➕  Nueva fila.",
                                   parent=self)
            self._actualizar_totales()
            return

        for f in filas:
            self._append_row(f)

        self._actualizar_totales()
        self.lbl_estado.configure(text=f"✅ Importado: {len(filas)} filas desde {os.path.basename(path)}  |  Total registros en tabla: {len(self._rows)}",
                                  fg="#059669")

    def _agregar_fila(self):
        fila = {
            "fecha": "",
            "tipo_doc": "Proforma - Sanitas Perú S.A.",
            "nro_documento": "",
            "doc_legal": "",
            "monto_doc": Decimal("0"),
            "monto_comision": Decimal("0"),
            "porcentaje_comision": Decimal("23.00"),
            "identificacion": "",
            "cliente": "",
        }
        self._append_row(fila)
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
        if not messagebox.askyesno("Eliminar fila", f"¿Seguro que desea eliminar {len(sel)} fila(s) seleccionada(s)?", parent=self):
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
        self._actualizar_totales()

    def _limpiar(self):
        if not self._rows:
            return
        if not messagebox.askyesno("Limpiar", "¿Borrar todos los registros de la tabla?", parent=self):
            return
        for iid in list(self.tree.get_children()):
            self.tree.delete(iid)
        self._rows.clear()
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
        self._actualizar_totales()
        self.lbl_estado.configure(text=f"✅ Comisiones recalculadas al 23% sobre Monto Doc. para {len(self._rows)} filas.", fg="#0f766e")

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
        editor.configure(background="#fef9c3", foreground="#0f172a",
                         justify="right" if col_id in {"monto_doc", "monto_comision", "porcentaje_comision"} else "left")
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
        self._actualizar_totales()

    # --- Helper datos
    def _valores_tabla(self, row: Dict[str, Any]) -> Tuple[str, ...]:
        values: List[str] = []
        for item in self.COLUMNS:
            cid = item[0]
            tipo = item[3] if len(item) > 3 else "text"
            raw = row.get(cid, "")
            if tipo == "moneda":
                v = _to_decimal(raw)
                values.append(f"{MONEDA} {_round2(v):,.2f}".replace(",", "¤").replace(".", ",").replace("¤", "."))
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
