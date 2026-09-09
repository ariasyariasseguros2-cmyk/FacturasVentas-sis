import re
from typing import List, Dict, Any, Tuple

from utils.conexion_bd import ConexionBD


SIS_KEY = "MiPassphraseSegura$$2025"

COLOR_EXISTE = "#dcfce7"
COLOR_NO_EXISTE = "#fee2e2"


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


def _condicion_cifrada_norm(col: str, valor_norm: str) -> Tuple[str, Tuple[str, str]]:
    expr = _DECRYPT_TPL.format(col=col)
    sql = f"UPPER(REPLACE(REPLACE({expr}, ' ', ''), 'Ñ', 'N')) = %s"
    return sql, (SIS_KEY, valor_norm)


def _condicion_plana_norm(col: str, valor_norm: str) -> Tuple[str, Tuple[str]]:
    sql = f"UPPER(REPLACE(REPLACE({col}, ' ', ''), 'Ñ', 'N')) = %s"
    return sql, (valor_norm,)


def validar_filas_contra_bd(
    filas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Valida cada fila contra la BD.
    Busca:
      - nro_documento en polizas.recibo (cifrado) y polizas.poliza, polizas.nro, cuotas.cupon
      - doc_legal    en polizas.numero_factura (cifrado) y cuotas.factura

    Retorna:
      (resultados, cantidad_existe, cantidad_no_existe)
      Cada resultado es: {"existe_recibo": bool, "existe_factura": bool,
                         "existe_general": bool, "detalle": str}
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
    resultados: List[Dict[str, Any]] = []
    cant_existe = 0
    cant_no_existe = 0

    for fila in filas:
        nro_doc = _normalizar(fila.get("nro_documento", ""))
        doc_legal = _normalizar(fila.get("doc_legal", ""))

        existe_recibo = False
        existe_factura = False
        detalle_partes: List[str] = []

        if nro_doc:
            existe_recibo = _buscar_nro_documento(bd, pre, nro_doc)
            if existe_recibo:
                detalle_partes.append("Recibo OK")
            else:
                detalle_partes.append("Recibo NO encontrado")

        if doc_legal:
            existe_factura = _buscar_doc_legal(bd, pre, doc_legal)
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
