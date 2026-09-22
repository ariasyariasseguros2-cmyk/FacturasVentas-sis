import sys
import os
import ctypes
import tkinter as tk
from tkinter import messagebox
from typing import Dict, Any

# ============================================================
# RUTA BASE DEL PROYECTO
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


# ============================================================
# IMPORTACIONES
# ============================================================

from controllers.auth_controller import AuthController
from views.login import LoginWindow
from views.main_window import MainWindow
from utils.updater import APP_VERSION


def _configurar_dpi_awareness():
    if os.name != "nt":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ============================================================
# APLICACIÓN PRINCIPAL
# ============================================================

class App:

    def __init__(self):
        self.auth = AuthController()

        self.login_window = None
        self.main_window = None

        # El actualizador puede volver a abrir la aplicación
        # utilizando este argumento.
        self.post_update = "--post-update" in sys.argv

    # ========================================================
    # INICIAR APLICACIÓN
    # ========================================================

    def iniciar(self):

        # Si venimos de una actualización,
        # mostramos mensaje de bienvenida.
        if self.post_update:
            self._mostrar_bienvenida_post_update()

        self._mostrar_login()

    # ========================================================
    # MENSAJE DESPUÉS DE ACTUALIZACIÓN
    # ========================================================

    def _mostrar_bienvenida_post_update(self):

        try:

            root = tk.Tk()
            root.withdraw()

            try:

                messagebox.showinfo(
                    "Actualización completada",
                    (
                        "FacturasVentas se actualizó correctamente.\n\n"
                        f"Versión actual: v{APP_VERSION}"
                    ),
                    parent=root,
                )

            except Exception:
                pass

            try:
                root.destroy()
            except Exception:
                pass

        except Exception:
            pass

    # ========================================================
    # MOSTRAR LOGIN
    # ========================================================

    def _mostrar_login(self):

        try:

            self.login_window = LoginWindow(
                auth=self.auth,
                on_login_success=self._al_login_exitoso,
            )

            # LoginWindow hereda de tk.Tk
            self.login_window.mainloop()

        except Exception as e:

            print(f"[ERROR] No se pudo abrir LoginWindow: {e}")

            try:
                messagebox.showerror(
                    "Error",
                    f"No se pudo abrir la ventana de inicio de sesión.\n\n{e}",
                )
            except Exception:
                pass

    # ========================================================
    # LOGIN CORRECTO
    # ========================================================

    def _al_login_exitoso(self, usuario: Dict[str, Any]):

        print("[APP] Login correcto")
        print(f"[APP] Usuario recibido: {usuario}")

        # El LoginWindow ya fue cerrado por LoginWindow
        self.login_window = None

        # ====================================================
        # IMPORTANTE:
        # NO HACER:
        #
        # self.auth.cerrar_sesion()
        #
        # porque MainWindow necesita la sesión actual.
        # ====================================================

        try:

            self.main_window = MainWindow(
                auth=self.auth,
                usuario=usuario,
                on_logout=self._al_logout,
            )

            print("[APP] MainWindow creada correctamente")

            self.main_window.mainloop()

            print("[APP] MainWindow terminó")

        except Exception as e:

            print(f"[ERROR] No se pudo abrir MainWindow: {e}")

            try:
                messagebox.showerror(
                    "Error al abrir el panel",
                    (
                        "El usuario se autenticó correctamente, "
                        "pero no se pudo abrir el panel principal.\n\n"
                        f"Detalle:\n{e}"
                    ),
                )
            except Exception:
                pass

            self.main_window = None

            # Si MainWindow falla, cerramos la sesión.
            try:
                self.auth.cerrar_sesion()
            except Exception:
                pass

            # Volver al login.
            self._mostrar_login()

    # ========================================================
    # LOGOUT
    # ========================================================

    def _al_logout(self):

        print("[APP] Cerrando sesión...")

        self.main_window = None

        try:
            self.auth.cerrar_sesion()
        except Exception as e:
            print(f"[APP] Error cerrando sesión: {e}")

        # Volver al login.
        self._mostrar_login()


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    try:

        _configurar_dpi_awareness()
        app = App()
        app.iniciar()

    except Exception as e:

        print(f"[ERROR FATAL] {e}")

        try:
            root = tk.Tk()
            root.withdraw()

            messagebox.showerror(
                "Error fatal",
                f"FacturasVentas no pudo iniciar.\n\n{e}",
                parent=root,
            )

            root.destroy()

        except Exception:
            pass