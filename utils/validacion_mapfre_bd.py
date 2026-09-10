import re
import traceback
from typing import Any, Dict, List, Optional, Tuple

from utils.conexion_bd import ConexionBD


SIS_KEY = "MiPassphraseSegura$$2025"

COLOR_VERDE = "#dcfce7"
COLOR_AMARILLO = "#fef3c7"
COLOR_ROJO = "#fee2e2"


def _norm(texto: Any) -> str:
    if texto is None:
        return ""
    s = str(texto).strip().upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("Ñ", "N")
    return s


def _buscar_combinacion_bd(
    bd: ConexionBD,
    poliza: str,
    recibo: str,
) -> List[Dict[str, Any]]:
    """
    Busca en la BD usando la misma forma de descifrado del proyecto:
    AES_DECRYPT(FROM_BASE64(...), SIS_KEY).
    Devuelve las filas de la unión de póliza y cuotas que tienen esa combinación.
    """
    if not poliza or not recibo:
        return []

    sql = """
        SELECT
            p.idPoliza,
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), %s) AS CHAR) AS poliza,
            CAST(AES_DECRYPT(FROM_BASE64(p.recibo), %s) AS CHAR) AS recibo,
            c.idCuota,
            CAST(AES_DECRYPT(FROM_BASE64(c.cupon), %s) AS CHAR) AS cupon,
            c.numero_cuota,
            c.fecha_vencimiento,
            c.importe,
            c.factura,
            c.fecha_pago,
            c.activo AS activo_cuota,
            c.anular AS anulado_cuot
        FROM polizas p
        LEFT JOIN cuotas c
            ON c.poliza_id = p.idPoliza
        WHERE UPPER(REPLACE(REPLACE(CAST(AES_DECRYPT(FROM_BASE64(p.poliza), %s) AS CHAR), ' ', ''), 'Ñ', 'N')) = %s
          AND UPPER(REPLACE(REPLACE(CAST(AES_DECRYPT(FROM_BASE64(p.recibo), %s) AS CHAR), ' ', ''), 'Ñ', 'N')) = %s
        ORDER BY p.idPoliza DESC, c.numero_cuota ASC
    """

    params = (
        SIS_KEY,
        SIS_KEY,
        SIS_KEY,
        SIS_KEY,
        _norm(poliza),
        SIS_KEY,
        _norm(recibo),
    )

    try:
        return bd.ejecutar_consulta(
            sql,
            params,
            solo_uno=False,
            pre_statements=[("SET @SIS_KEY = %s", (SIS_KEY,))],
        ) or []
    except Exception:
        traceback.print_exc()
        return []


def validar_filas_contra_mapfre_bd(
    filas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Reglas de validación Mapfre:
      1) si la combinación poliza + recibo existe en la unión polizas/cuotas
         y cualquiera de esas filas entrega fecha_pago o factura en BD => Verde
      2) si la combinación existe pero la unión no trae fecha_pago ni factura => Amarillo
      3) si la combinación no existe => Rojo

    La salida es consistente con la API genérica del proyecto:
      (resultados, cant_existe, cant_no_existe)
    """
    bd = ConexionBD()
    if not bd.conectar():
        resultados = []
        for _ in filas:
            resultados.append({
                "existe_recibo": False,
                "existe_factura": False,
                "existe_general": False,
                "detalle": "Sin conexión a BD",
            })
        return resultados, 0, len(filas)

    resultados: List[Dict[str, Any]] = []
    cant_existe = 0
    cant_no_existe = 0

    for fila in filas:
        # Acepta el formato de una fila de edición o de una fila del mapa.
        poliza = str(
            fila.get("poliza")
            or fila.get("nro_poliza")
            or fila.get("nro_documento")
            or ""
        ).strip()
        recibo = str(
            fila.get("nro_recibo")
            or fila.get("recibo")
            or fila.get("nro_documento")
            or ""
        ).strip()

        norm_poliza = _norm(poliza)
        norm_recibo = _norm(recibo)

        if not norm_poliza or not norm_recibo:
            resultados.append({
                "existe_recibo": False,
                "existe_factura": False,
                "existe_general": False,
                "detalle": "Sin poliza o recibo para validar",
            })
            cant_no_existe += 1
            continue

        rows_db = _buscar_combinacion_bd(bd, norm_poliza, norm_recibo)
        if not rows_db:
            resultados.append({
                "existe_recibo": False,
                "existe_factura": False,
                "existe_general": False,
                "detalle": "No existe la combinación poliza + recibo",
            })
            cant_no_existe += 1
            continue

        # La evidencia de factura/fecha debe venir de la base de datos, no de la
        # fila del extractor de PDF. Si algún row del join trae factura o fecha_pago,
        # la combinación ya está registrada y debe considerarse verde.
        hay_fecha_o_factura = False
        for row in rows_db:
            db_fecha = str(row.get("fecha_pago") or "").strip()
            db_factura = str(row.get("factura") or "").strip()
            if db_fecha or db_factura:
                hay_fecha_o_factura = True
                break

        if hay_fecha_o_factura:
            resultados.append({
                "existe_recibo": True,
                "existe_factura": True,
                "existe_general": True,
                "detalle": "Existe: poliza + recibo con fecha_pago/factura en BD",
            })
            cant_existe += 1
            continue

        resultados.append({
            "existe_recibo": True,
            "existe_factura": False,
            "existe_general": False,
            "detalle": "Existe poliza + recibo, pero falta fecha_pago/factura en BD",
        })
        cant_no_existe += 1

    bd.desconectar()
    return resultados, cant_existe, cant_no_existe
