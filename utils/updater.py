import json
import os
import sys
import shutil
import hashlib
import zipfile
import tempfile
import subprocess
import ssl
import urllib.request
import urllib.error
import urllib.parse
import webbrowser
from typing import Optional, Dict, Any, Tuple, Callable


APP_VERSION: str = "1.0.0"

VERSION_URL: str = "https://aasnet.tech/updates/version.json"

ALLOW_INSECURE_SSL_FALLBACK: bool = True

APP_EXE_NAME: str = "FacturasVentas.exe"


def _crear_contexto_ssl(inseguro: bool = False) -> Optional[ssl.SSLContext]:
    if inseguro:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def _alternar_http(url: str) -> str:
    p = urllib.parse.urlparse(url)
    if p.scheme == "https":
        return p._replace(scheme="http").geturl()
    if p.scheme == "http":
        return p._replace(scheme="https").geturl()
    return url


def _http_get_raw(
    url: str,
    timeout: int,
    extra_headers: Optional[Dict[str, str]] = None,
    salida_binaria: bool = False,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    destino_archivo: Optional[str] = None,
) -> Dict[str, Any]:
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

    headers = {"User-Agent": f"FacturasVentas-SIS/{APP_VERSION}",
               "Accept": "*/*"}
    if extra_headers:
        headers.update(extra_headers)

    estrategias = []
    url_actual = url
    estrategias.append((url_actual, None))
    if ALLOW_INSECURE_SSL_FALLBACK:
        estrategias.append((url_actual, _crear_contexto_ssl(True)))
    estrategias.append((_alternar_http(url_actual), None))
    estrategias.append((_alternar_http(url_actual), _crear_contexto_ssl(True)))

    ultimo_error = None
    for idx, (u, ctx) in enumerate(estrategias):
        try:
            resultados["url_final"] = u
            req = urllib.request.Request(u, headers=headers)
            kwargs = {"timeout": timeout}
            if ctx is not None:
                kwargs["context"] = ctx

            with urllib.request.urlopen(req, **kwargs) as resp:
                total_bytes = int(resp.headers.get("Content-Length") or 0)
                resultados["bytes_totales"] = total_bytes

                if destino_archivo:
                    os.makedirs(os.path.dirname(destino_archivo) or ".", exist_ok=True)
                    descargado = 0
                    h = hashlib.sha256() if progress_cb or salida_binaria else None
                    with open(destino_archivo, "wb") as out:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            out.write(chunk)
                            descargado += len(chunk)
                            resultados["bytes_descargados"] = descargado
                            if progress_cb and total_bytes:
                                try:
                                    progress_cb(descargado, total_bytes)
                                except Exception:
                                    pass
                    resultados["ok"] = True
                    resultados["ruta"] = destino_archivo
                    resultados["sha256"] = _sha256_archivo(destino_archivo)
                    return resultados
                else:
                    raw = resp.read()
                    resultados["data"] = raw
                    resultados["bytes_descargados"] = len(raw)
                    resultados["ok"] = True
                    return resultados
        except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError, OSError) as e:
            ultimo_error = f"{type(e).__name__}: {e}"
            resultados["errores"].append(f"[{idx}] {ultimo_error}")
            continue
        except Exception as e:
            ultimo_error = f"{type(e).__name__}: {e}"
            resultados["errores"].append(f"[{idx}] {ultimo_error}")
            continue

    resultados["errores"].append(f"URL original: {url}")
    return resultados



def _parse_version(version_str: str) -> Tuple[int, ...]:
    try:
        return tuple(int(x) for x in version_str.strip().split("."))
    except Exception:
        return (0, 0, 0)


def version_disponible(local: str, remota: str) -> bool:
    return _parse_version(remota) > _parse_version(local)


def obtener_ruta_ejecutable() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def obtener_directorio_ejecutable() -> str:
    return os.path.dirname(obtener_ruta_ejecutable())


def obtener_ruta_app_exe() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.join(obtener_directorio_ejecutable(), APP_EXE_NAME)


def consultar_version_remota(
    url: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    destino = url or VERSION_URL
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
            extra_headers={"Accept": "application/json"},
        )
        if not http_res["ok"]:
            err_list = http_res.get("errores") or []
            msj = err_list[-2] if len(err_list) >= 2 else (err_list[0] if err_list else "Error desconocido")
            resultado["error"] = msj
            return resultado

        resultado["url_version_json_usada"] = http_res.get("url_final")

        raw_bytes = http_res.get("data") or b""
        raw = raw_bytes.decode("utf-8", errors="replace")
        try:
            datos = json.loads(raw)
        except json.JSONDecodeError:
            resultado["error"] = "El archivo de versión remoto es inválido (JSON corrupto)"
            return resultado

        version_remota = str(datos.get("version", "")).strip()
        download_url = str(datos.get("download_url", "")).strip() or None
        patch_url = str(datos.get("patch_url", "")).strip() or None
        strategy = str(datos.get("strategy", "")).strip() or None
        force_update = bool(datos.get("force_update", False))
        checksum = str(datos.get("checksum_sha256", "")).strip() or None
        file_size = int(datos.get("file_size_bytes") or 0)
        min_patch = str(datos.get("min_version_to_patch", "")).strip() or None
        notas = datos.get("release_notes") or datos.get("notes") or None
        published_at = str(datos.get("published_at", "")).strip() or None

        resultado["ok"] = True
        resultado["version_remota"] = version_remota or None
        resultado["download_url"] = download_url
        resultado["patch_url"] = patch_url
        resultado["strategy"] = strategy
        resultado["force_update"] = force_update
        resultado["checksum_sha256"] = checksum
        resultado["file_size_bytes"] = file_size
        resultado["min_version_to_patch"] = min_patch
        resultado["notas"] = notas
        resultado["published_at"] = published_at

        if version_remota and version_disponible(APP_VERSION, version_remota):
            resultado["hay_actualizacion"] = True

        if (
            resultado["hay_actualizacion"]
            and patch_url
            and strategy == "zip_patch"
            and getattr(sys, "frozen", False)
        ):
            cumple_min = True
            if min_patch:
                cumple_min = not version_disponible(APP_VERSION, min_patch)
            resultado["puede_autoaplicar"] = cumple_min
    except Exception as e:
        resultado["error"] = f"Error inesperado: {e}"
    return resultado


def abrir_descarga(url: str) -> bool:
    try:
        webbrowser.open(url, new=2)
        return True
    except Exception:
        return False


def _sha256_archivo(ruta: str, progress_cb: Optional[Callable[[int, int], None]] = None) -> str:
    h = hashlib.sha256()
    total = os.path.getsize(ruta) if os.path.exists(ruta) else 0
    leido = 0
    with open(ruta, "rb") as f:
        while True:
            buf = f.read(65536)
            if not buf:
                break
            h.update(buf)
            leido += len(buf)
            if progress_cb and total:
                try:
                    progress_cb(leido, total)
                except Exception:
                    pass
    return h.hexdigest()


def descargar_archivo(
    url: str,
    destino: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
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
            destino_archivo=destino,
        )
        if not http_res["ok"]:
            err_list = http_res.get("errores") or []
            msj = err_list[-2] if len(err_list) >= 2 else (err_list[0] if err_list else "Error desconocido")
            res["error"] = msj
            if os.path.exists(destino):
                try:
                    os.remove(destino)
                except Exception:
                    pass
            return res
        res["ruta"] = destino
        res["sha256"] = http_res.get("sha256") or _sha256_archivo(destino)
        res["bytes_descargados"] = http_res.get("bytes_descargados", 0)
        res["bytes_totales"] = http_res.get("bytes_totales", 0)
        res["ok"] = True
    except Exception as e:
        res["error"] = f"Error de descarga: {e}"
        if os.path.exists(destino):
            try:
                os.remove(destino)
            except Exception:
                pass
    return res


def extraer_zip(
    ruta_zip: str,
    dir_destino: str,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    res: Dict[str, Any] = {"ok": False, "dir_destino": dir_destino, "error": None}
    try:
        os.makedirs(dir_destino, exist_ok=True)
        with zipfile.ZipFile(ruta_zip, "r") as zf:
            miembros = zf.namelist()
            total = len(miembros)
            for idx, nombre in enumerate(miembros, start=1):
                try:
                    zf.extract(nombre, dir_destino)
                except Exception:
                    pass
                if progress_cb and total:
                    try:
                        progress_cb(idx, total)
                    except Exception:
                        pass
        res["ok"] = True
    except zipfile.BadZipFile:
        res["error"] = "El archivo ZIP está corrupto"
    except Exception as e:
        res["error"] = f"Error al extraer ZIP: {e}"
    return res


def _generar_script_actualizacion(
    ruta_app_vieja: str,
    dir_extraccion: str,
    ruta_app_nueva: str,
) -> str:
    dir_app = os.path.dirname(ruta_app_vieja)
    nombre_bat = "_update_helper.bat"
    ruta_bat = os.path.join(dir_app, nombre_bat)
    nombre_exe = os.path.basename(ruta_app_vieja)
    dir_extraccion_q = f'"{dir_extraccion}"'
    dir_app_q = f'"{dir_app}"'
    ruta_app_vieja_q = f'"{ruta_app_vieja}"'
    ruta_app_nueva_q = f'"{ruta_app_nueva}"'
    ruta_bat_q = f'"{ruta_bat}"'
    exe_relanzar_q = f'"{os.path.join(dir_app, nombre_exe)}"'

    contenido = f"""@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Actualizando FacturasVentas...

echo.
echo ============================================
echo   FacturasVentas - Aplicando actualizacion
echo ============================================
echo.

set "DIR_EXE={dir_app_q}"
set "DIR_PATCH={dir_extraccion_q}"
set "EXE_OLD={ruta_app_vieja_q}"
set "EXE_NEW_FROM_ZIP={ruta_app_nueva_q}"
set "SELF={ruta_bat_q}"
set "RELAUNCH={exe_relanzar_q}"

ping -n 3 127.0.0.1 >nul

if not exist %DIR_PATCH% (
  echo [ERROR] Carpeta del parche no encontrada: %DIR_PATCH%
  goto end
)

echo [1/4] Limpiando archivos anteriores...
cd /d %DIR_EXE%

if exist "_old_version" rmdir /s /q "_old_version" 2>nul

echo [2/4] Copiando archivos nuevos...
xcopy %DIR_PATCH%\\*.* %DIR_EXE% /E /H /C /I /Y >nul

if exist %EXE_NEW_FROM_ZIP% (
  echo [3/4] Reemplazando ejecutable principal...
)

echo [4/4] Iniciando aplicacion actualizada...
echo.
echo Listo. Abriendo FacturasVentas...

ping -n 2 127.0.0.1 >nul

if exist %RELAUNCH% (
  start "" %RELAUNCH% --post-update
)

:cleanup
echo.
echo Limpiando archivos temporales...
if exist %DIR_PATCH% rmdir /s /q %DIR_PATCH% 2>nul
del /f /q %SELF% 2>nul

exit /b
:end
endlocal
"""
    try:
        with open(ruta_bat, "w", encoding="utf-8", errors="replace") as f:
            f.write(contenido)
    except Exception:
        with open(ruta_bat, "w", encoding="cp1252", errors="replace") as f:
            f.write(contenido)
    return ruta_bat


def aplicar_parche_y_cerrar(
    ruta_zip: str,
    checksum_esperado: Optional[str] = None,
    descargar_progress_cb: Optional[Callable[[int, int], None]] = None,
    extraer_progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    res: Dict[str, Any] = {"ok": False, "bat_path": None, "error": None}

    if not getattr(sys, "frozen", False):
        res["error"] = "El auto-parche solo funciona cuando la app está compilada a .exe"
        return res

    if checksum_esperado:
        checksum_actual = _sha256_archivo(ruta_zip)
        if checksum_actual.lower() != checksum_esperado.lower():
            res["error"] = "Verificación de integridad fallida (checksum SHA256 no coincide)"
            return res

    dir_app = obtener_directorio_ejecutable()
    ruta_app_exe = obtener_ruta_app_exe()

    tmp_patch = os.path.join(dir_app, "_pending_patch")
    if os.path.exists(tmp_patch):
        try:
            shutil.rmtree(tmp_patch, ignore_errors=True)
        except Exception:
            pass

    ext_res = extraer_zip(ruta_zip, tmp_patch, progress_cb=extraer_progress_cb)
    if not ext_res["ok"]:
        res["error"] = ext_res["error"]
        try:
            shutil.rmtree(tmp_patch, ignore_errors=True)
        except Exception:
            pass
        return res

    posibles_exes = [
        os.path.join(tmp_patch, os.path.basename(ruta_app_exe)),
        os.path.join(tmp_patch, APP_EXE_NAME),
    ]
    exe_en_zip = next((p for p in posibles_exes if os.path.exists(p)), posibles_exes[0])

    try:
        ruta_bat = _generar_script_actualizacion(ruta_app_exe, tmp_patch, exe_en_zip)
    except Exception as e:
        res["error"] = f"No se pudo crear el script de actualización: {e}"
        return res

    res["ok"] = True
    res["bat_path"] = ruta_bat
    return res


def ejecutar_actualizador_y_salir(ruta_bat: str) -> bool:
    try:
        ruta_bat_abs = os.path.abspath(ruta_bat)
        if not os.path.exists(ruta_bat_abs):
            return False
        if os.name == "nt":
            subprocess.Popen(
                ["cmd.exe", "/C", ruta_bat_abs],
                shell=False,
                close_fds=True,
                creationflags=0x08000000,
                cwd=os.path.dirname(ruta_bat_abs),
            )
        else:
            subprocess.Popen(["bash", ruta_bat_abs])
        return True
    except Exception:
        return False
