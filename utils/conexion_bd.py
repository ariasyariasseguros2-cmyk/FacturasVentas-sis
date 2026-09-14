try:
    import mysql.connector
    from mysql.connector import Error
except Exception:
    mysql = None
    Error = Exception

from typing import Optional, List, Dict, Any, Tuple
from bd import DB_CONFIG


class ConexionBD:

    def __init__(self):
        self.conexion: Optional[Any] = None
        self.config = DB_CONFIG

    def conectar(self) -> bool:

        if mysql is None:
            print("[BD] mysql.connector no está disponible")
            self.conexion = None
            return False

        try:

            print("[BD] Intentando conectar...")
            print(f"[BD] Host: {self.config['host']}")
            print(f"[BD] Puerto: {self.config['port']}")
            print(f"[BD] Base: {self.config['database']}")
            print(f"[BD] Usuario: {self.config['user']}")

            self.conexion = mysql.connector.connect(
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
                charset="utf8mb4",
                connection_timeout=10,
                use_pure=True,
            )

            if self.conexion.is_connected():

                print("[BD] MYSQL CONECTADO CORRECTAMENTE")

                # Verificación adicional
                cursor = self.conexion.cursor()
                cursor.execute("SELECT DATABASE(), USER(), VERSION()")
                resultado = cursor.fetchone()
                cursor.close()

                print(f"[BD] DATABASE: {resultado[0]}")
                print(f"[BD] USER: {resultado[1]}")
                print(f"[BD] MYSQL VERSION: {resultado[2]}")

                return True

            print("[BD] MySQL no está conectado")
            return False

        except Error as e:

            print("[BD] ERROR MYSQL")
            print(f"[BD] {type(e).__name__}: {e}")

            self.conexion = None
            return False

        except Exception as e:

            print("[BD] ERROR GENERAL")
            print(f"[BD] {type(e).__name__}: {e}")

            self.conexion = None
            return False

    def desconectar(self) -> None:

        if self.conexion:

            try:
                if self.conexion.is_connected():
                    self.conexion.close()
            except Exception:
                pass

            self.conexion = None

    def _asegurar_conexion(self) -> bool:

        if (
            self.conexion is None
            or not self.conexion.is_connected()
        ):
            return self.conectar()

        return True

    def ejecutar_consulta(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        solo_uno: bool = False,
        pre_statements: Optional[
            List[Tuple[str, Optional[Tuple[Any, ...]]]]
        ] = None,
    ) -> Optional[Any]:

        if not self._asegurar_conexion():
            return None

        cursor = None

        try:

            cursor = self.conexion.cursor(
                dictionary=True,
                buffered=True
            )

            if pre_statements:

                for ps_query, ps_params in pre_statements:

                    cursor.execute(
                        ps_query,
                        ps_params or ()
                    )

            cursor.execute(
                query,
                params or ()
            )

            if solo_uno:
                resultado = cursor.fetchone()
            else:
                resultado = cursor.fetchall()

            return resultado

        except Error as e:

            print(
                f"[BD] Error ejecutando consulta: "
                f"{type(e).__name__}: {e}"
            )

            try:
                self.desconectar()
            except Exception:
                pass

            return None

        except Exception as e:

            print(
                f"[BD] Error general consulta: "
                f"{type(e).__name__}: {e}"
            )

            try:
                self.desconectar()
            except Exception:
                pass

            return None

        finally:

            if cursor:

                try:
                    cursor.close()
                except Exception:
                    pass

    def ejecutar_operacion(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
    ) -> Tuple[bool, Optional[int], Optional[str]]:

        if not self._asegurar_conexion():

            return (
                False,
                None,
                "Sin conexión a la base de datos"
            )

        cursor = None

        try:

            cursor = self.conexion.cursor()

            cursor.execute(
                query,
                params or ()
            )

            self.conexion.commit()

            last_id = cursor.lastrowid

            return True, last_id, None

        except Error as e:

            try:
                self.conexion.rollback()
            except Exception:
                pass

            error = f"{type(e).__name__}: {e}"

            print(f"[BD] Error operación: {error}")

            self.desconectar()

            return False, None, error

        except Exception as e:

            try:
                self.conexion.rollback()
            except Exception:
                pass

            error = f"{type(e).__name__}: {e}"

            print(f"[BD] Error general operación: {error}")

            self.desconectar()

            return False, None, error

        finally:

            if cursor:

                try:
                    cursor.close()
                except Exception:
                    pass