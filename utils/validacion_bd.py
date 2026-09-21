import re
from typing import List, Dict, Any, Tuple, Set

from utils.conexion_bd import ConexionBD


SIS_KEY = "MiPassphraseSegura$$2025"

COLOR_VERDE = "#dcfce7"
COLOR_AMARILLO = "#fef3c7"
COLOR_ROJO = "#fee2e2"
COLOR_MORADO = "#ede9fe"

COLOR_EXISTE = COLOR_VERDE
COLOR_NO_EXISTE = COLOR_ROJO


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    s = str(texto).strip().upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("Ñ", "N")
    return s


_DECRYPT_TPL = (
    "CAST(AES_DECRYPT(FROM_BASE64({col}), %s) AS CHAR)"
)

_ALIAS_A_TABLA = {"p": "polizas", "c": "cuotas"}


def _alias_tabla(tabla_col: str) -> Tuple[str, str, str]:
    """Descompone 'p.recibo' → (alias='p', tabla='polizas', col='recibo')."""
    alias, col = tabla_col.split(".", 1)
    tabla = _ALIAS_A_TABLA.get(alias, alias)
    return alias, tabla, col


def _condicion_cifrada_norm(col: str, valor_norm: str) -> Tuple[str, Tuple[str, str]]:
    expr = _DECRYPT_TPL.format(col=col)
    sql = f"UPPER(REPLACE(REPLACE({expr}, ' ', ''), 'Ñ', 'N')) = %s"
    return sql, (SIS_KEY, valor_norm)


def _condicion_plana_norm(col: str, valor_norm: str) -> Tuple[str, Tuple[str]]:
    sql = f"UPPER(REPLACE(REPLACE({col}, ' ', ''), 'Ñ', 'N')) = %s"
    return sql, (valor_norm,)


def _merge_estado(
    destino: Dict[str, Dict[str, bool]],
    rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, bool]]:
    for row in (rows or []):
        valor = str(row.get("val") or "").strip()
        if not valor:
            continue

        estado = destino.setdefault(
            valor,
            {
                "existe_activo": False,
                "tiene_factura_bd": False,
                "esta_anulado": False,
            },
        )
        estado["existe_activo"] = (
            estado["existe_activo"]
            or bool(row.get("existe_activo"))
        )
        estado["tiene_factura_bd"] = (
            estado["tiene_factura_bd"]
            or bool(row.get("tiene_factura_bd"))
        )
        estado["esta_anulado"] = (
            estado["esta_anulado"]
            or bool(row.get("esta_anulado"))
        )
    return destino


def _buscar_estado_nro_documento(
    bd: ConexionBD,
    pre: List[Tuple[str, Tuple[Any, ...]]],
    valores: List[str],
) -> Dict[str, Dict[str, bool]]:
    if not valores:
        return {}

    placeholders = ", ".join(["%s"] * len(valores))
    sql = f"""
        SELECT
            sub.val,
            MAX(sub.existe_activo) AS existe_activo,
            MAX(sub.tiene_factura_bd) AS tiene_factura_bd,
            MAX(sub.esta_anulado) AS esta_anulado
        FROM (
            SELECT
                UPPER(REPLACE(REPLACE(
                    CAST(AES_DECRYPT(FROM_BASE64(p.recibo), %s) AS CHAR),
                    ' ',
                    ''
                ), 'Ñ', 'N')) AS val,
                CASE
                    WHEN COALESCE(p.activo, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                    THEN 1 ELSE 0
                END AS existe_activo,
                CASE
                    WHEN COALESCE(p.activo, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                     AND NULLIF(TRIM(c.factura), '') IS NOT NULL
                    THEN 1 ELSE 0
                END AS tiene_factura_bd,
                CASE
                    WHEN COALESCE(p.anulado, 0) = 1
                     OR COALESCE(p.prima_anulada, 0) = 1
                     OR COALESCE(c.anular, 1) = 0
                    THEN 1 ELSE 0
                END AS esta_anulado
            FROM polizas p
            LEFT JOIN cuotas c ON c.poliza_id = p.idPoliza

            UNION ALL

            SELECT
                UPPER(REPLACE(REPLACE(
                    CAST(AES_DECRYPT(FROM_BASE64(p.poliza), %s) AS CHAR),
                    ' ',
                    ''
                ), 'Ñ', 'N')) AS val,
                CASE
                    WHEN COALESCE(p.activo, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                    THEN 1 ELSE 0
                END AS existe_activo,
                CASE
                    WHEN COALESCE(p.activo, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                     AND NULLIF(TRIM(c.factura), '') IS NOT NULL
                    THEN 1 ELSE 0
                END AS tiene_factura_bd,
                CASE
                    WHEN COALESCE(p.anulado, 0) = 1
                     OR COALESCE(p.prima_anulada, 0) = 1
                     OR COALESCE(c.anular, 1) = 0
                    THEN 1 ELSE 0
                END AS esta_anulado
            FROM polizas p
            LEFT JOIN cuotas c ON c.poliza_id = p.idPoliza

            UNION ALL

            SELECT
                UPPER(REPLACE(REPLACE(
                    CAST(AES_DECRYPT(FROM_BASE64(p.nro), %s) AS CHAR),
                    ' ',
                    ''
                ), 'Ñ', 'N')) AS val,
                CASE
                    WHEN COALESCE(p.activo, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                    THEN 1 ELSE 0
                END AS existe_activo,
                CASE
                    WHEN COALESCE(p.activo, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                     AND NULLIF(TRIM(c.factura), '') IS NOT NULL
                    THEN 1 ELSE 0
                END AS tiene_factura_bd,
                CASE
                    WHEN COALESCE(p.anulado, 0) = 1
                     OR COALESCE(p.prima_anulada, 0) = 1
                     OR COALESCE(c.anular, 1) = 0
                    THEN 1 ELSE 0
                END AS esta_anulado
            FROM polizas p
            LEFT JOIN cuotas c ON c.poliza_id = p.idPoliza

            UNION ALL

            SELECT
                UPPER(REPLACE(REPLACE(
                    CAST(AES_DECRYPT(FROM_BASE64(c.cupon), %s) AS CHAR),
                    ' ',
                    ''
                ), 'Ñ', 'N')) AS val,
                CASE
                    WHEN COALESCE(c.activo, 1) = 1
                     AND COALESCE(c.anular, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                    THEN 1 ELSE 0
                END AS existe_activo,
                CASE
                    WHEN COALESCE(c.activo, 1) = 1
                     AND COALESCE(c.anular, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                     AND NULLIF(TRIM(c.factura), '') IS NOT NULL
                    THEN 1 ELSE 0
                END AS tiene_factura_bd,
                CASE
                    WHEN COALESCE(c.anular, 1) = 0
                     OR COALESCE(p.anulado, 0) = 1
                     OR COALESCE(p.prima_anulada, 0) = 1
                    THEN 1 ELSE 0
                END AS esta_anulado
            FROM cuotas c
            LEFT JOIN polizas p ON p.idPoliza = c.poliza_id
        ) sub
        WHERE sub.val IN ({placeholders})
        GROUP BY sub.val
    """
    params = (
        SIS_KEY,
        SIS_KEY,
        SIS_KEY,
        SIS_KEY,
    ) + tuple(valores)

    try:
        rows = bd.ejecutar_consulta(
            sql,
            params,
            solo_uno=False,
            pre_statements=pre,
        ) or []
    except Exception:
        return {}

    return _merge_estado({}, rows)


def _buscar_estado_doc_legal(
    bd: ConexionBD,
    pre: List[Tuple[str, Tuple[Any, ...]]],
    valores: List[str],
) -> Dict[str, Dict[str, bool]]:
    if not valores:
        return {}

    placeholders = ", ".join(["%s"] * len(valores))
    sql = f"""
        SELECT
            sub.val,
            MAX(sub.existe_activo) AS existe_activo,
            MAX(sub.tiene_factura_bd) AS tiene_factura_bd,
            MAX(sub.esta_anulado) AS esta_anulado
        FROM (
            SELECT
                UPPER(REPLACE(REPLACE(c.factura, ' ', ''), 'Ñ', 'N')) AS val,
                CASE
                    WHEN COALESCE(c.activo, 1) = 1
                     AND COALESCE(c.anular, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                    THEN 1 ELSE 0
                END AS existe_activo,
                CASE
                    WHEN COALESCE(c.activo, 1) = 1
                     AND COALESCE(c.anular, 1) = 1
                     AND COALESCE(p.anulado, 0) = 0
                     AND COALESCE(p.prima_anulada, 0) = 0
                    THEN 1 ELSE 0
                END AS tiene_factura_bd,
                CASE
                    WHEN COALESCE(c.anular, 1) = 0
                     OR COALESCE(p.anulado, 0) = 1
                     OR COALESCE(p.prima_anulada, 0) = 1
                    THEN 1 ELSE 0
                END AS esta_anulado
            FROM cuotas c
            LEFT JOIN polizas p ON p.idPoliza = c.poliza_id
        ) sub
        WHERE sub.val IN ({placeholders})
        GROUP BY sub.val
    """
    params = tuple(valores)

    try:
        rows = bd.ejecutar_consulta(
            sql,
            params,
            solo_uno=False,
            pre_statements=pre,
        ) or []
    except Exception:
        return {}

    return _merge_estado({}, rows)


def validar_filas_contra_bd(
    filas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    VALIDACIÓN RÁPIDA — Consultas MASIVAS (IN ...) en lugar de 1 consulta por fila.
    Busca:
      - nro_documento en polizas.recibo (cifrado), polizas.poliza, polizas.nro, cuotas.cupon
      - doc_legal    en polizas.numero_factura (cifrado y plano) y cuotas.factura

    Retorna:
      (resultados, cantidad_existe, cantidad_no_existe)
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

    pre = [("SET @SIS_KEY = %s", (SIS_KEY,))]

    # ================================================================
    # PASO 1: Normalizar y recolectar valores únicos de TODAS las filas
    # ================================================================
    filas_normalizadas: List[Dict[str, str]] = []
    set_nro_docs: Set[str] = set()
    set_doc_legales: Set[str] = set()

    for fila in filas:
        nro_doc = _normalizar(
            fila.get("nro_documento_validacion", "")
            or fila.get("documento_validacion", "")
            or fila.get("nro_documento", "")
            or fila.get("documento", "")
            or fila.get("poliza", "")
        )
        doc_legal = _normalizar(
            fila.get("doc_legal_validacion", "")
            or fila.get("doc_legal", "")
            or fila.get("comprobante", "")
            or fila.get("nro_comprobante", "")
            or fila.get("codigo_pago", "")
        )
        filas_normalizadas.append({"nro_doc": nro_doc, "doc_legal": doc_legal})
        if nro_doc:
            set_nro_docs.add(nro_doc)
        if doc_legal:
            set_doc_legales.add(doc_legal)

    lista_nro_docs = list(set_nro_docs)
    lista_doc_legales = list(set_doc_legales)

    # ================================================================
    # PASO 2: Consultas MASIVAS (solo 7 consultas TOTALES, sin importar N de filas)
    # ================================================================

    estado_nro_doc = _buscar_estado_nro_documento(
        bd,
        pre,
        lista_nro_docs,
    )
    estado_doc_legal = _buscar_estado_doc_legal(
        bd,
        pre,
        lista_doc_legales,
    )

    # ================================================================
    # PASO 3: Construir resultados (búsqueda en SET local — O(1))
    # ================================================================
    resultados: List[Dict[str, Any]] = []
    cant_existe = 0
    cant_no_existe = 0

    for fn in filas_normalizadas:
        nro_doc = fn["nro_doc"]
        doc_legal = fn["doc_legal"]

        estado_nro = estado_nro_doc.get(
            nro_doc,
            {},
        )
        estado_doc = estado_doc_legal.get(
            doc_legal,
            {},
        )

        existe_recibo = bool(
            estado_nro.get("existe_activo")
        )
        existe_factura = False
        detalle_partes: List[str] = []

        if nro_doc:
            if existe_recibo:
                detalle_partes.append("Recibo OK")
            else:
                detalle_partes.append("Recibo NO encontrado")

        if doc_legal:
            existe_factura = bool(
                estado_doc.get("existe_activo")
            )
            if existe_factura:
                detalle_partes.append("Factura OK")
            else:
                detalle_partes.append("Factura NO encontrada")
        elif nro_doc and bool(
            estado_nro.get("tiene_factura_bd")
        ):
            existe_factura = True
            detalle_partes.append(
                "Factura encontrada en BD"
            )

        esta_anulado = bool(
            estado_nro.get("esta_anulado")
        ) or bool(
            estado_doc.get("esta_anulado")
        )

        tiene_algun_doc = bool(nro_doc or doc_legal)

        if not tiene_algun_doc:
            existe_general = False
            estado_color = "rojo"
            detalle_partes.append("Sin documentos para validar")
        elif esta_anulado:
            existe_general = False
            estado_color = "morado"
            detalle_partes.append("Registro anulado en BD")
        elif existe_recibo and existe_factura:
            existe_general = True
            estado_color = "verde"
        elif existe_recibo:
            existe_general = False
            estado_color = "amarillo"
        else:
            existe_general = False
            estado_color = "rojo"

        if existe_general:
            cant_existe += 1
        else:
            cant_no_existe += 1

        resultados.append({
            "existe_recibo": existe_recibo,
            "existe_factura": existe_factura,
            "existe_general": existe_general,
            "estado_color": estado_color,
            "esta_anulado": esta_anulado,
            "detalle": "  |  ".join(detalle_partes),
        })

    bd.desconectar()
    return resultados, cant_existe, cant_no_existe


# ---------------------------------------------------------------------
# FUNCIONES MANTENIDAS PARA COMPATIBILIDAD (no usadas en el flujo rápido)
# ---------------------------------------------------------------------
def _buscar_nro_documento(bd: ConexionBD, pre, valor: str) -> bool:
    checks = []

    sql1, p1 = _condicion_cifrada_norm("p.recibo", valor)
    q1 = f"SELECT 1 FROM polizas p WHERE {sql1} LIMIT 1"
    checks.append((q1, p1))

    sql2, p2 = _condicion_cifrada_norm("p.poliza", valor)
    q2 = f"SELECT 1 FROM polizas p WHERE {sql2} LIMIT 1"
    checks.append((q2, p2))

    sql3, p3 = _condicion_cifrada_norm("p.nro", valor)
    q3 = f"SELECT 1 FROM polizas p WHERE {sql3} LIMIT 1"
    checks.append((q3, p3))

    sql4, p4 = _condicion_cifrada_norm("c.cupon", valor)
    q4 = f"SELECT 1 FROM cuotas c WHERE {sql4} LIMIT 1"
    checks.append((q4, p4))

    for q, p in checks:
        r = bd.ejecutar_consulta(q, p, solo_uno=True, pre_statements=pre)
        if r:
            return True
    return False


def _buscar_doc_legal(bd: ConexionBD, pre, valor: str) -> bool:
    sql2, p2 = _condicion_plana_norm("c.factura", valor)
    q2 = f"SELECT 1 FROM cuotas c WHERE {sql2} LIMIT 1"
    r2 = bd.ejecutar_consulta(q2, p2, solo_uno=True, pre_statements=pre)
    if r2:
        return True
    return False
