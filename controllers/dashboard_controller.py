# controllers/dashboard_controller.py
from utils.conexion_bd import ConexionBD

class DashboardController:
    @staticmethod
    def obtener_metricas_hoy():
        db = ConexionBD()

        # 1. Ventas del día en Soles (S/.)
        res_soles = db.ejecutar_consulta("""
            SELECT COALESCE(SUM(importe), 0) AS total 
            FROM cuotas 
            WHERE DATE(creado_en) = CURDATE() 
              AND activo = 1 
              AND (moneda = 'S/' OR moneda = 'PEN' OR moneda = 'SOLES')
        """, solo_uno=True)

        # 2. Ventas del día en Dólares (US$)
        res_dolares = db.ejecutar_consulta("""
            SELECT COALESCE(SUM(importe), 0) AS total 
            FROM cuotas 
            WHERE DATE(creado_en) = CURDATE() 
              AND activo = 1 
              AND (moneda = 'US$' OR moneda = 'USD' OR moneda = 'DOLARES')
        """, solo_uno=True)

        # 3. Facturas emitidas hoy
        res_facturas = db.ejecutar_consulta("""
            SELECT COUNT(*) AS total 
            FROM cuotas 
            WHERE DATE(fecha_factura) = CURDATE() AND factura IS NOT NULL
        """, solo_uno=True)

        # 4. Pólizas registradas hoy
        res_polizas = db.ejecutar_consulta("""
            SELECT COUNT(*) AS total 
            FROM polizas 
            WHERE DATE(creado_en) = CURDATE()
        """, solo_uno=True)

        # 5. Clientes registrados hoy
        res_clientes = db.ejecutar_consulta("""
            SELECT COUNT(*) AS total 
            FROM clientes 
            WHERE DATE(creado_en) = CURDATE()
        """, solo_uno=True)

        db.desconectar()

        return {
            "ventas_soles": res_soles["total"] if res_soles else 0.0,
            "ventas_dolares": res_dolares["total"] if res_dolares else 0.0,
            "facturas": res_facturas["total"] if res_facturas else 0,
            "polizas": res_polizas["total"] if res_polizas else 0,
            "clientes": res_clientes["total"] if res_clientes else 0
        }