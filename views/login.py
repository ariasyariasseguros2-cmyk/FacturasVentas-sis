import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Dict, Any

from controllers.auth_controller import AuthController

from utils.updater import (
    APP_VERSION,
    consultar_version_remota,
    descargar_archivo,
    aplicar_parche_y_cerrar,
    ejecutar_actualizador_y_salir,
    obtener_directorio_ejecutable,
)


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

    def __init__(
        self,
        auth: AuthController,
        on_login_success: Callable[[Dict[str, Any]], None]
    ):
        super().__init__()

        self.auth = auth
        self.on_login_success = on_login_success

        self._password_visible = False
        self._msg_job: Optional[str] = None

        # ============================================================
        # CONTROL DE ACTUALIZACIÓN
        # ============================================================

        self._actualizacion_verificada = False
        self._actualizacion_en_proceso = False
        self._login_en_proceso = False
        self._cerrando = False

        self._version_remota = None
        self._patch_url = None
        self._checksum = None

        # ============================================================
        # VENTANA
        # ============================================================

        self.title("FacturasVentas — Iniciar Sesión")
        self.geometry("960x580")
        self.minsize(900, 540)
        self.configure(bg=self.COLORS["bg"])

        self._center_window(960, 580)

        # ============================================================
        # UI
        # ============================================================

        self._construir_ui()

        # ============================================================
        # BLOQUEAR LOGIN MIENTRAS SE VERIFICA ACTUALIZACIÓN
        # ============================================================

        self.btn_login.configure(
            state="disabled",
            text="VERIFICANDO ACTUALIZACIONES..."
        )

        self.lbl_estado.configure(
            text="●  Verificando versión del sistema...",
            fg=self.COLORS["btn_bg"]
        )

        # No verificamos la BD inmediatamente.
        # Primero se verifica la actualización.
        self.after(
            100,
            self._verificar_actualizacion_inicial
        )

    # ================================================================
    # DETECTAR EJECUCIÓN LOCAL VS EXE
    # ================================================================

    def _es_exe(self) -> bool:
        """Devuelve True cuando la aplicación está ejecutándose como EXE."""
        return bool(getattr(sys, "frozen", False))

    # ================================================================
    # CENTRAR VENTANA
    # ================================================================

    def _center_window(self, w: int, h: int) -> None:
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        x = (sw - w) // 2
        y = (sh - h) // 2

        self.geometry(f"{w}x{h}+{x}+{y}")

    # ================================================================
    # CONSTRUIR UI
    # ================================================================

    def _construir_ui(self):

        container = tk.Frame(
            self,
            bg=self.COLORS["bg"]
        )

        container.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=28
        )

        card = tk.Frame(
            container,
            bg=self.COLORS["card"],
            highlightthickness=0
        )

        card.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            width=820,
            height=500
        )

        try:
            card.update_idletasks()
        except Exception:
            pass

        card_inner = tk.Frame(
            card,
            bg=self.COLORS["card"]
        )

        card_inner.pack(
            fill="both",
            expand=True
        )

        # ============================================================
        # PANEL IZQUIERDO
        # ============================================================

        panel_izq = tk.Frame(
            card_inner,
            bg=self.COLORS["panel_left_2"]
        )

        panel_izq.place(
            x=0,
            y=0,
            width=340,
            height=500
        )

        self._paint_panel_gradient(panel_izq)

        tk.Label(
            panel_izq,
            text="",
            bg=self.COLORS["panel_left_2"],
            fg="#ffffff",
            font=("Segoe UI", 36, "bold")
        ).place(
            x=32,
            y=40
        )

        tk.Label(
            panel_izq,
            text="FacturasVentas",
            bg=self.COLORS["panel_left_2"],
            fg="#ffffff",
            font=("Segoe UI", 22, "bold")
        ).place(
            x=32,
            y=108
        )

        tk.Label(
            panel_izq,
            text="Sistema de gestión de facturas",
            bg=self.COLORS["panel_left_2"],
            fg="#dbeafe",
            font=("Segoe UI", 10)
        ).place(
            x=34,
            y=148
        )

        tk.Label(
            panel_izq,
            text="SIS-ARIAS",
            bg=self.COLORS["panel_left_2"],
            fg="#ffffff",
            font=("Segoe UI", 13, "bold")
        ).place(
            x=34,
            y=190
        )

        tk.Label(
            panel_izq,
            text="Acceso seguro al sistema",
            bg=self.COLORS["panel_left_2"],
            fg="#dbeafe",
            font=("Segoe UI", 9)
        ).place(
            x=34,
            y=220
        )

        # ============================================================
        # PANEL DERECHO
        # ============================================================

        panel_der = tk.Frame(
            card_inner,
            bg=self.COLORS["card"]
        )

        panel_der.place(
            x=340,
            y=0,
            width=480,
            height=500
        )

        tk.Label(
            panel_der,
            text="Iniciar sesión",
            bg=self.COLORS["card"],
            fg=self.COLORS["text_primary"],
            font=("Segoe UI", 20, "bold")
        ).place(
            x=52,
            y=45
        )

        tk.Label(
            panel_der,
            text="Ingrese sus credenciales para continuar",
            bg=self.COLORS["card"],
            fg=self.COLORS["text_secondary"],
            font=("Segoe UI", 9)
        ).place(
            x=54,
            y=82
        )

        # ============================================================
        # USUARIO
        # ============================================================

        tk.Label(
            panel_der,
            text="Usuario",
            bg=self.COLORS["card"],
            fg=self.COLORS["label"],
            font=("Segoe UI", 9, "bold")
        ).place(
            x=52,
            y=120
        )

        self._user_frame = tk.Frame(
            panel_der,
            bg=self.COLORS["input_bg"],
            highlightbackground=self.COLORS["input_border"],
            highlightthickness=1
        )

        self._user_frame.place(
            x=52,
            y=145,
            width=376,
            height=40
        )

        self.entry_usuario = tk.Entry(
            self._user_frame,
            bg=self.COLORS["input_bg"],
            fg=self.COLORS["text_primary"],
            font=("Segoe UI", 11),
            relief="flat",
            bd=0,
            insertbackground=self.COLORS["text_primary"]
        )

        self.entry_usuario.place(
            x=10,
            y=6,
            width=356,
            height=26
        )

        # ============================================================
        # PASSWORD
        # ============================================================

        tk.Label(
            panel_der,
            text="Contraseña",
            bg=self.COLORS["card"],
            fg=self.COLORS["label"],
            font=("Segoe UI", 9, "bold")
        ).place(
            x=52,
            y=200
        )

        self._pass_frame = tk.Frame(
            panel_der,
            bg=self.COLORS["input_bg"],
            highlightbackground=self.COLORS["input_border"],
            highlightthickness=1
        )

        self._pass_frame.place(
            x=52,
            y=225,
            width=376,
            height=40
        )

        self.entry_password = tk.Entry(
            self._pass_frame,
            bg=self.COLORS["input_bg"],
            fg=self.COLORS["text_primary"],
            font=("Segoe UI", 11),
            relief="flat",
            bd=0,
            show="•",
            insertbackground=self.COLORS["text_primary"]
        )

        self.entry_password.place(
            x=10,
            y=6,
            width=320,
            height=26
        )

        self.btn_ver_pass = tk.Label(
            self._pass_frame,
            text="👁",
            bg=self.COLORS["input_bg"],
            fg=self.COLORS["text_secondary"],
            font=("Segoe UI", 12),
            cursor="hand2"
        )

        self.btn_ver_pass.place(
            x=340,
            y=6,
            width=28,
            height=26
        )

        self.btn_ver_pass.bind(
            "<Button-1>",
            lambda e: self._toggle_password()
        )

        # ============================================================
        # MENSAJE
        # ============================================================

        self.lbl_mensaje = tk.Label(
            panel_der,
            text="",
            bg=self.COLORS["card"],
            fg=self.COLORS["error"],
            font=("Segoe UI", 9),
            anchor="center"
        )

        self.lbl_mensaje.place(
            x=52,
            y=280,
            width=376,
            height=30
        )

        # ============================================================
        # BOTÓN LOGIN
        # ============================================================

        self.btn_login = tk.Button(
            panel_der,
            text="INICIAR SESIÓN",
            bg=self.COLORS["btn_bg"],
            fg=self.COLORS["btn_text"],
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            cursor="hand2",
            activebackground=self.COLORS["btn_hover"],
            activeforeground=self.COLORS["btn_text"],
            bd=0,
            command=self._on_login_click
        )

        self.btn_login.place(
            x=52,
            y=342,
            width=376,
            height=42
        )

        # ============================================================
        # ESTADO
        # ============================================================

        self.lbl_estado = tk.Label(
            panel_der,
            text="",
            bg=self.COLORS["card"],
            fg=self.COLORS["text_secondary"],
            font=("Segoe UI", 9),
            anchor="center"
        )

        self.lbl_estado.place(
            x=52,
            y=420,
            width=376,
            height=20
        )

        # ============================================================
        # VERSIÓN
        # ============================================================

        self.lbl_version = tk.Label(
            panel_der,
            text=f"v{APP_VERSION} | © 2025",
            bg=self.COLORS["card"],
            fg=self.COLORS["text_muted"],
            font=("Segoe UI", 8)
        )

        self.lbl_version.place(
            x=52,
            y=450,
            width=376,
            height=20
        )

        # ============================================================
        # EVENTOS
        # ============================================================

        self.entry_usuario.bind(
            "<Return>",
            lambda e: self.entry_password.focus_set()
        )

        self.entry_password.bind(
            "<Return>",
            lambda e: self._on_login_click()
        )

        self.btn_login.bind(
            "<Enter>",
            lambda e: self.btn_login.configure(
                bg=self.COLORS["btn_hover"]
            )
        )

        self.btn_login.bind(
            "<Leave>",
            lambda e: self.btn_login.configure(
                bg=self.COLORS["btn_bg"]
            )
        )

    # ================================================================
    # GRADIENTE
    # ================================================================

    def _paint_panel_gradient(self, panel: tk.Frame):

        try:
            panel.bind(
                "<Configure>",
                lambda e: self._draw_gradient(
                    panel,
                    e.width,
                    e.height
                )
            )

        except Exception:
            pass

    def _draw_gradient(
        self,
        widget: tk.Widget,
        w: int,
        h: int
    ):

        try:

            c = tk.Canvas(
                widget,
                width=w,
                height=h,
                highlightthickness=0,
                bd=0,
                bg=self.COLORS["panel_left_2"]
            )

            c.place(
                x=0,
                y=0,
                relwidth=1,
                relheight=1
            )

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

                c.create_rectangle(
                    0,
                    y0,
                    w,
                    y1,
                    fill=color,
                    outline=""
                )

        except Exception:
            try:
                widget.configure(
                    bg=self.COLORS["panel_left_2"]
                )
            except Exception:
                pass

    # ================================================================
    # MOSTRAR / OCULTAR PASSWORD
    # ================================================================

    def _toggle_password(self):

        if self._password_visible:

            self.entry_password.config(
                show="•"
            )

            self.btn_ver_pass.config(
                text="👁"
            )

        else:

            self.entry_password.config(
                show=""
            )

            self.btn_ver_pass.config(
                text="🙈"
            )

        self._password_visible = not self._password_visible

    # ================================================================
    # ACTUALIZACIÓN INICIAL
    # ================================================================

    def _verificar_actualizacion_inicial(self):

        if self._cerrando:
            return

        self._actualizacion_en_proceso = True

        self.btn_login.configure(
            state="disabled",
            text="VERIFICANDO..."
        )

        self.lbl_estado.configure(
            text="●  Comprobando actualización...",
            fg=self.COLORS["btn_bg"]
        )

        def _trabajo():

            try:

                resultado = consultar_version_remota(
                    timeout=15
                )

                self.after(
                    0,
                    lambda r=resultado:
                    self._finalizar_verificacion_actualizacion(r)
                )

            except Exception as e:

                self.after(
                    0,
                    lambda e=e:
                    self._error_verificacion_actualizacion(str(e))
                )

        threading.Thread(
            target=_trabajo,
            daemon=True
        ).start()

    # ================================================================
    # RESULTADO ACTUALIZACIÓN
    # ================================================================

    def _finalizar_verificacion_actualizacion(
        self,
        resultado: Dict[str, Any]
    ):

        if self._cerrando:
            return

        self._actualizacion_en_proceso = False

        if not resultado.get("ok"):

            self._mostrar_error_actualizacion(
                resultado.get(
                    "error",
                    "No se pudo comprobar la versión del sistema."
                )
            )

            return

        hay_actualizacion = bool(
            resultado.get("hay_actualizacion")
        )

        if not hay_actualizacion:

            self._actualizacion_verificada = True

            self.lbl_estado.configure(
                text="●  Buscando conexión con la base de datos...",
                fg=self.COLORS["btn_bg"]
            )

            self._verificar_conexion()

            self.btn_login.configure(
                state="normal",
                text="INICIAR SESIÓN"
            )

            self.after(
                150,
                lambda: self.entry_usuario.focus_set()
            )

            return

        # ============================================================
        # HAY ACTUALIZACIÓN
        # ============================================================

        # En desarrollo (python main.py) NO se descarga ni se aplica
        # el ZIP. El auto-parche requiere una aplicación compilada
        # como EXE. Se permite continuar normalmente con el login.
        if not self._es_exe():
            self._actualizacion_verificada = True

            self.lbl_estado.configure(
                text="●  Modo desarrollo — actualización omitida",
                fg=self.COLORS["warning"]
            )

            self._mostrar_mensaje(
                (
                    f"Actualización disponible "
                    f"(v{resultado.get('version_remota', 'nueva')}). "
                    "Se omitió porque estás ejecutando Python localmente."
                ),
                "info"
            )

            self._verificar_conexion()

            self.btn_login.configure(
                state="normal",
                text="INICIAR SESIÓN"
            )

            self.after(
                150,
                lambda: self.entry_usuario.focus_set()
            )

            return

        self._version_remota = resultado.get(
            "version_remota"
        )

        self._patch_url = resultado.get(
            "patch_url"
        )

        self._checksum = resultado.get(
            "checksum_sha256"
        )

        if not self._patch_url:

            self._mostrar_error_actualizacion(
                "Existe una actualización disponible, "
                "pero el servidor no proporcionó patch_url."
            )

            return

        self._mostrar_actualizacion_obligatoria(
            resultado
        )

    # ================================================================
    # ACTUALIZACIÓN OBLIGATORIA
    # ================================================================

    def _mostrar_actualizacion_obligatoria(
        self,
        resultado: Dict[str, Any]
    ):

        version_nueva = (
            resultado.get("version_remota")
            or "nueva"
        )

        notas = resultado.get("release_notes") or resultado.get("notas") or []

        if isinstance(notas, list):
            notas = "\n".join(
                f"• {str(nota)}"
                for nota in notas
            )

        if not notas:
            notas = "Se ha publicado una nueva versión del sistema."

        self.lbl_estado.configure(
            text=f"●  Actualización requerida: v{version_nueva}",
            fg=self.COLORS["warning"]
        )

        # No preguntamos si desea actualizar.
        # La actualización es obligatoria.
        messagebox.showinfo(
            "Actualización obligatoria",
            (
                f"Hay una nueva versión disponible.\n\n"
                f"Versión instalada: {APP_VERSION}\n"
                f"Nueva versión: {version_nueva}\n\n"
                f"{notas}\n\n"
                "La actualización se instalará ahora.\n"
                "No podrá iniciar sesión hasta completar "
                "la actualización."
            ),
            parent=self
        )

        self._iniciar_actualizacion_login()

    # ================================================================
    # INICIAR ACTUALIZACIÓN
    # ================================================================

    def _iniciar_actualizacion_login(self):

        if self._actualizacion_en_proceso:
            return

        if not self._patch_url:

            self._mostrar_error_actualizacion(
                "No existe una URL válida para descargar "
                "la actualización."
            )

            return

        self._actualizacion_en_proceso = True

        self.btn_login.configure(
            state="disabled",
            text="ACTUALIZANDO..."
        )

        self._mostrar_progreso_actualizacion(
            self._patch_url,
            self._checksum,
            self._version_remota
        )

    # ================================================================
    # DIÁLOGO PROGRESO
    # ================================================================

    def _mostrar_progreso_actualizacion(
        self,
        patch_url: str,
        checksum: Optional[str],
        version_remota: Optional[str]
    ):

        dlg = tk.Toplevel(self)

        dlg.title("Actualización")
        dlg.configure(bg="#ffffff")
        dlg.geometry("460x220")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        dlg.protocol(
            "WM_DELETE_WINDOW",
            lambda: None
        )

        dlg.update_idletasks()

        x = (
            self.winfo_rootx()
            + (self.winfo_width() - 460) // 2
        )

        y = (
            self.winfo_rooty()
            + (self.winfo_height() - 220) // 2
        )

        dlg.geometry(
            f"+{max(x, 50)}+{max(y, 50)}"
        )

        tk.Label(
            dlg,
            text="📦",
            bg="#ffffff",
            fg="#2563eb",
            font=("Segoe UI", 26)
        ).pack(
            pady=(18, 4)
        )

        tk.Label(
            dlg,
            text=f"Actualizando a v{version_remota}",
            bg="#ffffff",
            fg="#0f172a",
            font=("Segoe UI", 11, "bold")
        ).pack()

        lbl_estado = tk.Label(
            dlg,
            text="Preparando descarga...",
            bg="#ffffff",
            fg="#64748b",
            font=("Segoe UI", 9)
        )

        lbl_estado.pack(
            pady=(2, 0)
        )

        pb_frame = tk.Frame(
            dlg,
            bg="#ffffff"
        )

        pb_frame.pack(
            fill="x",
            padx=28,
            pady=(12, 0)
        )

        estilo = ttk.Style(dlg)

        try:
            estilo.theme_use("clam")
        except Exception:
            pass

        estilo.configure(
            "FV.Horizontal.TProgressbar",
            troughcolor="#e2e8f0",
            background="#2563eb",
            bordercolor="#ffffff",
            lightcolor="#2563eb",
            darkcolor="#1d4ed8"
        )

        pb = ttk.Progressbar(
            pb_frame,
            style="FV.Horizontal.TProgressbar",
            orient="horizontal",
            length=400,
            mode="determinate"
        )

        pb.pack(
            fill="x"
        )

        pb["maximum"] = 100
        pb["value"] = 0

        lbl_porcentaje = tk.Label(
            dlg,
            text="0%",
            bg="#ffffff",
            fg="#2563eb",
            font=("Segoe UI", 9, "bold")
        )

        lbl_porcentaje.pack(
            pady=(4, 0)
        )

        self._ejecutar_descarga_actualizacion(
            dlg,
            pb,
            lbl_estado,
            lbl_porcentaje,
            patch_url,
            checksum,
            version_remota
        )

    # ================================================================
    # DESCARGAR Y PREPARAR PARCHE
    # ================================================================

    def _ejecutar_descarga_actualizacion(
        self,
        dlg,
        pb,
        lbl_estado,
        lbl_porcentaje,
        patch_url: str,
        checksum: Optional[str],
        version_remota: Optional[str]
    ):

        dir_app = obtener_directorio_ejecutable()

        # IMPORTANTE:
        # usamos ZIP real, no .patch
        nombre_zip = (
            f"FacturasVentas-"
            f"{str(version_remota).replace('.', '_')}.zip"
        )

        ruta_updates = os.path.join(
            dir_app,
            "_updates"
        )

        ruta_zip = os.path.join(
            ruta_updates,
            nombre_zip
        )

        os.makedirs(
            ruta_updates,
            exist_ok=True
        )

        ultimo_porcentaje = [-1]

        # ============================================================
        # PROGRESO DESCARGA
        # ============================================================

        def prog_descarga(
            actual: int,
            total: int
        ):

            if total <= 0:
                return

            pct = int(
                (actual / total) * 100
            )

            if pct == ultimo_porcentaje[0]:
                return

            ultimo_porcentaje[0] = pct

            mb_act = actual / (
                1024 * 1024
            )

            mb_tot = total / (
                1024 * 1024
            )

            self.after(
                0,
                lambda:
                self._ui_set_progreso(
                    pb,
                    lbl_porcentaje,
                    lbl_estado,
                    pct,
                    (
                        f"Descargando... "
                        f"{mb_act:.1f} / "
                        f"{mb_tot:.1f} MB"
                    )
                )
            )

        # ============================================================
        # PROGRESO EXTRACCIÓN
        # ============================================================

        def prog_extraccion(
            actual: int,
            total: int
        ):

            if total <= 0:
                return

            pct = int(
                (actual / total) * 100
            )

            self.after(
                0,
                lambda:
                self._ui_set_progreso(
                    pb,
                    lbl_porcentaje,
                    lbl_estado,
                    pct,
                    (
                        f"Instalando archivos... "
                        f"{actual}/{total}"
                    )
                )
            )

        # ============================================================
        # TRABAJO EN SEGUNDO PLANO
        # ============================================================

        def _trabajo():

            try:

                # ----------------------------------------------------
                # DESCARGA
                # ----------------------------------------------------

                self.after(
                    0,
                    lambda:
                    lbl_estado.configure(
                        text="Descargando actualización..."
                    )
                )

                descarga = descargar_archivo(
                    patch_url,
                    ruta_zip,
                    progress_cb=prog_descarga
                )

                if not descarga.get("ok"):

                    error = descarga.get(
                        "error"
                    )

                    if not error:
                        errores = (
                            descarga.get("errores")
                            or []
                        )

                        error = (
                            errores[-1]
                            if errores
                            else "Error desconocido."
                        )

                    self.after(
                        0,
                        lambda e=error:
                        self._ui_error_progreso(
                            dlg,
                            str(e)
                        )
                    )

                    return

                # ----------------------------------------------------
                # CHECKSUM
                # ----------------------------------------------------

                self.after(
                    0,
                    lambda:
                    lbl_estado.configure(
                        text="Verificando integridad..."
                    )
                )

                self.after(
                    0,
                    lambda:
                    self._ui_set_progreso(
                        pb,
                        lbl_porcentaje,
                        lbl_estado,
                        100,
                        "Descarga completada. Verificando..."
                    )
                )

                # ----------------------------------------------------
                # PREPARAR PARCHE
                # ----------------------------------------------------

                self.after(
                    0,
                    lambda:
                    lbl_estado.configure(
                        text="Preparando instalación..."
                    )
                )

                patch_result = aplicar_parche_y_cerrar(
                    ruta_zip,
                    checksum_esperado=checksum,
                    extraer_progress_cb=prog_extraccion
                )

                if not patch_result.get("ok"):

                    error = patch_result.get(
                        "error",
                        "No se pudo preparar la actualización."
                    )

                    self.after(
                        0,
                        lambda e=error:
                        self._ui_error_progreso(
                            dlg,
                            str(e)
                        )
                    )

                    return

                ruta_bat = patch_result.get(
                    "bat_path"
                )

                if not ruta_bat:

                    self.after(
                        0,
                        lambda:
                        self._ui_error_progreso(
                            dlg,
                            "No se generó el script de actualización."
                        )
                    )

                    return

                # ----------------------------------------------------
                # LISTO PARA CERRAR
                # ----------------------------------------------------

                self.after(
                    0,
                    lambda:
                    self._ui_set_progreso(
                        pb,
                        lbl_porcentaje,
                        lbl_estado,
                        100,
                        "Actualización preparada. Reiniciando..."
                    )
                )

                self.after(
                    800,
                    lambda:
                    self._ejecutar_actualizador(
                        dlg,
                        ruta_bat
                    )
                )

            except Exception as e:

                self.after(
                    0,
                    lambda e=e:
                    self._ui_error_progreso(
                        dlg,
                        str(e)
                    )
                )

        threading.Thread(
            target=_trabajo,
            daemon=True
        ).start()

    # ================================================================
    # EJECUTAR BAT
    # ================================================================

    def _ejecutar_actualizador(
        self,
        dlg,
        ruta_bat: str
    ):

        if self._cerrando:
            return

        if not ruta_bat or not os.path.exists(ruta_bat):

            self._ui_error_progreso(
                dlg,
                "No se encontró el script de actualización."
            )

            return

        try:
            dlg.grab_release()
        except Exception:
            pass

        try:
            dlg.destroy()
        except Exception:
            pass

        # ============================================================
        # LANZAMOS EL BAT
        # ============================================================

        ok = ejecutar_actualizador_y_salir(
            ruta_bat
        )

        if not ok:

            self._actualizacion_en_proceso = False

            self.btn_login.configure(
                state="disabled",
                text="ACTUALIZACIÓN REQUERIDA"
            )

            messagebox.showerror(
                "Actualización",
                (
                    "No se pudo iniciar el actualizador.\n\n"
                    "La aplicación no puede continuar "
                    "hasta completar la actualización."
                ),
                parent=self
            )

            return

        # ============================================================
        # IMPORTANTE:
        #
        # NO usamos sys.exit()
        # NO usamos os._exit()
        #
        # Destruimos la ventana raíz.
        # El BAT queda encargado de esperar al proceso,
        # reemplazar el EXE y abrir la nueva versión.
        # ============================================================

        self._cerrando = True

        try:
            self.auth.cerrar_sesion()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass

    # ================================================================
    # ERROR VERIFICACIÓN
    # ================================================================

    def _error_verificacion_actualizacion(
        self,
        mensaje: str
    ):

        self._actualizacion_en_proceso = False

        self._mostrar_error_actualizacion(
            mensaje
        )

    # ================================================================
    # ERROR ACTUALIZACIÓN
    # ================================================================

    def _mostrar_error_actualizacion(
        self,
        mensaje: str
    ):

        self.btn_login.configure(
            state="disabled",
            text="ACTUALIZACIÓN REQUERIDA"
        )

        self.lbl_estado.configure(
            text="⚠  No se pudo verificar la actualización",
            fg=self.COLORS["error"]
        )

        self._mostrar_mensaje(
            (
                "No puede iniciar sesión hasta "
                "verificar la actualización."
            ),
            "error"
        )

        messagebox.showerror(
            "Actualización",
            (
                "No se puede continuar.\n\n"
                f"{mensaje}\n\n"
                "Verifique su conexión a Internet "
                "y vuelva a abrir FacturasVentas."
            ),
            parent=self
        )

    # ================================================================
    # PROGRESO UI
    # ================================================================

    def _ui_set_progreso(
        self,
        pb,
        lbl_porcentaje,
        lbl_estado,
        pct: int,
        estado: str
    ):

        try:

            pct = max(
                0,
                min(
                    100,
                    int(pct)
                )
            )

            pb["value"] = pct

            lbl_porcentaje.configure(
                text=f"{pct}%"
            )

            lbl_estado.configure(
                text=estado
            )

        except Exception:
            pass

    # ================================================================
    # ERROR DEL DIÁLOGO
    # ================================================================

    def _ui_error_progreso(
        self,
        dlg,
        mensaje: str
    ):

        self._actualizacion_en_proceso = False

        try:

            for widget in dlg.winfo_children():
                widget.destroy()

            tk.Label(
                dlg,
                text="⚠",
                bg="#ffffff",
                fg="#dc2626",
                font=("Segoe UI", 28)
            ).pack(
                pady=(18, 4)
            )

            tk.Label(
                dlg,
                text="No se pudo completar la actualización",
                bg="#ffffff",
                fg="#0f172a",
                font=("Segoe UI", 11, "bold")
            ).pack()

            tk.Label(
                dlg,
                text=str(mensaje)[:300],
                bg="#ffffff",
                fg="#64748b",
                font=("Segoe UI", 9),
                wraplength=380,
                justify="center"
            ).pack(
                padx=18,
                pady=(6, 14)
            )

            tk.Button(
                dlg,
                text="Cerrar",
                bg="#f1f5f9",
                fg="#0f172a",
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                bd=0,
                cursor="hand2",
                activebackground="#e2e8f0",
                command=dlg.destroy
            ).pack(
                pady=(0, 14)
            )

        except Exception:
            pass

    # ================================================================
    # CONEXIÓN BD
    # ================================================================

    def _verificar_conexion(self):

        try:

            ok = self.auth.probar_conexion()

            if ok:

                self.lbl_estado.configure(
                    text="●  Conectado a la base de datos",
                    fg=self.COLORS["success"]
                )

            else:

                self.lbl_estado.configure(
                    text=(
                        "⚠  Sin conexión — "
                        "modo de emergencia disponible"
                    ),
                    fg=self.COLORS["warning"]
                )

        except Exception:

            self.lbl_estado.configure(
                text=(
                    "⚠  No se pudo comprobar "
                    "la conexión"
                ),
                fg=self.COLORS["warning"]
            )

    # ================================================================
    # MENSAJE
    # ================================================================

    def _mostrar_mensaje(
        self,
        texto: str,
        estado: str = "error"
    ):

        color = self.COLORS["error"]

        if estado == "ok":
            color = self.COLORS["success"]

        elif estado == "info":
            color = self.COLORS["btn_bg"]

        self.lbl_mensaje.configure(
            text=texto,
            fg=color
        )

        if self._msg_job:

            try:
                self.after_cancel(
                    self._msg_job
                )
            except Exception:
                pass

        self._msg_job = self.after(
            5000,
            lambda:
            self.lbl_mensaje.configure(
                text=""
            )
        )

    # ================================================================
    # LOGIN
    # ================================================================

    def _on_login_click(self):

        # ============================================================
        # SEGURIDAD:
        # JAMÁS PERMITIR LOGIN SIN HABER VERIFICADO ACTUALIZACIÓN
        # ============================================================

        if not self._actualizacion_verificada:

            self._mostrar_mensaje(
                "Debe completarse la actualización antes de iniciar sesión.",
                "error"
            )

            return

        if self._actualizacion_en_proceso:

            self._mostrar_mensaje(
                "La actualización está en proceso. Espere...",
                "info"
            )

            return

        if self._login_en_proceso:
            return

        username = self.entry_usuario.get().strip()
        password = self.entry_password.get()

        if not username or not password:

            self._mostrar_mensaje(
                "Debe ingresar usuario y contraseña",
                "error"
            )

            if not username:
                self._animar_error(
                    self._user_frame
                )

            if not password:
                self._animar_error(
                    self._pass_frame
                )

            return

        self._login_en_proceso = True

        self.btn_login.configure(
            state="disabled",
            text="AUTENTICANDO..."
        )

        self.update_idletasks()

        self.after(
            50,
            lambda:
            self._procesar_login(
                username,
                password
            )
        )

    # ================================================================
    # PROCESAR LOGIN
    # ================================================================

    def _procesar_login(
        self,
        username: str,
        password: str
    ):

        try:

            resultado = self.auth.autenticar(
                username,
                password
            )

            if resultado["exito"]:

                self._mostrar_mensaje(
                    resultado["mensaje"],
                    "ok"
                )

                self.after(
                    400,
                    lambda:
                    self._finalizar_login(
                        resultado["usuario"]
                    )
                )

            else:

                self._login_en_proceso = False

                self._mostrar_mensaje(
                    resultado["mensaje"],
                    "error"
                )

                self.btn_login.configure(
                    state="normal",
                    text="INICIAR SESIÓN"
                )

                self._animar_error(
                    self._user_frame
                )

                self._animar_error(
                    self._pass_frame
                )

        except Exception as e:

            self._login_en_proceso = False

            self._mostrar_mensaje(
                f"Error al iniciar sesión: {e}",
                "error"
            )

            self.btn_login.configure(
                state="normal",
                text="INICIAR SESIÓN"
            )

    # ================================================================
    # FINALIZAR LOGIN
    # ================================================================

    def _finalizar_login(
        self,
        usuario: Dict[str, Any]
    ):

        if self._cerrando:
            return

        self.withdraw()

        try:

            self.on_login_success(
                usuario
            )

        finally:

            try:
                self.destroy()
            except Exception:
                pass

    # ================================================================
    # ANIMACIÓN ERROR
    # ================================================================

    def _animar_error(
        self,
        widget: tk.Widget
    ):

        try:

            dx = 6
            repeticiones = 3

            original_x = (
                widget.winfo_x()
                if hasattr(widget, "winfo_x")
                else 0
            )

            for i in range(
                repeticiones * 2
            ):

                offset = (
                    dx
                    if i % 2 == 0
                    else -dx
                )

                delay = (
                    30 + i * 10
                )

                self.after(
                    delay,
                    lambda
                    w=widget,
                    ox=original_x,
                    o=offset:
                    self._shake_widget(
                        w,
                        ox,
                        o
                    )
                )

            self.after(
                30
                + (repeticiones * 2) * 10
                + 20,
                lambda
                w=widget,
                ox=original_x:
                self._shake_widget(
                    w,
                    ox,
                    0
                )
            )

        except Exception:
            pass

    # ================================================================
    # SHAKE
    # ================================================================

    def _shake_widget(
        self,
        w: tk.Widget,
        orig_x: int,
        offset: int
    ):

        try:

            parent = w.master
            info = w.place_info()

            if "x" in info:

                new_x = (
                    orig_x
                    + offset
                )

                w.place_configure(
                    x=new_x
                )

                parent.update_idletasks()

        except Exception:
            pass

    # ================================================================
    # CIERRE DE VENTANA
    # ================================================================

    def destroy(self):

        self._cerrando = True

        try:
            self.auth.cerrar_sesion()
        except Exception:
            pass

        try:
            super().destroy()
        except Exception:
            pass