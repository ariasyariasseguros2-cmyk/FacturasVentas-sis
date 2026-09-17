import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Any

from controllers.auth_controller import AuthController

from utils.updater import (
    APP_VERSION,
    consultar_version_remota,
    descargar_archivo,
    aplicar_parche_y_cerrar,
    ejecutar_actualizador_y_salir,
    obtener_directorio_updates,
)


class LoginWindow(tk.Tk):

    def __init__(
        self,
        auth: Optional[AuthController] = None,
        on_login_success: Optional[Callable[[Any], None]] = None,
    ):
        super().__init__()

        # ====================================================
        # CONFIGURACIÓN
        # ====================================================

        self.title("FacturasVentas")
        self.geometry("460x520")
        self.resizable(False, False)

        self.protocol(
            "WM_DELETE_WINDOW",
            self._cerrar_ventana,
        )

        # ====================================================
        # AUTH
        # ====================================================

        self.auth = auth if auth is not None else AuthController()

        self.on_login_success = on_login_success

        # ====================================================
        # ESTADOS
        # ====================================================

        self._cerrando = False
        self._actualizacion_verificada = False
        self._actualizacion_en_proceso = False
        self._conectando_bd = False

        # ====================================================
        # DATOS ACTUALIZACIÓN
        # ====================================================

        self.version_remota = None
        self.patch_url = None
        self.checksum_sha256 = None
        self.release_notes = ""

        # ====================================================
        # VARIABLES
        # ====================================================

        self.var_usuario = tk.StringVar()
        self.var_password = tk.StringVar()

        self.var_estado = tk.StringVar(
            value="VERIFICANDO ACTUALIZACIONES..."
        )

        self.var_version = tk.StringVar(
            value=f"Versión {APP_VERSION}"
        )

        # ====================================================
        # INTERFAZ
        # ====================================================

        self._crear_interfaz()
        self._centrar_ventana()

        # ====================================================
        # VERIFICAR ACTUALIZACIÓN
        # ====================================================

        self.after(
            300,
            self._iniciar_verificacion_actualizacion,
        )

    # ========================================================
    # CENTRAR
    # ========================================================

    def _centrar_ventana(self):

        try:

            self.update_idletasks()

            ancho = 460
            alto = 520

            pantalla_ancho = self.winfo_screenwidth()
            pantalla_alto = self.winfo_screenheight()

            x = int((pantalla_ancho - ancho) / 2)
            y = int((pantalla_alto - alto) / 2)

            self.geometry(
                f"{ancho}x{alto}+{x}+{y}"
            )

        except Exception:
            pass

    # ========================================================
    # INTERFAZ
    # ========================================================

    def _crear_interfaz(self):

        frame = ttk.Frame(self)

        frame.pack(
            fill="both",
            expand=True,
            padx=40,
            pady=30,
        )

        # ====================================================
        # TÍTULO
        # ====================================================

        ttk.Label(
            frame,
            text="FacturasVentas",
            font=("Segoe UI", 24, "bold"),
        ).pack(
            pady=(15, 5)
        )

        ttk.Label(
            frame,
            text="Sistema de gestión",
            font=("Segoe UI", 11),
        ).pack(
            pady=(0, 30)
        )

        # ====================================================
        # USUARIO
        # ====================================================

        ttk.Label(
            frame,
            text="Usuario",
            font=("Segoe UI", 10),
        ).pack(
            anchor="w"
        )

        self.entry_usuario = ttk.Entry(
            frame,
            textvariable=self.var_usuario,
            font=("Segoe UI", 11),
        )

        self.entry_usuario.pack(
            fill="x",
            pady=(5, 15),
        )

        # ====================================================
        # CONTRASEÑA
        # ====================================================

        ttk.Label(
            frame,
            text="Contraseña",
            font=("Segoe UI", 10),
        ).pack(
            anchor="w"
        )

        self.entry_password = ttk.Entry(
            frame,
            textvariable=self.var_password,
            show="*",
            font=("Segoe UI", 11),
        )

        self.entry_password.pack(
            fill="x",
            pady=(5, 20),
        )

        # ====================================================
        # BOTÓN
        # ====================================================

        self.btn_login = ttk.Button(
            frame,
            text="Iniciar sesión",
            command=self._iniciar_login,
        )

        self.btn_login.pack(
            fill="x",
            ipady=6,
            pady=(0, 20),
        )

        # ====================================================
        # ESTADO
        # ====================================================

        ttk.Label(
            frame,
            textvariable=self.var_estado,
            font=("Segoe UI", 9),
        ).pack(
            pady=(5, 5)
        )

        # ====================================================
        # PROGRESO
        # ====================================================

        self.progress = ttk.Progressbar(
            frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
        )

        # ====================================================
        # VERSIÓN
        # ====================================================

        ttk.Label(
            frame,
            textvariable=self.var_version,
            font=("Segoe UI", 8),
        ).pack(
            side="bottom",
            pady=(20, 0),
        )

        # ====================================================
        # ENTER
        # ====================================================

        self.entry_usuario.bind(
            "<Return>",
            lambda event: self._iniciar_login(),
        )

        self.entry_password.bind(
            "<Return>",
            lambda event: self._iniciar_login(),
        )

        # ====================================================
        # DESACTIVAR
        # ====================================================

        self._habilitar_login(False)

    # ========================================================
    # HABILITAR LOGIN
    # ========================================================

    def _habilitar_login(self, habilitar: bool):

        estado = "normal" if habilitar else "disabled"

        try:

            self.entry_usuario.config(
                state=estado
            )

            self.entry_password.config(
                state=estado
            )

            self.btn_login.config(
                state=estado
            )

        except tk.TclError:
            pass

    # ========================================================
    # MOSTRAR PROGRESO
    # ========================================================

    def _mostrar_progreso(self):

        try:

            self.progress.pack(
                fill="x",
                pady=(0, 10),
            )

        except tk.TclError:
            pass

    # ========================================================
    # OCULTAR PROGRESO
    # ========================================================

    def _ocultar_progreso(self):

        try:
            self.progress.pack_forget()
        except tk.TclError:
            pass

    # ========================================================
    # PROGRESO
    # ========================================================

    def _set_progreso(self, valor):

        try:

            valor = float(valor)

            valor = max(
                0,
                min(100, valor),
            )

            self.progress["value"] = valor

        except Exception:
            pass

    # ========================================================
    # AFTER SEGURO
    # ========================================================

    def _after_ui(
        self,
        callback,
        *args,
    ):

        if self._cerrando:
            return

        try:

            self.after(
                0,
                lambda: self._ejecutar_ui(
                    callback,
                    *args,
                ),
            )

        except tk.TclError:
            pass

    # ========================================================
    # EJECUTAR UI
    # ========================================================

    def _ejecutar_ui(
        self,
        callback,
        *args,
    ):

        if self._cerrando:
            return

        try:

            callback(*args)

        except tk.TclError:
            pass

        except Exception as e:

            print(
                f"[LOGIN] Error UI: {e}"
            )

    # ========================================================
    # ACTUALIZACIONES
    # ========================================================

    def _iniciar_verificacion_actualizacion(self):

        if self._cerrando:
            return

        self.var_estado.set(
            "VERIFICANDO ACTUALIZACIONES..."
        )

        threading.Thread(
            target=self._hilo_verificar_actualizacion,
            daemon=True,
        ).start()

    # ========================================================
    # HILO ACTUALIZACIÓN
    # ========================================================

    def _hilo_verificar_actualizacion(self):

        try:

            print(
                "[LOGIN] Consultando versión remota..."
            )

            resultado = consultar_version_remota(
                timeout=15
            )

            print(
                f"[LOGIN] Resultado actualización: {resultado}"
            )

            if not isinstance(
                resultado,
                dict,
            ):

                self._after_ui(
                    self._actualizacion_error,
                    "Respuesta inválida del servidor.",
                )

                return

            if not resultado.get(
                "ok",
                False,
            ):

                self._after_ui(
                    self._actualizacion_error,
                    resultado.get(
                        "error",
                        "No se pudo verificar la versión.",
                    ),
                )

                return

            self.version_remota = resultado.get(
                "version_remota"
            )

            self.patch_url = resultado.get(
                "patch_url"
            )

            self.checksum_sha256 = resultado.get(
                "checksum_sha256"
            )

            self.release_notes = (
                resultado.get("release_notes")
                or resultado.get("notas")
                or ""
            )

            hay_actualizacion = bool(
                resultado.get(
                    "hay_actualizacion",
                    False,
                )
            )

            if hay_actualizacion:

                self._after_ui(
                    self._actualizacion_disponible
                )

            else:

                self._after_ui(
                    self._actualizacion_completa
                )

        except Exception as e:

            print(
                f"[LOGIN] Error actualización: {e}"
            )

            self._after_ui(
                self._actualizacion_error,
                str(e),
            )

    # ========================================================
    # ACTUALIZACIÓN COMPLETA
    # ========================================================

    def _actualizacion_completa(self):

        if self._cerrando:
            return

        self._actualizacion_verificada = True

        self.var_estado.set(
            "Versión actualizada. Verificando conexión..."
        )

        self._verificar_conexion_bd()

    # ========================================================
    # ERROR ACTUALIZACIÓN
    # ========================================================

    def _actualizacion_error(
        self,
        mensaje,
    ):

        if self._cerrando:
            return

        print(
            f"[LOGIN] Error actualización: {mensaje}"
        )

        self._actualizacion_verificada = True

        self.var_estado.set(
            "No se pudo verificar actualización. Verificando conexión..."
        )

        self._verificar_conexion_bd()

    # ========================================================
    # ACTUALIZACIÓN DISPONIBLE
    # ========================================================

    def _actualizacion_disponible(self):

        if self._cerrando:
            return

        version = (
            self.version_remota
            or "nueva"
        )

        # ====================================================
        # DESARROLLO
        # ====================================================

        if not getattr(
            sys,
            "frozen",
            False,
        ):

            messagebox.showinfo(
                "Actualización disponible",
                (
                    f"Hay una nueva versión disponible: v{version}\n\n"
                    "Estás ejecutando la aplicación en modo desarrollo.\n\n"
                    "La actualización automática se ejecutará "
                    "cuando la aplicación esté instalada como EXE."
                ),
                parent=self,
            )

            self._actualizacion_verificada = True

            self.var_estado.set(
                "Modo desarrollo. Verificando conexión..."
            )

            self._verificar_conexion_bd()

            return

        # ====================================================
        # EXE
        # ====================================================

        texto = (
            "Hay una nueva versión disponible.\n\n"
            f"Versión instalada: v{APP_VERSION}\n"
            f"Nueva versión: v{version}\n\n"
        )

        if self.release_notes:

            texto += (
                "Cambios:\n"
                f"{self.release_notes}\n\n"
            )

        texto += (
            "La actualización es obligatoria para continuar."
        )

        continuar = messagebox.askyesno(
            "Actualización requerida",
            texto,
            parent=self,
        )

        if not continuar:

            self.var_estado.set(
                "Actualización pendiente. No se puede iniciar sesión."
            )

            self._habilitar_login(False)

            return

        if not self.patch_url:

            messagebox.showerror(
                "Actualización",
                (
                    "El servidor indicó que existe una actualización "
                    "pero no proporcionó la URL del archivo."
                ),
                parent=self,
            )

            self.var_estado.set(
                "Error de actualización."
            )

            return

        self._actualizacion_en_proceso = True

        self._habilitar_login(False)

        self._mostrar_progreso()

        self._set_progreso(0)

        self.var_estado.set(
            f"Descargando versión v{version}..."
        )

        threading.Thread(
            target=self._hilo_descargar_actualizacion,
            daemon=True,
        ).start()

    # ========================================================
    # DESCARGAR
    # ========================================================

    def _hilo_descargar_actualizacion(self):

        try:

            updates_dir = obtener_directorio_updates()

            version_texto = str(
                self.version_remota
                or "update"
            )

            nombre_zip = (
                f"FacturasVentas-"
                f"{version_texto.replace('.', '_')}"
                f".zip"
            )

            ruta_zip = os.path.join(
                updates_dir,
                nombre_zip,
            )

            print(
                f"[LOGIN] URL ZIP: {self.patch_url}"
            )

            print(
                f"[LOGIN] ZIP destino: {ruta_zip}"
            )

            def progreso_descarga(
                porcentaje,
                *args,
                **kwargs,
            ):

                try:
                    porcentaje = float(
                        porcentaje
                    )
                except Exception:
                    return

                self._after_ui(
                    self._set_progreso,
                    porcentaje,
                )

            descarga = descargar_archivo(
                self.patch_url,
                ruta_zip,
                progress_cb=progreso_descarga,
            )

            if not descarga.get("ok"):

                raise RuntimeError(
                    "No se pudo descargar el parche: "
                    + descarga.get(
                        "error",
                        "Error desconocido.",
                    )
                )

            print(
                "[LOGIN] Descarga completada"
            )

            self._after_ui(
                self.var_estado.set,
                "Verificando archivo descargado...",
            )

            self._after_ui(
                self._set_progreso,
                0,
            )

            def progreso_extraccion(
                porcentaje,
                *args,
                **kwargs,
            ):

                try:
                    porcentaje = float(
                        porcentaje
                    )
                except Exception:
                    return

                self._after_ui(
                    self._set_progreso,
                    porcentaje,
                )

            patch_result = aplicar_parche_y_cerrar(
                ruta_zip,
                checksum_esperado=self.checksum_sha256,
                extraer_progress_cb=progreso_extraccion,
            )

            print(
                f"[LOGIN] Resultado parche: {patch_result}"
            )

            if not isinstance(
                patch_result,
                dict,
            ):

                raise RuntimeError(
                    "El actualizador no devolvió un resultado válido."
                )

            ruta_bat = patch_result.get(
                "bat_path"
            )

            if not ruta_bat:

                raise RuntimeError(
                    "No se generó el archivo BAT del actualizador."
                )

            self._after_ui(
                self.var_estado.set,
                "Preparando actualización...",
            )

            self._after_ui(
                self._set_progreso,
                100,
            )

            self._after_ui(
                self._ejecutar_actualizador,
                ruta_bat,
            )

        except Exception as e:

            print(
                f"[LOGIN] Error actualizando: {e}"
            )

            self._after_ui(
                self._actualizacion_fallida,
                str(e),
            )

    # ========================================================
    # EJECUTAR ACTUALIZADOR
    # ========================================================

    def _ejecutar_actualizador(
        self,
        ruta_bat,
    ):

        if self._cerrando:
            return

        try:

            print(
                f"[LOGIN] Ejecutando BAT: {ruta_bat}"
            )

            resultado = ejecutar_actualizador_y_salir(
                ruta_bat
            )

            print(
                f"[LOGIN] Resultado actualizador: {resultado}"
            )

            if not resultado:

                raise RuntimeError(
                    "No se pudo iniciar el actualizador."
                )

            self._cerrando = True

            try:
                self.auth.cerrar_sesion()
            except Exception:
                pass

            try:
                self.quit()
            except Exception:
                pass

            try:
                self.destroy()
            except Exception:
                pass

        except Exception as e:

            print(
                f"[LOGIN] Error ejecutando actualizador: {e}"
            )

            self._actualizacion_fallida(
                str(e)
            )

    # ========================================================
    # ACTUALIZACIÓN FALLIDA
    # ========================================================

    def _actualizacion_fallida(
        self,
        mensaje,
    ):

        if self._cerrando:
            return

        self._actualizacion_en_proceso = False

        self._ocultar_progreso()

        self.var_estado.set(
            "Error durante la actualización."
        )

        messagebox.showerror(
            "Actualización",
            (
                "No se pudo completar la actualización.\n\n"
                f"Detalle:\n{mensaje}"
            ),
            parent=self,
        )

        self._habilitar_login(False)

    # ========================================================
    # CONEXIÓN BD
    # ========================================================

    def _verificar_conexion_bd(self):

        if self._cerrando:
            return

        if self._conectando_bd:
            return

        self._conectando_bd = True

        self.var_estado.set(
            "Verificando conexión a la base de datos..."
        )

        threading.Thread(
            target=self._hilo_verificar_bd,
            daemon=True,
        ).start()

    # ========================================================
    # HILO BD
    # ========================================================

    def _hilo_verificar_bd(self):

        try:

            conectado = None

            if hasattr(
                self.auth,
                "verificar_conexion",
            ):

                conectado = (
                    self.auth.verificar_conexion()
                )

            elif hasattr(
                self.auth,
                "test_connection",
            ):

                conectado = (
                    self.auth.test_connection()
                )

            elif hasattr(
                self.auth,
                "probar_conexion",
            ):

                conectado = (
                    self.auth.probar_conexion()
                )

            elif hasattr(
                self.auth,
                "conexion",
            ):

                conectado = (
                    self.auth.conexion is not None
                )

            else:

                conectado = True

            print(
                f"[LOGIN] Estado BD: {conectado}"
            )

            self._after_ui(
                self._resultado_verificacion_bd,
                bool(conectado),
                None,
            )

        except Exception as e:

            print(
                f"[LOGIN] Error BD: {e}"
            )

            self._after_ui(
                self._resultado_verificacion_bd,
                False,
                str(e),
            )

    # ========================================================
    # RESULTADO BD
    # ========================================================

    def _resultado_verificacion_bd(
        self,
        conectado,
        error,
    ):

        self._conectando_bd = False

        if self._cerrando:
            return

        if conectado:

            self.var_estado.set(
                "Sistema listo. Inicie sesión."
            )

            self._actualizacion_verificada = True

            self._habilitar_login(True)

            try:
                self.entry_usuario.focus_set()
            except Exception:
                pass

        else:

            self.var_estado.set(
                "Sin conexión a la base de datos."
            )

            self._habilitar_login(False)

            detalle = ""

            if error:
                detalle = (
                    f"\n\nDetalle:\n{error}"
                )

            messagebox.showerror(
                "Conexión",
                (
                    "No se pudo conectar con la base de datos."
                    f"{detalle}"
                ),
                parent=self,
            )

    # ========================================================
    # LOGIN
    # ========================================================

    def _iniciar_login(self):

        if self._cerrando:
            return

        if self._actualizacion_en_proceso:
            return

        if not self._actualizacion_verificada:

            messagebox.showwarning(
                "FacturasVentas",
                "Espere mientras se verifica el sistema.",
                parent=self,
            )

            return

        usuario = self.var_usuario.get().strip()

        password = self.var_password.get()

        # ====================================================
        # VALIDAR USUARIO
        # ====================================================

        if not usuario:

            messagebox.showwarning(
                "Inicio de sesión",
                "Ingrese el usuario.",
                parent=self,
            )

            self.entry_usuario.focus_set()

            return

        # ====================================================
        # VALIDAR PASSWORD
        # ====================================================

        if not password:

            messagebox.showwarning(
                "Inicio de sesión",
                "Ingrese la contraseña.",
                parent=self,
            )

            self.entry_password.focus_set()

            return

        # ====================================================
        # DESACTIVAR
        # ====================================================

        self._habilitar_login(False)

        self.var_estado.set(
            "Autenticando..."
        )

        # ====================================================
        # AUTENTICAR EN SEGUNDO PLANO
        # ====================================================

        threading.Thread(
            target=self._hilo_login,
            args=(usuario, password),
            daemon=True,
        ).start()

    # ========================================================
    # HILO LOGIN
    # ========================================================

    def _hilo_login(
        self,
        usuario,
        password,
    ):

        try:

            print(
                f"[LOGIN] Autenticando usuario: {usuario}"
            )

            resultado = self.auth.autenticar(
                usuario,
                password,
            )

            print(
                f"[LOGIN] Resultado autenticar: {resultado}"
            )

            self._after_ui(
                self._procesar_login,
                resultado,
            )

        except Exception as e:

            print(
                f"[LOGIN] Excepción autenticación: {e}"
            )

            self._after_ui(
                self._login_error,
                str(e),
            )

    # ========================================================
    # PROCESAR LOGIN
    # ========================================================

    def _procesar_login(
        self,
        resultado,
    ):

        if self._cerrando:
            return

        print(
            "[LOGIN] Procesando resultado..."
        )

        print(
            f"[LOGIN] Tipo resultado: {type(resultado)}"
        )

        print(
            f"[LOGIN] Resultado: {resultado}"
        )

        autenticado = False

        usuario_resultado = resultado

        # ====================================================
        # RESULTADO BOOLEANO
        # ====================================================

        if isinstance(
            resultado,
            bool,
        ):

            autenticado = resultado

            if autenticado:

                usuario_actual = getattr(
                    self.auth,
                    "usuario_actual",
                    None,
                )

                if usuario_actual is not None:

                    usuario_resultado = (
                        usuario_actual
                    )

        # ====================================================
        # RESULTADO DICT
        # ====================================================

        elif isinstance(
            resultado,
            dict,
        ):

            # =================================================
            # AQUÍ ESTÁ LA CORRECCIÓN IMPORTANTE
            #
            # AuthController devuelve:
            #
            # {
            #     "exito": True,
            #     "mensaje": "Login exitoso",
            #     "usuario": {...}
            # }
            #
            # =================================================

            autenticado = bool(
                resultado.get(
                    "exito",
                    resultado.get(
                        "ok",
                        resultado.get(
                            "success",
                            resultado.get(
                                "autenticado",
                                False,
                            ),
                        ),
                    ),
                )
            )

            print(
                f"[LOGIN] Campo exito: "
                f"{resultado.get('exito')}"
            )

            print(
                f"[LOGIN] Autenticado: "
                f"{autenticado}"
            )

            # =================================================
            # OBTENER USUARIO
            # =================================================

            if autenticado:

                usuario_resultado = (
                    resultado.get("usuario")
                    or resultado.get("user")
                    or resultado
                )

                print(
                    "[LOGIN] Usuario obtenido:"
                )

                print(
                    usuario_resultado
                )

        # ====================================================
        # OTRO TIPO
        # ====================================================

        else:

            autenticado = bool(
                resultado
            )

        # ====================================================
        # LOGIN CORRECTO
        # ====================================================

        if autenticado:

            print(
                "========================================"
            )

            print(
                "[LOGIN] AUTENTICACIÓN CORRECTA"
            )

            print(
                f"[LOGIN] USUARIO: {usuario_resultado}"
            )

            print(
                "========================================"
            )

            self.var_estado.set(
                "Inicio de sesión correcto..."
            )

            # =================================================
            # GUARDAR USUARIO EN AUTH
            # =================================================

            try:

                if hasattr(
                    self.auth,
                    "usuario_actual",
                ):

                    self.auth.usuario_actual = (
                        usuario_resultado
                    )

            except Exception as e:

                print(
                    f"[LOGIN] No se pudo guardar "
                    f"usuario_actual: {e}"
                )

            # =================================================
            # GUARDAR CALLBACK
            # =================================================

            callback = (
                self.on_login_success
            )

            # =================================================
            # IMPORTANTE:
            #
            # Cerramos SOLO la ventana.
            #
            # NO hacemos:
            #
            # self.auth.cerrar_sesion()
            #
            # porque MainWindow necesita la sesión.
            # =================================================

            self._cerrando = True

            try:
                self.quit()
            except Exception:
                pass

            try:
                self.destroy()
            except Exception:
                pass

            # =================================================
            # MANDAR USUARIO A main.py
            # =================================================

            if callback:

                try:

                    print(
                        "[LOGIN] Ejecutando "
                        "on_login_success..."
                    )

                    callback(
                        usuario_resultado
                    )

                    print(
                        "[LOGIN] on_login_success ejecutado."
                    )

                except Exception as e:

                    print(
                        "[LOGIN] ERROR en "
                        "on_login_success:"
                    )

                    print(
                        repr(e)
                    )

                    try:

                        messagebox.showerror(
                            "Error",
                            (
                                "El login fue correcto, "
                                "pero ocurrió un error "
                                "al abrir el panel.\n\n"
                                f"{e}"
                            ),
                        )

                    except Exception:
                        pass

            else:

                print(
                    "[LOGIN] ADVERTENCIA: "
                    "No existe on_login_success."
                )

            return

        # ====================================================
        # LOGIN INCORRECTO
        # ====================================================

        print(
            "[LOGIN] AUTENTICACIÓN FALLIDA"
        )

        self._login_error(
            (
                resultado.get(
                    "mensaje",
                    "Usuario o contraseña incorrectos.",
                )
                if isinstance(resultado, dict)
                else "Usuario o contraseña incorrectos."
            )
        )

    # ========================================================
    # ERROR LOGIN
    # ========================================================

    def _login_error(
        self,
        mensaje,
    ):

        if self._cerrando:
            return

        self.var_estado.set(
            "Error de autenticación."
        )

        self._habilitar_login(True)

        try:
            self.entry_password.focus_set()
        except Exception:
            pass

        messagebox.showerror(
            "Inicio de sesión",
            mensaje,
            parent=self,
        )

    # ========================================================
    # CERRAR
    # ========================================================

    def _cerrar_ventana(self):

        if self._actualizacion_en_proceso:

            continuar = messagebox.askyesno(
                "Actualización",
                (
                    "Hay una actualización en proceso.\n\n"
                    "¿Desea cancelar y cerrar la aplicación?"
                ),
                parent=self,
            )

            if not continuar:
                return

        self._cerrando = True

        # ====================================================
        # CERRAR SESIÓN
        # ====================================================

        try:

            self.auth.cerrar_sesion()

        except Exception as e:

            print(
                f"[LOGIN] Error cerrando sesión: {e}"
            )

        # ====================================================
        # CERRAR TK
        # ====================================================

        try:
            self.quit()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass


# ============================================================
# FUNCIÓN COMPATIBILIDAD
# ============================================================

def mostrar_login(
    auth: Optional[AuthController] = None,
    on_login_success: Optional[Callable[[Any], None]] = None,
):

    ventana = LoginWindow(
        auth=auth,
        on_login_success=on_login_success,
    )

    ventana.mainloop()

    return ventana


# ============================================================
# EJECUCIÓN DIRECTA
# ============================================================

if __name__ == "__main__":

    auth = AuthController()

    ventana = LoginWindow(
        auth=auth,
    )

    ventana.mainloop()