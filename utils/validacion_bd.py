import re
from typing import List, Dict, Any, Tuple, Set

from utils.conexion_bd import ConexionBD


SIS_KEY = "MiPassphraseSegura$$2025"

COLOR_VERDE = "#dcfce7"
COLOR_AMARILLO = "#fef3c7"
COLOR_ROJO = "#fee2e2"

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


def _buscar_masivo_cifrado(
    bd: ConexionBD,
    pre: List[Tuple[str, Tuple[Any, ...]]],
    tabla_col: str,
    valores: List[str],
) -> Set[str]:
    """
    Busca MASIVAMENTE una lista de valores en una columna CIFRADA usando IN (...).
    Usa un SUBQUERY wrapper para que MySQL materialice el descifrado correctamente.
    Devuelve el set de valores NORMALIZADOS que SÍ existen en la columna.
    """
    if not valores:
        return set()

    alias, tabla, col = _alias_tabla(tabla_col)
    expr_col = _DECRYPT_TPL.format(col=f"{alias}.{col}")
    norm_expr = f"UPPER(REPLACE(REPLACE({expr_col}, ' ', ''), 'Ñ', 'N'))"

    placeholders = ", ".join(["%s"] * len(valores))
    sql = (
        f"SELECT DISTINCT sub.val FROM ("
        f"  SELECT {norm_expr} AS val FROM {tabla} {alias}"
        f") sub "
        f"WHERE sub.val IN ({placeholders})"
    )
    params = (SIS_KEY,) + tuple(valores)

    try:
        rows = bd.ejecutar_consulta(sql, params, solo_uno=False, pre_statements=pre)
    except Exception:
        return set()

    encontrados: Set[str] = set()
    for row in (rows or []):
        v = row.get("val")
        if v is not None:
            encontrados.add(str(v))
    return encontrados


def _buscar_masivo_plano(
    bd: ConexionBD,
    pre: List[Tuple[str, Tuple[Any, ...]]],
    tabla_col: str,
    valores: List[str],
) -> Set[str]:
    """
    Busca MASIVAMENTE una lista de valores en una columna PLANA (sin cifrar) usando IN (...).
    Usa SUBQUERY wrapper para coherencia con el método cifrado y robustez.
    Devuelve el set de valores NORMALIZADOS que SÍ existen.
    """
    if not valores:
        return set()

    alias, tabla, col = _alias_tabla(tabla_col)
    norm_expr = f"UPPER(REPLACE(REPLACE({alias}.{col}, ' ', ''), 'Ñ', 'N'))"
    placeholders = ", ".join(["%s"] * len(valores))
    sql = (
        f"SELECT DISTINCT sub.val FROM ("
        f"  SELECT {norm_expr} AS val FROM {tabla} {alias}"
        f") sub "
        f"WHERE sub.val IN ({placeholders})"
    )
    params = tuple(valores)

    try:
        rows = bd.ejecutar_consulta(sql, params, solo_uno=False, pre_statements=pre)
    except Exception:
        return set()

    encontrados: Set[str] = set()
    for row in (rows or []):
        v = row.get("val")
        if v is not None:
            encontrados.add(str(v))
    return encontrados


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
        nro_doc = _normalizar(fila.get("nro_documento", ""))
        doc_legal = _normalizar(fila.get("doc_legal", ""))
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

    # --- Búsqueda masiva de NRO DOCUMENTO (4 columnas) ---
    hits_recibo   = _buscar_masivo_cifrado(bd, pre, "p.recibo",   lista_nro_docs)
    hits_poliza   = _buscar_masivo_cifrado(bd, pre, "p.poliza",   lista_nro_docs)
    hits_nro      = _buscar_masivo_cifrado(bd, pre, "p.nro",      lista_nro_docs)
    hits_cupon    = _buscar_masivo_cifrado(bd, pre, "c.cupon",    lista_nro_docs)
    todos_hits_nro_doc = hits_recibo | hits_poliza | hits_nro | hits_cupon

    # --- Búsqueda masiva de DOC LEGAL (3 columnas) ---
    hits_numfact_cif  = _buscar_masivo_cifrado(bd, pre, "p.numero_factura", lista_doc_legales)
    hits_numfact_plan = _buscar_masivo_plano(bd, pre,   "p.numero_factura", lista_doc_legales)
    hits_cfactura     = _buscar_masivo_plano(bd, pre,   "c.factura",        lista_doc_legales)
    todos_hits_doc_legal = hits_numfact_cif | hits_numfact_plan | hits_cfactura

    # ================================================================
    # PASO 3: Construir resultados (búsqueda en SET local — O(1))
    # ================================================================
    resultados: List[Dict[str, Any]] = []
    cant_existe = 0
    cant_no_existe = 0

    for fn in filas_normalizadas:
        nro_doc = fn["nro_doc"]
        doc_legal = fn["doc_legal"]

        existe_recibo = False
        existe_factura = False
        detalle_partes: List[str] = []

        if nro_doc:
            existe_recibo = nro_doc in todos_hits_nro_doc
            if existe_recibo:
                detalle_partes.append("Recibo OK")
            else:
                detalle_partes.append("Recibo NO encontrado")

        if doc_legal:
            existe_factura = doc_legal in todos_hits_doc_legal
            if existe_factura:
                detalle_partes.append("Factura OK")
            else:
                detalle_partes.append("Factura NO encontrada")

        tiene_algun_doc = bool(nro_doc or doc_legal)

        if tiene_algun_doc:
            if nro_doc and doc_legal:
                existe_general = existe_recibo and existe_factura
            elif nro_doc:
                existe_general = existe_recibo
            else:
                existe_general = existe_factura
        else:
            existe_general = False
            detalle_partes.append("Sin documentos para validar")

        if existe_general:
            cant_existe += 1
        else:
            cant_no_existe += 1

        resultados.append({
            "existe_recibo": existe_recibo,
            "existe_factura": existe_factura,
            "existe_general": existe_general,
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
    sql1, p1 = _condicion_cifrada_norm("p.numero_factura", valor)
    q1 = f"SELECT 1 FROM polizas p WHERE {sql1} LIMIT 1"
    r1 = bd.ejecutar_consulta(q1, p1, solo_uno=True, pre_statements=pre)
    if r1:
        return True

    sql1b, p1b = _condicion_plana_norm("p.numero_factura", valor)
    q1b = f"SELECT 1 FROM polizas p WHERE {sql1b} LIMIT 1"
    r1b = bd.ejecutar_consulta(q1b, p1b, solo_uno=True, pre_statements=pre)
    if r1b:
        return True

    sql2, p2 = _condicion_plana_norm("c.factura", valor)
    q2 = f"SELECT 1 FROM cuotas c WHERE {sql2} LIMIT 1"
    r2 = bd.ejecutar_consulta(q2, p2, solo_uno=True, pre_statements=pre)
    if r2:
        return True
    return False
