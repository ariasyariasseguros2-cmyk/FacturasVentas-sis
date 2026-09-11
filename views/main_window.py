import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Callable, Dict, Any, Optional
import threading
import os
import sys

from controllers.auth_controller import AuthController
from controllers.dashboard_controller import DashboardController
from views.bill import TableroFacturacion
from views.bill_rimac import TableroFacturacionRimac
from views.bill_grandias import TableroFacturacionGrandias
from views.bill_positiva import TableroFacturacionPositiva
from views.bill_mapfre import TableroFacturacionMapfre

from utils.updater import (
    APP_VERSION,
    consultar_version_remota,
    abrir_descarga,
    descargar_archivo,
    aplicar_parche_y_cerrar,
    ejecutar_actualizador_y_salir,
    obtener_directorio_ejecutable,
)


class MainWindow(tk.Tk):
    COLORS = {
        "header_bg": "#0f172a",
        "header_text": "#f8fafc",
        "header_subtext": "#94a3b8",
        "sidebar_bg": "#ffffff",
        "sidebar_border": "#e2e8f0",
        "content_bg": "#f1f5f9",
        "card_bg": "#ffffff",
        "card_border": "#e2e8f0",
        "text_primary": "#0f172a",
        "text_secondary": "#64748b",
        "text_muted": "#94a3b8",
        "menu_text": "#334155",
        "menu_hover_bg": "#f1f5f9",
        "menu_active_bg": "#dbeafe",
        "menu_active_fg": "#2563eb",
        "accent": "#2563eb",
        "success": "#16a34a",
        "warning": "#ea580c",
        "emergency": "#fbbf24",
        
    }

    MENU_ITEMS = [
        ("📊", "Dashboard", 0),
        ("🧾", "Facturas Sa/Cre/Proc", 1),
        ("🔴", "Facturas Rimac", 2),
        ("🟡", "Facturas Grandia", 3),
        ("🟣", "Facturas Positiva", 4),
        ("🔵", "Facturas Mapfre", 5),
        ("📑", "Pólizas", 6),
        ("👥", "Clientes", 7),
        ("📦", "Productos", 8),
        ("👤", "Usuarios", 9),
        ("⚙️", "Configuración", 10),
    ]

    def __init__(
        self,
        auth: AuthController,
        usuario: Dict[str, Any],
        on_logout: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.auth = auth
        self.usuario = usuario
        self.on_logout = on_logout
        self._botones_menu = []
        self._paginas = []
        self._fecha_job = None
        self._metricas_job = None
        self._metricas_running = False
        self._grafico_job = None
        self._grafico_running = False
        self._grafico_token = 0
        self._destroying = False
        self._grafico_moneda = "PEN"

        self.title("FacturasVentas — Sistema de Facturación")
        self.geometry("1280x820")
        self.minsize(1100, 680)
        self.configure(bg=self.COLORS["content_bg"])
        self._maximizar_ventana()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self._construir_ui()
        self._actualizar_fecha()
        self._cambiar_pagina(0)
        self.actualizar_metricas_dashboard()
        self._programar_actualizacion_metricas(30000)

    def _maximizar_ventana(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"{sw - 40}x{sh - 80}+20+20")

    def _construir_ui(self):
        raiz = tk.Frame(self, bg=self.COLORS["content_bg"])
        raiz.pack(fill="both", expand=True)

        self._construir_header(raiz)

        cuerpo = tk.Frame(raiz, bg=self.COLORS["content_bg"])
        cuerpo.pack(fill="both", expand=True)

        self._construir_sidebar(cuerpo)
        self._construir_contenido(cuerpo)

    def _construir_header(self, parent: tk.Widget):
        header = tk.Frame(parent, bg=self.COLORS["header_bg"], height=58)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="📊", bg=self.COLORS["header_bg"], fg="#ffffff",
                 font=("Segoe UI", 16)).pack(side="left", padx=(22, 10), pady=14)

        tit_box = tk.Frame(header, bg=self.COLORS["header_bg"])
        tit_box.pack(side="left", pady=8)
        tk.Label(tit_box, text="FacturasVentas", bg=self.COLORS["header_bg"],
                 fg=self.COLORS["header_text"],
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(tit_box, text="Sistema de Gestión Comercial", bg=self.COLORS["header_bg"],
                 fg=self.COLORS["header_subtext"],
                 font=("Segoe UI", 9)).pack(anchor="w")

        header_mid = tk.Frame(header, bg=self.COLORS["header_bg"])
        header_mid.pack(side="right", padx=6)

        self.lbl_fecha = tk.Label(header_mid, text="", bg=self.COLORS["header_bg"],
                                  fg="#cbd5e1", font=("Segoe UI", 9))
        self.lbl_fecha.pack(side="right", padx=10, pady=18)

        if self.usuario.get("modo_emergencia"):
            modo = tk.Label(header_mid, text="⚠ MODO EMERGENCIA", bg=self.COLORS["header_bg"],
                            fg=self.COLORS["emergency"], font=("Segoe UI", 9, "bold"),
                            padx=10, pady=3, relief="solid", bd=1)
            modo.pack(side="right", padx=6, pady=15)
        else:
            modo = tk.Label(header_mid, text="● En línea", bg=self.COLORS["header_bg"],
                            fg="#34d399", font=("Segoe UI", 9, "bold"))
            modo.pack(side="right", padx=6, pady=18)

        user_box = tk.Frame(header, bg=self.COLORS["header_bg"], cursor="hand2")
        user_box.pack(side="right", padx=10, pady=8)

        iniciales = self._obtener_iniciales(self.usuario.get("nombre", "U"))
        color_avatar = self.usuario.get("color_avatar", "#3b82f6")
        avatar_lbl = self._crear_avatar(user_box, iniciales, color_avatar, 32)
        avatar_lbl.pack(side="left", padx=(4, 8))

        info_box = tk.Frame(user_box, bg=self.COLORS["header_bg"])
        info_box.pack(side="left", pady=2)
        tk.Label(info_box, text=self.usuario.get("nombre", "Usuario"),
                 bg=self.COLORS["header_bg"], fg="#ffffff",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(info_box, text=self.usuario.get("rol_nombre", "Usuario"),
                 bg=self.COLORS["header_bg"], fg="#94a3b8",
                 font=("Segoe UI", 8)).pack(anchor="w")

        btn_update = tk.Button(header, text="🔄 Actualizaciones", bg="#1e3a8a", fg="#ffffff",
                               font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                               cursor="hand2", activebackground="#1e40af",
                               activeforeground="#ffffff", padx=12, pady=6,
                               command=self._buscar_actualizaciones)
        btn_update.pack(side="right", padx=(0, 6), pady=12)

        version_tag = tk.Label(header, text=f"v{APP_VERSION}", bg="#1e293b",
                               fg="#94a3b8", font=("Segoe UI", 8, "bold"),
                               padx=8, pady=3)
        version_tag.pack(side="right", padx=(0, 0), pady=15)

        btn_logout = tk.Button(header, text="Cerrar Sesión", bg="#1e293b", fg="#f8fafc",
                               font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                               cursor="hand2", activebackground="#334155",
                               activeforeground="#ffffff", padx=14, pady=6,
                               command=self._confirmar_logout)
        btn_logout.pack(side="right", padx=(0, 18), pady=12)

    def _crear_avatar(self, parent, iniciales: str, color: str, size: int = 32) -> tk.Canvas:
        c = tk.Canvas(parent, width=size, height=size, bg=self.COLORS["header_bg"],
                      highlightthickness=0, bd=0)
        c.oval = c.create_oval(1, 1, size - 1, size - 1, fill=color, outline="")
        c.text = c.create_text(size // 2, size // 2, text=iniciales, fill="#ffffff",
                               font=("Segoe UI", int(size * 0.4), "bold"))
        return c

    def _construir_sidebar(self, parent: tk.Widget):
        sidebar = tk.Frame(parent, bg=self.COLORS["sidebar_bg"], width=230,
                           highlightbackground=self.COLORS["sidebar_border"],
                           highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        for idx, (icono, texto, id_pag) in enumerate(self.MENU_ITEMS):
            btn = self._crear_boton_menu(sidebar, icono, texto, id_pag)
            btn.pack(fill="x", padx=4, pady=1 if idx else (18, 1))
            self._botones_menu.append((btn, id_pag, texto))

        sep = tk.Frame(sidebar, bg="#e2e8f0", height=1)
        sep.pack(fill="x", padx=14, pady=(12, 10))

        user_card = tk.Frame(sidebar, bg="#f8fafc", bd=0, highlightthickness=0)
        user_card.pack(fill="x", padx=14, pady=0)
        uc_pad = tk.Frame(user_card, bg="#f8fafc")
        uc_pad.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(uc_pad, text=self.usuario.get("nombre", "Usuario"), bg="#f8fafc",
                 fg=self.COLORS["text_primary"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(uc_pad, text=f"@{self.usuario.get('username', '')}", bg="#f8fafc",
                 fg="#64748b", font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 2))
        tk.Label(uc_pad, text=self.usuario.get("rol_nombre", "Usuario"), bg="#f8fafc",
                 fg="#2563eb", font=("Segoe UI", 9, "bold")).pack(anchor="w")

    def _crear_boton_menu(self, parent, icono: str, texto: str, id_pag: int) -> tk.Frame:
        wrap = tk.Frame(parent, bg=self.COLORS["sidebar_bg"])
        inner = tk.Frame(wrap, bg=self.COLORS["sidebar_bg"], cursor="hand2")
        inner.pack(fill="x", padx=2, pady=2)

        icon_lbl = tk.Label(inner, text=icono, bg=self.COLORS["sidebar_bg"],
                            fg=self.COLORS["menu_text"],
                            font=("Segoe UI", 12))
        icon_lbl.pack(side="left", padx=(14, 10), pady=9)

        txt_lbl = tk.Label(inner, text=texto, bg=self.COLORS["sidebar_bg"],
                           fg=self.COLORS["menu_text"],
                           font=("Segoe UI", 10), anchor="w")
        txt_lbl.pack(side="left", fill="x", expand=True, pady=9)

        def _entrar(e):
            if wrap._activo:
                return
            inner.configure(bg=self.COLORS["menu_hover_bg"])
            icon_lbl.configure(bg=self.COLORS["menu_hover_bg"])
            txt_lbl.configure(bg=self.COLORS["menu_hover_bg"])

        def _salir(e):
            if wrap._activo:
                return
            inner.configure(bg=self.COLORS["sidebar_bg"])
            icon_lbl.configure(bg=self.COLORS["sidebar_bg"])
            txt_lbl.configure(bg=self.COLORS["sidebar_bg"])

        def _click(e):
            self._cambiar_pagina(id_pag)

        wrap._activo = False
        wrap._icon = icon_lbl
        wrap._txt = txt_lbl
        wrap._inner = inner

        for w in (inner, icon_lbl, txt_lbl, wrap):
            w.bind("<Enter>", _entrar)
            w.bind("<Leave>", _salir)
            w.bind("<Button-1>", _click)

        return wrap

    def _marcar_menu_activo(self, id_pag: int):
        for btn, idp, _ in self._botones_menu:
            if idp == id_pag:
                btn._activo = True
                btn._inner.configure(bg=self.COLORS["menu_active_bg"])
                btn._icon.configure(bg=self.COLORS["menu_active_bg"],
                                    fg=self.COLORS["menu_active_fg"])
                btn._txt.configure(bg=self.COLORS["menu_active_bg"],
                                   fg=self.COLORS["menu_active_fg"],
                                   font=("Segoe UI", 10, "bold"))
            else:
                btn._activo = False
                btn._inner.configure(bg=self.COLORS["sidebar_bg"])
                btn._icon.configure(bg=self.COLORS["sidebar_bg"],
                                    fg=self.COLORS["menu_text"])
                btn._txt.configure(bg=self.COLORS["sidebar_bg"],
                                   fg=self.COLORS["menu_text"],
                                   font=("Segoe UI", 10))

    def _construir_contenido(self, parent: tk.Widget):
        self.contenedor = tk.Frame(parent, bg=self.COLORS["content_bg"])
        self.contenedor.pack(side="left", fill="both", expand=True)

        self.stack = tk.Frame(self.contenedor, bg=self.COLORS["content_bg"])
        self.stack.pack(fill="both", expand=True, padx=24, pady=(22, 22))

        self._paginas = [
            self._crear_dashboard(self.stack),
            TableroFacturacion(self.stack, bg=self.COLORS["content_bg"]),
            TableroFacturacionRimac(self.stack, bg=self.COLORS["content_bg"]),
            TableroFacturacionGrandias(self.stack, bg=self.COLORS["content_bg"]),
            TableroFacturacionPositiva(self.stack, bg=self.COLORS["content_bg"]),
            TableroFacturacionMapfre(self.stack, bg=self.COLORS["content_bg"]),
        ]
        for nombre in ("Pólizas", "Clientes", "Productos", "Usuarios", "Configuración"):
            self._paginas.append(self._crear_pagina_generica(self.stack, nombre))

    def _cambiar_pagina(self, idx: int):
        self._marcar_menu_activo(idx)
        for w in self.stack.winfo_children():
            w.pack_forget()
            try:
                w.place_forget()
            except Exception:
                pass
        if 0 <= idx < len(self._paginas):
            pagina = self._paginas[idx]
            pagina.pack(fill="both", expand=True)
            pagina.lift()
            self.update_idletasks()

    def _crear_card(self, parent: tk.Widget) -> tk.Frame:
        wrap = tk.Frame(parent, bg=self.COLORS["card_border"])
        inner = tk.Frame(wrap, bg=self.COLORS["card_bg"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        wrap._inner = inner
        return wrap

    def _crear_dashboard(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=self.COLORS["content_bg"])

        cabecera = tk.Frame(page, bg=self.COLORS["content_bg"])
        cabecera.pack(fill="x")

        cab_izq = tk.Frame(cabecera, bg=self.COLORS["content_bg"])
        cab_izq.pack(side="left", fill="y")
        tk.Label(cab_izq, text="Panel Principal", bg=self.COLORS["content_bg"],
            fg=self.COLORS["text_primary"],
        font=("Segoe UI", 18, "bold")).pack(anchor="w")
        subt = f"Bienvenido(a), {self.usuario.get('nombre', 'Usuario')}  —  Hoy es {self._hoy_texto()}"
        tk.Label(cab_izq, text=subt, bg=self.COLORS["content_bg"],
            fg=self.COLORS["text_secondary"],
            font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 12))
        tk.Label(cabecera, text="Panel Principal", bg=self.COLORS["content_bg"],
            fg=self.COLORS["text_primary"],
            font=("Segoe UI", 18, "bold")).pack(anchor="w")
        subt = f"Bienvenido(a), {self.usuario.get('nombre', 'Usuario')}  —  Hoy es {self._hoy_texto()}"
        tk.Label(cabecera, text=subt, bg=self.COLORS["content_bg"],
                 fg=self.COLORS["text_secondary"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 12))

        tarjetas_row = tk.Frame(page, bg=self.COLORS["content_bg"])
        tarjetas_row.pack(fill="x")

        # Tarjeta 1: Ventas del día (S/ y US$)
        i = 0
        card_ventas = self._crear_card(tarjetas_row)
        card_ventas.pack(side="left", fill="both", expand=True,
                         padx=(0, 6))
        inner_v = card_ventas._inner
        inner_v.configure(height=108)
        inner_v.pack_propagate(False)

        color_v = "#2563eb"
        icon_bg_v = self._hex_with_alpha(color_v, 0x1A)
        icono_lbl_v = tk.Label(inner_v, text="💵", bg=icon_bg_v, fg=color_v,
                               font=("Segoe UI", 20), anchor="center")
        icono_lbl_v.place(x=16, y=26, width=56, height=56)

        txt_col_v = tk.Frame(inner_v, bg=self.COLORS["card_bg"])
        txt_col_v.place(x=90, y=18, relwidth=1, width=-106)
        tk.Label(txt_col_v, text="Ventas del día", bg=self.COLORS["card_bg"],
                 fg=self.COLORS["text_secondary"],
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.lbl_ventas_soles = tk.Label(
            txt_col_v, text="S/ 0.00", bg=self.COLORS["card_bg"], fg=color_v,
            font=("Segoe UI", 14, "bold"))
        self.lbl_ventas_soles.pack(anchor="w", pady=(3, 0))
        self.lbl_ventas_dolares = tk.Label(
            txt_col_v, text="US$ 0.00", bg=self.COLORS["card_bg"],
            fg="#64748b", font=("Segoe UI", 9, "bold"))
        self.lbl_ventas_dolares.pack(anchor="w", pady=(2, 0))

        # Tarjetas 2-4: Facturas, Pólizas, Clientes
        tarjetas_simples = [
            (1, "🧾", "Facturas emitidas", "0", "#059669"),
            (2, "📑", "Pólizas activas", "0", "#7c3aed"),
            (3, "👥", "Clientes registrados", "0", "#ea580c"),
        ]
        self._tarjeta_labels = {}
        for idx, (i, ico, titulo, valor, color) in enumerate(tarjetas_simples):
            card = self._crear_card(tarjetas_row)
            pad_left = 6
            pad_right = 0 if idx == len(tarjetas_simples) - 1 else 6
            card.pack(side="left", fill="both", expand=True,
                      padx=(pad_left, pad_right))

            inner = card._inner
            inner.configure(height=108)
            inner.pack_propagate(False)

            icon_bg = self._hex_with_alpha(color, 0x1A)
            icono_lbl = tk.Label(inner, text=ico, bg=icon_bg, fg=color,
                                 font=("Segoe UI", 20), anchor="center")
            icono_lbl.place(x=16, y=26, width=56, height=56)

            txt_col = tk.Frame(inner, bg=self.COLORS["card_bg"])
            txt_col.place(x=90, y=22, relwidth=1, width=-106)
            tk.Label(txt_col, text=titulo, bg=self.COLORS["card_bg"],
                     fg=self.COLORS["text_secondary"],
                     font=("Segoe UI", 10)).pack(anchor="w")
            lbl_valor = tk.Label(txt_col, text=valor, bg=self.COLORS["card_bg"],
                                 fg=color, font=("Segoe UI", 18, "bold"))
            lbl_valor.pack(anchor="w", pady=(4, 0))

            if titulo == "Facturas emitidas":
                self.lbl_facturas = lbl_valor
            elif titulo == "Pólizas activas":
                self.lbl_polizas = lbl_valor
            elif titulo == "Clientes registrados":
                self.lbl_clientes = lbl_valor

        fila2 = tk.Frame(page, bg=self.COLORS["content_bg"])
        fila2.pack(fill="both", expand=True, pady=(12, 0))

        act_card = self._crear_card(fila2)
        act_card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        act_inner = act_card._inner
        act_pad = tk.Frame(act_inner, bg=self.COLORS["card_bg"])
        act_pad.pack(fill="both", expand=True, padx=18, pady=16)
        tk.Label(act_pad, text="Actividad reciente", bg=self.COLORS["card_bg"],
                 fg=self.COLORS["text_primary"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(act_pad, text="  •  No hay actividad reciente", bg=self.COLORS["card_bg"],
                 fg="#475569", font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 0))

        atajos_card = self._crear_card(fila2)
        atajos_card.configure(width=320)
        atajos_card.pack_propagate(False)
        atajos_card.pack(side="left", fill="both", expand=False, padx=(6, 0))
        atajos_inner = atajos_card._inner
        at_pad = tk.Frame(atajos_inner, bg=self.COLORS["card_bg"])
        at_pad.pack(fill="both", expand=True, padx=18, pady=16)
        tk.Label(at_pad, text="Accesos rápidos", bg=self.COLORS["card_bg"],
                 fg=self.COLORS["text_primary"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        atajos = [
            ("➕", "Nueva factura"),
            ("🔍", "Buscar cliente"),
            ("📑", "Crear póliza"),
            ("📊", "Ver reportes"),
        ]
        for ico, txt in atajos:
            b = tk.Label(at_pad, text=f"  {ico}   {txt}", bg="#f8fafc", fg="#334155",
                         font=("Segoe UI", 10), anchor="w", cursor="hand2",
                         relief="solid", bd=0, padx=12, pady=10)
            b.configure(highlightbackground="#e2e8f0", highlightthickness=1)
            b.pack(fill="x", pady=5)
            b.bind("<Enter>", lambda e, w=b: w.configure(bg="#eef2ff"))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg="#f8fafc"))

        fila3 = tk.Frame(page, bg=self.COLORS["content_bg"])
        fila3.pack(fill="both", expand=False, pady=(12, 0))

        chart_card = self._crear_card(fila3)
        chart_card.pack(fill="both", expand=True)
        chart_inner = chart_card._inner
        chart_pad = tk.Frame(chart_inner, bg=self.COLORS["card_bg"])
        chart_pad.pack(fill="both", expand=True, padx=18, pady=16)

        chart_header = tk.Frame(chart_pad, bg=self.COLORS["card_bg"])
        chart_header.pack(fill="x")

        title_col = tk.Frame(chart_header, bg=self.COLORS["card_bg"])
        title_col.pack(side="left", fill="y")
        tk.Label(title_col, text="Prima Neta y Comisiones del Día",
                 bg=self.COLORS["card_bg"], fg=self.COLORS["text_primary"],
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(title_col, text="Distribución por horas del día actual",
                 bg=self.COLORS["card_bg"], fg=self.COLORS["text_secondary"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

        right_col = tk.Frame(chart_header, bg=self.COLORS["card_bg"])
        right_col.pack(side="right", fill="y")

        badges_row = tk.Frame(right_col, bg=self.COLORS["card_bg"])
        badges_row.pack(anchor="e")

        def _crear_badge(parent, texto_leyenda: str, color_ico: str, valor_inicial: str):
            wrap = tk.Frame(parent, bg=self.COLORS["card_bg"],
                            highlightbackground="#e2e8f0", highlightthickness=1,
                            bd=0)
            wrap.pack(side="left", padx=(0, 8))
            inner = tk.Frame(wrap, bg="#ffffff")
            inner.pack(fill="both", expand=True, padx=10, pady=6)
            ico_dot = tk.Label(inner, text="●", bg="#ffffff", fg=color_ico,
                               font=("Segoe UI", 8))
            ico_dot.pack(side="left", padx=(0, 6))
            lbl_ley = tk.Label(inner, text=texto_leyenda, bg="#ffffff",
                               fg=self.COLORS["text_secondary"],
                               font=("Segoe UI", 9))
            lbl_ley.pack(side="left")
            lbl_val = tk.Label(inner, text=valor_inicial, bg="#ffffff",
                               fg=self.COLORS["text_primary"],
                               font=("Segoe UI", 9, "bold"))
            lbl_val.pack(side="left", padx=(4, 0))
            return lbl_val

        self._badge_prima_neta = _crear_badge(badges_row, "Prima Neta:", "#2563eb", "S/ 0.00")
        self._badge_prima_cigv = _crear_badge(badges_row, "Prima Comercial c/IGV:", "#10b981", "S/ 0.00")
        self._badge_comision = _crear_badge(badges_row, "Comisión:", "#8b5cf6", "S/ 0.00")

        moneda_row = tk.Frame(right_col, bg=self.COLORS["card_bg"])
        moneda_row.pack(anchor="e", pady=(10, 0))

        moneda_wrap = tk.Frame(moneda_row, bg="#f1f5f9",
                               highlightbackground="#e2e8f0", highlightthickness=1)
        moneda_wrap.pack(anchor="e")

        def _crear_btn_moneda(parent, texto: str, moneda: str, activo_inicial: bool):
            if activo_inicial:
                bg_btn = "#2563eb"
                fg_btn = "#ffffff"
                relief_btn = "flat"
            else:
                bg_btn = "#f1f5f9"
                fg_btn = "#64748b"
                relief_btn = "flat"
            btn = tk.Label(parent, text=texto, bg=bg_btn, fg=fg_btn,
                           font=("Segoe UI", 9, "bold"), padx=16, pady=6,
                           cursor="hand2", relief=relief_btn, bd=0)
            btn.pack(side="left")
            btn._moneda = moneda
            return btn

        self._btn_moneda_pen = _crear_btn_moneda(moneda_wrap, "S/.", "PEN", True)
        self._btn_moneda_usd = _crear_btn_moneda(moneda_wrap, "US$", "USD", False)

        def _toggle_pen(e):
            self._cambiar_moneda_grafico("PEN")

        def _toggle_usd(e):
            self._cambiar_moneda_grafico("USD")

        self._btn_moneda_pen.bind("<Button-1>", _toggle_pen)
        self._btn_moneda_usd.bind("<Button-1>", _toggle_usd)

        chart_sep = tk.Frame(chart_pad, bg="#e2e8f0", height=1)
        chart_sep.pack(fill="x", pady=(14, 0))

        chart_canvas_wrap = tk.Frame(chart_pad, bg=self.COLORS["card_bg"])
        chart_canvas_wrap.pack(fill="both", expand=True, pady=(10, 0))

        self._canvas_grafico_diario = tk.Canvas(chart_canvas_wrap,
                                                bg=self.COLORS["card_bg"],
                                                highlightthickness=0, bd=0,
                                                height=320)
        self._canvas_grafico_diario.pack(fill="both", expand=True)
        self._canvas_grafico_diario.bind("<Configure>",
                                         lambda e: self._programar_actualizacion_grafico(250))

        return page

    def _cambiar_moneda_grafico(self, moneda: str):
        if self._grafico_moneda == moneda:
            return
        self._grafico_moneda = moneda
        pen_activo = moneda == "PEN"
        usd_activo = moneda == "USD"
        self._btn_moneda_pen.configure(bg="#2563eb" if pen_activo else "#f1f5f9",
                                       fg="#ffffff" if pen_activo else "#64748b")
        self._btn_moneda_usd.configure(bg="#2563eb" if usd_activo else "#f1f5f9",
                                       fg="#ffffff" if usd_activo else "#64748b")

        try:
            if self._grafico_job is not None:
                self.after_cancel(self._grafico_job)
                self._grafico_job = None
        except Exception:
            pass

        self._grafico_token += 1
        self._actualizar_grafico_diario()

    def _programar_actualizacion_grafico(self, intervalo_ms: int = 250):
        if self._destroying or not self.winfo_exists():
            return
        try:
            if self._grafico_job is not None:
                self.after_cancel(self._grafico_job)
        except Exception:
            pass
        self._grafico_job = self.after(intervalo_ms, lambda: self._actualizar_grafico_diario())

    def _formatear_escala_y(self, valor: float) -> str:
        if valor >= 1_000_000:
            return f"{valor / 1_000_000:.1f}M"
        if valor >= 1_000:
            return f"{valor / 1_000:.0f}k"
        return f"{valor:.0f}"

    def _dibujar_grafico_diario_canvas(self, datos: dict):
        canvas = self._canvas_grafico_diario
        canvas.delete("all")

        w = max(canvas.winfo_width(), 600)
        h = max(canvas.winfo_height(), 320)

        pad_izq = 56
        pad_der = 20
        pad_sup = 20
        pad_inf = 50
        plot_w = w - pad_izq - pad_der
        plot_h = h - pad_sup - pad_inf

        if plot_w <= 0 or plot_h <= 0:
            return

        simbolo = datos.get("simbolo", "S/")
        por_hora = datos.get("por_hora", [])
        if not por_hora:
            return

        max_vals = []
        for f in por_hora:
            max_vals.append(f.get("prima_neta", 0) or 0)
            max_vals.append(f.get("prima_comercial_igv", 0) or 0)
            max_vals.append(f.get("comision", 0) or 0)
        max_raw = max(max_vals) if max_vals else 0

        if max_raw <= 0:
            max_y = 500
        else:
            if max_raw < 1000:
                paso = 100
            elif max_raw < 10000:
                paso = 1000
            elif max_raw < 100000:
                paso = 10000
            elif max_raw < 1_000_000:
                paso = 100000
            else:
                paso = 1_000_000
            mult = 1
            while mult * paso < max_raw * 1.1:
                mult += 1
            max_y = mult * paso

        canvas.create_rectangle(0, 0, w, h, fill=self.COLORS["card_bg"], outline="")

        n_pasos = 5
        for i in range(n_pasos + 1):
            y = pad_sup + plot_h - (i / n_pasos) * plot_h
            val = (i / n_pasos) * max_y
            label = self._formatear_escala_y(val)
            canvas.create_line(pad_izq, y, pad_izq + plot_w, y,
                               fill="#e2e8f0", dash=(4, 2))
            canvas.create_text(pad_izq - 8, y, text=label,
                               fill="#94a3b8", font=("Segoe UI", 8),
                               anchor="e")

        n_horas = len(por_hora)
        ancho_grupo = plot_w / n_horas
        gap_grupo = ancho_grupo * 0.22
        ancho_barra = (ancho_grupo - gap_grupo) / 2.0

        color_prima = "#2563eb"
        color_comision = "#8b5cf6"

        for idx, f in enumerate(por_hora):
            x_grupo = pad_izq + idx * ancho_grupo + gap_grupo / 2
            x_azul = x_grupo
            x_morado = x_grupo + ancho_barra

            pn = f.get("prima_neta", 0) or 0
            co = f.get("comision", 0) or 0

            h_pn = (pn / max_y) * plot_h if max_y > 0 else 0
            h_co = (co / max_y) * plot_h if max_y > 0 else 0

            if h_pn > 0:
                y0_pn = pad_sup + plot_h - h_pn
                y1_pn = pad_sup + plot_h
                canvas.create_rectangle(x_azul, y0_pn, x_azul + ancho_barra, y1_pn,
                                        fill=color_prima, outline="")

            if h_co > 0:
                y0_co = pad_sup + plot_h - h_co
                y1_co = pad_sup + plot_h
                canvas.create_rectangle(x_morado, y0_co, x_morado + ancho_barra, y1_co,
                                        fill=color_comision, outline="")

        step_etiqueta = 1
        if n_horas > 16:
            step_etiqueta = 2
        if n_horas > 20:
            step_etiqueta = 3

        for idx in range(0, n_horas, step_etiqueta):
            f = por_hora[idx]
            h_ = f.get("hora", 0)
            x_centro = pad_izq + idx * ancho_grupo + ancho_grupo / 2
            y_lbl = pad_sup + plot_h + 14
            canvas.create_text(x_centro, y_lbl,
                               text=f"{h_:02d}:00",
                               fill="#64748b", font=("Segoe UI", 8),
                               anchor="n")

        axis_y_x0 = pad_izq
        axis_y_y0 = pad_sup
        axis_y_x1 = pad_izq
        axis_y_y1 = pad_sup + plot_h
        canvas.create_line(axis_y_x0, axis_y_y0, axis_y_x1, axis_y_y1,
                           fill="#cbd5e1")
        canvas.create_line(pad_izq, pad_sup + plot_h, pad_izq + plot_w, pad_sup + plot_h,
                           fill="#cbd5e1")

    def _desbloquear_grafico_diario(self):
        if self._destroying or not self.winfo_exists():
            return
        self._grafico_running = False

    def _actualizar_grafico_diario(self):
        if self._destroying or not self.winfo_exists():
            return

        token = self._grafico_token
        call_token = token

        def _trabajo(token_local):
            try:
                datos = DashboardController.obtener_datos_grafico_diario(self._grafico_moneda)
                if self.winfo_exists() and token_local == self._grafico_token:
                    self.after(0, lambda: self._mostrar_grafico_diario(datos))
            except Exception as e:
                print(f"[Dashboard] Error al actualizar gráfico diario: {e}")
                if self.winfo_exists() and token_local == self._grafico_token:
                    self.after(0, lambda: self._mostrar_grafico_diario({}))
            finally:
                if self.winfo_exists() and token_local == self._grafico_token:
                    self.after(0, self._desbloquear_grafico_diario)

        self._grafico_running = True
        threading.Thread(target=_trabajo, args=(call_token,), daemon=True).start()

    def _mostrar_grafico_diario(self, datos: Dict[str, Any]):
        if self._destroying or not self.winfo_exists():
            return
        try:
            simbolo = datos.get("simbolo", "S/")
            totales = datos.get("totales", {})
            pn = totales.get("prima_neta", 0) or 0
            pcigv = totales.get("prima_comercial_igv", 0) or 0
            co = totales.get("comision", 0) or 0
            if hasattr(self, "_badge_prima_neta"):
                self._badge_prima_neta.configure(text=f"{simbolo} {pn:,.2f}")
            if hasattr(self, "_badge_prima_cigv"):
                self._badge_prima_cigv.configure(text=f"{simbolo} {pcigv:,.2f}")
            if hasattr(self, "_badge_comision"):
                self._badge_comision.configure(text=f"{simbolo} {co:,.2f}")
            if hasattr(self, "_canvas_grafico_diario") and datos:
                self._dibujar_grafico_diario_canvas(datos)
        except Exception as e:
            print(f"[Dashboard] Error al pintar gráfico diario: {e}")

    def _crear_pagina_generica(self, parent: tk.Widget, nombre: str) -> tk.Frame:
        page = tk.Frame(parent, bg=self.COLORS["content_bg"])

        card = self._crear_card(page)
        card.pack(fill="both", expand=True)
        inner = card._inner

        center_box = tk.Frame(inner, bg=self.COLORS["card_bg"])
        center_box.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center_box, text="🚧", bg=self.COLORS["card_bg"],
                 fg=self.COLORS["text_muted"],
                 font=("Segoe UI", 48)).pack(pady=(0, 12))
        tk.Label(center_box, text=f"Módulo: {nombre}", bg=self.COLORS["card_bg"],
                 fg=self.COLORS["text_primary"],
                 font=("Segoe UI", 18, "bold")).pack(pady=(0, 6))
        tk.Label(center_box, text="Esta sección se encuentra en construcción.",
                 bg=self.COLORS["card_bg"], fg=self.COLORS["text_secondary"],
                 font=("Segoe UI", 11)).pack()

        return page

    def _hex_with_alpha(self, hex_color: str, alpha: int) -> str:
        try:
            hex_color = hex_color.lstrip("#")
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            bg_r, bg_g, bg_b = 0xFF, 0xFF, 0xFF
            a = alpha / 255.0
            nr = int(r * a + bg_r * (1 - a))
            ng = int(g * a + bg_g * (1 - a))
            nb = int(b * a + bg_b * (1 - a))
            return f"#{nr:02x}{ng:02x}{nb:02x}"
        except Exception:
            return "#eff6ff"

    def _obtener_iniciales(self, texto: str) -> str:
        texto = (texto or "").strip()
        if not texto:
            return "U"
        partes = [p for p in texto.split() if p][:2]
        return "".join(p[0].upper() for p in partes)

    def _actualizar_fecha(self):
        if self._destroying or not self.winfo_exists():
            return
        try:
            self.lbl_fecha.configure(text=datetime.now().strftime("%d/%m/%Y  %H:%M"))
        except Exception:
            return
        self._fecha_job = self.after(30000, self._actualizar_fecha)

    def _hoy_texto(self) -> str:
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                 "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        d = datetime.now()
        return f"{d.day} de {meses[d.month - 1]} de {d.year}"

    def actualizar_metricas_dashboard(self):
        if self._destroying or not self.winfo_exists():
            return
        if self._metricas_running:
            return

        self._metricas_running = True

        def _trabajo():
            try:
                metricas = DashboardController.obtener_metricas_hoy()
                if self.winfo_exists():
                    self.after(0, lambda: self._mostrar_metricas_dashboard(metricas))
            except Exception as e:
                print(f"[Dashboard] Error al actualizar métricas: {e}")
                if self.winfo_exists():
                    self.after(0, lambda: self._mostrar_metricas_dashboard({}))
            finally:
                if self.winfo_exists():
                    self._metricas_running = False

        threading.Thread(target=_trabajo, daemon=True).start()

    def _mostrar_metricas_dashboard(self, metricas: Dict[str, Any]):
        if self._destroying or not self.winfo_exists():
            return
        try:
            ventas_soles = metricas.get("ventas_soles", 0.0) or 0.0
            ventas_dolares = metricas.get("ventas_dolares", 0.0) or 0.0
            facturas = metricas.get("facturas", 0) or 0
            polizas = metricas.get("polizas", 0) or 0
            clientes = metricas.get("clientes", 0) or 0

            if hasattr(self, "lbl_ventas_soles"):
                self.lbl_ventas_soles.configure(text=f"S/ {ventas_soles:,.2f}")
            if hasattr(self, "lbl_ventas_dolares"):
                self.lbl_ventas_dolares.configure(text=f"US$ {ventas_dolares:,.2f}")
            if hasattr(self, "lbl_facturas"):
                self.lbl_facturas.configure(text=str(facturas))
            if hasattr(self, "lbl_polizas"):
                self.lbl_polizas.configure(text=str(polizas))
            if hasattr(self, "lbl_clientes"):
                self.lbl_clientes.configure(text=str(clientes))

            if hasattr(self, "_canvas_grafico_diario"):
                self._actualizar_grafico_diario()
        except Exception as e:
            print(f"[Dashboard] Error al pintar métricas: {e}")

    def _refrescar_dashboard_completo(self, texto_original: str = "🔄  Actualizar"):
        try:
            self.actualizar_metricas_dashboard()
            if hasattr(self, "_btn_refresh"):
                self._btn_refresh.configure(text="✅  Listo", bg="#059669")
                self.after(1200, lambda: self._restaurar_btn_refresh(texto_original))
        except Exception as e:
            print(f"[Dashboard] Error en refresco completo: {e}")
            self._restaurar_btn_refresh(texto_original)

    def _restaurar_btn_refresh(self, texto_original: str):
        self._refrescando = False
        if hasattr(self, "_btn_refresh"):
            self._btn_refresh.configure(text=texto_original, bg="#2563eb")

    def _buscar_actualizaciones(self):
        dlg = self._mostrar_dialogo_espera()
        self.update_idletasks()

        def _trabajo():
            res = consultar_version_remota()
            self.after(0, lambda: self._finalizar_busqueda(dlg, res))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _mostrar_dialogo_espera(self) -> tk.Toplevel:
        dlg = tk.Toplevel(self)
        dlg.title("Actualizaciones")
        dlg.configure(bg="#ffffff")
        dlg.geometry("380x160")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 380) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 160) // 2
        dlg.geometry(f"+{max(x, 50)}+{max(y, 50)}")

        tk.Label(dlg, text="🔍", bg="#ffffff", fg="#2563eb",
                 font=("Segoe UI", 24)).pack(pady=(22, 6))
        tk.Label(dlg, text="Buscando actualizaciones...", bg="#ffffff",
                 fg="#0f172a", font=("Segoe UI", 11, "bold")).pack()
        tk.Label(dlg, text="Conectando al servidor de versiones", bg="#ffffff",
                 fg="#64748b", font=("Segoe UI", 9)).pack(pady=(2, 0))
        return dlg

    def _finalizar_busqueda(self, dlg: tk.Toplevel, resultado: Dict[str, Any]):
        try:
            dlg.destroy()
        except Exception:
            pass
        self.after(10, lambda: self._mostrar_resultado_actualizacion(resultado))

    def _mostrar_resultado_actualizacion(self, res: Dict[str, Any]):
        dlg = tk.Toplevel(self)
        dlg.title("Actualizaciones")
        dlg.configure(bg="#ffffff")
        dlg.geometry("500x420")
        dlg.minsize(500, 420)
        dlg.transient(self)
        dlg.grab_set()
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 500) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 420) // 2
        dlg.geometry(f"+{max(x, 50)}+{max(y, 50)}")

        if res.get("hay_actualizacion"):
            titulo_barra = "Nueva versión disponible"
            color_titulo = "#16a34a"
            icono = "🎉"
            color_barra_bg = "#dcfce7"
            color_barra_bd = "#86efac"
        elif res.get("ok"):
            titulo_barra = "Aplicación actualizada"
            color_titulo = "#2563eb"
            icono = "✔"
            color_barra_bg = "#dbeafe"
            color_barra_bd = "#93c5fd"
        else:
            titulo_barra = "⚠ No se pudo comprobar"
            color_titulo = "#b45309"
            icono = "⚠"
            color_barra_bg = "#fef3c7"
            color_barra_bd = "#fcd34d"

        barra = tk.Frame(dlg, bg=color_barra_bg, height=54,
                         highlightbackground=color_barra_bd, highlightthickness=1)
        barra.pack(fill="x", padx=14, pady=(14, 0))
        barra.pack_propagate(False)

        tk.Label(barra, text=icono, bg=color_barra_bg, fg=color_titulo,
                 font=("Segoe UI", 18)).pack(side="left", padx=(14, 10))
        tk.Label(barra, text=titulo_barra, bg=color_barra_bg, fg=color_titulo,
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        cuerpo = tk.Frame(dlg, bg="#ffffff")
        cuerpo.pack(fill="both", expand=True, padx=22, pady=14)

        row1 = tk.Frame(cuerpo, bg="#ffffff")
        row1.pack(fill="x")
        tk.Label(row1, text="Versión instalada:", bg="#ffffff",
                 fg="#64748b", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        tk.Label(row1, text=f"v{res.get('version_local', APP_VERSION)}", bg="#ffffff",
                 fg="#0f172a", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=(10, 0))
        tk.Label(row1, text="Versión remota:", bg="#ffffff",
                 fg="#64748b", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(6, 0))
        vr = res.get("version_remota") or "—"
        lbl_vr = tk.Label(row1, text=f"v{vr}" if vr != "—" else vr, bg="#ffffff",
                          fg="#0f172a", font=("Segoe UI", 9, "bold"))
        lbl_vr.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(6, 0))

        if res.get("file_size_bytes", 0) > 0:
            tam_mb = res["file_size_bytes"] / (1024 * 1024)
            tk.Label(row1, text="Tamaño parche:", bg="#ffffff",
                     fg="#64748b", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=(6, 0))
            tk.Label(row1, text=f"{tam_mb:.1f} MB", bg="#ffffff",
                     fg="#0f172a", font=("Segoe UI", 9, "bold")).grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(6, 0))

        if res.get("hay_actualizacion") and res.get("notas"):
            tk.Label(cuerpo, text="Novedades de esta versión:", bg="#ffffff",
                     fg="#334155", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(14, 6))
            notas_box = tk.Frame(cuerpo, bg="#f8fafc",
                                 highlightbackground="#e2e8f0", highlightthickness=1)
            notas_box.pack(fill="x")
            nb = tk.Frame(notas_box, bg="#f8fafc")
            nb.pack(fill="x", padx=10, pady=8)
            for nota in res["notas"]:
                tk.Label(nb, text=f"•  {nota}", bg="#f8fafc", fg="#334155",
                         font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=1)

        modo = tk.Frame(cuerpo, bg="#ffffff")
        modo.pack(fill="x", pady=(14, 0))
        if res.get("hay_actualizacion"):
            if res.get("puede_autoaplicar"):
                etq = tk.Label(modo, text="⚡ Actualización automática disponible", bg="#ffffff",
                               fg="#16a34a", font=("Segoe UI", 9, "bold"))
                etq.pack(anchor="w")
                tk.Label(modo,
                         text="Se descargará y aplicará el parche, luego se reiniciará la aplicación.",
                         bg="#ffffff", fg="#64748b", font=("Segoe UI", 8), anchor="w").pack(anchor="w", pady=(1, 0))
            elif getattr(sys, "frozen", False):
                etq = tk.Label(modo, text="⚠ Esta versión requiere instalador completo", bg="#ffffff",
                               fg="#b45309", font=("Segoe UI", 9, "bold"))
                etq.pack(anchor="w")
            else:
                etq = tk.Label(modo, text="ℹ Modo desarrollo: auto-parche solo con .exe compilado", bg="#ffffff",
                               fg="#2563eb", font=("Segoe UI", 9, "bold"))
                etq.pack(anchor="w")

        if not res.get("ok"):
            tk.Label(cuerpo, text=f"Detalle: {res.get('error', '')}", bg="#ffffff",
                     fg="#b91c1c", font=("Segoe UI", 9)).pack(anchor="w", pady=(14, 0))

        pie = tk.Frame(dlg, bg="#ffffff")
        pie.pack(fill="x", padx=16, pady=(0, 14))

        def _cerrar():
            try:
                dlg.destroy()
            except Exception:
                pass

        def _descargar():
            url = res.get("download_url")
            if url:
                abrir_descarga(url)

        def _actualizar_auto():
            patch_url = res.get("patch_url")
            if not patch_url:
                messagebox.showerror("Actualización",
                                     "No hay URL de parche definida en el servidor.", parent=dlg)
                return
            checksum = res.get("checksum_sha256") or None
            version_remota = res.get("version_remota") or "nueva"
            resp = messagebox.askyesno(
                "Confirmar actualización",
                f"Se actualizará FacturasVentas a la versión v{version_remota}.\n\n"
                "La aplicación se cerrará y luego se abrirá automáticamente actualizada.\n\n"
                "¿Desea continuar?",
                parent=dlg,
            )
            if not resp:
                return
            try:
                dlg.destroy()
            except Exception:
                pass
            self._iniciar_descarga_y_parcheo(patch_url, checksum, version_remota)

        btn_cerrar = tk.Button(pie, text="Cerrar", bg="#f1f5f9", fg="#0f172a",
                               font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                               cursor="hand2", activebackground="#e2e8f0",
                               activeforeground="#0f172a", padx=16, pady=7,
                               command=_cerrar)
        btn_cerrar.pack(side="right")

        if res.get("hay_actualizacion") and res.get("download_url"):
            btn_desc = tk.Button(pie, text="⬇  Descargar instalador", bg="#475569",
                                 fg="#ffffff", font=("Segoe UI", 9, "bold"),
                                 relief="flat", bd=0, cursor="hand2",
                                 activebackground="#334155", activeforeground="#ffffff",
                                 padx=14, pady=7, command=_descargar)
            btn_desc.pack(side="right", padx=(0, 8))

        if res.get("hay_actualizacion") and res.get("puede_autoaplicar") and res.get("patch_url"):
            btn_auto = tk.Button(pie, text="⚡  Actualizar ahora", bg="#16a34a",
                                 fg="#ffffff", font=("Segoe UI", 9, "bold"),
                                 relief="flat", bd=0, cursor="hand2",
                                 activebackground="#15803d", activeforeground="#ffffff",
                                 padx=14, pady=7, command=_actualizar_auto)
            btn_auto.pack(side="right", padx=(0, 8))

    def _mostrar_dialogo_progreso(self, titulo: str = "Descargando actualización") -> Dict[str, Any]:
        dlg = tk.Toplevel(self)
        dlg.title("Actualizaciones")
        dlg.configure(bg="#ffffff")
        dlg.geometry("460x220")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 460) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 220) // 2
        dlg.geometry(f"+{max(x, 50)}+{max(y, 50)}")

        tk.Label(dlg, text="📦", bg="#ffffff", fg="#2563eb",
                 font=("Segoe UI", 26)).pack(pady=(18, 4))
        tk.Label(dlg, text=titulo, bg="#ffffff", fg="#0f172a",
                 font=("Segoe UI", 11, "bold")).pack()
        lbl_estado = tk.Label(dlg, text="Preparando...", bg="#ffffff",
                              fg="#64748b", font=("Segoe UI", 9))
        lbl_estado.pack(pady=(2, 0))

        pb_frame = tk.Frame(dlg, bg="#ffffff")
        pb_frame.pack(fill="x", padx=28, pady=(12, 0))
        estilo = ttk.Style(dlg)
        try:
            estilo.theme_use("clam")
        except Exception:
            pass
        estilo.configure("FV.Horizontal.TProgressbar",
                         troughcolor="#e2e8f0", background="#2563eb",
                         bordercolor="#ffffff", lightcolor="#2563eb", darkcolor="#1d4ed8")
        pb = ttk.Progressbar(pb_frame, style="FV.Horizontal.TProgressbar",
                             orient="horizontal", length=400, mode="determinate")
        pb.pack(fill="x")
        pb["maximum"] = 100
        pb["value"] = 0

        lbl_porcentaje = tk.Label(dlg, text="0%", bg="#ffffff",
                                  fg="#2563eb", font=("Segoe UI", 9, "bold"))
        lbl_porcentaje.pack(pady=(4, 0))

        return {
            "dlg": dlg,
            "pb": pb,
            "lbl_estado": lbl_estado,
            "lbl_porcentaje": lbl_porcentaje,
        }

    def _iniciar_descarga_y_parcheo(self, patch_url: str, checksum: Optional[str], version_remota: str):
        ui = self._mostrar_dialogo_progreso(titulo=f"Descargando actualización v{version_remota}")
        self.update_idletasks()

        dlg = ui["dlg"]
        pb = ui["pb"]
        lbl_estado = ui["lbl_estado"]
        lbl_porcentaje = ui["lbl_porcentaje"]

        dir_app = obtener_directorio_ejecutable()
        nombre_zip = f"FacturasVentas-{version_remota.replace('.', '_')}.patch"
        ruta_zip = os.path.join(dir_app, "_updates", nombre_zip)
        os.makedirs(os.path.dirname(ruta_zip), exist_ok=True)

        ultimo_porcentaje = [-1]

        def prog_descarga(actual: int, total: int):
            if total <= 0:
                return
            pct = int((actual / total) * 100)
            if pct == ultimo_porcentaje[0]:
                return
            ultimo_porcentaje[0] = pct
            mb_act = actual / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.after(0, lambda: self._ui_set_progreso(
                pb, lbl_porcentaje, lbl_estado,
                pct, f"Descargando... {mb_act:.1f} / {mb_tot:.1f} MB"
            ))

        def prog_extraccion(actual: int, total: int):
            if total <= 0:
                return
            pct = int((actual / total) * 100)
            self.after(0, lambda: self._ui_set_progreso(
                pb, lbl_porcentaje, lbl_estado,
                pct, f"Extrayendo archivos... {actual}/{total}"
            ))

        def _trabajo():
            try:
                desc_res = descargar_archivo(patch_url, ruta_zip, progress_cb=prog_descarga)
                if not desc_res["ok"]:
                    self.after(0, lambda: self._ui_error_progreso(dlg, desc_res.get("error", "Error desconocido")))
                    return

                self.after(0, lambda: self._ui_set_progreso(
                    pb, lbl_porcentaje, lbl_estado,
                    0, "Verificando integridad..."
                ))

                self.after(0, lambda: lbl_estado.configure(text="Aplicando parche..."))
                patch_result = aplicar_parche_y_cerrar(
                    ruta_zip,
                    checksum_esperado=checksum,
                    extraer_progress_cb=prog_extraccion,
                )
                if not patch_result["ok"]:
                    self.after(0, lambda: self._ui_error_progreso(dlg, patch_result.get("error", "No se pudo aplicar el parche")))
                    return

                ruta_bat = patch_result.get("bat_path")
                self.after(0, lambda: lbl_estado.configure(text="Cerrando y aplicando actualización..."))
                self.after(600, lambda: self._aplicar_y_salir(ruta_bat, dlg))

            except Exception as e:
                self.after(0, lambda: self._ui_error_progreso(dlg, str(e)))

        threading.Thread(target=_trabajo, daemon=True).start()

    def _ui_set_progreso(self, pb, lbl_porcentaje, lbl_estado, pct: int, estado: str):
        try:
            pb["value"] = max(0, min(100, int(pct)))
            lbl_porcentaje.configure(text=f"{max(0, min(100, int(pct)))}%")
            lbl_estado.configure(text=estado)
        except Exception:
            pass

    def _ui_error_progreso(self, dlg, mensaje: str):
        try:
            for w in dlg.winfo_children():
                w.destroy()
            tk.Label(dlg, text="⚠", bg="#ffffff", fg="#dc2626",
                     font=("Segoe UI", 28)).pack(pady=(18, 4))
            tk.Label(dlg, text="No se pudo completar la actualización", bg="#ffffff",
                     fg="#0f172a", font=("Segoe UI", 11, "bold")).pack()
            tk.Label(dlg, text=str(mensaje)[:200], bg="#ffffff",
                     fg="#64748b", font=("Segoe UI", 9), wraplength=380,
                     justify="center").pack(padx=18, pady=(6, 14))
            tk.Button(dlg, text="Cerrar", bg="#f1f5f9", fg="#0f172a",
                      font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
                      cursor="hand2", activebackground="#e2e8f0",
                      activeforeground="#0f172a", padx=20, pady=6,
                      command=dlg.destroy).pack(pady=(0, 14))
        except Exception:
            pass

    def _aplicar_y_salir(self, ruta_bat: str, dlg):
        try:
            dlg.destroy()
        except Exception:
            pass
        if not ruta_bat or not os.path.exists(ruta_bat):
            messagebox.showerror("Actualización",
                                 "No se encontró el script de actualización.", parent=self)
            return
        ok = ejecutar_actualizador_y_salir(ruta_bat)
        if not ok:
            messagebox.showerror("Actualización",
                                 "No se pudo lanzar el actualizador.\nDescargue el instalador manual.",
                                 parent=self)
            return
        try:
            self.auth.cerrar_sesion()
            self.destroy()
        except Exception:
            try:
                os._exit(0)
            except Exception:
                pass

    def _programar_actualizacion_metricas(self, intervalo_ms: int = 30000):
        if self._destroying or not self.winfo_exists():
            return
        try:
            if self._metricas_job is not None:
                self.after_cancel(self._metricas_job)
        except Exception:
            pass
        self._metricas_job = self.after(intervalo_ms, self._refrescar_metricas_periodico)

    def _refrescar_metricas_periodico(self):
        if self._destroying or not self.winfo_exists():
            return
        try:
            self.actualizar_metricas_dashboard()
        except Exception as e:
            print(f"[Dashboard] Error al refrescar métricas: {e}")
        self._programar_actualizacion_metricas(30000)

    def _cancelar_jobs_pendientes(self):
        if self._fecha_job is not None:
            try:
                self.after_cancel(self._fecha_job)
            except Exception:
                pass
            self._fecha_job = None
        if self._metricas_job is not None:
            try:
                self.after_cancel(self._metricas_job)
            except Exception:
                pass
            self._metricas_job = None

    def _confirmar_logout(self):
        resp = messagebox.askyesno(
            "Cerrar sesión",
            f"¿Está seguro que desea cerrar la sesión de {self.usuario.get('nombre', 'este usuario')}?",
            parent=self,
        )
        if resp:
            self._cancelar_jobs_pendientes()
            self._destroying = True
            self.auth.cerrar_sesion()
            callback = self.on_logout
            try:
                self.destroy()
            except Exception:
                pass
            if callback:
                try:
                    callback()
                except Exception:
                    pass

    def _al_cerrar(self):
        if self._destroying:
            return
        resp = messagebox.askyesno(
            "Salir del sistema",
            f"¿Está seguro que desea cerrar FacturasVentas?\n\nSe cerrará la sesión de {self.usuario.get('nombre', 'este usuario')}.",
            parent=self,
        )
        if not resp:
            return
        self._destroying = True
        self._cancelar_jobs_pendientes()
        try:
            self.auth.cerrar_sesion()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        try:
            sys.exit(0)
        except SystemExit:
            raise
        except Exception:
            try:
                os._exit(0)
            except Exception:
                pass
