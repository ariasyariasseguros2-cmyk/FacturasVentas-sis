import re
import traceback
from typing import List, Dict, Any, Tuple, Set, Optional

from utils.conexion_bd import ConexionBD


SIS_KEY = "MiPassphraseSegura$$2025"

COLOR_VERDE = "#dcfce7"
COLOR_AMARILLO = "#fef3c7"
COLOR_ROJO = "#fee2e2"

COLOR_EXISTE = COLOR_VERDE
COLOR_NO_EXISTE = COLOR_ROJO


def _normalizar(texto: Any) -> str:
    if texto is None:
        return ""
    s = str(texto).strip().upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("Ñ", "N")
    return s


_DECRYPT_TPL = (
    "CAST(AES_DECRYPT(FROM_BASE64({col}), %s) AS CHAR)"
)


# ================================================================
#   HERRAMIENTAS PEQUEÑAS Y ROBUSTAS DE BÚSQUEDA
#   Cada una = 1 sola consulta simple (sin UNION, sin sub-CTEs)
#   Así si una columna falla por cifrado/plano, lo demás sigue andando.
# ================================================================

def _buscar_columna(
    bd: ConexionBD,
    pre: List[Tuple[str, Tuple[Any, ...]]],
    tabla_alias: str,
    tabla_real: str,
    id_col: str,
    valor_col: str,
    valores: List[str],
    cifrada: bool,
    ids_por_valor: Dict[str, Set[int]],
) -> None:
    """
    Busca en 1 SOLA columna (cifrada o plana) y pobla `ids_por_valor`
    agregando los idPoliza/id encontrados. No usa UNIONs de ningún tipo.
    """
    if not valores:
        return

    ph = ", ".join(["%s"] * len(valores))

    if cifrada:
        expr = _DECRYPT_TPL.format(col=f"{tabla_alias}.{valor_col}")
        params: Tuple[Any, ...] = (SIS_KEY,)
    else:
        expr = f"{tabla_alias}.{valor_col}"
        params = ()

    norm_expr = f"UPPER(REPLACE(REPLACE(COALESCE({expr}, ''), ' ', ''), 'Ñ', 'N'))"

    sql = (
        f"SELECT DISTINCT {tabla_alias}.{id_col} AS idp, {norm_expr} AS val "
        f"FROM {tabla_real} {tabla_alias} "
        f"HAVING val IN ({ph})"
    )
    params = params + tuple(valores)

    rows: Optional[Any] = None
    try:
        rows = bd.ejecutar_consulta(sql, params, solo_uno=False, pre_statements=pre)
    except Exception:
        try:
            print(
                f"[validacion_grandias_bd] ERROR en consulta "
                f"{tabla_real}.{valor_col} ({'cifrada' if cifrada else 'plano'}):"
            )
            traceback.print_exc()
        except Exception:
            pass
        return

    if not rows:
        return

    for row in rows:
        v = row.get("val")
        idp = row.get("idp")
        if v is None or idp is None:
            continue
        vs = str(v).strip()
        if not vs:
            continue
        try:
            idp_int = int(idp)
        except Exception:
            continue
        ids_por_valor.setdefault(vs, set()).add(idp_int)


def _juntar_ids(
    *dicts: Dict[str, Set[int]],
) -> Dict[str, Set[int]]:
    """Combina múltiples Dict[valor, Set[id]] en uno solo (unión de ids por valor)."""
    out: Dict[str, Set[int]] = {}
    for d in dicts:
        for k, ids_set in d.items():
            if not ids_set:
                continue
            out.setdefault(k, set()).update(ids_set)
    return out


# ================================================================
#   FUNCIÓN PRINCIPAL
# ================================================================

def validar_filas_contra_grandias_bd(
    filas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Validación ESPECÍFICA para Grandia EPS (Liquidación de Comisiones).

    Campos de entrada POR FILA (formato Grandia):
      - nro_contrato:      N° Contrato  (ej: 500013893)  → PÓLIZA
      - factura_movimiento: Factura de Movimiento  (ej: F099-00028629) → FACTURA
      - producto/contratante: opcionales (detalle, no se buscan)

    Columnas de BÚSQUEDA (cada una = 1 consulta independiente, cifrada + plano):

         PÓLIZA (existe_recibo = False ↔ no se encuentra en ninguna):
        - polizas.poliza           | cifrada + plano
        - polizas.recibo           | cifrada + plano
        - polizas.nro              | cifrada + plano
        - cuotas.cupon             | cifrada + plano   (id = cuotas.poliza_id)

         FACTURA (existe_factura = False ↔ no se encuentra en ninguna):
        - polizas.numero_factura   | cifrada + plano
        - cuotas.factura           | plano

         VALIDACIÓN CRUZADA (mismo idPoliza):
        Cuando existen AMBOS campos, ambos deben coincidir en AL MENOS
        un idPoliza común. Si la factura tiene intersección vacía de
        ids con la póliza, existe PERO en OTRA póliza → se invalida
        (existe_factura = False) para evitar falsos VERDES.
    """

    resultados: List[Dict[str, Any]] = []
    cant_existe = 0
    cant_no_existe = 0

    bd = ConexionBD()
    if not bd.conectar():
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
    # PASO 1: Normalizar y recolectar valores únicos
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
    # PASO 2: Búsqueda por columna INDIVIDUAL (8 + 3 = 11 consultas)
    #   Son consultas chiquitas. Si alguna falla, las demás siguen.
    # ================================================================
    ids_poliza_cif: Dict[str, Set[int]] = {}
    ids_poliza_plan: Dict[str, Set[int]] = {}
    ids_recibo_cif: Dict[str, Set[int]] = {}
    ids_recibo_plan: Dict[str, Set[int]] = {}
    ids_nro_cif: Dict[str, Set[int]] = {}
    ids_nro_plan: Dict[str, Set[int]] = {}
    ids_cupon_cif: Dict[str, Set[int]] = {}
    ids_cupon_plan: Dict[str, Set[int]] = {}

    ids_numfact_cif: Dict[str, Set[int]] = {}
    ids_numfact_plan: Dict[str, Set[int]] = {}
    ids_cfactura_plan: Dict[str, Set[int]] = {}

    # --- Pólizas (idColumna = idPoliza) ---
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "poliza",
                    lista_contratos, True, ids_poliza_cif)
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "poliza",
                    lista_contratos, False, ids_poliza_plan)
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "recibo",
                    lista_contratos, True, ids_recibo_cif)
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "recibo",
                    lista_contratos, False, ids_recibo_plan)
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "nro",
                    lista_contratos, True, ids_nro_cif)
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "nro",
                    lista_contratos, False, ids_nro_plan)

    # --- Cuotas (idColumna = poliza_id) ---
    _buscar_columna(bd, pre, "c", "cuotas", "poliza_id", "cupon",
                    lista_contratos, True, ids_cupon_cif)
    _buscar_columna(bd, pre, "c", "cuotas", "poliza_id", "cupon",
                    lista_contratos, False, ids_cupon_plan)

    # --- Facturas ---
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "numero_factura",
                    lista_facturas, True, ids_numfact_cif)
    _buscar_columna(bd, pre, "p", "polizas", "idPoliza", "numero_factura",
                    lista_facturas, False, ids_numfact_plan)
    _buscar_columna(bd, pre, "c", "cuotas", "poliza_id", "factura",
                    lista_facturas, False, ids_cfactura_plan)

    ids_por_contrato = _juntar_ids(
        ids_poliza_cif, ids_poliza_plan,
        ids_recibo_cif, ids_recibo_plan,
        ids_nro_cif, ids_nro_plan,
        ids_cupon_cif, ids_cupon_plan,
    )
    ids_por_factura = _juntar_ids(
        ids_numfact_cif, ids_numfact_plan, ids_cfactura_plan,
    )

    # Sets planos para búsquedas rápidas
    todos_hits_contrato: Set[str] = {k for k, s in ids_por_contrato.items() if s}
    todos_hits_factura: Set[str] = {k for k, s in ids_por_factura.items() if s}

    # ================================================================
    # PASO 3: Construir resultados
    # ================================================================

    for fn in filas_normalizadas:
        nro_contrato = fn["nro_contrato"]
        factura_mov = fn["factura_movimiento"]

        existe_recibo = False
        existe_factura = False
        detalle_partes: List[str] = []

        # PÓLIZA
        if nro_contrato:
            existe_recibo = nro_contrato in todos_hits_contrato
            if existe_recibo:
                ids_cto = sorted(ids_por_contrato.get(nro_contrato, set()) or [])
                if ids_cto:
                    detalle_partes.append(f"Póliza OK (ids {ids_cto[:3]})")
                else:
                    detalle_partes.append("Póliza OK")
            else:
                detalle_partes.append("Póliza NO encontrada")

        # FACTURA
        if factura_mov:
            factura_existe_sola = factura_mov in todos_hits_factura

            if nro_contrato and existe_recibo and factura_existe_sola:
                ids_cto = ids_por_contrato.get(nro_contrato, set()) or set()
                ids_fact = ids_por_factura.get(factura_mov, set()) or set()
                interseccion = ids_cto & ids_fact
                if interseccion:
                    existe_factura = True
                    lista_ids = sorted(interseccion)[:3]
                    detalle_partes.append(
                        f"Factura OK (coincide id {lista_ids})"
                    )
                else:
                    existe_factura = False
                    lista_cto = sorted(ids_cto)[:3]
                    lista_fac = sorted(ids_fact)[:3]
                    detalle_partes.append(
                        f"Factura en OTRA póliza (cto ids {lista_cto}, fact ids {lista_fac})"
                    )
            else:
                existe_factura = factura_existe_sola
                if existe_factura:
                    ids_f = sorted(ids_por_factura.get(factura_mov, set()) or [])
                    if ids_f:
                        detalle_partes.append(f"Factura OK (ids {ids_f[:3]})")
                    else:
                        detalle_partes.append("Factura OK")
                else:
                    detalle_partes.append("Factura NO encontrada")

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
            detalle_partes.append("Sin Póliza ni Factura para validar")

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

    try:
        bd.desconectar()
    except Exception:
        pass

    return resultados, cant_existe, cant_no_existe
