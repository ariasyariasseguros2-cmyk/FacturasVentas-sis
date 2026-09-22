import re
import traceback
from collections import defaultdict
from typing import Any, DefaultDict, Dict, Iterable, List, Tuple

from utils.conexion_bd import ConexionBD


SIS_KEY = "MiPassphraseSegura$$2025"

COLOR_VERDE = "#dcfce7"
COLOR_AMARILLO = "#fef3c7"
COLOR_ROJO = "#fee2e2"

_IN_CHUNK_SIZE = 300


def _norm(texto: Any) -> str:
    if texto is None:
        return ""
    s = str(texto).strip().upper()
    s = re.sub(r"\s+", "", s)
    return s.replace("Ñ", "N")


def _solo_digitos(texto: Any) -> str:
    return "".join(ch for ch in str(texto or "") if ch.isdigit())


def _flag(valor: Any, default: bool = False) -> bool:
    if valor is None:
        return default
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return int(valor) != 0
    texto = str(valor).strip().lower()
    if texto == "":
        return default
    if texto in {"1", "true", "t", "si", "sí", "y", "yes"}:
        return True
    if texto in {"0", "false", "f", "no", "n"}:
        return False
    return default


def _texto_candidatos(*valores: Any) -> List[str]:
    candidatos: List[str] = []
    vistos = set()
    for valor in valores:
        if valor is None:
            continue
        texto = str(valor).strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        candidatos.append(texto)
    return candidatos


def _norm_candidatos(*valores: Any) -> List[str]:
    candidatos: List[str] = []
    vistos = set()
    for valor in valores:
        norm = _norm(valor)
        if not norm or norm in vistos:
            continue
        vistos.add(norm)
        candidatos.append(norm)
    return candidatos


def _coincide_cupon(cupon_fila: Any, cupon_bd: Any) -> bool:
    fila_digits = _solo_digitos(cupon_fila)
    bd_digits = _solo_digitos(cupon_bd)
    if fila_digits and bd_digits:
        return fila_digits == bd_digits
    return _norm(cupon_fila) == _norm(cupon_bd)


def _coincide_con_candidatos(cupon_fila: Any, *candidatos: Any) -> bool:
    return any(_coincide_cupon(cupon_fila, candidato) for candidato in candidatos)


def _chunked(valores: Iterable[Any], size: int) -> Iterable[List[Any]]:
    bloque: List[Any] = []
    for valor in valores:
        bloque.append(valor)
        if len(bloque) >= size:
            yield bloque
            bloque = []
    if bloque:
        yield bloque


def _buscar_polizas_en_lote(
    bd: ConexionBD,
    polizas: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    resultado: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    polizas_norm = sorted({_norm(poliza) for poliza in polizas if _norm(poliza)})
    if not polizas_norm:
        return {}

    sql_base = """
        SELECT
            p.idPoliza,
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), %s) AS CHAR) AS poliza_b64,
            CAST(AES_DECRYPT(p.poliza, %s) AS CHAR) AS poliza_aes,
            p.poliza AS poliza_plano,
            CAST(AES_DECRYPT(FROM_BASE64(p.contrato_nro), %s) AS CHAR) AS contrato_b64,
            CAST(AES_DECRYPT(p.contrato_nro, %s) AS CHAR) AS contrato_aes,
            p.contrato_nro AS contrato_plano,
            CAST(AES_DECRYPT(FROM_BASE64(p.nro), %s) AS CHAR) AS nro_b64,
            CAST(AES_DECRYPT(p.nro, %s) AS CHAR) AS nro_aes,
            p.nro AS nro_plano,
            COALESCE(p.activo, 1) AS activo_poliza,
            COALESCE(p.anulado, 0) AS anulado_poliza,
            COALESCE(p.prima_anulada, 0) AS prima_anulada
        FROM polizas p
        WHERE
            UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.poliza), %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(p.poliza, %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(p.poliza, ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.contrato_nro), %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(p.contrato_nro, %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(p.contrato_nro, ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.nro), %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(p.nro, %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
            OR UPPER(REPLACE(REPLACE(COALESCE(p.nro, ''), ' ', ''), 'Ñ', 'N')) IN ({placeholders})
    """

    for bloque in _chunked(polizas_norm, _IN_CHUNK_SIZE):
        placeholders = ", ".join(["%s"] * len(bloque))
        sql = sql_base.format(placeholders=placeholders)
        params = (
            SIS_KEY, SIS_KEY, SIS_KEY, SIS_KEY, SIS_KEY, SIS_KEY,
            SIS_KEY, *bloque,
            SIS_KEY, *bloque,
            *bloque,
            SIS_KEY, *bloque,
            SIS_KEY, *bloque,
            *bloque,
            SIS_KEY, *bloque,
            SIS_KEY, *bloque,
            *bloque,
        )
        try:
            rows = bd.ejecutar_consulta(
                sql,
                params,
                solo_uno=False,
                pre_statements=[("SET @SIS_KEY = %s", (SIS_KEY,))],
            ) or []
        except Exception:
            traceback.print_exc()
            continue

        for row in rows:
            for poliza_norm in _norm_candidatos(
                row.get("poliza_b64"),
                row.get("poliza_aes"),
                row.get("poliza_plano"),
                row.get("contrato_b64"),
                row.get("contrato_aes"),
                row.get("contrato_plano"),
                row.get("nro_b64"),
                row.get("nro_aes"),
                row.get("nro_plano"),
            ):
                if poliza_norm in polizas_norm:
                    resultado[poliza_norm].append(row)

    return dict(resultado)


def _buscar_cuotas_en_lote(
    bd: ConexionBD,
    poliza_ids: List[int],
    polizas: List[str],
) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    resultado_por_id: DefaultDict[int, List[Dict[str, Any]]] = defaultdict(list)
    resultado_por_poliza: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    ids_unicos = sorted({int(pid) for pid in poliza_ids if pid is not None})
    polizas_norm = sorted({_norm(poliza) for poliza in polizas if _norm(poliza)})
    if not ids_unicos and not polizas_norm:
        return {}, {}

    sql_base = """
        SELECT
            c.poliza_id,
            CAST(AES_DECRYPT(FROM_BASE64(c.poliza), %s) AS CHAR) AS poliza_b64,
            CAST(AES_DECRYPT(c.poliza, %s) AS CHAR) AS poliza_aes,
            c.poliza AS poliza_plano,
            CAST(AES_DECRYPT(FROM_BASE64(c.cupon), %s) AS CHAR) AS cupon_b64,
            CAST(AES_DECRYPT(c.cupon, %s) AS CHAR) AS cupon_aes,
            c.cupon AS cupon_plano,
            COALESCE(c.factura, '') AS factura,
            COALESCE(c.activo, 1) AS activo_cuota,
            COALESCE(c.anular, 1) AS anulado_cuota
        FROM cuotas c
        WHERE {where_clause}
    """

    bloques_ids = list(_chunked(ids_unicos, _IN_CHUNK_SIZE)) or [[]]
    bloques_polizas = list(_chunked(polizas_norm, _IN_CHUNK_SIZE)) or [[]]

    for bloque_ids in bloques_ids:
        for bloque_polizas in bloques_polizas:
            condiciones = []
            params: Tuple[Any, ...] = (SIS_KEY, SIS_KEY, SIS_KEY, SIS_KEY)
            if bloque_ids:
                placeholders_ids = ", ".join(["%s"] * len(bloque_ids))
                condiciones.append(f"c.poliza_id IN ({placeholders_ids})")
                params += tuple(bloque_ids)
            if bloque_polizas:
                placeholders_polizas = ", ".join(["%s"] * len(bloque_polizas))
                condiciones.append(
                    "UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(c.poliza), %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) "
                    f"IN ({placeholders_polizas}) OR "
                    "UPPER(REPLACE(REPLACE(COALESCE(CAST(AES_DECRYPT(c.poliza, %s) AS CHAR), ''), ' ', ''), 'Ñ', 'N')) "
                    f"IN ({placeholders_polizas}) OR "
                    "UPPER(REPLACE(REPLACE(COALESCE(c.poliza, ''), ' ', ''), 'Ñ', 'N')) "
                    f"IN ({placeholders_polizas})"
                )
                params += (SIS_KEY, *bloque_polizas, SIS_KEY, *bloque_polizas, *bloque_polizas)
            if not condiciones:
                continue

            sql = sql_base.format(where_clause=" OR ".join(condiciones))
            try:
                rows = bd.ejecutar_consulta(
                    sql,
                    params,
                    solo_uno=False,
                    pre_statements=[("SET @SIS_KEY = %s", (SIS_KEY,))],
                ) or []
            except Exception:
                traceback.print_exc()
                continue

            for row in rows:
                for poliza_norm in _norm_candidatos(
                    row.get("poliza_b64"),
                    row.get("poliza_aes"),
                    row.get("poliza_plano"),
                ):
                    if poliza_norm in polizas_norm:
                        resultado_por_poliza[poliza_norm].append(row)
                try:
                    poliza_id = int(row.get("poliza_id"))
                except Exception:
                    poliza_id = None
                if poliza_id is not None:
                    resultado_por_id[poliza_id].append(row)

    return dict(resultado_por_id), dict(resultado_por_poliza)


def _resolver_validacion_fila(
    fila: Dict[str, Any],
    polizas_bd: Dict[str, List[Dict[str, Any]]],
    cuotas_bd_por_id: Dict[int, List[Dict[str, Any]]],
    cuotas_bd_por_poliza: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    poliza = str(fila.get("poliza") or fila.get("nro_documento") or "").strip()
    cupon = str(
        fila.get("cupon")
        or fila.get("doc_legal")
        or fila.get("documento")
        or ""
    ).strip()

    poliza_norm = _norm(poliza)
    if not poliza_norm or not cupon:
        return {
            "existe_recibo": False,
            "existe_factura": False,
            "existe_general": False,
            "detalle": "Sin poliza o cupon para validar",
        }

    polizas_encontradas = polizas_bd.get(poliza_norm, [])
    if not polizas_encontradas:
        return {
            "existe_recibo": False,
            "existe_factura": False,
            "existe_general": False,
            "detalle": "No existe la poliza en BD",
        }

    coincidencias_cupon: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for poliza_row in polizas_encontradas:
        cuotas_candidatas: List[Dict[str, Any]] = []
        try:
            poliza_id = int(poliza_row.get("idPoliza"))
        except Exception:
            poliza_id = None
        if poliza_id is not None:
            cuotas_candidatas.extend(cuotas_bd_por_id.get(poliza_id, []))
        cuotas_candidatas.extend(cuotas_bd_por_poliza.get(poliza_norm, []))

        vistos = set()
        for cuota_row in cuotas_candidatas:
            cuota_key = (
                cuota_row.get("poliza_id"),
                tuple(_norm_candidatos(
                    cuota_row.get("poliza_b64"),
                    cuota_row.get("poliza_aes"),
                    cuota_row.get("poliza_plano"),
                )),
                tuple(_norm_candidatos(
                    cuota_row.get("cupon_b64"),
                    cuota_row.get("cupon_aes"),
                    cuota_row.get("cupon_plano"),
                )),
                str(cuota_row.get("factura") or "").strip(),
            )
            if cuota_key in vistos:
                continue
            vistos.add(cuota_key)
            if _coincide_con_candidatos(
                cupon,
                cuota_row.get("cupon_b64"),
                cuota_row.get("cupon_aes"),
                cuota_row.get("cupon_plano"),
            ):
                coincidencias_cupon.append((poliza_row, cuota_row))

    if not coincidencias_cupon:
        return {
            "existe_recibo": False,
            "existe_factura": False,
            "existe_general": False,
            "detalle": "Existe la poliza, pero no el cupon",
        }

    coincidencias_activas: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for poliza_row, cuota_row in coincidencias_cupon:
        activo_poliza = _flag(poliza_row.get("activo_poliza"), default=True)
        anulado_poliza = _flag(poliza_row.get("anulado_poliza"), default=False)
        prima_anulada = _flag(poliza_row.get("prima_anulada"), default=False)
        activo_cuota = _flag(cuota_row.get("activo_cuota"), default=True)
        anulado_cuota = _flag(cuota_row.get("anulado_cuota"), default=True)
        if activo_poliza and not anulado_poliza and not prima_anulada and activo_cuota and anulado_cuota:
            coincidencias_activas.append((poliza_row, cuota_row))

    if not coincidencias_activas:
        return {
            "existe_recibo": False,
            "existe_factura": False,
            "existe_general": False,
            "detalle": "La combinación poliza + cupon existe, pero está anulada o inactiva",
        }

    hay_factura = any(str(cuota_row.get("factura") or "").strip() for _, cuota_row in coincidencias_activas)
    if hay_factura:
        return {
            "existe_recibo": True,
            "existe_factura": True,
            "existe_general": True,
            "detalle": "Existe poliza + cupon con factura en BD",
        }

    return {
        "existe_recibo": True,
        "existe_factura": False,
        "existe_general": False,
        "detalle": "Existe poliza + cupon, pero falta factura en BD",
    }


def validar_filas_contra_positiva_bd(
    filas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Reglas Positiva:
      1) poliza se valida en tabla polizas
      2) cupon y factura se validan en tabla cuotas
      3) Verde: existe poliza + cupon y hay factura
      4) Amarillo: existe poliza + cupon pero no factura
      5) Rojo: no existe la combinación o está inactiva
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

    try:
        polizas_input = [
            str(fila.get("poliza") or fila.get("nro_documento") or "").strip()
            for fila in filas
        ]
        polizas_bd = _buscar_polizas_en_lote(bd, polizas_input)

        poliza_ids: List[int] = []
        for rows in polizas_bd.values():
            for row in rows:
                try:
                    poliza_ids.append(int(row.get("idPoliza")))
                except Exception:
                    continue
        cuotas_bd_por_id, cuotas_bd_por_poliza = _buscar_cuotas_en_lote(
            bd,
            poliza_ids,
            polizas_input,
        )

        cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        resultados: List[Dict[str, Any]] = []
        cant_existe = 0
        cant_no_existe = 0

        for fila in filas:
            poliza_norm = _norm(fila.get("poliza") or fila.get("nro_documento") or "")
            cupon_base = fila.get("cupon") or fila.get("doc_legal") or fila.get("documento") or ""
            cupon_key = _solo_digitos(cupon_base) or _norm(cupon_base)
            cache_key = (poliza_norm, cupon_key)

            resultado = cache.get(cache_key)
            if resultado is None:
                resultado = _resolver_validacion_fila(
                    fila,
                    polizas_bd,
                    cuotas_bd_por_id,
                    cuotas_bd_por_poliza,
                )
                cache[cache_key] = resultado

            resultados.append(dict(resultado))
            if resultado.get("existe_recibo") and resultado.get("existe_factura"):
                cant_existe += 1
            else:
                cant_no_existe += 1

        return resultados, cant_existe, cant_no_existe
    finally:
        bd.desconectar()
