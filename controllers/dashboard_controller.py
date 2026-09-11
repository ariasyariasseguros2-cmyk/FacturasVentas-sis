# controllers/dashboard_controller.py
from datetime import date, datetime
from utils.conexion_bd import ConexionBD

class DashboardController:
    @staticmethod
    def obtener_metricas_hoy():
        db = ConexionBD()

        hoy = date.today().isoformat()

        # 1. Ventas del día en Soles (S/.)
        res_soles = db.ejecutar_consulta("""
            SELECT COALESCE(SUM(importe), 0) AS total 
            FROM cuotas 
            WHERE DATE(creado_en) = %s 
              AND activo = 1 
              AND (moneda = 'S/' OR moneda = 'PEN' OR moneda = 'SOLES')
        """, params=(hoy,), solo_uno=True)

        # 2. Ventas del día en Dólares (US$)
        res_dolares = db.ejecutar_consulta("""
            SELECT COALESCE(SUM(importe), 0) AS total 
            FROM cuotas 
            WHERE DATE(creado_en) = %s 
              AND activo = 1 
              AND (moneda = 'US$' OR moneda = 'USD' OR moneda = 'DOLARES')
        """, params=(hoy,), solo_uno=True)

        # 3. Facturas emitidas hoy
        res_facturas = db.ejecutar_consulta("""
            SELECT COUNT(*) AS total 
            FROM cuotas 
            WHERE DATE(fecha_factura) = %s AND factura IS NOT NULL
        """, params=(hoy,), solo_uno=True)

        # 4. Pólizas registradas hoy
        res_polizas = db.ejecutar_consulta("""
            SELECT COUNT(*) AS total 
            FROM polizas 
            WHERE DATE(creado_en) = %s
        """, params=(hoy,), solo_uno=True)

        # 5. Clientes registrados hoy
        res_clientes = db.ejecutar_consulta("""
            SELECT COUNT(*) AS total 
            FROM clientes 
            WHERE DATE(fecha_registro) = %s
        """, params=(hoy,), solo_uno=True)

        db.desconectar()

        return {
            "ventas_soles": res_soles["total"] if res_soles else 0.0,
            "ventas_dolares": res_dolares["total"] if res_dolares else 0.0,
            "facturas": res_facturas["total"] if res_facturas else 0,
            "polizas": res_polizas["total"] if res_polizas else 0,
            "clientes": res_clientes["total"] if res_clientes else 0
        }

    @staticmethod
    def obtener_datos_grafico_diario(moneda: str = "PEN"):
        db = ConexionBD()
        hoy = date.today().isoformat()
        ahora = datetime.now()

        if moneda == "PEN":
            moneda_sql = ("S/", "PEN", "SOLES")
            simbolo = "S/"
        else:
            moneda_sql = ("US$", "USD", "DOLARES")
            simbolo = "US$"

        moneda_placeholder = ", ".join(["%s"] * len(moneda_sql))

        totales = db.ejecutar_consulta(f"""
            SELECT
                COALESCE(SUM(prima_neta), 0) AS total_prima_neta,
                COALESCE(SUM(prima_comercial_igv), 0) AS total_prima_comercial_igv,
                COALESCE(SUM(COALESCE(imp_compania, 0) + COALESCE(imp_subagente, 0)), 0) AS total_comision
            FROM polizas
            WHERE DATE(creado_en) = %s
              AND activo = 1
              AND anulado = 0
              AND prima_anulada = 0
              AND moneda IN ({moneda_placeholder})
        """, params=(hoy, *moneda_sql), solo_uno=True)

        por_hora_raw = db.ejecutar_consulta(f"""
            SELECT
                HOUR(creado_en) AS hora,
                COALESCE(SUM(prima_neta), 0) AS prima_neta,
                COALESCE(SUM(prima_comercial_igv), 0) AS prima_comercial_igv,
                COALESCE(SUM(COALESCE(imp_compania, 0) + COALESCE(imp_subagente, 0)), 0) AS comision
            FROM polizas
            WHERE DATE(creado_en) = %s
              AND activo = 1
              AND anulado = 0
              AND prima_anulada = 0
              AND moneda IN ({moneda_placeholder})
            GROUP BY HOUR(creado_en)
            ORDER BY hora
        """, params=(hoy, *moneda_sql))

        db.desconectar()

        por_hora = []
        for h in range(24):
            fila = {
                "hora": h,
                "prima_neta": 0.0,
                "prima_comercial_igv": 0.0,
                "comision": 0.0,
            }
            if por_hora_raw:
                for r in por_hora_raw:
                    if r.get("hora") == h:
                        fila["prima_neta"] = float(r.get("prima_neta", 0) or 0)
                        fila["prima_comercial_igv"] = float(r.get("prima_comercial_igv", 0) or 0)
                        fila["comision"] = float(r.get("comision", 0) or 0)
                        break
            por_hora.append(fila)

        return {
            "moneda": moneda,
            "simbolo": simbolo,
            "fecha": hoy,
            "hora_actual": ahora.hour,
            "totales": {
                "prima_neta": float(totales.get("total_prima_neta", 0) or 0) if totales else 0.0,
                "prima_comercial_igv": float(totales.get("total_prima_comercial_igv", 0) or 0) if totales else 0.0,
                "comision": float(totales.get("total_comision", 0) or 0) if totales else 0.0,
            },
            "por_hora": por_hora,
        }

