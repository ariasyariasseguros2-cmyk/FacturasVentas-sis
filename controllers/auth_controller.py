from typing import Optional, Dict, Any

from utils.conexion_bd import ConexionBD
from utils.crypto import verify_password
from bd import EMERGENCY_USER


class AuthController:
    def __init__(self):
        self.bd = ConexionBD()
        self.usuario_actual: Optional[Dict[str, Any]] = None

    def autenticar(self, username: str, password: str) -> Dict[str, Any]:
        if not username or not password:
            return {"exito": False, "mensaje": "Debe ingresar usuario y contraseña"}

        usuario_bd = self._obtener_usuario_bd(username)

        if usuario_bd is None:
            if (username == EMERGENCY_USER["username"]
                    and password == EMERGENCY_USER["password"]):
                self.usuario_actual = {
                    "id": 0,
                    "username": EMERGENCY_USER["username"],
                    "nombre": EMERGENCY_USER["nombre"],
                    "id_rol": EMERGENCY_USER["id_rol"],
                    "rol_nombre": EMERGENCY_USER["rol_nombre"],
                    "color_avatar": "#ef4444",
                    "modo_emergencia": True,
                }
                return {"exito": True, "mensaje": "Login de emergencia exitoso", "usuario": self.usuario_actual}

            return {"exito": False, "mensaje": "Usuario o contraseña incorrectos"}

        if usuario_bd.get("estado", 1) == 0:
            return {"exito": False, "mensaje": "Usuario inactivo. Contacte al administrador"}

        stored_password = usuario_bd.get("password", "")
        if verify_password(password, stored_password):
            self.usuario_actual = {
                "id": usuario_bd.get("id"),
                "username": usuario_bd.get("username"),
                "nombre": usuario_bd.get("nombre") or usuario_bd.get("username"),
                "id_rol": usuario_bd.get("id_rol"),
                "rol_nombre": usuario_bd.get("rol_nombre") or "Usuario",
                "foto_perfil": usuario_bd.get("foto_perfil"),
                "color_avatar": usuario_bd.get("color_avatar") or "#3b82f6",
                "modo_emergencia": False,
            }
            return {"exito": True, "mensaje": "Login exitoso", "usuario": self.usuario_actual}

        return {"exito": False, "mensaje": "Usuario o contraseña incorrectos"}

    def _obtener_usuario_bd(self, username: str) -> Optional[Dict[str, Any]]:
        if not self.bd.conectar():
            return None

        query = """
            SELECT u.id, u.username, u.password, u.id_rol, u.nombre,
                   u.foto_perfil, u.color_avatar, u.estado, r.nombre AS rol_nombre
            FROM usuarios u
            LEFT JOIN roles r ON r.idRol = u.id_rol
            WHERE u.username = %s
            LIMIT 1
        """
        resultado = self.bd.ejecutar_consulta(query, (username,), solo_uno=True)
        self.bd.desconectar()
        return resultado

    def probar_conexion(self) -> bool:
        ok = self.bd.conectar()
        if ok:
            self.bd.desconectar()
        return ok

    def cerrar_sesion(self) -> None:
        self.usuario_actual = None
        self.bd.desconectar()
