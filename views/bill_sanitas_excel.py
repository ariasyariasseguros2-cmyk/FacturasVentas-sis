import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List


ESTADO_CUENTA_COLUMNS = (
    "compania",
    "ruc",
    "contratante",
    "contrato",
    "fecha_emision",
    "documento",
    "inicio_vigencia",
    "fin_vigencia",
    "fecha_comprobante",
    "comprobante",
    "fecha_vencimiento",
    "estado_pago",
    "fecha_pago",
    "cip",
    "importe",
)


_ESTADO_CUENTA_HEADERS = {
    "compania": ("compania", "compania aseguradora"),
    "ruc": ("ruc",),
    "contratante": ("contratante",),
    "contrato": ("contrato",),
    "fecha_emision": ("fecha emision",),
    "documento": ("documento",),
    "inicio_vigencia": ("inicio vigencia",),
    "fin_vigencia": ("fin vigencia",),
    "fecha_comprobante": ("fecha comprobante",),
    "comprobante": ("comprobante",),
    "fecha_vencimiento": ("fecha vencimiento",),
    "estado_pago": ("estado pago",),
    "fecha_pago": ("fecha pago",),
    "cip": ("cip",),
    "importe": ("importe",),
}


def _normalizar_encabezado_excel(value: Any) -> str:
    """
    Normaliza un encabezado de Excel.
    """

    texto = "" if value is None else str(value).strip().lower()

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    # IMPORTANTE:
    # Regex correcto para espacios múltiples.
    return re.sub(r"\s+", " ", texto)


def _formatear_fecha_excel(value: Any) -> str:
    """
    Convierte fechas a DD/MM/YYYY.
    """

    if value in (None, ""):
        return ""

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")

    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    return str(value).strip()


def _formatear_importe_excel(value: Any) -> Decimal:
    """
    Convierte el importe a Decimal con 2 decimales.
    """

    if value in (None, ""):
        return Decimal("0.00")

    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value)).quantize(
            Decimal("0.01")
        )

    texto = str(value).strip()

    texto = texto.replace("S/", "")
    texto = texto.replace("$", "")
    texto = texto.strip()

    texto = texto.replace(",", "")

    try:
        return Decimal(texto).quantize(
            Decimal("0.01")
        )

    except InvalidOperation:
        return Decimal("0.00")


def _limpiar_contrato(value: Any) -> str:
    if value is None:
        return ""

    texto = str(value).strip()

    if not texto:
        return ""

    # Eliminar espacios
    texto = texto.strip()

    # ---------------------------------------------------------
    # ELIMINAR CC- DEL INICIO
    # ---------------------------------------------------------
    while texto.upper().startswith("CC-"):
        texto = texto[3:].strip()

    # ---------------------------------------------------------
    # ELIMINAR TODO LO QUE VENGA DESPUÉS DEL ÚLTIMO /
    # SI DESPUÉS DEL / SOLO HAY NÚMEROS
    # ---------------------------------------------------------
    if "/" in texto:
        partes = texto.rsplit("/", 1)

        if len(partes) == 2:
            base = partes[0].strip()
            sufijo = partes[1].strip()

            if sufijo.isdigit():
                texto = base

    return texto.strip()


def extraer_estado_cuenta_sanitas(
    excel_path: str
) -> List[Dict[str, Any]]:
    
    try:
        from openpyxl import load_workbook

    except ImportError as exc:
        raise RuntimeError(
            "Se requiere la librería 'openpyxl' "
            "para leer archivos Excel."
        ) from exc

    workbook = load_workbook(
        excel_path,
        read_only=True,
        data_only=True
    )

    try:

        for worksheet in workbook.worksheets:

            header_row = None

            column_map: Dict[str, int] = {}

            # =====================================================
            # BUSCAR ENCABEZADOS
            # =====================================================

            for row_number, row in enumerate(
                worksheet.iter_rows(
                    max_row=30,
                    values_only=True
                ),
                start=1
            ):

                normalized = [
                    _normalizar_encabezado_excel(value)
                    for value in row
                ]

                candidate: Dict[str, int] = {}

                for index, header in enumerate(normalized):

                    for field, aliases in _ESTADO_CUENTA_HEADERS.items():

                        if header in aliases:

                            candidate[field] = index

                            break

                # Permitimos que falte como máximo un encabezado.

                if len(candidate) >= (
                    len(ESTADO_CUENTA_COLUMNS) - 1
                ):

                    header_row = row_number
                    column_map = candidate

                    break

            # Si no encontró encabezados,
            # probar siguiente hoja.

            if header_row is None:
                continue

            rows: List[Dict[str, Any]] = []

            # =====================================================
            # LEER FILAS
            # =====================================================

            for row in worksheet.iter_rows(
                min_row=header_row + 1,
                values_only=True
            ):

                values = {
                    field: (
                        row[index]
                        if index < len(row)
                        else ""
                    )
                    for field, index in column_map.items()
                }

                # =================================================
                # IGNORAR FILA VACÍA
                # =================================================

                if not any(
                    value not in (None, "")
                    for value in values.values()
                ):
                    continue

                # =================================================
                # IGNORAR FILA TOTAL
                # =================================================

                if all(
                    _normalizar_encabezado_excel(value) == "total"
                    for value in values.values()
                    if value
                ):
                    continue

                # =================================================
                # CREAR RESULTADO
                # =================================================

                result = {
                    field: ""
                    for field in ESTADO_CUENTA_COLUMNS
                }

                # =================================================
                # FECHAS
                # =================================================

                for field in (
                    "fecha_emision",
                    "inicio_vigencia",
                    "fin_vigencia",
                    "fecha_comprobante",
                    "fecha_vencimiento",
                    "fecha_pago",
                ):

                    result[field] = _formatear_fecha_excel(
                        values.get(field)
                    )

                # =================================================
                # IMPORTE
                # =================================================

                result["importe"] = _formatear_importe_excel(
                    values.get("importe")
                )

                # =================================================
                # CAMPOS DE TEXTO
                # =================================================

                for field in (
                    "compania",
                    "ruc",
                    "contratante",
                    "documento",
                    "comprobante",
                    "estado_pago",
                    "cip",
                ):

                    value = values.get(field)

                    result[field] = (
                        ""
                        if value is None
                        else str(value).strip()
                    )

                # =================================================
                # CONTRATO
                # =================================================

                result["documento"] = _limpiar_contrato(
                    values.get("documento")
                )

                # =================================================
                # AGREGAR FILA
                # =================================================

                rows.append(result)

            return rows

    finally:
        workbook.close()

    # =============================================================
    # NO SE ENCONTRARON ENCABEZADOS
    # =============================================================

    raise ValueError(
        "No se encontraron los encabezados del estado de cuenta: "
        + ", ".join(
            (
                "Compañía",
                "Ruc",
                "Contratante",
                "Contrato",
                "Fecha Emisión",
                "Documento",
                "Inicio Vigencia",
                "Fin Vigencia",
                "Fecha Comprobante",
                "Comprobante",
                "Fecha Vencimiento",
                "Estado Pago",
                "Fecha Pago",
                "CIP",
                "Importe",
            )
        )
    )