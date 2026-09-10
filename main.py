import sys
import os
import tkinter as tk
from tkinter import messagebox
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controllers.auth_controller import AuthController
from views.login import LoginWindow
from views.main_window import MainWindow
from utils.updater import APP_VERSION


class App:
    def __init__(self):
        self.auth = AuthController()
        self.login_window = None
        self.main_window = None
        self.post_update = "--post-update" in sys.argv

    def iniciar(self):
        if self.post_update:
            self._mostrar_bienvenida_post_update()
        self._mostrar_login()

    def _mostrar_bienvenida_post_update(self):
        try:
            root = tk.Tk()
            root.withdraw()
            try:
                root.after(200, lambda: messagebox.showinfo(
                    "Actualización completada",
                    f"FacturasVentas se actualizó correctamente.\n\n"
                    f"Versión actual: v{APP_VERSION}",
                    parent=root,
                ))
                root.after(250, root.destroy)
                root.mainloop()
            except Exception:
                try:
                    root.destroy()
                except Exception:
                    pass
        except Exception:
            pass

    def _mostrar_login(self):
        self.login_window = LoginWindow(
            auth=self.auth,
            on_login_success=self._al_login_exitoso,
        )
        self.login_window.mainloop()

    def _al_login_exitoso(self, usuario: Dict[str, Any]):
        self.login_window = None
        self.main_window = MainWindow(
            auth=self.auth,
            usuario=usuario,
            on_logout=self._al_logout,
        )
        self.main_window.mainloop()

    def _al_logout(self):
        self.main_window = None
        self.auth.cerrar_sesion()
        self._mostrar_login()


if __name__ == "__main__":
    App().iniciar()
