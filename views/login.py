import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Dict, Any

from controllers.auth_controller import AuthController


class LoginWindow(tk.Tk):
    COLORS = {
        "bg": "#f1f5f9",
        "card": "#ffffff",
        "panel_left_1": "#1e3a8a",
        "panel_left_2": "#2563eb",
        "panel_left_3": "#3b82f6",
        "text_primary": "#0f172a",
        "text_secondary": "#64748b",
        "text_muted": "#94a3b8",
        "label": "#334155",
        "input_border": "#cbd5e1",
        "input_bg": "#ffffff",
        "btn_bg": "#2563eb",
        "btn_hover": "#1d4ed8",
        "btn_text": "#ffffff",
        "success": "#16a34a",
        "warning": "#ea580c",
        "error": "#dc2626",
        "accent_soft": "#dbeafe",
    }

    def __init__(self, auth: AuthController, on_login_success: Callable[[Dict[str, Any]], None]):
        super().__init__()
        self.auth = auth
        self.on_login_success = on_login_success
        self._password_visible = False
        self._msg_job: Optional[str] = None

        self.title("FacturasVentas — Iniciar Sesión")
        self.geometry("960x580")
        self.minsize(900, 540)
        self.configure(bg=self.COLORS["bg"])
        self._center_window(960, 580)

        self._construir_ui()
        self._verificar_conexion()
        self.after(120, lambda: self.entry_usuario.focus_set())

    def _center_window(self, w: int, h: int) -> None:
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _construir_ui(self):
        container = tk.Frame(self, bg=self.COLORS["bg"])
        container.pack(fill="both", expand=True, padx=30, pady=28)

        card = tk.Frame(container, bg=self.COLORS["card"], highlightthickness=0)
        card.place(relx=0.5, rely=0.5, anchor="center", width=820, height=500)

        try:
            card.update_idletasks()
        except Exception:
            pass

        card_inner = tk.Frame(card, bg=self.COLORS["card"])
        card_inner.pack(fill="both", expand=True)

        panel_izq = tk.Frame(card_inner, bg=self.COLORS["panel_left_2"])
        panel_izq.place(x=0, y=0, width=340, height=500)

        self._paint_panel_gradient(panel_izq)

        tk.Label(panel_izq, text="", bg=self.COLORS["panel_left_2"], fg="#ffffff",
                 font=("Segoe UI", 36, "bold")).place(x=32, y=40)
        tk.Label(panel_izq, text="FacturasVentas", bg=self.COLORS["panel_left_2"], fg="#ffffff",
                 font=("Segoe UI", 22, "bold")).place(x=32, y=108)
        tk.Label(panel_izq, text="Sistema Integral de Facturación y Gestión Comercial",
                 bg=self.COLORS["panel_left_2"], fg="#bfdbfe",
                 font=("Segoe UI", 10), wraplength=280, justify="left").place(x=32, y=144)

        features = [
            ("", "Gestión de pólizas"),
            ("", "Control de facturación"),
            ("", "Reportes ejecutivos"),
        ]
        fy = 210
        for ico, txt in features:
            tk.Label(panel_izq, text=f"{ico}   {txt}", bg=self.COLORS["panel_left_2"],
                     fg="#e0f2fe", font=("Segoe UI", 10)).place(x=32, y=fy)
            fy += 22

        tk.Label(panel_izq, text="v1.0.0  |  © 2025", bg=self.COLORS["panel_left_2"],
                 fg="#93c5fd", font=("Segoe UI", 8)).place(x=32, y=466)

        panel_der = tk.Frame(card_inner, bg=self.COLORS["card"])
        panel_der.place(x=340, y=0, width=480, height=500)

        tk.Label(panel_der, text="Iniciar Sesión", bg=self.COLORS["card"],
                 fg=self.COLORS["text_primary"],
                 font=("Segoe UI", 20, "bold")).place(x=52, y=60)
        tk.Label(panel_der, text="Ingrese sus credenciales para acceder al sistema",
                 bg=self.COLORS["card"], fg=self.COLORS["text_secondary"],
                 font=("Segoe UI", 10)).place(x=52, y=96)

        self.lbl_mensaje = tk.Label(panel_der, text="", bg=self.COLORS["card"],
                                    fg=self.COLORS["error"], font=("Segoe UI", 10),
                                    anchor="center", justify="center")
        self.lbl_mensaje.place(x=52, y=134, width=376, height=26)

        tk.Label(panel_der, text="Usuario", bg=self.COLORS["card"],
                 fg=self.COLORS["label"], font=("Segoe UI", 10, "bold")).place(x=52, y=178)

        self._user_frame = tk.Frame(panel_der, bg=self.COLORS["input_bg"],
                                    highlightbackground=self.COLORS["input_border"],
                                    highlightthickness=1)
        self._user_frame.place(x=52, y=202, width=376, height=38)

        self.entry_usuario = tk.Entry(self._user_frame, bg=self.COLORS["input_bg"], fg=self.COLORS["text_primary"],
                                      font=("Segoe UI", 11), relief="flat", bd=0,
                                      insertbackground=self.COLORS["text_primary"])
        self.entry_usuario.place(x=10, y=6, width=346, height=26)

        tk.Label(panel_der, text="Contraseña", bg=self.COLORS["card"],
                 fg=self.COLORS["label"], font=("Segoe UI", 10, "bold")).place(x=52, y=256)

        self._pass_frame = tk.Frame(panel_der, bg=self.COLORS["input_bg"],
                                    highlightbackground=self.COLORS["input_border"],
                                    highlightthickness=1)
        self._pass_frame.place(x=52, y=280, width=376, height=38)

        self.entry_password = tk.Entry(self._pass_frame, bg=self.COLORS["input_bg"], fg=self.COLORS["text_primary"],
                                       font=("Segoe UI", 11), relief="flat", bd=0, show="•",
                                       insertbackground=self.COLORS["text_primary"])
        self.entry_password.place(x=10, y=6, width=320, height=26)

        self.btn_ver_pass = tk.Label(self._pass_frame, text="👁", bg=self.COLORS["input_bg"],
                                     fg=self.COLORS["text_secondary"], font=("Segoe UI", 12),
                                     cursor="hand2")
        self.btn_ver_pass.place(x=340, y=6, width=28, height=26)
        self.btn_ver_pass.bind("<Button-1>", lambda e: self._toggle_password())

        self.btn_login = tk.Button(panel_der, text="INICIAR SESIÓN", bg=self.COLORS["btn_bg"],
                                   fg=self.COLORS["btn_text"], font=("Segoe UI", 11, "bold"),
                                   relief="flat", cursor="hand2", activebackground=self.COLORS["btn_hover"],
                                   activeforeground=self.COLORS["btn_text"], bd=0,
                                   command=self._on_login_click)
        self.btn_login.place(x=52, y=342, width=376, height=42)

        self.lbl_estado = tk.Label(panel_der, text="", bg=self.COLORS["card"],
                                   fg=self.COLORS["text_secondary"], font=("Segoe UI", 9),
                                   anchor="center")
        self.lbl_estado.place(x=52, y=450, width=376, height=20)

        self.entry_usuario.bind("<Return>", lambda e: self.entry_password.focus_set())
        self.entry_password.bind("<Return>", lambda e: self._on_login_click())

        self.btn_login.bind("<Enter>", lambda e: self.btn_login.configure(bg=self.COLORS["btn_hover"]))
        self.btn_login.bind("<Leave>", lambda e: self.btn_login.configure(bg=self.COLORS["btn_bg"]))

    def _paint_panel_gradient(self, panel: tk.Frame):
        try:
            panel.bind("<Configure>", lambda e: self._draw_gradient(panel, e.width, e.height))
        except Exception:
            pass

    def _draw_gradient(self, widget: tk.Widget, w: int, h: int):
        try:
            c = tk.Canvas(widget, width=w, height=h, highlightthickness=0, bd=0,
                          bg=self.COLORS["panel_left_2"])
            c.place(x=0, y=0, relwidth=1, relheight=1)
            c.tag_lower("all")
            steps = max(2, h // 2)
            r1, g1, b1 = 0x1e, 0x3a, 0x8a
            r2, g2, b2 = 0x3b, 0x82, 0xf6
            for i in range(steps):
                t = i / steps
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
                color = f"#{r:02x}{g:02x}{b:02x}"
                y0 = int(i * h / steps)
                y1 = int((i + 1) * h / steps)
                c.create_rectangle(0, y0, w, y1, fill=color, outline="")
        except Exception:
            widget.configure(bg=self.COLORS["panel_left_2"])

    def _toggle_password(self):
        if self._password_visible:
            self.entry_password.config(show="•")
            self.btn_ver_pass.config(text="👁")
        else:
            self.entry_password.config(show="")
            self.btn_ver_pass.config(text="🙈")
        self._password_visible = not self._password_visible

    def _verificar_conexion(self):
        ok = self.auth.probar_conexion()
        if ok:
            self.lbl_estado.configure(text="●  Conectado a la base de datos", fg=self.COLORS["success"])
        else:
            self.lbl_estado.configure(text="⚠  Sin conexión — modo de emergencia disponible", fg=self.COLORS["warning"])

    def _mostrar_mensaje(self, texto: str, estado: str = "error"):
        color = self.COLORS["error"]
        if estado == "ok":
            color = self.COLORS["success"]
        elif estado == "info":
            color = self.COLORS["btn_bg"]
        self.lbl_mensaje.configure(text=texto, fg=color)
        if self._msg_job:
            try:
                self.after_cancel(self._msg_job)
            except Exception:
                pass
        self._msg_job = self.after(5000, lambda: self.lbl_mensaje.configure(text=""))

    def _on_login_click(self):
        username = self.entry_usuario.get().strip()
        password = self.entry_password.get()
        if not username or not password:
            self._mostrar_mensaje("Debe ingresar usuario y contraseña", "error")
            if not username:
                self._animar_error(self._user_frame)
            if not password:
                self._animar_error(self._pass_frame)
            return

        self.btn_login.configure(state="disabled", text="AUTENTICANDO...")
        self.update_idletasks()
        self.after(50, lambda: self._procesar_login(username, password))

    def _procesar_login(self, username: str, password: str):
        resultado = self.auth.autenticar(username, password)
        if resultado["exito"]:
            self._mostrar_mensaje(resultado["mensaje"], "ok")
            self.after(400, lambda: self._finalizar_login(resultado["usuario"]))
        else:
            self._mostrar_mensaje(resultado["mensaje"], "error")
            self.btn_login.configure(state="normal", text="INICIAR SESIÓN")
            self._animar_error(self._user_frame)
            self._animar_error(self._pass_frame)

    def _animar_error(self, widget: tk.Widget):
        try:
            dx = 6
            repeticiones = 3
            original_x = widget.winfo_x() if hasattr(widget, "winfo_x") else 0
            for i in range(repeticiones * 2):
                offset = dx if i % 2 == 0 else -dx
                delay = 30 + i * 10
                self.after(delay, lambda w=widget, ox=original_x, o=offset: self._shake_widget(w, ox, o))
            self.after(30 + (repeticiones * 2) * 10 + 20,
                       lambda w=widget, ox=original_x: self._shake_widget(w, ox, 0))
        except Exception:
            pass

    def _shake_widget(self, w: tk.Widget, orig_x: int, offset: int):
        try:
            parent = w.master
            info = w.place_info()
            if "x" in info:
                new_x = orig_x + offset
                w.place_configure(x=new_x)
                parent.update_idletasks()
        except Exception:
            pass

    def _finalizar_login(self, usuario: Dict[str, Any]):
        self.withdraw()
        try:
            self.on_login_success(usuario)
        finally:
            try:
                self.destroy()
            except Exception:
                pass
