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
    alias, col = tabla_col.split(".", 1)
    tabla = _ALIAS_A_TABLA.get(alias, alias)
    return alias, tabla, col


def _buscar_masivo_cifrado(
    bd: ConexionBD,
    pre: List[Tuple[str, Tuple[Any, ...]]],
    tabla_col: str,
    valores: List[str],
) -> Set[str]:
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


def validar_filas_contra_grandias_bd(
    filas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Validación ESPECÍFICA para Grandia EPS (Liquidación de Comisiones).

    Campos de entrada POR FILA (formato Grandia):
      - nro_contrato:      N° Contrato  (ej: 500013893)  → PÓLIZA
      - factura_movimiento: Factura de Movimiento  (ej: F099-00028629) → FACTURA
      - producto/contratante: opcionales (detalle, no se buscan)

    Búsquedas:
         PÓLIZA (existe_recibo):
        - polizas.recibo          (AES cifrado)
        - polizas.poliza          (AES cifrado)
        - polizas.nro             (AES cifrado)
        - cuotas.cupon            (AES cifrado)

         FACTURA (existe_factura):
        - polizas.numero_factura  (AES cifrado)
        - polizas.numero_factura  (PLANO - legacy)
        - cuotas.factura          (PLANO)

    Retorna igual que validacion_bd.py:
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
    set_nro_contrato: Set[str] = set()
    set_factura_mov: Set[str] = set()

    for fila in filas:
        nro_contrato = _normalizar(fila.get("nro_contrato", ""))
        factura_mov = _normalizar(fila.get("factura_movimiento", ""))
        filas_normalizadas.append({
            "nro_contrato": nro_contrato,
            "factura_movimiento": factura_mov,
        })
        if nro_contrato:
            set_nro_contrato.add(nro_contrato)
        if factura_mov:
            set_factura_mov.add(factura_mov)

    lista_contratos = list(set_nro_contrato)
    lista_facturas = list(set_factura_mov)

    # ================================================================
    # PASO 2: Consultas MASIVAS (7 consultas TOTALES)
    # ================================================================

    # --- Búsqueda masiva de N° CONTRATO (póliza / recibo / nro / cupón) ---
    hits_recibo = _buscar_masivo_cifrado(bd, pre, "p.recibo", lista_contratos)
    hits_poliza = _buscar_masivo_cifrado(bd, pre, "p.poliza", lista_contratos)
    hits_nro = _buscar_masivo_cifrado(bd, pre, "p.nro", lista_contratos)
    hits_cupon = _buscar_masivo_cifrado(bd, pre, "c.cupon", lista_contratos)
    todos_hits_contrato = hits_recibo | hits_poliza | hits_nro | hits_cupon

    # --- Búsqueda masiva de FACTURA MOVIMIENTO (F099-XXXXXXX) ---
    hits_numfact_cif = _buscar_masivo_cifrado(bd, pre, "p.numero_factura", lista_facturas)
    hits_numfact_plan = _buscar_masivo_plano(bd, pre, "p.numero_factura", lista_facturas)
    hits_cfactura = _buscar_masivo_plano(bd, pre, "c.factura", lista_facturas)
    todos_hits_factura = hits_numfact_cif | hits_numfact_plan | hits_cfactura

    # ================================================================
    # PASO 3: Construir resultados
    # ================================================================
    resultados: List[Dict[str, Any]] = []
    cant_existe = 0
    cant_no_existe = 0

    for fn in filas_normalizadas:
        nro_contrato = fn["nro_contrato"]
        factura_mov = fn["factura_movimiento"]

        existe_recibo = False  # N° Contrato encontrado (póliza/recibo)
        existe_factura = False  # Factura Movimiento encontrada
        detalle_partes: List[str] = []

        if nro_contrato:
            existe_recibo = nro_contrato in todos_hits_contrato
            if existe_recibo:
                detalle_partes.append(f"N°Contrato OK")
            else:
                detalle_partes.append(f"N°Contrato NO encontrado")

        if factura_mov:
            existe_factura = factura_mov in todos_hits_factura
            if existe_factura:
                detalle_partes.append(f"Factura Mov. OK")
            else:
                detalle_partes.append(f"Factura Mov. NO encontrada")

        tiene_algun_doc = bool(nro_contrato or factura_mov)

        if tiene_algun_doc:
            if nro_contrato and factura_mov:
                existe_general = existe_recibo and existe_factura
            elif nro_contrato:
                existe_general = existe_recibo
            else:
                existe_general = existe_factura
        else:
            existe_general = False
            detalle_partes.append("Sin N°Contrato ni Factura Mov. para validar")

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
