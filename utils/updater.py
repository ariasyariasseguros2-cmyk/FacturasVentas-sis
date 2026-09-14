import json
import os
import sys
import shutil
import hashlib
import zipfile
import subprocess
import ssl
import urllib.request
import urllib.error
import urllib.parse
import webbrowser
import traceback
import time
from typing import Optional, Dict, Any, Tuple, Callable


# ============================================================
# CONFIGURACIÓN
# ============================================================

APP_VERSION: str = "1.0.0"

VERSION_URL: str = (
    "https://aasnet.tech/updates/version.json"
)

APP_EXE_NAME: str = "main.exe"

ALLOW_INSECURE_SSL_FALLBACK: bool = True

DEBUG: bool = True


# ============================================================
# LOG
# ============================================================

def obtener_directorio_log() -> str:
    try:
        return obtener_directorio_ejecutable()
    except Exception:
        return os.getcwd()


def obtener_ruta_log() -> str:
    return os.path.join(
        obtener_directorio_log(),
        "updater.log"
    )


def log(mensaje: str):
    """
    Muestra el mensaje en consola y lo guarda en updater.log.
    """

    texto = (
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
        f"{mensaje}"
    )

    # Consola
    try:
        print(texto, flush=True)
    except Exception:
        pass

    # Archivo
    try:
        with open(
            obtener_ruta_log(),
            "a",
            encoding="utf-8"
        ) as f:
            f.write(texto + "\n")
    except Exception:
        pass


def log_error(mensaje: str, exc: Optional[Exception] = None):
    log("ERROR: " + mensaje)

    if exc is not None:
        log(
            f"TIPO ERROR: {type(exc).__name__}"
        )
        log(
            f"DETALLE ERROR: {exc}"
        )

    if DEBUG:
        try:
            traceback.print_exc()

            with open(
                obtener_ruta_log(),
                "a",
                encoding="utf-8"
            ) as f:
                f.write(
                    traceback.format_exc()
                    + "\n"
                )
        except Exception:
            pass


# ============================================================
# SSL
# ============================================================

def _crear_contexto_ssl(
    inseguro: bool = False
) -> Optional[ssl.SSLContext]:

    log(
        f"Creando contexto SSL. inseguro={inseguro}"
    )

    if inseguro:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    return None


# ============================================================
# CAMBIAR HTTP / HTTPS
# ============================================================

def _alternar_http(url: str) -> str:

    try:
        p = urllib.parse.urlparse(url)

        if p.scheme == "https":
            return p._replace(
                scheme="http"
            ).geturl()

        if p.scheme == "http":
            return p._replace(
                scheme="https"
            ).geturl()

    except Exception as e:
        log_error(
            "Error alternando HTTP/HTTPS",
            e
        )

    return url


# ============================================================
# HTTP GET
# ============================================================

def _http_get_raw(
    url: str,
    timeout: int,
    extra_headers: Optional[Dict[str, str]] = None,
    salida_binaria: bool = False,
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
    destino_archivo: Optional[str] = None,
) -> Dict[str, Any]:

    log("=" * 70)
    log("INICIO HTTP GET")
    log(f"URL: {url}")
    log(f"TIMEOUT: {timeout}")
    log(f"DESTINO: {destino_archivo}")

    resultados: Dict[str, Any] = {
        "ok": False,
        "data": None,
        "ruta": None,
        "bytes_descargados": 0,
        "bytes_totales": 0,
        "sha256": None,
        "url_final": None,
        "errores": [],
    }

    headers = {
        "User-Agent": (
            f"FacturasVentas-SIS/{APP_VERSION}"
        ),
        "Accept": "*/*",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    if extra_headers:
        headers.update(extra_headers)

    log(f"HEADERS: {headers}")

    estrategias = []

    # ========================================================
    # 1. HTTPS NORMAL
    # ========================================================

    estrategias.append(
        (url, None)
    )

    # ========================================================
    # 2. HTTPS SIN VALIDACIÓN SSL
    # ========================================================

    if ALLOW_INSECURE_SSL_FALLBACK:
        estrategias.append(
            (
                url,
                _crear_contexto_ssl(True)
            )
        )

    # ========================================================
    # 3. HTTP
    # ========================================================

    url_http = _alternar_http(url)

    if url_http != url:

        estrategias.append(
            (
                url_http,
                None
            )
        )

    ultimo_error = None

    # ========================================================
    # EJECUTAR ESTRATEGIAS
    # ========================================================

    for idx, (u, ctx) in enumerate(
        estrategias,
        start=1
    ):

        log("-" * 70)

        log(
            f"ESTRATEGIA {idx}/{len(estrategias)}"
        )

        log(f"URL: {u}")

        if ctx is None:
            log("SSL: NORMAL")
        else:
            log("SSL: SIN VALIDACIÓN")

        try:

            resultados["url_final"] = u

            req = urllib.request.Request(
                u,
                headers=headers,
                method="GET"
            )

            kwargs = {
                "timeout": timeout
            }

            if ctx is not None:
                kwargs["context"] = ctx

            log("Ejecutando urllib.request.urlopen()...")

            with urllib.request.urlopen(
                req,
                **kwargs
            ) as resp:

                log(
                    f"HTTP STATUS: {resp.status}"
                )

                log(
                    f"RESPONSE URL: {resp.geturl()}"
                )

                log(
                    f"HEADERS RESPONSE: {dict(resp.headers)}"
                )

                total_bytes = int(
                    resp.headers.get(
                        "Content-Length"
                    ) or 0
                )

                resultados[
                    "bytes_totales"
                ] = total_bytes

                log(
                    f"CONTENT-LENGTH: {total_bytes}"
                )

                # ==================================================
                # GUARDAR ARCHIVO
                # ==================================================

                if destino_archivo:

                    directorio = os.path.dirname(
                        destino_archivo
                    )

                    if directorio:
                        os.makedirs(
                            directorio,
                            exist_ok=True
                        )

                    log(
                        f"Guardando archivo en: "
                        f"{destino_archivo}"
                    )

                    descargado = 0

                    with open(
                        destino_archivo,
                        "wb"
                    ) as out:

                        while True:

                            chunk = resp.read(
                                64 * 1024
                            )

                            if not chunk:
                                break

                            out.write(chunk)

                            descargado += len(
                                chunk
                            )

                            resultados[
                                "bytes_descargados"
                            ] = descargado

                            if (
                                progress_cb
                                and total_bytes
                            ):
                                try:
                                    progress_cb(
                                        descargado,
                                        total_bytes
                                    )
                                except Exception as e:
                                    log_error(
                                        "Error en progress_cb",
                                        e
                                    )

                    log(
                        f"DESCARGA COMPLETADA: "
                        f"{descargado} bytes"
                    )

                    resultados["ok"] = True

                    resultados[
                        "ruta"
                    ] = destino_archivo

                    resultados[
                        "sha256"
                    ] = _sha256_archivo(
                        destino_archivo
                    )

                    log(
                        f"SHA256: "
                        f"{resultados['sha256']}"
                    )

                    return resultados

                # ==================================================
                # DEVOLVER DATA
                # ==================================================

                log(
                    "Leyendo respuesta HTTP..."
                )

                raw = resp.read()

                resultados["data"] = raw

                resultados[
                    "bytes_descargados"
                ] = len(raw)

                resultados["ok"] = True

                log(
                    f"DATA RECIBIDA: {len(raw)} bytes"
                )

                return resultados

        except urllib.error.HTTPError as e:

            ultimo_error = (
                f"HTTPError "
                f"status={e.code} "
                f"reason={e.reason}"
            )

            log_error(
                f"HTTP ERROR en estrategia {idx}",
                e
            )

            resultados[
                "errores"
            ].append(
                f"[{idx}] {ultimo_error}"
            )

        except urllib.error.URLError as e:

            ultimo_error = (
                f"URLError: {e.reason}"
            )

            log_error(
                f"URL ERROR en estrategia {idx}",
                e
            )

            resultados[
                "errores"
            ].append(
                f"[{idx}] {ultimo_error}"
            )

        except ssl.SSLError as e:

            ultimo_error = (
                f"SSLError: {e}"
            )

            log_error(
                f"SSL ERROR en estrategia {idx}",
                e
            )

            resultados[
                "errores"
            ].append(
                f"[{idx}] {ultimo_error}"
            )

        except OSError as e:

            ultimo_error = (
                f"OSError: {e}"
            )

            log_error(
                f"OS ERROR en estrategia {idx}",
                e
            )

            resultados[
                "errores"
            ].append(
                f"[{idx}] {ultimo_error}"
            )

        except Exception as e:

            ultimo_error = (
                f"{type(e).__name__}: {e}"
            )

            log_error(
                f"ERROR GENERAL en estrategia {idx}",
                e
            )

            resultados[
                "errores"
            ].append(
                f"[{idx}] {ultimo_error}"
            )

    log("=" * 70)

    log(
        "TODAS LAS ESTRATEGIAS HTTP FALLARON"
    )

    resultados[
        "errores"
    ].append(
        f"URL original: {url}"
    )

    return resultados


# ============================================================
# SHA256
# ============================================================

def _sha256_archivo(
    ruta: str,
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
) -> str:

    log(
        f"Calculando SHA256: {ruta}"
    )

    h = hashlib.sha256()

    if not os.path.exists(ruta):

        log(
            "SHA256: archivo no existe"
        )

        return ""

    total = os.path.getsize(ruta)

    leido = 0

    with open(
        ruta,
        "rb"
    ) as f:

        while True:

            buf = f.read(
                64 * 1024
            )

            if not buf:
                break

            h.update(buf)

            leido += len(buf)

            if (
                progress_cb
                and total
            ):
                try:
                    progress_cb(
                        leido,
                        total
                    )
                except Exception:
                    pass

    resultado = h.hexdigest()

    log(
        f"SHA256 RESULTADO: {resultado}"
    )

    return resultado


# ============================================================
# VERSION
# ============================================================

def _parse_version(
    version_str: str
) -> Tuple[int, ...]:

    try:

        return tuple(
            int(x)
            for x in version_str.strip().split(".")
        )

    except Exception as e:

        log_error(
            f"No se pudo interpretar versión: "
            f"{version_str}",
            e
        )

        return (
            0,
            0,
            0
        )


def version_disponible(
    local: str,
    remota: str
) -> bool:

    local_tuple = _parse_version(local)
    remota_tuple = _parse_version(remota)

    log(
        f"Comparando versiones: "
        f"LOCAL={local_tuple} "
        f"REMOTA={remota_tuple}"
    )

    return remota_tuple > local_tuple


# ============================================================
# RUTAS
# ============================================================

def obtener_ruta_ejecutable() -> str:

    if getattr(
        sys,
        "frozen",
        False
    ):

        return sys.executable

    return os.path.abspath(
        sys.argv[0]
    )


def obtener_directorio_ejecutable() -> str:

    return os.path.dirname(
        obtener_ruta_ejecutable()
    )


def obtener_ruta_app_exe() -> str:

    if getattr(
        sys,
        "frozen",
        False
    ):

        return sys.executable

    return os.path.join(
        obtener_directorio_ejecutable(),
        APP_EXE_NAME
    )


# ============================================================
# CONSULTAR VERSION REMOTA
# ============================================================

def consultar_version_remota(
    url: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:

    destino = (
        url
        or VERSION_URL
    )

    log("=" * 70)
    log("CONSULTANDO VERSION REMOTA")
    log(f"VERSION LOCAL: {APP_VERSION}")
    log(f"VERSION URL: {destino}")

    resultado: Dict[str, Any] = {
        "ok": False,
        "hay_actualizacion": False,
        "version_remota": None,
        "version_local": APP_VERSION,
        "download_url": None,
        "patch_url": None,
        "strategy": None,
        "force_update": False,
        "checksum_sha256": None,
        "file_size_bytes": 0,
        "min_version_to_patch": None,
        "notas": None,
        "published_at": None,
        "puede_autoaplicar": False,
        "url_version_json_usada": None,
        "error": None,
    }

    try:

        http_res = _http_get_raw(
            destino,
            timeout=timeout,
            extra_headers={
                "Accept": "application/json"
            }
        )

        if not http_res["ok"]:

            err_list = (
                http_res.get(
                    "errores"
                )
                or []
            )

            log(
                "ERRORES VERSION.JSON:"
            )

            for error in err_list:
                log(
                    f"  {error}"
                )

            if err_list:
                msj = err_list[-1]
            else:
                msj = "Error desconocido"

            resultado["error"] = msj

            return resultado

        resultado[
            "url_version_json_usada"
        ] = http_res.get(
            "url_final"
        )

        raw_bytes = (
            http_res.get(
                "data"
            )
            or b""
        )

        log(
            f"VERSION.JSON recibida: "
            f"{len(raw_bytes)} bytes"
        )

        raw = raw_bytes.decode(
            "utf-8",
            errors="replace"
        )

        log(
            "CONTENIDO VERSION.JSON:"
        )
        log(raw)

        try:

            datos = json.loads(
                raw
            )

        except json.JSONDecodeError as e:

            log_error(
                "El version.json no contiene JSON válido",
                e
            )

            resultado[
                "error"
            ] = (
                "El archivo de versión remoto "
                "es inválido (JSON corrupto)"
            )

            return resultado

        # ==================================================
        # LEER VERSION.JSON
        # ==================================================

        version_remota = str(
            datos.get(
                "version",
                ""
            )
        ).strip()

        download_url = str(
            datos.get(
                "download_url",
                ""
            )
        ).strip() or None

        patch_url = str(
            datos.get(
                "patch_url",
                ""
            )
        ).strip() or None

        strategy = str(
            datos.get(
                "strategy",
                ""
            )
        ).strip() or None

        force_update = bool(
            datos.get(
                "force_update",
                False
            )
        )

        checksum = str(
            datos.get(
                "checksum_sha256",
                ""
            )
        ).strip() or None

        try:

            file_size = int(
                datos.get(
                    "file_size_bytes"
                )
                or 0
            )

        except Exception:

            file_size = 0

        min_patch = str(
            datos.get(
                "min_version_to_patch",
                ""
            )
        ).strip() or None

        notas = (
            datos.get(
                "release_notes"
            )
            or datos.get(
                "notes"
            )
            or None
        )

        published_at = str(
            datos.get(
                "published_at",
                ""
            )
        ).strip() or None

        # ==================================================
        # GUARDAR RESULTADOS
        # ==================================================

        resultado["ok"] = True

        resultado[
            "version_remota"
        ] = (
            version_remota
            or None
        )

        resultado[
            "download_url"
        ] = download_url

        resultado[
            "patch_url"
        ] = patch_url

        resultado[
            "strategy"
        ] = strategy

        resultado[
            "force_update"
        ] = force_update

        resultado[
            "checksum_sha256"
        ] = checksum

        resultado[
            "file_size_bytes"
        ] = file_size

        resultado[
            "min_version_to_patch"
        ] = min_patch

        resultado[
            "notas"
        ] = notas

        resultado[
            "published_at"
        ] = published_at

        # ==================================================
        # MOSTRAR DATOS
        # ==================================================

        log(
            f"VERSION REMOTA: {version_remota}"
        )

        log(
            f"DOWNLOAD URL: {download_url}"
        )

        log(
            f"PATCH URL: {patch_url}"
        )

        log(
            f"STRATEGY: {strategy}"
        )

        log(
            f"FORCE UPDATE: {force_update}"
        )

        log(
            f"CHECKSUM: {checksum}"
        )

        log(
            f"FILE SIZE: {file_size}"
        )

        log(
            f"MIN VERSION PATCH: {min_patch}"
        )

        # ==================================================
        # COMPARAR VERSION
        # ==================================================

        if (
            version_remota
            and version_disponible(
                APP_VERSION,
                version_remota
            )
        ):

            resultado[
                "hay_actualizacion"
            ] = True

            log(
                "ACTUALIZACIÓN DISPONIBLE"
            )

        else:

            log(
                "NO HAY ACTUALIZACIÓN"
            )

        # ==================================================
        # VALIDAR PATCH
        # ==================================================

        if (
            resultado[
                "hay_actualizacion"
            ]
            and patch_url
            and strategy == "zip_patch"
            and getattr(
                sys,
                "frozen",
                False
            )
        ):

            cumple_min = True

            if min_patch:

                cumple_min = not (
                    version_disponible(
                        APP_VERSION,
                        min_patch
                    )
                )

            resultado[
                "puede_autoaplicar"
            ] = cumple_min

            log(
                f"PUEDE AUTOAPLICAR: "
                f"{cumple_min}"
            )

        return resultado

    except Exception as e:

        log_error(
            "Error inesperado consultando versión",
            e
        )

        resultado[
            "error"
        ] = (
            f"Error inesperado: {e}"
        )

        return resultado


# ============================================================
# ABRIR DESCARGA
# ============================================================

def abrir_descarga(
    url: str
) -> bool:

    log(
        f"Abriendo navegador: {url}"
    )

    try:

        webbrowser.open(
            url,
            new=2
        )

        return True

    except Exception as e:

        log_error(
            "No se pudo abrir el navegador",
            e
        )

        return False


# ============================================================
# DESCARGAR ARCHIVO
# ============================================================

def descargar_archivo(
    url: str,
    destino: str,
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
    timeout: int = 300,
) -> Dict[str, Any]:

    log("=" * 70)
    log("DESCARGANDO ARCHIVO")
    log(f"URL: {url}")
    log(f"DESTINO: {destino}")

    res: Dict[str, Any] = {
        "ok": False,
        "ruta": None,
        "bytes_descargados": 0,
        "bytes_totales": 0,
        "sha256": None,
        "error": None,
    }

    try:

        http_res = _http_get_raw(
            url,
            timeout=timeout,
            progress_cb=progress_cb,
            destino_archivo=destino
        )

        if not http_res["ok"]:

            err_list = (
                http_res.get(
                    "errores"
                )
                or []
            )

            for error in err_list:
                log(
                    f"DESCARGA ERROR: {error}"
                )

            if err_list:
                msj = err_list[-1]
            else:
                msj = "Error desconocido"

            res[
                "error"
            ] = msj

            if os.path.exists(destino):

                try:
                    os.remove(destino)
                except Exception:
                    pass

            return res

        res[
            "ruta"
        ] = destino

        res[
            "sha256"
        ] = (
            http_res.get(
                "sha256"
            )
            or _sha256_archivo(
                destino
            )
        )

        res[
            "bytes_descargados"
        ] = http_res.get(
            "bytes_descargados",
            0
        )

        res[
            "bytes_totales"
        ] = http_res.get(
            "bytes_totales",
            0
        )

        res["ok"] = True

        log(
            "DESCARGA OK"
        )

        log(
            f"BYTES: {res['bytes_descargados']}"
        )

        log(
            f"SHA256: {res['sha256']}"
        )

    except Exception as e:

        log_error(
            "Error de descarga",
            e
        )

        res[
            "error"
        ] = (
            f"Error de descarga: {e}"
        )

        if os.path.exists(destino):

            try:
                os.remove(destino)
            except Exception:
                pass

    return res


# ============================================================
# EXTRAER ZIP
# ============================================================

def extraer_zip(
    ruta_zip: str,
    dir_destino: str,
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
) -> Dict[str, Any]:

    log("=" * 70)
    log("EXTRAYENDO ZIP")
    log(f"ZIP: {ruta_zip}")
    log(f"DESTINO: {dir_destino}")

    res: Dict[str, Any] = {
        "ok": False,
        "dir_destino": dir_destino,
        "error": None
    }

    try:

        if not os.path.exists(ruta_zip):

            raise FileNotFoundError(
                f"No existe ZIP: {ruta_zip}"
            )

        os.makedirs(
            dir_destino,
            exist_ok=True
        )

        with zipfile.ZipFile(
            ruta_zip,
            "r"
        ) as zf:

            miembros = zf.infolist()

            total = len(
                miembros
            )

            log(
                f"ARCHIVOS EN ZIP: {total}"
            )

            destino_real = os.path.realpath(
                dir_destino
            )

            # =================================================
            # SEGURIDAD ZIP SLIP
            # =================================================

            for miembro in miembros:

                nombre = miembro.filename

                log(
                    f"VALIDANDO ZIP: {nombre}"
                )

                ruta_final = os.path.realpath(
                    os.path.join(
                        dir_destino,
                        nombre
                    )
                )

                if not (
                    ruta_final == destino_real
                    or ruta_final.startswith(
                        destino_real
                        + os.sep
                    )
                ):

                    raise RuntimeError(
                        "El ZIP contiene "
                        "una ruta insegura: "
                        + nombre
                    )

            # =================================================
            # EXTRAER
            # =================================================

            for idx, miembro in enumerate(
                miembros,
                start=1
            ):

                log(
                    f"Extrayendo "
                    f"{idx}/{total}: "
                    f"{miembro.filename}"
                )

                try:

                    zf.extract(
                        miembro,
                        dir_destino
                    )

                except Exception as e:

                    raise RuntimeError(
                        f"No se pudo extraer "
                        f"{miembro.filename}: {e}"
                    )

                if (
                    progress_cb
                    and total
                ):

                    try:

                        progress_cb(
                            idx,
                            total
                        )

                    except Exception:
                        pass

        res["ok"] = True

        log(
            "ZIP EXTRAÍDO CORRECTAMENTE"
        )

    except zipfile.BadZipFile as e:

        log_error(
            "ZIP CORRUPTO",
            e
        )

        res[
            "error"
        ] = (
            "El archivo ZIP está corrupto"
        )

    except Exception as e:

        log_error(
            "Error al extraer ZIP",
            e
        )

        res[
            "error"
        ] = (
            f"Error al extraer ZIP: {e}"
        )

    return res


# ============================================================
# GENERAR BAT
# ============================================================

def _generar_script_actualizacion(
    ruta_app_vieja: str,
    dir_extraccion: str,
    ruta_app_nueva: str,
) -> str:

    log("=" * 70)
    log("GENERANDO SCRIPT BAT")

    dir_app = os.path.dirname(
        ruta_app_vieja
    )

    nombre_bat = (
        "_update_helper.bat"
    )

    ruta_bat = os.path.join(
        dir_app,
        nombre_bat
    )

    nombre_exe = os.path.basename(
        ruta_app_vieja
    )

    log(
        f"DIR APP: {dir_app}"
    )

    log(
        f"DIR PATCH: {dir_extraccion}"
    )

    log(
        f"EXE VIEJO: {ruta_app_vieja}"
    )

    log(
        f"EXE NUEVO: {ruta_app_nueva}"
    )

    contenido = f"""@echo off
setlocal EnableExtensions DisableDelayedExpansion

chcp 65001 >nul

title FacturasVentas - Actualizando

echo.
echo ============================================
echo       FacturasVentas - ACTUALIZACION
echo ============================================
echo.

set "DIR_APP={dir_app}"
set "DIR_PATCH={dir_extraccion}"
set "EXE_OLD={ruta_app_vieja}"
set "EXE_NEW={ruta_app_nueva}"
set "RELAUNCH={os.path.join(dir_app, nombre_exe)}"
set "SELF={ruta_bat}"

echo [1/7] Esperando cierre de la aplicacion...
ping -n 3 127.0.0.1 >nul

echo.
echo [2/7] Verificando parche...

if not exist "%DIR_PATCH%" (
    echo [ERROR] Carpeta del parche no encontrada:
    echo %DIR_PATCH%
    goto error
)

if not exist "%EXE_NEW%" (
    echo [ERROR] No se encontro el nuevo ejecutable:
    echo %EXE_NEW%
    goto error
)

echo.
echo [3/7] Cerrando aplicacion anterior...

taskkill /F /IM "{nombre_exe}" >nul 2>&1

ping -n 3 127.0.0.1 >nul

echo.
echo [4/7] Preparando archivos...

if exist "%DIR_APP%\\_old_version" (
    rmdir /S /Q "%DIR_APP%\\_old_version" >nul 2>&1
)

mkdir "%DIR_APP%\\_old_version" >nul 2>&1

echo.
echo [5/7] Copiando archivos nuevos...

xcopy "%DIR_PATCH%\\*.*" "%DIR_APP%\\" /E /H /C /I /Y

if errorlevel 1 (
    echo.
    echo [ERROR] Error copiando archivos.
    goto error
)

echo.
echo [6/7] Verificando ejecutable...

if not exist "%RELAUNCH%" (
    echo [ERROR] El nuevo ejecutable no existe:
    echo %RELAUNCH%
    goto error
)

echo.
echo [7/7] Actualizacion completada correctamente.

echo.
echo ============================================
echo          ACTUALIZACION EXITOSA
echo ============================================
echo.

ping -n 2 127.0.0.1 >nul

echo Iniciando nueva version...

start "" "%RELAUNCH%" --post-update

ping -n 3 127.0.0.1 >nul

echo Limpiando archivos temporales...

if exist "%DIR_PATCH%" (
    rmdir /S /Q "%DIR_PATCH%" >nul 2>&1
)

del /F /Q "%SELF%" >nul 2>&1

exit /b 0


:error

echo.
echo ============================================
echo   ERROR: NO SE PUDO COMPLETAR ACTUALIZACION
echo ============================================
echo.

echo Carpeta:
echo %DIR_PATCH%

echo.

echo Ejecutable:
echo %RELAUNCH%

echo.

echo El programa NO ha sido actualizado.

echo.
pause

exit /b 1
"""

    try:

        with open(
            ruta_bat,
            "w",
            encoding="utf-8",
            errors="replace"
        ) as f:

            f.write(
                contenido
            )

    except Exception:

        with open(
            ruta_bat,
            "w",
            encoding="cp1252",
            errors="replace"
        ) as f:

            f.write(
                contenido
            )

    log(
        f"BAT CREADO: {ruta_bat}"
    )

    return ruta_bat


# ============================================================
# APLICAR PARCHE
# ============================================================

def aplicar_parche_y_cerrar(
    ruta_zip: str,
    checksum_esperado: Optional[str] = None,
    descargar_progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
    extraer_progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
) -> Dict[str, Any]:

    log("=" * 70)
    log("APLICAR PARCHE")

    res: Dict[str, Any] = {
        "ok": False,
        "bat_path": None,
        "error": None
    }

    # ========================================================
    # SOLO EXE
    # ========================================================

    if not getattr(
        sys,
        "frozen",
        False
    ):

        res[
            "error"
        ] = (
            "El auto-parche solo funciona "
            "cuando la app está compilada a .exe"
        )

        log(
            res["error"]
        )

        return res

    # ========================================================
    # EXISTENCIA ZIP
    # ========================================================

    if not os.path.exists(
        ruta_zip
    ):

        res[
            "error"
        ] = (
            "No existe el archivo ZIP descargado: "
            + ruta_zip
        )

        log(
            res["error"]
        )

        return res

    log(
        f"ZIP EXISTE: {ruta_zip}"
    )

    log(
        f"TAMAÑO ZIP: "
        f"{os.path.getsize(ruta_zip)} bytes"
    )

    # ========================================================
    # CHECKSUM
    # ========================================================

    if checksum_esperado:

        log(
            "Verificando SHA256..."
        )

        checksum_actual = (
            _sha256_archivo(
                ruta_zip
            )
        )

        log(
            f"SHA256 ESPERADO: "
            f"{checksum_esperado}"
        )

        log(
            f"SHA256 ACTUAL: "
            f"{checksum_actual}"
        )

        if (
            checksum_actual.lower()
            != checksum_esperado.lower()
        ):

            res[
                "error"
            ] = (
                "Verificación de integridad "
                "fallida. El checksum SHA256 "
                "no coincide."
            )

            log(
                res["error"]
            )

            return res

    # ========================================================
    # RUTAS
    # ========================================================

    dir_app = (
        obtener_directorio_ejecutable()
    )

    ruta_app_exe = (
        obtener_ruta_app_exe()
    )

    tmp_patch = os.path.join(
        dir_app,
        "_pending_patch"
    )

    log(
        f"DIR APP: {dir_app}"
    )

    log(
        f"APP EXE: {ruta_app_exe}"
    )

    log(
        f"PATCH TEMP: {tmp_patch}"
    )

    # ========================================================
    # ELIMINAR PARCHE ANTERIOR
    # ========================================================

    if os.path.exists(
        tmp_patch
    ):

        log(
            "Eliminando parche anterior..."
        )

        try:

            shutil.rmtree(
                tmp_patch,
                ignore_errors=True
            )

        except Exception as e:

            log_error(
                "No se pudo eliminar parche anterior",
                e
            )

    # ========================================================
    # EXTRAER
    # ========================================================

    ext_res = extraer_zip(
        ruta_zip,
        tmp_patch,
        progress_cb=extraer_progress_cb
    )

    if not ext_res["ok"]:

        res[
            "error"
        ] = ext_res[
            "error"
        ]

        try:

            shutil.rmtree(
                tmp_patch,
                ignore_errors=True
            )

        except Exception:
            pass

        return res

    # ========================================================
    # BUSCAR MAIN.EXE
    # ========================================================

    log(
        "Buscando ejecutable dentro del ZIP..."
    )

    posibles_exes = [

        os.path.join(
            tmp_patch,
            os.path.basename(
                ruta_app_exe
            )
        ),

        os.path.join(
            tmp_patch,
            APP_EXE_NAME
        ),
    ]

    exe_en_zip = next(
        (
            p
            for p in posibles_exes
            if os.path.exists(p)
        ),
        None
    )

    # ========================================================
    # BUSQUEDA RECURSIVA
    # ========================================================

    if not exe_en_zip:

        log(
            "No se encontró directamente. "
            "Buscando recursivamente..."
        )

        for root, dirs, files in os.walk(
            tmp_patch
        ):

            log(
                f"Revisando: {root}"
            )

            if APP_EXE_NAME in files:

                exe_en_zip = os.path.join(
                    root,
                    APP_EXE_NAME
                )

                break

    if not exe_en_zip:

        res[
            "error"
        ] = (
            f"No se encontró {APP_EXE_NAME} "
            "dentro del ZIP."
        )

        log(
            res["error"]
        )

        try:

            shutil.rmtree(
                tmp_patch,
                ignore_errors=True
            )

        except Exception:
            pass

        return res

    log(
        f"EXE EN ZIP: {exe_en_zip}"
    )

    # ========================================================
    # GENERAR BAT
    # ========================================================

    try:

        ruta_bat = (
            _generar_script_actualizacion(
                ruta_app_exe,
                tmp_patch,
                exe_en_zip
            )
        )

    except Exception as e:

        log_error(
            "No se pudo crear script BAT",
            e
        )

        res[
            "error"
        ] = (
            "No se pudo crear el script "
            f"de actualización: {e}"
        )

        return res

    res["ok"] = True

    res[
        "bat_path"
    ] = ruta_bat

    log(
        f"PARCHE PREPARADO: {ruta_bat}"
    )

    return res


# ============================================================
# EJECUTAR ACTUALIZADOR
# ============================================================

def ejecutar_actualizador_y_salir(
    ruta_bat: str
) -> bool:

    log("=" * 70)
    log("EJECUTANDO ACTUALIZADOR")

    try:

        ruta_bat_abs = os.path.abspath(
            ruta_bat
        )

        log(
            f"BAT: {ruta_bat_abs}"
        )

        if not os.path.exists(
            ruta_bat_abs
        ):

            log(
                "ERROR: BAT no existe"
            )

            return False

        if os.name == "nt":

            creation_flags = (
                0x08000000
            )

            log(
                "Sistema operativo: Windows"
            )

            log(
                "Ejecutando cmd.exe..."
            )

            proceso = subprocess.Popen(
                [
                    "cmd.exe",
                    "/C",
                    ruta_bat_abs
                ],
                shell=False,
                close_fds=True,
                creationflags=creation_flags,
                cwd=os.path.dirname(
                    ruta_bat_abs
                )
            )

            log(
                f"PID actualizador: "
                f"{proceso.pid}"
            )

        else:

            proceso = subprocess.Popen(
                [
                    "bash",
                    ruta_bat_abs
                ]
            )

            log(
                f"PID actualizador: "
                f"{proceso.pid}"
            )

        log(
            "Actualizador iniciado correctamente."
        )

        return True

    except Exception as e:

        log_error(
            "No se pudo ejecutar actualizador",
            e
        )

        return False


# ============================================================
# FUNCIÓN COMPLETA PARA ACTUALIZAR
# ============================================================

def actualizar_desde_servidor(
    progress_descarga_cb: Optional[
        Callable[[int, int], None]
    ] = None,
    progress_extraccion_cb: Optional[
        Callable[[int, int], None]
    ] = None,
) -> Dict[str, Any]:

    log("")
    log("=" * 70)
    log("INICIO ACTUALIZACIÓN")
    log("=" * 70)

    log(
        f"APP VERSION: {APP_VERSION}"
    )

    log(
        f"EXE: {obtener_ruta_app_exe()}"
    )

    log(
        f"LOG: {obtener_ruta_log()}"
    )

    resultado: Dict[str, Any] = {
        "ok": False,
        "actualizacion_disponible": False,
        "actualizacion_aplicada": False,
        "version_actual": APP_VERSION,
        "version_nueva": None,
        "error": None,
        "bat_path": None,
    }

    # ========================================================
    # CONSULTAR VERSION
    # ========================================================

    log(
        "PASO 1: Consultando version.json..."
    )

    info = consultar_version_remota()

    if not info["ok"]:

        resultado[
            "error"
        ] = (
            info.get(
                "error"
            )
            or "No se pudo consultar la versión."
        )

        log(
            f"ERROR FINAL: {resultado['error']}"
        )

        return resultado

    # ========================================================
    # NO HAY ACTUALIZACIÓN
    # ========================================================

    if not info[
        "hay_actualizacion"
    ]:

        log(
            "No hay actualización disponible."
        )

        resultado["ok"] = True

        return resultado

    resultado[
        "actualizacion_disponible"
    ] = True

    resultado[
        "version_nueva"
    ] = info.get(
        "version_remota"
    )

    log(
        f"NUEVA VERSION: "
        f"{resultado['version_nueva']}"
    )

    # ========================================================
    # VERIFICAR PATCH
    # ========================================================

    log(
        "PASO 2: Verificando posibilidad "
        "de autoaplicación..."
    )

    if not info[
        "puede_autoaplicar"
    ]:

        resultado[
            "error"
        ] = (
            "La actualización está disponible, "
            "pero no puede aplicarse automáticamente."
        )

        log(
            resultado["error"]
        )

        return resultado

    patch_url = info.get(
        "patch_url"
    )

    if not patch_url:

        resultado[
            "error"
        ] = (
            "version.json no contiene patch_url."
        )

        log(
            resultado["error"]
        )

        return resultado

    log(
        f"PATCH URL: {patch_url}"
    )

    # ========================================================
    # CARPETA TEMPORAL
    # ========================================================

    dir_app = (
        obtener_directorio_ejecutable()
    )

    ruta_zip = os.path.join(
        dir_app,
        "_update_package.zip"
    )

    log(
        f"ZIP TEMPORAL: {ruta_zip}"
    )

    # ========================================================
    # ELIMINAR ZIP ANTERIOR
    # ========================================================

    if os.path.exists(
        ruta_zip
    ):

        log(
            "Eliminando ZIP anterior..."
        )

        try:

            os.remove(
                ruta_zip
            )

        except Exception as e:

            log_error(
                "No se pudo eliminar ZIP anterior",
                e
            )

    # ========================================================
    # DESCARGAR
    # ========================================================

    log(
        "PASO 3: Descargando parche..."
    )

    descarga = descargar_archivo(
        patch_url,
        ruta_zip,
        progress_cb=progress_descarga_cb,
        timeout=300
    )

    if not descarga["ok"]:

        resultado[
            "error"
        ] = (
            descarga.get(
                "error"
            )
            or "No se pudo descargar el parche."
        )

        log(
            f"ERROR DESCARGA: "
            f"{resultado['error']}"
        )

        return resultado

    # ========================================================
    # VALIDAR TAMAÑO
    # ========================================================

    log(
        "PASO 4: Validando tamaño del ZIP..."
    )

    file_size = int(
        info.get(
            "file_size_bytes"
        )
        or 0
    )

    if file_size > 0:

        tamano_real = os.path.getsize(
            ruta_zip
        )

        log(
            f"TAMAÑO ESPERADO: {file_size}"
        )

        log(
            f"TAMAÑO REAL: {tamano_real}"
        )

        if tamano_real != file_size:

            resultado[
                "error"
            ] = (
                "El tamaño del ZIP descargado "
                "no coincide con file_size_bytes."
            )

            log(
                resultado["error"]
            )

            try:
                os.remove(
                    ruta_zip
                )
            except Exception:
                pass

            return resultado

    # ========================================================
    # APLICAR PARCHE
    # ========================================================

    log(
        "PASO 5: Preparando parche..."
    )

    parche = aplicar_parche_y_cerrar(
        ruta_zip,
        checksum_esperado=info.get(
            "checksum_sha256"
        ),
        descargar_progress_cb=progress_descarga_cb,
        extraer_progress_cb=progress_extraccion_cb
    )

    if not parche["ok"]:

        resultado[
            "error"
        ] = (
            parche.get(
                "error"
            )
            or "No se pudo preparar la actualización."
        )

        log(
            f"ERROR PARCHE: "
            f"{resultado['error']}"
        )

        return resultado

    resultado[
        "ok"
    ] = True

    resultado[
        "actualizacion_aplicada"
    ] = True

    resultado[
        "bat_path"
    ] = parche.get(
        "bat_path"
    )

    log(
        "ACTUALIZACIÓN PREPARADA CORRECTAMENTE"
    )

    log(
        f"BAT: {resultado['bat_path']}"
    )

    log("=" * 70)
    log("FIN ACTUALIZACIÓN")
    log("=" * 70)

    return resultado


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    print("")
    print("=" * 70)
    print(" FACTURASVENTAS - TEST ACTUALIZADOR")
    print("=" * 70)
    print("")

    log(
        "INICIANDO TEST MANUAL"
    )

    log(
        f"Python: {sys.version}"
    )

    log(
        f"OS: {os.name}"
    )

    log(
        f"Frozen: {getattr(sys, 'frozen', False)}"
    )

    log(
        f"Executable: {sys.executable}"
    )

    log(
        f"Directorio: "
        f"{obtener_directorio_ejecutable()}"
    )

    log(
        f"Log: {obtener_ruta_log()}"
    )

    resultado = consultar_version_remota()

    print("")
    print("=" * 70)
    print(" RESULTADO")
    print("=" * 70)

    print(
        json.dumps(
            resultado,
            indent=4,
            ensure_ascii=False
        )
    )

    print("")
    print(
        "Presiona ENTER para cerrar..."
    )

    input()
