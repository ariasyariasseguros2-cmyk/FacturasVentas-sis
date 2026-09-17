import os
import sys
import ssl
import json
import time
import shutil
import hashlib
import zipfile
import tempfile
import subprocess
import urllib.request
import urllib.error
import ctypes
from typing import Optional, Dict, Any, Callable


# ============================================================
# CONFIGURACIÓN
# ============================================================

APP_NAME = "FacturasVentas-SIS"

# ------------------------------------------------------------
# IMPORTANTE:
#
# Para probar:
#   EXE actual = 1.0.0
#   servidor   = 1.0.1
#
# Cuando compiles la nueva versión:
#   APP_VERSION = "1.0.1"
# ------------------------------------------------------------

APP_VERSION = "1.0.1"

VERSION_URL = (
    "https://www.aasnet.tech/updates/version.json"
)

APP_EXE_NAME = "main.exe"

REQUEST_TIMEOUT = 30

# Permitir segundo intento SSL sin validación
ALLOW_INSECURE_SSL = True


# ============================================================
# LOG
# ============================================================

def _log(mensaje: str) -> None:

    try:

        print(
            f"[UPDATER] {mensaje}",
            flush=True
        )

    except Exception:
        pass


# ============================================================
# DETECTAR EXE
# ============================================================

def es_exe() -> bool:

    return bool(
        getattr(
            sys,
            "frozen",
            False
        )
    )


# ============================================================
# DIRECTORIO DEL EJECUTABLE
# ============================================================

def obtener_directorio_ejecutable() -> str:

    """
    EXE:

        C:\\Program Files\\FacturasVentas-SIS

    Python:

        carpeta donde se ejecuta el proyecto
    """

    try:

        if es_exe():

            return os.path.dirname(
                os.path.abspath(
                    sys.executable
                )
            )

        return os.path.dirname(
            os.path.abspath(
                sys.argv[0]
            )
        )

    except Exception:

        return os.getcwd()


# ============================================================
# DIRECTORIO SEGURO DE ACTUALIZACIONES
# ============================================================

def obtener_directorio_updates() -> str:

    """
    NUNCA usar Program Files para descargas.

    Se utiliza:

    C:\\Users\\USUARIO\\AppData\\Local\\
        FacturasVentas-SIS\\_updates
    """

    local_app_data = os.environ.get(
        "LOCALAPPDATA"
    )

    if not local_app_data:

        local_app_data = os.path.expanduser(
            "~"
        )

    ruta = os.path.join(
        local_app_data,
        APP_NAME,
        "_updates"
    )

    os.makedirs(
        ruta,
        exist_ok=True
    )

    _log(
        f"DIRECTORIO UPDATES: {ruta}"
    )

    return ruta


# ============================================================
# CREAR CONTEXTO SSL
# ============================================================

def _crear_contexto_ssl(
    inseguro: bool = False
):

    try:

        if inseguro:

            return ssl._create_unverified_context()

        return ssl.create_default_context()

    except Exception as e:

        _log(
            f"Error creando SSL: {e}"
        )

        return ssl._create_unverified_context()


# ============================================================
# HTTP GET
# ============================================================

def _http_get(
    url: str,
    timeout: int = REQUEST_TIMEOUT,
    destino: Optional[str] = None,
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
) -> Dict[str, Any]:

    _log("=" * 70)
    _log("INICIO HTTP GET")
    _log(f"URL: {url}")
    _log(f"TIMEOUT: {timeout}")
    _log(f"DESTINO: {destino}")

    headers = {

        "User-Agent":
            f"FacturasVentas-SIS/{APP_VERSION}",

        "Accept":
            "*/*",

        "Cache-Control":
            "no-cache, no-store, must-revalidate",

        "Pragma":
            "no-cache",

    }

    _log(
        f"HEADERS: {headers}"
    )

    ultimo_error = None

    estrategias = []

    if ALLOW_INSECURE_SSL:

        estrategias = [

            (
                "NORMAL",
                _crear_contexto_ssl(False)
            ),

            (
                "SSL INSEGURO",
                _crear_contexto_ssl(True)
            ),

        ]

    else:

        estrategias = [

            (
                "NORMAL",
                _crear_contexto_ssl(False)
            )

        ]

    for indice, (
        nombre,
        contexto
    ) in enumerate(
        estrategias,
        start=1
    ):

        try:

            _log("-" * 70)

            _log(
                f"ESTRATEGIA "
                f"{indice}/"
                f"{len(estrategias)}"
            )

            _log(
                f"URL: {url}"
            )

            _log(
                f"SSL: {nombre}"
            )

            _log(
                "Ejecutando urllib.request.urlopen()..."
            )

            request = urllib.request.Request(
                url,
                headers=headers,
                method="GET"
            )

            with urllib.request.urlopen(
                request,
                timeout=timeout,
                context=contexto
            ) as response:

                status = getattr(
                    response,
                    "status",
                    response.getcode()
                )

                response_url = response.geturl()

                _log(
                    f"HTTP STATUS: {status}"
                )

                _log(
                    f"RESPONSE URL: "
                    f"{response_url}"
                )

                if (
                    status < 200
                    or status >= 300
                ):

                    raise RuntimeError(
                        f"HTTP {status}"
                    )

                # ------------------------------------------------
                # DESCARGA A ARCHIVO
                # ------------------------------------------------

                if destino:

                    return _guardar_descarga(
                        response,
                        destino,
                        progress_cb
                    )

                # ------------------------------------------------
                # DATOS EN MEMORIA
                # ------------------------------------------------

                data = response.read()

                _log(
                    f"DATA RECIBIDA: "
                    f"{len(data)} bytes"
                )

                return {

                    "ok": True,

                    "status":
                        status,

                    "url":
                        response_url,

                    "data":
                        data,

                }

        except Exception as e:

            ultimo_error = e

            _log(
                f"ERROR ESTRATEGIA "
                f"{indice}: {e}"
            )

    return {

        "ok": False,

        "error":
            str(
                ultimo_error
                or
                "Error HTTP desconocido."
            ),

    }


# ============================================================
# GUARDAR DESCARGA
# ============================================================

def _guardar_descarga(
    response,
    destino: str,
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
) -> Dict[str, Any]:

    try:

        carpeta = os.path.dirname(
            os.path.abspath(
                destino
            )
        )

        # ----------------------------------------------------
        # CREAR CARPETA
        # ----------------------------------------------------

        os.makedirs(
            carpeta,
            exist_ok=True
        )

        _log(
            f"CARPETA DESCARGA: {carpeta}"
        )

        # ----------------------------------------------------
        # CONTENT LENGTH
        # ----------------------------------------------------

        total = 0

        try:

            total = int(
                response.headers.get(
                    "Content-Length",
                    "0"
                )
            )

        except Exception:

            total = 0

        _log(
            f"CONTENT-LENGTH: {total}"
        )

        # ----------------------------------------------------
        # ARCHIVO TEMPORAL
        # ----------------------------------------------------

        temporal = (
            destino
            + ".download"
        )

        recibidos = 0

        # ----------------------------------------------------
        # DESCARGAR
        # ----------------------------------------------------

        with open(
            temporal,
            "wb"
        ) as archivo:

            while True:

                bloque = response.read(
                    1024 * 1024
                )

                if not bloque:

                    break

                archivo.write(
                    bloque
                )

                recibidos += len(
                    bloque
                )

                if progress_cb:

                    try:

                        progress_cb(
                            recibidos,
                            total
                        )

                    except Exception:

                        pass

        # ----------------------------------------------------
        # VALIDAR ARCHIVO
        # ----------------------------------------------------

        if not os.path.exists(
            temporal
        ):

            raise RuntimeError(
                "No se creó el archivo descargado."
            )

        tamano = os.path.getsize(
            temporal
        )

        if tamano <= 0:

            raise RuntimeError(
                "El archivo descargado está vacío."
            )

        _log(
            f"ARCHIVO TEMPORAL: {temporal}"
        )

        _log(
            f"TAMAÑO DESCARGADO: {tamano} bytes"
        )

        # ----------------------------------------------------
        # REEMPLAZAR DESTINO
        # ----------------------------------------------------

        if os.path.exists(
            destino
        ):

            try:

                os.remove(
                    destino
                )

            except Exception:

                pass

        os.replace(
            temporal,
            destino
        )

        _log(
            f"DESCARGA COMPLETADA: {destino}"
        )

        _log(
            f"TAMAÑO FINAL: "
            f"{os.path.getsize(destino)} bytes"
        )

        return {

            "ok": True,

            "path":
                destino,

            "size":
                os.path.getsize(
                    destino
                ),

        }

    except Exception as e:

        try:

            if os.path.exists(
                temporal
            ):

                os.remove(
                    temporal
                )

        except Exception:

            pass

        _log(
            f"ERROR GUARDANDO DESCARGA: {e}"
        )

        return {

            "ok": False,

            "error":
                str(e),

        }


# ============================================================
# CONSULTAR VERSIÓN REMOTA
# ============================================================

def consultar_version_remota(
    timeout: int = 15
) -> Dict[str, Any]:

    _log("=" * 70)
    _log("CONSULTANDO VERSION REMOTA")

    _log(
        f"VERSION LOCAL: "
        f"{APP_VERSION}"
    )

    _log(
        f"VERSION URL: "
        f"{VERSION_URL}"
    )

    _log("=" * 70)

    resultado = _http_get(
        VERSION_URL,
        timeout=timeout
    )

    if not resultado.get(
        "ok"
    ):

        return {

            "ok": False,

            "error":
                resultado.get(
                    "error",
                    "No se pudo consultar la versión remota."
                )

        }

    try:

        data = resultado.get(
            "data",
            b""
        )

        texto = data.decode(
            "utf-8-sig"
        )

        _log(
            f"VERSION.JSON recibida: "
            f"{len(data)} bytes"
        )

        _log(
            "CONTENIDO VERSION.JSON:"
        )

        _log(
            texto
        )

        remoto = json.loads(
            texto
        )

        # ----------------------------------------------------
        # DATOS
        # ----------------------------------------------------

        version_remota = str(
            remoto.get(
                "version",
                ""
            )
        ).strip()

        strategy = str(
            remoto.get(
                "strategy",
                "zip_patch"
            )
        ).strip()

        force_update = bool(
            remoto.get(
                "force_update",
                False
            )
        )

        download_url = remoto.get(
            "download_url"
        )

        patch_url = remoto.get(
            "patch_url"
        )

        checksum = remoto.get(
            "checksum_sha256"
        )

        if not checksum:

            checksum = None

        file_size = remoto.get(
            "file_size_bytes",
            0
        )

        min_version = str(
            remoto.get(
                "min_version_to_patch",
                "0.0.0"
            )
        )

        release_notes = remoto.get(
            "release_notes",
            []
        )

        # ----------------------------------------------------
        # LOG
        # ----------------------------------------------------

        _log(
            f"VERSION REMOTA: "
            f"{version_remota}"
        )

        _log(
            f"DOWNLOAD URL: "
            f"{download_url}"
        )

        _log(
            f"PATCH URL: "
            f"{patch_url}"
        )

        _log(
            f"STRATEGY: "
            f"{strategy}"
        )

        _log(
            f"FORCE UPDATE: "
            f"{force_update}"
        )

        _log(
            f"CHECKSUM: "
            f"{checksum}"
        )

        _log(
            f"FILE SIZE: "
            f"{file_size}"
        )

        _log(
            f"MIN VERSION PATCH: "
            f"{min_version}"
        )

        # ----------------------------------------------------
        # COMPARAR
        # ----------------------------------------------------

        hay_actualizacion = (
            comparar_versiones(
                APP_VERSION,
                version_remota
            ) < 0
        )

        puede_autoaplicar = (
            comparar_versiones(
                APP_VERSION,
                min_version
            ) >= 0
        )

        _log(
            f"ACTUALIZACIÓN DISPONIBLE: "
            f"{hay_actualizacion}"
        )

        _log(
            f"PUEDE AUTOAPLICAR: "
            f"{puede_autoaplicar}"
        )

        return {

            "ok": True,

            "hay_actualizacion":
                hay_actualizacion,

            "version_local":
                APP_VERSION,

            "version_remota":
                version_remota,

            "download_url":
                download_url,

            "patch_url":
                patch_url,

            "strategy":
                strategy,

            "force_update":
                force_update,

            "checksum_sha256":
                checksum,

            "file_size_bytes":
                file_size,

            "min_version_to_patch":
                min_version,

            "puede_autoaplicar":
                puede_autoaplicar,

            "release_notes":
                release_notes,

            "notas":
                release_notes,

            "raw":
                remoto,

        }

    except Exception as e:

        _log(
            "ERROR PROCESANDO "
            f"VERSION.JSON: {e}"
        )

        return {

            "ok": False,

            "error":
                "El servidor respondió correctamente, "
                "pero version.json no es válido: "
                f"{e}"

        }


# ============================================================
# VERSIONES
# ============================================================

def _version_tuple(
    version: str
):

    try:

        partes = str(
            version
        ).strip().split(".")

        valores = []

        for parte in partes:

            numero = ""

            for caracter in parte:

                if caracter.isdigit():

                    numero += caracter

                else:

                    break

            valores.append(
                int(
                    numero
                    or
                    "0"
                )
            )

        while len(valores) < 3:

            valores.append(0)

        return tuple(
            valores[:3]
        )

    except Exception:

        return (
            0,
            0,
            0
        )


def comparar_versiones(
    version_a: str,
    version_b: str
) -> int:

    a = _version_tuple(
        version_a
    )

    b = _version_tuple(
        version_b
    )

    _log(
        f"Comparando versiones: "
        f"LOCAL={a} "
        f"REMOTA={b}"
    )

    if a < b:

        return -1

    if a > b:

        return 1

    return 0


# ============================================================
# DESCARGAR ARCHIVO
# ============================================================

def descargar_archivo(
    url: str,
    destino: str,
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None,
    timeout: int = 60
) -> Dict[str, Any]:

    if not url:

        return {

            "ok": False,

            "error":
                "URL de descarga vacía."

        }

    _log(
        f"INICIANDO DESCARGA: {url}"
    )

    _log(
        f"DESTINO: {destino}"
    )

    resultado = _http_get(
        url,
        timeout=timeout,
        destino=destino,
        progress_cb=progress_cb
    )

    return resultado


# ============================================================
# SHA256
# ============================================================

def calcular_sha256(
    ruta: str
) -> str:

    sha = hashlib.sha256()

    with open(
        ruta,
        "rb"
    ) as archivo:

        while True:

            bloque = archivo.read(
                1024 * 1024
            )

            if not bloque:

                break

            sha.update(
                bloque
            )

    return sha.hexdigest().lower()


# ============================================================
# VALIDAR ZIP
# ============================================================

def validar_zip(
    ruta_zip: str
) -> Dict[str, Any]:

    try:

        if not os.path.isfile(
            ruta_zip
        ):

            return {

                "ok": False,

                "error":
                    "No existe el archivo ZIP."

            }

        if os.path.getsize(
            ruta_zip
        ) <= 0:

            return {

                "ok": False,

                "error":
                    "El ZIP está vacío."

            }

        with zipfile.ZipFile(
            ruta_zip,
            "r"
        ) as z:

            # ------------------------------------------------
            # TEST ZIP
            # ------------------------------------------------

            if z.testzip() is not None:

                return {

                    "ok": False,

                    "error":
                        "El ZIP está corrupto."

                }

            nombres = z.namelist()

            if not nombres:

                return {

                    "ok": False,

                    "error":
                        "El ZIP no contiene archivos."

                }

            return {

                "ok": True,

                "files":
                    nombres

            }

    except zipfile.BadZipFile:

        return {

            "ok": False,

            "error":
                "El archivo descargado "
                "no es un ZIP válido."

        }

    except Exception as e:

        return {

            "ok": False,

            "error":
                str(e)

        }


# ============================================================
# BUSCAR MAIN.EXE DENTRO DEL ZIP
# ============================================================

def _buscar_main_en_zip(
    nombres
) -> Optional[str]:

    # --------------------------------------------------------
    # CASO 1:
    #
    # main.exe
    # --------------------------------------------------------

    for nombre in nombres:

        limpio = nombre.replace(
            "\\",
            "/"
        ).strip("/")

        if (
            limpio.lower()
            ==
            APP_EXE_NAME.lower()
        ):

            return nombre

    # --------------------------------------------------------
    # CASO 2:
    #
    # carpeta/main.exe
    # --------------------------------------------------------

    for nombre in nombres:

        limpio = nombre.replace(
            "\\",
            "/"
        ).strip("/")

        if (
            os.path.basename(
                limpio
            ).lower()
            ==
            APP_EXE_NAME.lower()
        ):

            return nombre

    return None


# ============================================================
# CREAR SCRIPT POWERSHELL
# ============================================================

def _crear_script_actualizador(
    ruta_zip: str,
    dir_app: str
) -> Dict[str, Any]:

    try:

        # ----------------------------------------------------
        # MUY IMPORTANTE
        #
        # El script se guarda en LOCALAPPDATA.
        #
        # NO en Program Files.
        # ----------------------------------------------------

        updates_dir = (
            obtener_directorio_updates()
        )

        script_path = os.path.join(
            updates_dir,
            "apply_update.ps1"
        )

        pid_actual = os.getpid()

        zip_ps = (
            os.path.abspath(
                ruta_zip
            ).replace(
                "'",
                "''"
            )
        )

        app_ps = (
            os.path.abspath(
                dir_app
            ).replace(
                "'",
                "''"
            )
        )

        exe_ps = (
            os.path.abspath(
                os.path.join(
                    dir_app,
                    APP_EXE_NAME
                )
            ).replace(
                "'",
                "''"
            )
        )

        # ----------------------------------------------------
        # POWERSHELL
        # ----------------------------------------------------

        script = f'''$ErrorActionPreference = "Stop"

$ZipPath = '{zip_ps}'
$AppDir = '{app_ps}'
$ExePath = '{exe_ps}'
$PidToWait = {pid_actual}

$TempDir = Join-Path `
    $env:TEMP `
    "FacturasVentas-SIS-update-$PidToWait"

$ExtractDir = Join-Path `
    $TempDir `
    "extract"

Write-Host "=========================================="
Write-Host "FACTURASVENTAS-SIS ACTUALIZADOR"
Write-Host "=========================================="

Write-Host "ZIP:"
Write-Host $ZipPath

Write-Host "APP:"
Write-Host $AppDir

Write-Host "EXE:"
Write-Host $ExePath

Write-Host ""
Write-Host "Esperando proceso principal..."

# ------------------------------------------------------------
# ESPERAR A QUE CIERRE EL EXE
# ------------------------------------------------------------

for ($i = 0; $i -lt 120; $i++) {{

    $proc = Get-Process `
        -Id $PidToWait `
        -ErrorAction SilentlyContinue

    if ($null -eq $proc) {{

        break
    }}

    Start-Sleep `
        -Milliseconds 500
}}

Write-Host "Proceso principal cerrado."

Start-Sleep `
    -Seconds 2

# ------------------------------------------------------------
# VALIDAR ZIP
# ------------------------------------------------------------

if (-not (Test-Path -LiteralPath $ZipPath)) {{

    throw "No existe el ZIP: $ZipPath"
}}

# ------------------------------------------------------------
# CREAR TEMPORAL
# ------------------------------------------------------------

New-Item `
    -ItemType Directory `
    -Force `
    -Path $TempDir |
    Out-Null

New-Item `
    -ItemType Directory `
    -Force `
    -Path $ExtractDir |
    Out-Null

# ------------------------------------------------------------
# EXTRAER ZIP
# ------------------------------------------------------------

Write-Host "Extrayendo ZIP..."

Expand-Archive `
    -LiteralPath $ZipPath `
    -DestinationPath $ExtractDir `
    -Force

# ------------------------------------------------------------
# BUSCAR MAIN.EXE
# ------------------------------------------------------------

$NewExe = Get-ChildItem `
    -Path $ExtractDir `
    -Filter "{APP_EXE_NAME}" `
    -File `
    -Recurse |
    Select-Object -First 1

if ($null -eq $NewExe) {{

    throw `
        "No se encontró {APP_EXE_NAME} dentro del ZIP."
}}

Write-Host "Nuevo ejecutable:"
Write-Host $NewExe.FullName

# ------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------

$BackupPath = "$ExePath.backup"

if (Test-Path -LiteralPath $ExePath) {{

    Write-Host "Creando respaldo..."

    Copy-Item `
        -LiteralPath $ExePath `
        -Destination $BackupPath `
        -Force
}}

# ------------------------------------------------------------
# REEMPLAZAR EXE
# ------------------------------------------------------------

Write-Host "Reemplazando ejecutable..."

Copy-Item `
    -LiteralPath $NewExe.FullName `
    -Destination $ExePath `
    -Force

# ------------------------------------------------------------
# VERIFICAR
# ------------------------------------------------------------

if (-not (Test-Path -LiteralPath $ExePath)) {{

    throw `
        "No se pudo instalar {APP_EXE_NAME}."
}}

Write-Host ""
Write-Host "=========================================="
Write-Host "ACTUALIZACION APLICADA CORRECTAMENTE"
Write-Host "=========================================="

Start-Sleep `
    -Seconds 2

# ------------------------------------------------------------
# INICIAR NUEVA VERSIÓN
# ------------------------------------------------------------

Write-Host "Iniciando nueva versión..."

Start-Process `
    -FilePath $ExePath `
    -WorkingDirectory $AppDir

Start-Sleep `
    -Seconds 3

# ------------------------------------------------------------
# LIMPIAR TEMPORAL
# ------------------------------------------------------------

try {{

    Remove-Item `
        -LiteralPath $TempDir `
        -Recurse `
        -Force `
        -ErrorAction SilentlyContinue

}} catch {{}}

# ------------------------------------------------------------
# LIMPIAR ZIP
# ------------------------------------------------------------

try {{

    Remove-Item `
        -LiteralPath $ZipPath `
        -Force `
        -ErrorAction SilentlyContinue

}} catch {{}}

# ------------------------------------------------------------
# LIMPIAR SCRIPT
# ------------------------------------------------------------

try {{

    Remove-Item `
        -LiteralPath $PSCommandPath `
        -Force `
        -ErrorAction SilentlyContinue

}} catch {{}}

Write-Host ""
Write-Host "ACTUALIZACION FINALIZADA."
'''

        # ----------------------------------------------------
        # GUARDAR SCRIPT
        # ----------------------------------------------------

        with open(
            script_path,
            "w",
            encoding="utf-8"
        ) as archivo:

            archivo.write(
                script
            )

        _log(
            f"PowerShell creado: "
            f"{script_path}"
        )

        return {

            "ok": True,

            "script_path":
                script_path

        }

    except Exception as e:

        _log(
            f"ERROR CREANDO SCRIPT: {e}"
        )

        return {

            "ok": False,

            "error":
                str(e)

        }


# ============================================================
# APLICAR PARCHE
# ============================================================

def aplicar_parche_y_cerrar(
    ruta_zip: str,
    checksum_esperado: Optional[str] = None,
    extraer_progress_cb: Optional[
        Callable[[int, int], None]
    ] = None
) -> Dict[str, Any]:

    try:

        _log("=" * 70)
        _log("PREPARANDO ACTUALIZACIÓN")

        _log(
            f"ZIP: {ruta_zip}"
        )

        # ----------------------------------------------------
        # VALIDAR EXISTENCIA
        # ----------------------------------------------------

        if not os.path.isfile(
            ruta_zip
        ):

            return {

                "ok": False,

                "error":
                    "No existe el archivo ZIP."

            }

        # ----------------------------------------------------
        # SHA256
        # ----------------------------------------------------

        if checksum_esperado:

            _log(
                "Calculando SHA256..."
            )

            checksum_real = (
                calcular_sha256(
                    ruta_zip
                )
            )

            _log(
                f"SHA256 REAL: "
                f"{checksum_real}"
            )

            _log(
                f"SHA256 ESPERADO: "
                f"{checksum_esperado}"
            )

            if (
                checksum_real.lower()
                !=
                str(
                    checksum_esperado
                ).strip().lower()
            ):

                return {

                    "ok": False,

                    "error":
                        "El SHA-256 del archivo "
                        "no coincide con el servidor."

                }

        else:

            _log(
                "No se proporcionó SHA256."
            )

            _log(
                "Se continúa sin validación SHA256."
            )

        # ----------------------------------------------------
        # VALIDAR ZIP
        # ----------------------------------------------------

        validacion = validar_zip(
            ruta_zip
        )

        if not validacion.get(
            "ok"
        ):

            return validacion

        nombres = validacion.get(
            "files",
            []
        )

        # ----------------------------------------------------
        # BUSCAR MAIN.EXE
        # ----------------------------------------------------

        main_zip = (
            _buscar_main_en_zip(
                nombres
            )
        )

        if not main_zip:

            return {

                "ok": False,

                "error":
                    "El ZIP no contiene "
                    f"{APP_EXE_NAME}."

            }

        _log(
            f"MAIN.EXE EN ZIP: "
            f"{main_zip}"
        )

        # ----------------------------------------------------
        # DIRECTORIO DE LA APP
        # ----------------------------------------------------

        dir_app = (
            obtener_directorio_ejecutable()
        )

        _log(
            f"DIRECTORIO APP: "
            f"{dir_app}"
        )

        # ----------------------------------------------------
        # VERIFICAR DIRECTORIO
        # ----------------------------------------------------

        if not os.path.isdir(
            dir_app
        ):

            return {

                "ok": False,

                "error":
                    "No existe el directorio "
                    f"de la aplicación: {dir_app}"

            }

        # ----------------------------------------------------
        # CREAR SCRIPT
        # ----------------------------------------------------

        resultado_script = (
            _crear_script_actualizador(
                ruta_zip,
                dir_app
            )
        )

        if not resultado_script.get(
            "ok"
        ):

            return resultado_script

        script_path = (
            resultado_script.get(
                "script_path"
            )
        )

        _log(
            f"ACTUALIZADOR: "
            f"{script_path}"
        )

        # ----------------------------------------------------
        # PROGRESO
        # ----------------------------------------------------

        if extraer_progress_cb:

            try:

                extraer_progress_cb(
                    1,
                    1
                )

            except Exception:

                pass

        return {

            "ok": True,

            "bat_path":
                script_path,

            "script_path":
                script_path,

            "zip_path":
                ruta_zip,

            "app_dir":
                dir_app,

        }

    except Exception as e:

        _log(
            f"ERROR PREPARANDO PARCHE: {e}"
        )

        return {

            "ok": False,

            "error":
                str(e)

        }


# ============================================================
# EJECUTAR ACTUALIZADOR CON UAC
# ============================================================

def ejecutar_actualizador_y_salir(
    ruta_bat: str
) -> bool:

    try:

        # ----------------------------------------------------
        # VALIDAR RUTA
        # ----------------------------------------------------

        if not ruta_bat:

            _log(
                "ruta_bat vacía."
            )

            return False

        if not os.path.isfile(
            ruta_bat
        ):

            _log(
                f"No existe actualizador: "
                f"{ruta_bat}"
            )

            return False

        # ----------------------------------------------------
        # POWERSHELL
        # ----------------------------------------------------

        powershell = shutil.which(
            "powershell.exe"
        )

        if not powershell:

            powershell = os.path.join(

                os.environ.get(
                    "WINDIR",
                    r"C:\Windows"
                ),

                "System32",

                "WindowsPowerShell",

                "v1.0",

                "powershell.exe"
            )

        if not os.path.isfile(
            powershell
        ):

            _log(
                "No se encontró PowerShell."
            )

            return False

        # ----------------------------------------------------
        # ARGUMENTOS
        # ----------------------------------------------------

        parametros = (
            "-NoProfile "
            "-ExecutionPolicy Bypass "
            "-File "
            f'"{ruta_bat}"'
        )

        _log(
            "Solicitando permisos de administrador..."
        )

        # ----------------------------------------------------
        # UAC
        # ----------------------------------------------------

        resultado = (
            ctypes.windll.shell32.ShellExecuteW(

                None,

                "runas",

                powershell,

                parametros,

                os.path.dirname(
                    ruta_bat
                ),

                1
            )
        )

        # ----------------------------------------------------
        # RESULTADO
        # ----------------------------------------------------

        if resultado <= 32:

            _log(
                f"ShellExecuteW falló: "
                f"{resultado}"
            )

            return False

        _log(
            "Actualizador elevado iniciado."
        )

        _log(
            "La aplicación principal debe cerrarse."
        )

        return True

    except Exception as e:

        _log(
            "ERROR EJECUTANDO ACTUALIZADOR: "
            f"{e}"
        )

        return False


# ============================================================
# FLUJO COMPLETO DE ACTUALIZACIÓN
# ============================================================

def comprobar_y_preparar_actualizacion(
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None
) -> Dict[str, Any]:

    try:

        _log("=" * 70)
        _log("INICIO COMPROBACIÓN ACTUALIZACIÓN")
        _log("=" * 70)

        # ----------------------------------------------------
        # 1. CONSULTAR SERVIDOR
        # ----------------------------------------------------

        resultado = (
            consultar_version_remota()
        )

        if not resultado.get(
            "ok"
        ):

            return resultado

        # ----------------------------------------------------
        # 2. NO HAY ACTUALIZACIÓN
        # ----------------------------------------------------

        if not resultado.get(
            "hay_actualizacion"
        ):

            _log(
                "No hay actualización disponible."
            )

            return {

                "ok": True,

                "hay_actualizacion":
                    False,

                "version_local":
                    APP_VERSION,

                "version_remota":
                    resultado.get(
                        "version_remota"
                    )

            }

        # ----------------------------------------------------
        # 3. VERIFICAR SI PUEDE AUTOAPLICAR
        # ----------------------------------------------------

        if not resultado.get(
            "puede_autoaplicar"
        ):

            _log(
                "La actualización no puede "
                "autoaplicarse desde esta versión."
            )

            return {

                "ok": True,

                "hay_actualizacion":
                    True,

                "puede_autoaplicar":
                    False,

                "version_local":
                    APP_VERSION,

                "version_remota":
                    resultado.get(
                        "version_remota"
                    ),

                "mensaje":
                    "La versión actual no puede "
                    "aplicar este parche."

            }

        # ----------------------------------------------------
        # 4. DETERMINAR URL
        # ----------------------------------------------------

        strategy = str(
            resultado.get(
                "strategy",
                "zip_patch"
            )
        ).lower().strip()

        version_remota = str(
            resultado.get(
                "version_remota"
            )
        ).strip()

        patch_url = resultado.get(
            "patch_url"
        )

        download_url = resultado.get(
            "download_url"
        )

        checksum = resultado.get(
            "checksum_sha256"
        )

        # ----------------------------------------------------
        # 5. ZIP
        # ----------------------------------------------------

        if strategy == "zip_patch":

            url = patch_url

            if not url:

                return {

                    "ok": False,

                    "error":
                        "strategy=zip_patch pero "
                        "patch_url está vacío."

                }

            updates_dir = (
                obtener_directorio_updates()
            )

            ruta_zip = os.path.join(
                updates_dir,
                f"FacturasVentas-{version_remota}.zip"
            )

            _log(
                "ESTRATEGIA: ZIP PATCH"
            )

            _log(
                f"URL ZIP: {url}"
            )

            _log(
                f"RUTA ZIP LOCAL: {ruta_zip}"
            )

            # ------------------------------------------------
            # DESCARGAR
            # ------------------------------------------------

            descarga = descargar_archivo(
                url,
                ruta_zip,
                progress_cb=progress_cb,
                timeout=120
            )

            if not descarga.get(
                "ok"
            ):

                return {

                    "ok": False,

                    "error":
                        "No se pudo descargar "
                        "el parche: "
                        +
                        descarga.get(
                            "error",
                            "Error desconocido."
                        )

                }

            # ------------------------------------------------
            # PREPARAR
            # ------------------------------------------------

            preparado = (
                aplicar_parche_y_cerrar(
                    ruta_zip,
                    checksum_esperado=checksum,
                    extraer_progress_cb=
                        progress_cb
                )
            )

            if not preparado.get(
                "ok"
            ):

                return preparado

            return {

                "ok": True,

                "hay_actualizacion":
                    True,

                "preparado":
                    True,

                "strategy":
                    strategy,

                "version_local":
                    APP_VERSION,

                "version_remota":
                    version_remota,

                "zip_path":
                    ruta_zip,

                "script_path":
                    preparado.get(
                        "script_path"
                    ),

                "app_dir":
                    preparado.get(
                        "app_dir"
                    ),

                "checksum_sha256":
                    checksum,

                "release_notes":
                    resultado.get(
                        "release_notes",
                        []
                    )

            }

        # ----------------------------------------------------
        # 6. ACTUALIZACIÓN DIRECTA EXE
        # ----------------------------------------------------

        elif strategy in (
            "exe",
            "direct",
            "direct_exe"
        ):

            if not download_url:

                return {

                    "ok": False,

                    "error":
                        "No existe download_url."

                }

            updates_dir = (
                obtener_directorio_updates()
            )

            ruta_exe = os.path.join(
                updates_dir,
                f"FacturasVentas-{version_remota}.exe"
            )

            _log(
                "ESTRATEGIA: EXE DIRECTO"
            )

            descarga = descargar_archivo(
                download_url,
                ruta_exe,
                progress_cb=progress_cb,
                timeout=120
            )

            if not descarga.get(
                "ok"
            ):

                return descarga

            return {

                "ok": True,

                "hay_actualizacion":
                    True,

                "preparado":
                    True,

                "strategy":
                    "exe",

                "version_local":
                    APP_VERSION,

                "version_remota":
                    version_remota,

                "exe_path":
                    ruta_exe,

                "release_notes":
                    resultado.get(
                        "release_notes",
                        []
                    )

            }

        # ----------------------------------------------------
        # 7. ESTRATEGIA DESCONOCIDA
        # ----------------------------------------------------

        else:

            return {

                "ok": False,

                "error":
                    "Estrategia de actualización "
                    f"no soportada: {strategy}"

            }

    except Exception as e:

        _log(
            f"ERROR ACTUALIZACIÓN: {e}"
        )

        return {

            "ok": False,

            "error":
                str(e)

        }


# ============================================================
# FUNCIÓN PRINCIPAL PARA LLAMAR DESDE LOGIN
# ============================================================

def ejecutar_actualizacion_automatica(
    progress_cb: Optional[
        Callable[[int, int], None]
    ] = None
) -> Dict[str, Any]:

    try:

        _log("=" * 70)
        _log("ACTUALIZACIÓN AUTOMÁTICA")
        _log("=" * 70)

        resultado = (
            comprobar_y_preparar_actualizacion(
                progress_cb
            )
        )

        if not resultado.get(
            "ok"
        ):

            _log(
                "ERROR: "
                +
                str(
                    resultado.get(
                        "error"
                    )
                )
            )

            return resultado

        if not resultado.get(
            "hay_actualizacion"
        ):

            return resultado

        # ----------------------------------------------------
        # ZIP PATCH
        # ----------------------------------------------------

        if resultado.get(
            "strategy"
        ) == "zip_patch":

            script_path = resultado.get(
                "script_path"
            )

            if not script_path:

                return {

                    "ok": False,

                    "error":
                        "No se generó "
                        "el script de actualización."

                }

            _log(
                "Ejecutando actualizador..."
            )

            iniciado = (
                ejecutar_actualizador_y_salir(
                    script_path
                )
            )

            if not iniciado:

                return {

                    "ok": False,

                    "error":
                        "No se pudo iniciar "
                        "el actualizador."

                }

            return {

                "ok": True,

                "hay_actualizacion":
                    True,

                "actualizador_iniciado":
                    True,

                "cerrar_app":
                    True,

                "version_local":
                    APP_VERSION,

                "version_remota":
                    resultado.get(
                        "version_remota"
                    )

            }

        # ----------------------------------------------------
        # EXE DIRECTO
        # ----------------------------------------------------

        if resultado.get(
            "strategy"
        ) == "exe":

            return resultado

        return resultado

    except Exception as e:

        _log(
            f"ERROR EJECUTANDO "
            f"ACTUALIZACIÓN: {e}"
        )

        return {

            "ok": False,

            "error":
                str(e)

        }