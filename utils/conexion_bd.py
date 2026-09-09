import mysql.connector
from mysql.connector import Error
from typing import Optional, List, Dict, Any, Tuple

from bd import DB_CONFIG


class ConexionBD:
    def __init__(self):
        self.conexion: Optional[mysql.connector.MySQLConnection] = None
        self.config = DB_CONFIG

    def conectar(self) -> bool:
        try:
            self.conexion = mysql.connector.connect(
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
                charset="utf8mb4",
                connection_timeout=10,
            )
            return self.conexion.is_connected()
        except Error:
            self.conexion = None
            return False

    def desconectar(self) -> None:
        if self.conexion and self.conexion.is_connected():
            self.conexion.close()
            self.conexion = None

    def _asegurar_conexion(self) -> bool:
        if not self.conexion or not self.conexion.is_connected():
            return self.conectar()
        return True

    def ejecutar_consulta(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        solo_uno: bool = False,
        pre_statements: Optional[List[Tuple[str, Optional[Tuple[Any, ...]]]]] = None,
    ) -> Optional[Any]:
        if not self._asegurar_conexion():
            return None

        try:
            cursor = self.conexion.cursor(dictionary=True, buffered=True)
            if pre_statements:
                for ps_query, ps_params in pre_statements:
                    cursor.execute(ps_query, ps_params or ())
            cursor.execute(query, params or ())
            if solo_uno:
                resultado = cursor.fetchone()
            else:
                resultado = cursor.fetchall()
            cursor.close()
            return resultado
        except Error:
            return None

    def ejecutar_operacion(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        if not self._asegurar_conexion():
            return False, None, "Sin conexión a la base de datos"

        try:
            cursor = self.conexion.cursor()
            cursor.execute(query, params or ())
            self.conexion.commit()
            last_id = cursor.lastrowid
            cursor.close()
            return True, last_id, None
        except Error as e:
            return False, None, str(e)
