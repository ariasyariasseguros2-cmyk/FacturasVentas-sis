CREATE DATABASE IF NOT EXISTS ariasyariaspe_bd_sisnet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ariasyariaspe_bd_sisnet;

-- Tabla de usuarios (sin cambios del ejemplo del usuario)
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    id_rol INT NULL,
    nombre VARCHAR(100) NULL,
    foto_perfil VARCHAR(255) NULL,
    color_avatar VARCHAR(20) DEFAULT '#3b82f6',
    estado TINYINT(1) DEFAULT 1,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DELIMITER $$
DROP PROCEDURE IF EXISTS sp_login_usuario $$
CREATE PROCEDURE sp_login_usuario(IN p_username VARCHAR(50))
BEGIN
    SELECT 
        u.id,
        u.username,
        u.password,
        u.id_rol,
        u.nombre,
        u.foto_perfil,
        u.color_avatar,
        r.nombre AS rol_nombre
    FROM usuarios u
    LEFT JOIN roles r ON r.idRol = u.id_rol
    WHERE u.username = p_username
    LIMIT 1;
END $$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_listar_usuarios()
BEGIN
    SELECT COALESCE(NULLIF(TRIM(nombre), ''), username) AS nombre
    FROM usuarios
    WHERE estado = 1
    ORDER BY COALESCE(NULLIF(TRIM(nombre), ''), username) ASC;
END$$
DELIMITER ;

-- Tabla de Ajustadores
CREATE TABLE IF NOT EXISTS ajustadores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    abreviacion VARCHAR(150),
    codigo VARCHAR(20) NOT NULL UNIQUE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DELIMITER $$

CREATE PROCEDURE sp_listar_ajustadores()
BEGIN
    SELECT
        nombre,
        abreviacion,
        codigo
    FROM ajustadores
    ORDER BY nombre ASC;
END $$
DELIMITER ;



DROP PROCEDURE IF EXISTS sp_insertar_ajustador;
DELIMITER $$
CREATE PROCEDURE sp_insertar_ajustador(
    IN p_nombre VARCHAR(255),
    IN p_abreviacion VARCHAR(150),
    IN p_codigo VARCHAR(20),
    OUT p_new_id INT
)
BEGIN
    INSERT INTO ajustadores (nombre, abreviacion, codigo)
    VALUES (p_nombre, p_abreviacion, p_codigo)
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

    SET p_new_id = LAST_INSERT_ID();
END $$

DELIMITER ;

DELIMITER $$

CREATE PROCEDURE sp_eliminar_ajustador(
    IN p_id INT
)
BEGIN
DELETE FROM ajustadores
WHERE id = p_id;
END $$

DELIMITER ;

-- Table Ramos
CREATE TABLE ramos (
    idRamo INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    abreviacion VARCHAR(50),
    codigo VARCHAR(50),
    grupo VARCHAR(100),
    estado ENUM('Activo','Inactivo') DEFAULT 'Activo',
    UNIQUE KEY uq_ramos_nombre (nombre)
);

-- SP listar ramos -> nombre; abreviacion
DELIMITER $$

CREATE PROCEDURE sp_listar_ramos()
BEGIN
    SELECT
        nombre,
        abreviacion,
        codigo,
        grupo
    FROM ramos
    ORDER BY idRamo ASC;
END $$

DELIMITER ;

-- PROCEDIMIENTOS: RAMOS (insertar / eliminar)
DROP PROCEDURE IF EXISTS sp_insertar_ramo;
DELIMITER $$
CREATE PROCEDURE sp_insertar_ramo(
    IN p_nombre VARCHAR(150),
    IN p_abreviacion VARCHAR(50),
    IN p_codigo VARCHAR(50),
    IN p_grupo VARCHAR(100),
    OUT p_new_id INT
)
BEGIN
    IF TRIM(p_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre del ramo no puede estar vacío';
    END IF;

    INSERT INTO ramos (nombre, abreviacion, codigo, grupo)
    VALUES (TRIM(p_nombre), NULLIF(TRIM(p_abreviacion), ''), NULLIF(TRIM(p_codigo), ''), NULLIF(TRIM(p_grupo), ''))
    ON DUPLICATE KEY UPDATE idRamo = LAST_INSERT_ID(idRamo);

    SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_eliminar_ramo;
DELIMITER $$
CREATE PROCEDURE sp_eliminar_ramo(
    IN p_id INT
)
BEGIN
    DELETE FROM ramos WHERE idRamo = p_id;
END$$
DELIMITER ;

CREATE TABLE IF NOT EXISTS productos (
    id_producto BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    idRamo      INT NOT NULL,
    nombre      VARCHAR(150) NOT NULL,
    codigo      VARCHAR(50),
    grupo       VARCHAR(100),
    CONSTRAINT fk_productos_ramos
    FOREIGN KEY (idRamo) REFERENCES ramos(idRamo)
    ON UPDATE CASCADE
    ON DELETE RESTRICT
);

CREATE INDEX idx_productos_idRamo ON productos(idRamo);
CREATE UNIQUE INDEX uk_productos_ramo_nombre ON productos(idRamo, nombre);

-- PROCEDIMIENTOS: PRODUCTOS
DROP PROCEDURE IF EXISTS sp_listar_productos;
DELIMITER $$
CREATE PROCEDURE sp_listar_productos()
BEGIN
    SELECT id_producto AS id, idRamo AS ramo_id, nombre, codigo, grupo
    FROM productos
    ORDER BY nombre ASC;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_insertar_producto;
DELIMITER $$
CREATE PROCEDURE sp_insertar_producto(
    IN p_idRamo INT,
    IN p_nombre VARCHAR(150),
    IN p_codigo VARCHAR(50),
    IN p_grupo VARCHAR(100),
    OUT p_new_id BIGINT UNSIGNED
)
BEGIN
    IF p_idRamo IS NULL OR p_idRamo = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El idRamo es requerido';
    END IF;
    IF TRIM(p_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre del producto no puede estar vacío';
    END IF;

    INSERT INTO productos (idRamo, nombre, codigo, grupo)
    VALUES (p_idRamo, TRIM(p_nombre), NULLIF(TRIM(p_codigo), ''), NULLIF(TRIM(p_grupo), ''))
    ON DUPLICATE KEY UPDATE id_producto = LAST_INSERT_ID(id_producto);

    SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_eliminar_producto;
DELIMITER $$
CREATE PROCEDURE sp_eliminar_producto(
    IN p_id BIGINT UNSIGNED
)
BEGIN
    DELETE FROM productos WHERE id_producto = p_id;
END$$
DELIMITER ;


-- Table asegudoras = proveedor
CREATE TABLE companias (
    id_compania INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    nombre_corto VARCHAR(50),
    ruc VARCHAR(15),
    tel1 VARCHAR(20),
    central_emergencia VARCHAR(20),
    logo VARCHAR(255)
);


-- SP Listado de asegudora
DELIMITER $$

CREATE PROCEDURE sp_listar_companias()
BEGIN
    SELECT
        nombre_corto
    FROM companias
    ORDER BY nombre_corto ASC;
END $$

DELIMITER ;

CREATE TABLE comisiones_temp (
    id INT AUTO_INCREMENT PRIMARY KEY,

    ramo_nombre        VARCHAR(100),
    ramo_abreviacion   VARCHAR(50),
    ramo_codigo        VARCHAR(50),
    ramo_grupo         VARCHAR(100),
    ramo_estado        VARCHAR(20),

    producto           VARCHAR(150),
    producto_abrev     VARCHAR(50),
    producto_codigo    VARCHAR(50),
    producto_grupo     VARCHAR(100),

    pos_eps       DECIMAL(5,2),
    pos_vsr       DECIMAL(5,2),
    pos_sr        DECIMAL(5,2),
    pacifico      DECIMAL(5,2),
    sanitas       DECIMAL(5,2),
    protecta      DECIMAL(5,2),
    mapfre        DECIMAL(5,2),
    crecer        DECIMAL(5,2),
    ohio_natural  DECIMAL(5,2),
    grandia_eps   DECIMAL(5,2),
    qualitas      DECIMAL(5,2),

    factor        DECIMAL(10,4)
);

-- Table de SUB AGENTE
CREATE TABLE SubAgente (
    idProductor INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    abreviacion VARCHAR(100),
    email VARCHAR(120),
    telefono VARCHAR(20),
    celular VARCHAR(20),
    codigo_subagente VARCHAR(50)
);

-- SP lista SUB AGENTE
DELIMITER $$

CREATE PROCEDURE sp_listar_SubAgente_abreviacion()
BEGIN
    SELECT abreviacion
    FROM SubAgente
    ORDER BY abreviacion ASC;
END $$

DELIMITER ;

-- Tabla Endosatarios
CREATE TABLE IF NOT EXISTS endosatarios (
    idEndosatario INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    estado ENUM('Activo','Inactivo') DEFAULT 'Activo'
);

-- SP listar endosatarios
DELIMITER $$
CREATE PROCEDURE sp_listar_endosatarios()
BEGIN
    SELECT nombre
    FROM endosatarios
    WHERE estado = 'Activo'
    ORDER BY nombre ASC;
END$$
DELIMITER ;


-- Table de ejecutivos
CREATE TABLE ejecutivos (
    idEjecutivo INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    abreviacion VARCHAR(100),
    grupo VARCHAR(100)
);

-- SP Listado de ejecutivos por nombre

DELIMITER $$

CREATE PROCEDURE sp_listar_ejecutivos()
BEGIN
    SELECT
        nombre,
        abreviacion,
        grupo
    FROM ejecutivos
    ORDER BY nombre ASC;
END $$

DELIMITER ;

-- Tabla clientes (ajustada del ejemplo del usuario)
CREATE TABLE IF NOT EXISTS clientes (
    idCliente INT AUTO_INCREMENT PRIMARY KEY,
    razon_social VARCHAR(255) NOT NULL,
    tipo_documento ENUM('DNI', 'RUC', 'CE', 'PAS', 'CEX', 'DNI/CEDULA') NOT NULL,
    numero_documento VARCHAR(100) NOT NULL,

    -- Contacto y ubicación
    telefono VARCHAR(100),
    celular VARCHAR(20),
    telefono_sec VARCHAR(20),
    email VARCHAR(255),
    direccion VARCHAR(200),
    departamento VARCHAR(100),
    provincia VARCHAR(100),
    distrito VARCHAR(100),

    -- Relación con subagente
    subagente VARCHAR(250),
    idProductor INT NULL,

    -- Estado y tipo
    estado VARCHAR(20) DEFAULT 'Vigente',
    tipo_persona TINYINT NULL,

    -- Fechas de sistema
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,

    -- Perfil y clasificación
    profesion VARCHAR(150) NULL,
    fecha_ingreso DATE NULL,
    fecha_nacimiento DATE NULL,
    licencia_num VARCHAR(50) NULL,
    licencia_venc DATE NULL,
    grupo_economico VARCHAR(100) NULL,
    giro_negocio VARCHAR(100) NULL,
    referencia VARCHAR(200) NULL,
    recomendado_por VARCHAR(150) NULL,

    -- Contacto de emergencia
    recibir_notificaciones TINYINT(1) DEFAULT 0,
    contacto_nombre VARCHAR(150) NULL,
    contacto_email VARCHAR(150) NULL,
    contacto_telefono VARCHAR(20) NULL,

    -- Auditoría: registro de usuarios
    usuario_creacion VARCHAR(50) NULL COMMENT 'Usuario que registró el cliente',
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Fecha de creación del registro',
    usuario_modificacion VARCHAR(50) NULL COMMENT 'Último usuario que modificó el cliente',
    fecha_modificacion DATETIME NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'Última fecha de modificación',

    -- Borrado lógico
    activo BOOLEAN NOT NULL DEFAULT TRUE COMMENT '1=activo, 0=eliminado lógicamente',

    --
    -- Foreign Key a tabla subagente
    CONSTRAINT fk_clientes_subagente FOREIGN KEY (idProductor)
        REFERENCES SubAgente(idProductor) ON DELETE SET NULL


);

    -- ACTUALIZA EL ROW ACTIVE A 1 PARA REGISTROS EXISTENTES (NO FUNCIONAL TEMPORALMENTE)
    UPDATE clientes SET activo = 1 WHERE activo IS NULL AND idCliente IS NOT NULL;

DELIMITER $$
CREATE PROCEDURE sp_insert_cliente (
    IN p_razon_social VARCHAR(255),
    IN p_tipo_documento VARCHAR(20),
    IN p_numero_documento VARCHAR(100),
    IN p_telefono VARCHAR(100),
    IN p_celular VARCHAR(20),
    IN p_telefono_sec VARCHAR(20),
    IN p_subagente VARCHAR(250),
    IN p_idProductor INT,
    IN p_email VARCHAR(255),
    IN p_direccion VARCHAR(200),
    IN p_departamento VARCHAR(100),
    IN p_provincia VARCHAR(100),
    IN p_distrito VARCHAR(100),
    IN p_estado VARCHAR(20),
    IN p_tipo_persona TINYINT,
    IN p_profesion VARCHAR(150),
    IN p_fecha_ingreso DATE,
    IN p_fecha_nacimiento DATE,
    IN p_licencia_num VARCHAR(50),
    IN p_licencia_venc DATE,
    IN p_grupo_economico VARCHAR(100),
    IN p_giro_negocio VARCHAR(100),
    IN p_referencia VARCHAR(200),
    IN p_recomendado_por VARCHAR(150),
    IN p_recibir_notificaciones TINYINT,
    IN p_contacto_nombre VARCHAR(150),
    IN p_contacto_email VARCHAR(150),
    IN p_contacto_telefono VARCHAR(20),
    IN p_usuario_creacion VARCHAR(50)
)
BEGIN
    DECLARE v_cliente_id INT;
    DECLARE v_exists INT DEFAULT 0;

    IF p_numero_documento IS NOT NULL AND TRIM(p_numero_documento) <> '' THEN
        SELECT COUNT(*)
        INTO v_exists
        FROM clientes c
        WHERE COALESCE(c.activo, 1) = 1
          AND (
                CONVERT(
                    COALESCE(
                        CAST(AES_DECRYPT(FROM_BASE64(c.numero_documento), @SIS_KEY) AS CHAR(100) CHARACTER SET utf8mb4),
                        CAST(AES_DECRYPT(c.numero_documento, @SIS_KEY) AS CHAR(100) CHARACTER SET utf8mb4),
                        CONVERT(c.numero_documento USING utf8mb4)
                    )
                    USING utf8mb4
                ) COLLATE utf8mb4_unicode_ci
              ) = CONVERT(p_numero_documento USING utf8mb4) COLLATE utf8mb4_unicode_ci;

        IF v_exists > 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El numero_documento ya existe';
        END IF;
    END IF;

    INSERT INTO clientes (
        razon_social, tipo_documento, numero_documento,
        telefono, celular, telefono_sec,
        subagente, idProductor,
        email, direccion, departamento, provincia, distrito,
        estado, tipo_persona,
        profesion, fecha_ingreso, fecha_nacimiento,
        licencia_num, licencia_venc,
        grupo_economico, giro_negocio, referencia, recomendado_por,
        recibir_notificaciones, contacto_nombre, contacto_email, contacto_telefono,
        usuario_creacion
    ) VALUES (
        TO_BASE64(AES_ENCRYPT(p_razon_social, @SIS_KEY)), p_tipo_documento, TO_BASE64(AES_ENCRYPT(p_numero_documento, @SIS_KEY)),
        TO_BASE64(AES_ENCRYPT(p_telefono, @SIS_KEY)), p_celular, p_telefono_sec,
        p_subagente, p_idProductor,
        TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY)), p_direccion, p_departamento, p_provincia, p_distrito,
        p_estado, p_tipo_persona,
        p_profesion, p_fecha_ingreso, p_fecha_nacimiento,
        p_licencia_num, p_licencia_venc,
        p_grupo_economico, p_giro_negocio, p_referencia, p_recomendado_por,
        p_recibir_notificaciones, p_contacto_nombre, p_contacto_email, p_contacto_telefono,
        p_usuario_creacion
    );

    SET v_cliente_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_list_clientes ()
BEGIN
    SELECT
        idCliente,
        fecha_registro,
        razon_social,
        tipo_documento,
        numero_documento,
        telefono,
        subagente,
        email,
        direccion,
        estado,
        tipo_persona
    FROM clientes
    WHERE activo = 1
    ORDER BY fecha_registro DESC;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_buscar_cliente (IN p_texto VARCHAR(150))
BEGIN
    SELECT
        idCliente,
        fecha_registro,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(razon_social, @SIS_KEY) AS CHAR),
            razon_social
        ) AS razon_social,
        tipo_documento,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(numero_documento), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(numero_documento, @SIS_KEY) AS CHAR),
            numero_documento
        ) AS numero_documento,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(telefono), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(telefono, @SIS_KEY) AS CHAR),
            telefono
        ) AS telefono,
        subagente,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(email), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(email, @SIS_KEY) AS CHAR),
            email
        ) AS email,
        direccion
    FROM clientes
    WHERE activo = 1
      AND (
            CAST(AES_DECRYPT(FROM_BASE64(razon_social), @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR CAST(AES_DECRYPT(razon_social, @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR razon_social LIKE CONCAT('%', p_texto, '%')
         OR CAST(AES_DECRYPT(FROM_BASE64(numero_documento), @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR CAST(AES_DECRYPT(numero_documento, @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR numero_documento LIKE CONCAT('%', p_texto, '%')
         OR CAST(AES_DECRYPT(FROM_BASE64(email), @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR CAST(AES_DECRYPT(email, @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR email LIKE CONCAT('%', p_texto, '%')
         OR CAST(AES_DECRYPT(FROM_BASE64(telefono), @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR CAST(AES_DECRYPT(telefono, @SIS_KEY) AS CHAR) LIKE CONCAT('%', p_texto, '%')
         OR telefono LIKE CONCAT('%', p_texto, '%')
      )
    ORDER BY fecha_registro DESC;
END$$
DELIMITER ;

-- Tabla financiamiento grupal
CREATE TABLE IF NOT EXISTS financiamiento_grupal (
    id_financiamiento_grupal INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    cliente_id INT NOT NULL,
    compania_id INT NOT NULL,
    moneda VARCHAR(10) NOT NULL,
    numero_cupones INT NOT NULL,
    primer_cupon VARCHAR(50) NULL,
    importe DECIMAL(15,2) NOT NULL,
    fecha_primer_vencimiento DATE NOT NULL,
    documento_ruta_archivo VARCHAR(255) NULL,
    documento_nombre_original VARCHAR(255) NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    usuario_creacion VARCHAR(100) NULL,
    usuario_modificacion VARCHAR(100) NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_financiamiento_grupal_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(idCliente),
    CONSTRAINT fk_financiamiento_grupal_compania
        FOREIGN KEY (compania_id) REFERENCES companias(id_compania)
);

CREATE INDEX idx_financiamiento_grupal_cliente ON financiamiento_grupal (cliente_id);
CREATE INDEX idx_financiamiento_grupal_compania ON financiamiento_grupal (compania_id);
CREATE INDEX idx_financiamiento_grupal_activo ON financiamiento_grupal (activo);

CREATE TABLE IF NOT EXISTS financiamiento_grupal_avisos (
    id_item INT AUTO_INCREMENT PRIMARY KEY,
    financiamiento_grupal_id INT NOT NULL,
    poliza_id INT NOT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (financiamiento_grupal_id) REFERENCES financiamiento_grupal(id_financiamiento_grupal)
);

CREATE UNIQUE INDEX uk_fg_avisos_fin_poliza ON financiamiento_grupal_avisos (financiamiento_grupal_id, poliza_id);
CREATE INDEX idx_fg_avisos_fin ON financiamiento_grupal_avisos (financiamiento_grupal_id);
CREATE INDEX idx_fg_avisos_poliza ON financiamiento_grupal_avisos (poliza_id);

DROP PROCEDURE IF EXISTS sp_insert_financiamiento_grupal;
DELIMITER $$
CREATE PROCEDURE sp_insert_financiamiento_grupal(
    IN p_nombre VARCHAR(255),
    IN p_cliente_id INT,
    IN p_compania_id INT,
    IN p_moneda VARCHAR(10),
    IN p_numero_cupones INT,
    IN p_primer_cupon VARCHAR(50),
    IN p_importe DECIMAL(15,2),
    IN p_fecha_primer_vencimiento DATE,
    OUT p_new_id INT
)
BEGIN
    IF p_nombre IS NULL OR TRIM(p_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre del financiamiento grupal es obligatorio';
    END IF;

    IF p_cliente_id IS NULL OR p_cliente_id <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El cliente es obligatorio';
    END IF;

    IF p_compania_id IS NULL OR p_compania_id <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La compania es obligatoria';
    END IF;

    IF p_moneda IS NULL OR TRIM(p_moneda) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La moneda es obligatoria';
    END IF;

    IF p_numero_cupones IS NULL OR p_numero_cupones <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El numero de cupones debe ser mayor a cero';
    END IF;

    IF p_primer_cupon IS NULL OR TRIM(p_primer_cupon) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El primer cupon es obligatorio';
    END IF;

    IF p_importe IS NULL OR p_importe <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El importe debe ser mayor a cero';
    END IF;

    IF p_fecha_primer_vencimiento IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La fecha del primer vencimiento es obligatoria';
    END IF;

    INSERT INTO financiamiento_grupal (
        nombre,
        cliente_id,
        compania_id,
        moneda,
        numero_cupones,
        primer_cupon,
        importe,
        fecha_primer_vencimiento
    ) VALUES (
        TRIM(p_nombre),
        p_cliente_id,
        p_compania_id,
        UPPER(TRIM(p_moneda)),
        p_numero_cupones,
        NULLIF(TRIM(p_primer_cupon), ''),
        p_importe,
        p_fecha_primer_vencimiento
    );

    SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

-- Tabla polizas: quitar 'producto' y 'motivo', mantener 'cia' y 'ramos_producto'
CREATE TABLE IF NOT EXISTS polizas (
    idPoliza INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,

    asegurado VARCHAR(150) NULL,
    cia VARCHAR(100) NULL,
    ramo VARCHAR(120) NULL,
    -- producto VARCHAR(120) NULL,        -- ELIMINADO
    poliza VARCHAR(50) NULL,
    recibo VARCHAR(50) NULL,
    contrato_nro VARCHAR(50) NULL,
    nro VARCHAR(50) NULL,

    moneda VARCHAR(20) NULL,
    fecha_emision DATE NULL,
    vig_desde DATE NULL,
    vig_hasta DATE NULL,
    ultimo_dia_pago DATE NULL,
    fecha_vencimiento DATE NULL,      -- NUEVO
    tipo_vigencia VARCHAR(50) NULL,   -- NUEVO
    endosatario VARCHAR(150) NULL,    -- NUEVO
    forma_pago VARCHAR(30) NULL,

    sub_agente VARCHAR(250) NULL,
    ejecutivo VARCHAR(250) NULL,
    tipo_doc VARCHAR(10) NULL,
    asegurada VARCHAR(150) NULL,
    motivo VARCHAR(200) NULL,
    prima_comercial DECIMAL(15,2) NULL,
    prima_neta DECIMAL(15,2) NULL,
    prima_comercial_igv DECIMAL(15,2) NULL,
    prima_total DECIMAL(15,2) NULL,

    porc_compania DECIMAL(5,2) NULL,
    imp_compania DECIMAL(15,2) NULL,
    porc_subagente DECIMAL(5,2) NULL,
    imp_subagente DECIMAL(15,2) NULL,

    datos_vehiculo JSON NULL,         -- NUEVO: Para almacenar datos del vehículo en SOAT
    datos_adicionales JSON NULL,      -- NUEVO: Campos adicionales (flete, fob, sobreseguro, nro_factura, ip_ipl_ipf, origen, destino, etd, eta, proveedor, ruta, puerto_embarque, embalaje, certificado, descripcion, cupon, factura, fecha_pago, importe, cuotas)
    codigo_agente VARCHAR(50) NULL,   -- NUEVO: Código de agente/vendedor

    ramos_producto VARCHAR(120) NULL,

    estado VARCHAR(20) DEFAULT 'PENDIENTE',
    anulado TINYINT(1) NOT NULL DEFAULT 0,
    prima_anulada TINYINT(1) NOT NULL DEFAULT 0,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    recibo_uk VARCHAR(50) GENERATED ALWAYS AS (
        CASE
            WHEN activo = 1 AND anulado = 0 THEN NULLIF(TRIM(recibo), '')
            ELSE NULL
        END
    ) STORED,
    usuario_registro VARCHAR(100) NULL,
    usuario_edicion VARCHAR(100) NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (cliente_id) REFERENCES clientes(idCliente)
);

CREATE UNIQUE INDEX uk_polizas_cliente_recibo ON polizas (cliente_id, recibo_uk);
CREATE INDEX idx_polizas_reporte_vencimientos
    ON polizas (activo, anulado, prima_anulada, vig_hasta, estado, ramo);
CREATE INDEX idx_polizas_usuario_registro ON polizas (usuario_registro);
CREATE INDEX idx_polizas_ejecutivo ON polizas (ejecutivo);

ALTER TABLE financiamiento_grupal_avisos
ADD CONSTRAINT fk_financiamiento_grupal_avisos_poliza
FOREIGN KEY (poliza_id) REFERENCES polizas(idPoliza);

-- Tabla para archivos de pólizas (separada)
CREATE TABLE IF NOT EXISTS poliza_archivos (
    idArchivo INT AUTO_INCREMENT PRIMARY KEY,
    poliza_id INT NOT NULL,
    numero_poliza VARCHAR(50),
    ruta_archivo VARCHAR(255) NOT NULL,
    nombre_original VARCHAR(255),
    origen VARCHAR(50) DEFAULT 'CARGA_MASIVA',
    ramo VARCHAR(120),
    producto VARCHAR(120),
    usuario VARCHAR(100),
    compania VARCHAR(100),
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (poliza_id) REFERENCES polizas(idPoliza) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS poliza_anulaciones (
    idAnulacion INT AUTO_INCREMENT PRIMARY KEY,
    poliza_id INT NOT NULL,
    poliza_numero VARCHAR(50) NULL,
    usuario VARCHAR(100) NULL,
    motivo VARCHAR(200) NOT NULL,
    fecha_anulacion DATE NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (poliza_id) REFERENCES polizas(idPoliza)
);

CREATE INDEX idx_poliza_anulaciones_poliza ON poliza_anulaciones (poliza_id);


DELIMITER $$
CREATE PROCEDURE sp_get_cliente_por_numero(IN p_numero_documento VARCHAR(20))
BEGIN
    SELECT
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(razon_social, @SIS_KEY) AS CHAR),
            razon_social
        ) AS razon_social,
        tipo_documento,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(numero_documento), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(numero_documento, @SIS_KEY) AS CHAR),
            numero_documento
        ) AS numero_documento,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(telefono), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(telefono, @SIS_KEY) AS CHAR),
            telefono
        ) AS telefono
    FROM clientes
    WHERE (
            CAST(AES_DECRYPT(FROM_BASE64(numero_documento), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR CAST(AES_DECRYPT(numero_documento, @SIS_KEY) AS CHAR)            COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR numero_documento                                                 COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
    )
      AND activo = 1
    LIMIT 1;
END$$
DELIMITER ;

-- Insertar póliza enlazando por numero_documento del cliente (actualizado con todos los campos)
DELIMITER $$

DROP PROCEDURE IF EXISTS sp_insert_poliza_por_numero;

CREATE PROCEDURE sp_insert_poliza_por_numero (
    IN p_numero_documento VARCHAR(20),
    IN p_tipo_doc VARCHAR(10),
    IN p_asegurado VARCHAR(150),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    -- IN p_producto VARCHAR(120),        -- ELIMINADO

    IN p_poliza VARCHAR(50),
    IN p_recibo VARCHAR(50),
    IN p_contrato_nro VARCHAR(50),
    IN p_nro VARCHAR(50),

    IN p_moneda VARCHAR(20),
    IN p_fecha_emision DATE,
    IN p_vig_desde DATE,
    IN p_vig_hasta DATE,
    IN p_ultimo_dia_pago DATE,
    IN p_fecha_vencimiento DATE,  -- NUEVO
    IN p_tipo_vigencia VARCHAR(50),   -- NUEVO
    IN p_endosatario VARCHAR(150),    -- NUEVO
    IN p_forma_pago VARCHAR(30),

    IN p_sub_agente VARCHAR(150),
    IN p_ejecutivo VARCHAR(250),

    IN p_asegurada VARCHAR(150),
    IN p_motivo VARCHAR(200),
    IN p_prima_comercial DECIMAL(15,2),
    IN p_prima_neta DECIMAL(15,2),
    IN p_prima_comercial_igv DECIMAL(15,2),
    IN p_prima_total DECIMAL(15,2),

    IN p_porc_compania DECIMAL(5,2),
    IN p_imp_compania DECIMAL(15,2),
    IN p_porc_subagente DECIMAL(5,2),
    IN p_imp_subagente DECIMAL(15,2),

    -- IN p_motivo VARCHAR(200),          -- ELIMINADO
    IN p_ramos_producto VARCHAR(120),
    IN p_estado VARCHAR(20),
    IN p_pdf_path VARCHAR(255),
    IN p_usuario_registro VARCHAR(100),
    IN p_datos_adicionales JSON            -- NUEVO: datos extra en JSON
)
BEGIN
    DECLARE v_cliente_id INT;
    DECLARE v_exists INT DEFAULT 0;
    DECLARE v_msg VARCHAR(255);
    DECLARE v_key VARCHAR(50); -- clave para duplicados: contrato_nro o recibo
    DECLARE v_recibo_key VARCHAR(50); -- recibo normalizado
    DECLARE v_poliza_id INT;
    DECLARE v_usuario_registro_nombre VARCHAR(100);

    SELECT idCliente INTO v_cliente_id
    FROM clientes
    WHERE (
            CAST(AES_DECRYPT(FROM_BASE64(numero_documento), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR CAST(AES_DECRYPT(numero_documento, @SIS_KEY) AS CHAR)            COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR numero_documento COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
    )
      AND activo = 1
    LIMIT 1;

    IF v_cliente_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cliente no existe';
    END IF;

    -- Validar duplicado por recibo (por cliente)
    SET v_recibo_key = NULLIF(TRIM(IFNULL(p_recibo, '')), '');
    IF v_recibo_key IS NOT NULL THEN
        SELECT COUNT(*) INTO v_exists
        FROM polizas
        WHERE cliente_id = v_cliente_id
          AND TRIM(COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(recibo), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(recibo, @SIS_KEY) AS CHAR),
                recibo
              )) COLLATE utf8mb4_0900_ai_ci = v_recibo_key COLLATE utf8mb4_0900_ai_ci
          AND activo = 1
          AND (anulado = 0 OR anulado IS NULL);

        IF v_exists > 0 THEN
            SET v_msg = CONCAT('El recibo ya existe para este cliente: ', v_recibo_key);
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
        END IF;
    END IF;

    -- Normalizar clave de duplicado: primero contrato_nro, si no, recibo
    SET v_key = NULLIF(TRIM(IFNULL(p_contrato_nro, '')), '');
    IF v_key IS NULL THEN
        SET v_key = NULLIF(TRIM(IFNULL(p_recibo, '')), '');
    END IF;

    -- Validación de duplicados: poliza + (contrato_nro|recibo), acotado por cliente
    IF COALESCE(p_poliza, '') <> '' AND COALESCE(v_key, '') <> '' THEN
        SELECT COUNT(*) INTO v_exists
        FROM polizas
        WHERE cliente_id = v_cliente_id
          AND TRIM(COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(poliza, @SIS_KEY) AS CHAR),
                poliza
              )) COLLATE utf8mb4_0900_ai_ci = TRIM(p_poliza) COLLATE utf8mb4_0900_ai_ci
          AND (
               TRIM(COALESCE(
                   CAST(AES_DECRYPT(FROM_BASE64(contrato_nro), @SIS_KEY) AS CHAR),
                   CAST(AES_DECRYPT(contrato_nro, @SIS_KEY) AS CHAR),
                   contrato_nro
               )) COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
            OR TRIM(COALESCE(
                   CAST(AES_DECRYPT(FROM_BASE64(recibo), @SIS_KEY) AS CHAR),
                   CAST(AES_DECRYPT(recibo, @SIS_KEY) AS CHAR),
                   recibo
               )) COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
          )
          AND activo = 1
          AND (anulado = 0 OR anulado IS NULL);

        IF v_exists > 0 THEN
            SET v_msg = CONCAT('Póliza ya existe con mismo número y contrato/recibo: ', p_poliza, ' / ', v_key);
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
        END IF;
    END IF;

    SET v_usuario_registro_nombre = NULL;
    IF p_usuario_registro IS NOT NULL AND TRIM(p_usuario_registro) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_registro_nombre
        FROM usuarios
        WHERE username COLLATE utf8mb4_0900_ai_ci = p_usuario_registro COLLATE utf8mb4_0900_ai_ci
        LIMIT 1;
    END IF;
    IF v_usuario_registro_nombre IS NULL OR v_usuario_registro_nombre = '' THEN
        SET v_usuario_registro_nombre = p_usuario_registro;
    END IF;

    INSERT INTO polizas (
        cliente_id, asegurado, cia, ramo,
        poliza, recibo, contrato_nro, nro,
        moneda, fecha_emision, vig_desde, vig_hasta, ultimo_dia_pago, fecha_vencimiento, tipo_vigencia, endosatario, forma_pago,
        sub_agente, ejecutivo, tipo_doc,
        asegurada, motivo, prima_comercial, prima_neta, prima_comercial_igv, prima_total,
        porc_compania, imp_compania, porc_subagente, imp_subagente,
        datos_adicionales,
        ramos_producto, estado, usuario_registro, creado_en
    ) VALUES (
        v_cliente_id, p_asegurado, p_cia, p_ramo,
        p_poliza, p_recibo, p_contrato_nro, p_nro,
        p_moneda, p_fecha_emision, p_vig_desde, p_vig_hasta, p_ultimo_dia_pago, p_fecha_vencimiento, p_tipo_vigencia, p_endosatario, p_forma_pago,
        p_sub_agente, p_ejecutivo, p_tipo_doc,
        p_asegurada, p_motivo, p_prima_comercial, p_prima_neta, p_prima_comercial_igv, p_prima_total,
        p_porc_compania, p_imp_compania, p_porc_subagente, p_imp_subagente,
        p_datos_adicionales,
        p_ramos_producto, p_estado, v_usuario_registro_nombre, CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', '-05:00')
    );

    SET v_poliza_id = LAST_INSERT_ID();

    IF p_pdf_path IS NOT NULL AND p_pdf_path <> '' THEN
        INSERT INTO poliza_archivos (poliza_id, numero_poliza, ruta_archivo, nombre_original, ramo, producto, usuario, compania)
        VALUES (v_poliza_id, p_poliza, p_pdf_path, SUBSTRING_INDEX(p_pdf_path, '/', -1), p_ramo, p_ramos_producto, v_usuario_registro_nombre, p_cia);
    END IF;


END$$
DELIMITER ;
-- NUEVO: listado global de pólizas (opcional, si prefieres usar SP)
DELIMITER $$
CREATE PROCEDURE sp_list_polizas_all()
BEGIN
    SELECT
        p.idPoliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
            c.razon_social
        ) AS contratante,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.asegurado), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.asegurado, @SIS_KEY) AS CHAR),
            p.asegurado
        ) AS asegurado,
        p.cia,
        p.ramo,
        p.ramos_producto AS producto,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
            p.poliza
        ) AS poliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.nro), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.nro, @SIS_KEY) AS CHAR),
            p.nro
        ) AS nro,
        p.moneda,
        DATE_FORMAT(p.fecha_emision, '%d/%m/%Y') AS fecha_emision,
        DATE_FORMAT(p.vig_desde, '%d/%m/%Y') AS vig_desde,
        DATE_FORMAT(p.vig_hasta, '%d/%m/%Y') AS vig_hasta,
        p.sub_agente,
        p.asegurada,
        COALESCE(NULLIF(TRIM(ur.nombre), ''), p.usuario_registro) AS usuario_registro,
        COALESCE(NULLIF(TRIM(ue.nombre), ''), p.usuario_edicion) AS usuario_edicion,
    (SELECT ruta_archivo FROM poliza_archivos WHERE poliza_id = p.idPoliza ORDER BY idArchivo DESC LIMIT 1) AS pdf_path
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    LEFT JOIN usuarios ur ON ur.username = p.usuario_registro OR ur.nombre = p.usuario_registro
    LEFT JOIN usuarios ue ON ue.username = p.usuario_edicion OR ue.nombre = p.usuario_edicion
    WHERE p.activo = 1 AND p.anulado = 0
    ORDER BY p.idPoliza DESC;
END$$
DELIMITER ;

-- Listado de pólizas por cliente (mantiene columnas usadas en la vista)
DELIMITER $$
CREATE PROCEDURE sp_list_polizas_por_numero(IN p_numero_documento VARCHAR(20))
BEGIN
    SELECT
        p.idPoliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
            c.razon_social
        ) AS contratante,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.asegurado), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.asegurado, @SIS_KEY) AS CHAR),
            p.asegurado
        ) AS asegurado,
        p.cia,
        p.ramo,
        p.ramos_producto AS producto,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
            p.poliza
        ) AS poliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.nro), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.nro, @SIS_KEY) AS CHAR),
            p.nro
        ) AS nro,
        p.moneda,
        DATE_FORMAT(p.fecha_emision, '%d/%m/%Y') AS fecha_emision,
        DATE_FORMAT(p.vig_desde, '%d/%m/%Y') AS vig_desde,
        DATE_FORMAT(p.vig_hasta, '%d/%m/%Y') AS vig_hasta,
        p.sub_agente,
        p.asegurada,
        COALESCE(NULLIF(TRIM(ur.nombre), ''), p.usuario_registro) AS usuario_registro,
        COALESCE(NULLIF(TRIM(ue.nombre), ''), p.usuario_edicion) AS usuario_edicion,
        (SELECT ruta_archivo FROM poliza_archivos WHERE poliza_id = p.idPoliza ORDER BY idArchivo DESC LIMIT 1) AS pdf_path
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    LEFT JOIN usuarios ur ON ur.username = p.usuario_registro OR ur.nombre = p.usuario_registro
    LEFT JOIN usuarios ue ON ue.username = p.usuario_edicion OR ue.nombre = p.usuario_edicion
    WHERE (
            CAST(AES_DECRYPT(FROM_BASE64(c.numero_documento), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR CAST(AES_DECRYPT(c.numero_documento, @SIS_KEY) AS CHAR)           COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR c.numero_documento                                                COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
    )
      AND p.activo = 1 AND p.anulado = 0
    ORDER BY p.creado_en DESC;
END$$
DELIMITER ;

-- Nuevo: obtener cliente por ID

DELIMITER $$
CREATE PROCEDURE sp_get_cliente_por_id(IN p_id INT)
BEGIN
SELECT
    idCliente,
    COALESCE(
        CAST(AES_DECRYPT(FROM_BASE64(razon_social), @SIS_KEY) AS CHAR),
        CAST(AES_DECRYPT(razon_social, @SIS_KEY) AS CHAR),
        razon_social
    ) AS razon_social,
    tipo_documento,
    COALESCE(
        CAST(AES_DECRYPT(FROM_BASE64(numero_documento), @SIS_KEY) AS CHAR),
        CAST(AES_DECRYPT(numero_documento, @SIS_KEY) AS CHAR),
        numero_documento
    ) AS numero_documento,
    COALESCE(
        CAST(AES_DECRYPT(FROM_BASE64(telefono), @SIS_KEY) AS CHAR),
        CAST(AES_DECRYPT(telefono, @SIS_KEY) AS CHAR),
        telefono
    ) AS telefono,
    celular,
    telefono_sec,
    COALESCE(
        CAST(AES_DECRYPT(FROM_BASE64(email), @SIS_KEY) AS CHAR),
        CAST(AES_DECRYPT(email, @SIS_KEY) AS CHAR),
        email
    ) AS email,
    direccion,
    departamento,
    provincia,
    distrito,
    subagente,
    idProductor,
    estado,
    tipo_persona,
    fecha_registro,
    fecha_actualizacion,
    profesion,
    fecha_ingreso,
    fecha_nacimiento,
    licencia_num,
    licencia_venc,
    grupo_economico,
    giro_negocio,
    referencia,
    recomendado_por,
    recibir_notificaciones,
    contacto_nombre,
    contacto_email,
    contacto_telefono,
    usuario_creacion,
    fecha_creacion,
    usuario_modificacion,
    fecha_modificacion,
    activo
FROM clientes
WHERE idCliente = p_id
  AND activo = 1
    LIMIT 1;
END$$
DELIMITER ;

-- Nuevo: listar pólizas por cliente_id
DELIMITER $$
CREATE PROCEDURE sp_list_polizas_por_cliente_id(IN p_cliente_id INT)
BEGIN
    SELECT
        p.idPoliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
            c.razon_social
        ) AS contratante,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.asegurado), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.asegurado, @SIS_KEY) AS CHAR),
            p.asegurado
        ) AS asegurado,
        p.cia,
        p.ramo,
        p.ramos_producto AS producto,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
            p.poliza
        ) AS poliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.nro), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.nro, @SIS_KEY) AS CHAR),
            p.nro
        ) AS nro,
        p.moneda,
        DATE_FORMAT(p.fecha_emision, '%d/%m/%Y') AS fecha_emision,
        DATE_FORMAT(p.vig_desde, '%d/%m/%Y') AS vig_desde,
        DATE_FORMAT(p.vig_hasta, '%d/%m/%Y') AS vig_hasta,
        p.sub_agente,
        p.asegurada,
        COALESCE(NULLIF(TRIM(ur.nombre), ''), p.usuario_registro) AS usuario_registro,
        COALESCE(NULLIF(TRIM(ue.nombre), ''), p.usuario_edicion) AS usuario_edicion,
    (SELECT ruta_archivo FROM poliza_archivos WHERE poliza_id = p.idPoliza ORDER BY idArchivo DESC LIMIT 1) AS pdf_path
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    LEFT JOIN usuarios ur ON ur.username = p.usuario_registro OR ur.nombre = p.usuario_registro
    LEFT JOIN usuarios ue ON ue.username = p.usuario_edicion OR ue.nombre = p.usuario_edicion
    WHERE p.cliente_id = p_cliente_id AND p.activo = 1 AND p.anulado = 0
    ORDER BY p.creado_en DESC;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_list_primas_por_poliza$$
DELIMITER ;
DELIMITER $$
CREATE PROCEDURE sp_list_primas_por_poliza(IN p_poliza VARCHAR(50))
BEGIN
    SELECT
        p.idPoliza,
        p.prima_anulada,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
            p.recibo
        ) AS recibo,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
            p.recibo
        ) AS cupon,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
            p.poliza
        ) AS poliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
            c.razon_social
        ) AS contratante,
        p.cia AS compania,
        p.ramo,
        p.tipo_doc AS tipo,
        p.prima_comercial,
        p.prima_neta,
        p.prima_comercial_igv,
        p.prima_comercial_igv AS importe,
        p.moneda,
        DATE_FORMAT(p.fecha_vencimiento, '%d/%m/%Y') AS fecha_vencimiento,
        DATE_FORMAT(p.vig_desde, '%d/%m/%Y') AS vig_inicio,
        DATE_FORMAT(p.vig_hasta, '%d/%m/%Y') AS vig_fin,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.nro), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.nro, @SIS_KEY) AS CHAR),
            p.nro
        ) AS nro_operacion,
        p.motivo AS motivo
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    WHERE (
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
         OR CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR)            COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
         OR p.poliza COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
    )
      AND p.activo = 1 AND p.anulado = 0
    ORDER BY p.creado_en DESC;
END$$
DELIMITER ;

DELIMITER $$
DROP PROCEDURE IF EXISTS sp_list_primas_por_cliente_id$$
DELIMITER ;
DELIMITER $$
-- sp_list_primas_por_cliente_id
CREATE PROCEDURE sp_list_primas_por_cliente_id(IN p_cliente_id INT)
BEGIN
    SELECT
        p.idPoliza,
        p.prima_anulada,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
            p.recibo
        ) AS recibo,
        p.ejecutivo AS Ejecutivo,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
            p.poliza
        ) AS poliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
            c.razon_social
        ) AS contratante,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.asegurado), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.asegurado, @SIS_KEY) AS CHAR),
            p.asegurado
        ) AS Asegurado,
        p.cia AS compania,
        p.ramo,
        p.tipo_doc AS tipo,
        p.prima_comercial,
        p.prima_neta,
        p.prima_comercial_igv,
        DATE_FORMAT(p.vig_desde, '%d/%m/%Y') AS vig_inicio,
        DATE_FORMAT(p.vig_hasta, '%d/%m/%Y') AS vig_fin,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.nro), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.nro, @SIS_KEY) AS CHAR),
            p.nro
        ) AS nro_operacion,
        p.motivo AS motivo
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    WHERE p.cliente_id = p_cliente_id AND p.activo = 1 AND p.anulado = 0
    ORDER BY p.creado_en DESC;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_get_poliza_detalle_por_numero(IN p_poliza VARCHAR(50))
BEGIN
    SELECT
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.asegurado), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.asegurado, @SIS_KEY) AS CHAR),
            p.asegurado
        ) AS asegurado,
        p.ejecutivo AS Ejecutivo,
        DATE_FORMAT(p.vig_desde, '%d/%m/%Y') AS vig_desde,
        DATE_FORMAT(p.vig_hasta, '%d/%m/%Y') AS vig_hasta
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    WHERE (
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
         OR CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR)            COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
         OR p.poliza COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
    )
    LIMIT 1;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_list_polizas_anuladas()
BEGIN
    SELECT
        p.idPoliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
            c.razon_social
        ) AS contratante,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.asegurado), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.asegurado, @SIS_KEY) AS CHAR),
            p.asegurado
        ) AS asegurado,
        p.cia,
        p.ramo,
        p.ramos_producto AS producto,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
            p.poliza
        ) AS poliza,
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(p.nro), @SIS_KEY) AS CHAR),
            CAST(AES_DECRYPT(p.nro, @SIS_KEY) AS CHAR),
            p.nro
        ) AS nro,
        p.moneda,
        DATE_FORMAT(p.fecha_emision, '%d/%m/%Y') AS fecha_emision,
        DATE_FORMAT(p.vig_desde, '%d/%m/%Y') AS vig_desde,
        DATE_FORMAT(p.vig_hasta, '%d/%m/%Y') AS vig_hasta,
        p.sub_agente,
        p.asegurada,
        COALESCE(NULLIF(TRIM(ur.nombre), ''), p.usuario_registro) AS usuario_registro,
        COALESCE(NULLIF(TRIM(ue.nombre), ''), p.usuario_edicion) AS usuario_edicion
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    LEFT JOIN usuarios ur ON ur.username = p.usuario_registro OR ur.nombre = p.usuario_registro
    LEFT JOIN usuarios ue ON ue.username = p.usuario_edicion OR ue.nombre = p.usuario_edicion
    WHERE p.activo = 1 AND p.anulado = 1
    ORDER BY p.creado_en DESC;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_restore_poliza(
    IN p_id INT,
    IN p_usuario VARCHAR(100)
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username COLLATE utf8mb4_0900_ai_ci = p_usuario COLLATE utf8mb4_0900_ai_ci
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    UPDATE polizas
    SET anulado = 0,
        estado = 'VIGENTE',
        usuario_edicion = v_usuario_nombre
    WHERE idPoliza = p_id AND activo = 1 AND anulado = 1;
    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_anular_poliza(
    IN p_id INT,
    IN p_usuario VARCHAR(100),
    IN p_motivo VARCHAR(200),
    IN p_fecha DATE
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    DECLARE v_poliza_numero VARCHAR(50);
    DECLARE v_affected INT;
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    SELECT poliza INTO v_poliza_numero
    FROM polizas
    WHERE idPoliza = p_id
    LIMIT 1;

    UPDATE polizas
    SET anulado = 1,
        estado = 'ANULADA',
        motivo = p_motivo,
        usuario_edicion = v_usuario_nombre
    WHERE idPoliza = p_id AND activo = 1 AND anulado = 0;
    SET v_affected = ROW_COUNT();

    IF v_affected > 0 THEN
        INSERT INTO poliza_anulaciones (poliza_id, poliza_numero, usuario, motivo, fecha_anulacion)
        VALUES (p_id, v_poliza_numero, v_usuario_nombre, p_motivo, COALESCE(p_fecha, CURDATE()));
    END IF;

    SELECT v_affected AS affected_rows;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_anular_cuotas_por_poliza(
    IN p_id INT,
    IN p_usuario VARCHAR(100)
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    DECLARE v_poliza_numero VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    SET v_poliza_numero = NULL;
    SELECT TRIM(
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
            CAST(AES_DECRYPT(poliza, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
            poliza
        )
    )
    INTO v_poliza_numero
    FROM polizas
    WHERE idPoliza = p_id
    LIMIT 1;

    UPDATE cuotas
    SET activo = 0,
        anular = 0,
        usuario_edicion = v_usuario_nombre
    WHERE poliza_id = p_id
       OR (
            v_poliza_numero IS NOT NULL
            AND TRIM(
                    COALESCE(
                        CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                        CAST(AES_DECRYPT(poliza, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                        poliza
                    )
                ) COLLATE utf8mb4_0900_ai_ci = (v_poliza_numero COLLATE utf8mb4_0900_ai_ci)
       );

    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

-- SP: Anula UNA prima específica y solo sus cuotas ligadas.
-- Usa prima_anulada=1 (NO anulado=1) para que la póliza padre
-- permanezca visible en el listado de pólizas activas.
-- El UPDATE de cuotas filtra por idCuota (PK) via subquery
-- para no requerir SQL_SAFE_UPDATES=0.
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_anular_prima$$
CREATE PROCEDURE sp_anular_prima(
    IN p_prima_id   INT,
    IN p_usuario    VARCHAR(100),
    IN p_motivo     VARCHAR(200),
    IN p_fecha      DATE
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    DECLARE v_poliza_numero  VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
    DECLARE v_recibo_prima   VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
    DECLARE v_affected       INT DEFAULT 0;

    -- Resolver nombre de usuario
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    -- Obtener número de póliza y recibo (cupon) de la prima
    SELECT
        TRIM(COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
            CAST(AES_DECRYPT(poliza, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
            poliza
        )),
        TRIM(COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(recibo), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
            CAST(AES_DECRYPT(recibo, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
            recibo
        ))
    INTO v_poliza_numero, v_recibo_prima
    FROM polizas
    WHERE idPoliza = p_prima_id
    LIMIT 1;

    -- Marcar prima como anulada (prima_anulada=1, anulado permanece 0
    -- → la póliza sigue visible en el listado de pólizas activas).
    -- idPoliza es PK: no activa safe mode.
    UPDATE polizas
    SET prima_anulada   = 1,
        estado          = 'ANULADA',
        motivo          = p_motivo,
        usuario_edicion = v_usuario_nombre
    WHERE idPoliza      = p_prima_id
      AND activo        = 1
      AND prima_anulada = 0;

    SET v_affected = ROW_COUNT();

    -- Auditoría
    IF v_affected > 0 THEN
        INSERT INTO poliza_anulaciones (poliza_id, poliza_numero, usuario, motivo, fecha_anulacion)
        VALUES (p_prima_id, v_poliza_numero, v_usuario_nombre, p_motivo, COALESCE(p_fecha, CURDATE()));
    END IF;

    -- Anular cuotas de esta prima filtrando por idCuota (PK) via subquery.
    -- El doble nivel de subquery es necesario porque MySQL no permite
    -- UPDATE sobre la misma tabla que aparece en el FROM del subquery directo.
    UPDATE cuotas
    SET activo          = 0,
        anular          = 0,
        usuario_edicion = v_usuario_nombre
    WHERE idCuota IN (
        SELECT id FROM (
            SELECT idCuota AS id
            FROM cuotas
            WHERE activo = 1
              AND (
                    poliza_id = p_prima_id
                    OR (
                        v_recibo_prima IS NOT NULL
                        AND TRIM(v_recibo_prima) <> ''
                        AND TRIM(COALESCE(
                                CAST(AES_DECRYPT(FROM_BASE64(cupon), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                                CAST(AES_DECRYPT(cupon, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                                cupon
                            )) COLLATE utf8mb4_0900_ai_ci = (v_recibo_prima COLLATE utf8mb4_0900_ai_ci)
                    )
              )
        ) AS _ids
    );

    SELECT v_affected AS affected_rows;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_delete_poliza(
    IN p_id INT,
    IN p_usuario VARCHAR(100)
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    DECLARE v_poliza_numero VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
    DECLARE v_cupon_numero VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
    DECLARE v_poliza_affected INT;
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    UPDATE polizas
    SET activo = 0,
        usuario_edicion = v_usuario_nombre
    WHERE idPoliza = p_id AND activo = 1;
    SET v_poliza_affected = ROW_COUNT();

    IF v_poliza_affected > 0 THEN
        SET v_poliza_numero = NULL;
        SET v_cupon_numero = NULL;
        SELECT TRIM(
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                CAST(AES_DECRYPT(poliza, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                poliza
            )
        )
        INTO v_poliza_numero
        FROM polizas
        WHERE idPoliza = p_id
        LIMIT 1;

        SELECT TRIM(
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(recibo), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                CAST(AES_DECRYPT(recibo, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                recibo
            )
        )
        INTO v_cupon_numero
        FROM polizas
        WHERE idPoliza = p_id
        LIMIT 1;

        IF v_cupon_numero IS NOT NULL AND TRIM(v_cupon_numero) <> '' THEN
            UPDATE cuotas
            SET activo = 0,
                usuario_edicion = v_usuario_nombre
            WHERE activo = 1
              AND TRIM(
                    COALESCE(
                        CAST(AES_DECRYPT(FROM_BASE64(cupon), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                        CAST(AES_DECRYPT(cupon, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                        cupon
                    )
                ) COLLATE utf8mb4_0900_ai_ci = (v_cupon_numero COLLATE utf8mb4_0900_ai_ci)
              AND (
                    poliza_id = p_id
                    OR (
                        v_poliza_numero IS NOT NULL AND TRIM(v_poliza_numero) <> ''
                        AND TRIM(
                                COALESCE(
                                    CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                                    CAST(AES_DECRYPT(poliza, @SIS_KEY) AS CHAR CHARACTER SET utf8mb4),
                                    poliza
                                )
                            ) COLLATE utf8mb4_0900_ai_ci = (v_poliza_numero COLLATE utf8mb4_0900_ai_ci)
                    )
                  );
        END IF;
    END IF;

    SELECT v_poliza_affected AS affected_rows;
END$$
DELIMITER ;
-- Tabla cuotas (mínima)
CREATE TABLE IF NOT EXISTS cuotas (
    idCuota INT AUTO_INCREMENT PRIMARY KEY,
    poliza_id INT NULL,
    financiamiento_grupal_id INT NULL,
    poliza VARCHAR(50) NOT NULL,
    cupon VARCHAR(50) NULL,
    fecha_vencimiento DATE NOT NULL,
    moneda VARCHAR(10) DEFAULT 'SOLES',
    importe DECIMAL(15,2) NOT NULL,
    fecha_pago DATE NULL,
    factura VARCHAR(50) NULL,
    fecha_factura DATETIME NULL,
    observacion VARCHAR(255) NULL,
    usuario_registro VARCHAR(100) NULL,
    usuario_edicion VARCHAR(100) NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    numero_cuota INT NULL,
    activo TINYINT(1) DEFAULT 1,
    anular TINYINT(1) DEFAULT 1,
    motivo_anulacion VARCHAR(200) NULL,
    usuario_anulacion VARCHAR(100) NULL,
    fecha_anulacion DATETIME NULL,
    CONSTRAINT fk_cuotas_financiamiento_grupal
        FOREIGN KEY (financiamiento_grupal_id) REFERENCES financiamiento_grupal(id_financiamiento_grupal)
);

CREATE INDEX idx_cuotas_financiamiento_grupal ON cuotas (financiamiento_grupal_id);
CREATE INDEX idx_cuotas_poliza_activo_venc ON cuotas (poliza_id, activo, fecha_vencimiento, idCuota);
CREATE INDEX idx_cuotas_poliza_fecha_pago ON cuotas (poliza_id, fecha_pago);

-- Nota operativa:
-- El importe de las cuotas de financiamiento grupal debe salir de
-- `financiamiento_grupal.importe` y NO de la suma de avisos/pólizas agregadas.
-- Los avisos solo vinculan pólizas al grupo; no recalculan automáticamente
-- el importe maestro del financiamiento.
-- Regla funcional:
-- Si el financiamiento tiene importe 29.00 y 5 cuotas, entonces cada cuota
-- debe quedar con importe 29.00.

DELIMITER $$
DROP PROCEDURE IF EXISTS sp_sync_financiamiento_grupal_cuotas_importe$$
CREATE PROCEDURE sp_sync_financiamiento_grupal_cuotas_importe(
    IN p_financiamiento_id INT
)
BEGIN
    DECLARE v_importe DECIMAL(15,2) DEFAULT 0.00;
    DECLARE v_numero_cupones INT DEFAULT 1;

    IF p_financiamiento_id IS NULL OR p_financiamiento_id <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'ID de financiamiento inválido';
    END IF;

    SELECT
        COALESCE(importe, 0),
        GREATEST(COALESCE(numero_cupones, 1), 1)
    INTO v_importe, v_numero_cupones
    FROM financiamiento_grupal
    WHERE id_financiamiento_grupal = p_financiamiento_id
      AND activo = 1
    LIMIT 1;

    UPDATE cuotas
    SET importe = v_importe
    WHERE financiamiento_grupal_id = p_financiamiento_id
      AND activo = 1;

    SELECT
        p_financiamiento_id AS financiamiento_grupal_id,
        v_importe AS importe_financiamiento,
        v_numero_cupones AS numero_cupones;
END$$
DELIMITER ;

-- Tabla para archivos de cuotas (análoga a poliza_archivos) — debe ir después de cuotas
CREATE TABLE IF NOT EXISTS cuota_archivos (
    idArchivo INT AUTO_INCREMENT PRIMARY KEY,
    cuota_id INT NOT NULL,
    poliza_id INT NULL,
    numero_poliza VARCHAR(50),
    cupon VARCHAR(50),
    ruta_archivo VARCHAR(255) NOT NULL,
    nombre_original VARCHAR(255),
    usuario VARCHAR(100),
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cuota_id) REFERENCES cuotas(idCuota) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- SP: insertar archivo de cuota
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_insert_cuota_archivo$$
CREATE PROCEDURE sp_insert_cuota_archivo(
    IN p_cuota_id INT,
    IN p_poliza_id INT,
    IN p_numero_poliza VARCHAR(50),
    IN p_cupon VARCHAR(50),
    IN p_ruta_archivo VARCHAR(255),
    IN p_nombre_original VARCHAR(255),
    IN p_usuario VARCHAR(100)
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    INSERT INTO cuota_archivos (cuota_id, poliza_id, numero_poliza, cupon, ruta_archivo, nombre_original, usuario, creado_en)
    VALUES (p_cuota_id, p_poliza_id, p_numero_poliza, p_cupon, p_ruta_archivo, p_nombre_original, v_usuario_nombre, CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', '-05:00'));
    SELECT LAST_INSERT_ID() AS idArchivo;
END$$
DELIMITER ;

DELIMITER $$
DROP PROCEDURE IF EXISTS sp_reporte_archivos_detalle$$
CREATE PROCEDURE sp_reporte_archivos_detalle(
    IN p_busqueda VARCHAR(100),
    IN p_identificador VARCHAR(50),
    IN p_tipo_origen VARCHAR(20)
)
BEGIN
    IF p_tipo_origen = 'CUOTA' THEN
        -- Los archivos de cuotas se almacenan en poliza_archivos con origen='CUOTA'
        SELECT
            pa.idArchivo,
            pa.ruta_archivo,
            pa.nombre_original,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
                p.poliza
            ) AS identificador,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
                p.recibo
            ) AS recibo,
            'CUOTA' AS tipo_origen
        FROM poliza_archivos pa
        INNER JOIN polizas p ON pa.poliza_id = p.idPoliza
        WHERE pa.origen = 'CUOTA'
          AND (p_identificador IS NULL OR p_identificador = '' 
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR), p.poliza) = p_identificador
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR), p.recibo) = p_identificador
               OR CAST(pa.poliza_id AS CHAR) = p_identificador);
    ELSE
        SELECT
            pa.idArchivo,
            pa.ruta_archivo,
            pa.nombre_original,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
                p.poliza
            ) AS identificador,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
                p.recibo
            ) AS recibo,
            'POLIZA' AS tipo_origen
        FROM poliza_archivos pa
        INNER JOIN polizas p ON pa.poliza_id = p.idPoliza
        INNER JOIN clientes c ON p.cliente_id = c.idCliente
        WHERE (p_busqueda IS NULL OR p_busqueda = ''
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR), p.poliza) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR), c.razon_social) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR pa.nombre_original LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.contrato_nro), @SIS_KEY) AS CHAR), p.contrato_nro) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR), p.recibo) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%'))
          AND (p_identificador IS NULL OR p_identificador = ''
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR), p.poliza) = p_identificador)
          AND (p_tipo_origen IS NULL OR p_tipo_origen = '' OR 'POLIZA' = p_tipo_origen);
    END IF;
END$$
DELIMITER ;

DELIMITER $$
DROP PROCEDURE IF EXISTS sp_reporte_archivos_resumen$$
CREATE PROCEDURE sp_reporte_archivos_resumen(IN p_busqueda VARCHAR(100), IN p_limite INT)
BEGIN
    -- Si p_limite es NULL o 0 se usa 200 por defecto
    IF p_limite IS NULL OR p_limite <= 0 THEN
        SET p_limite = 200;
    END IF;
    SELECT
        identificador,
        recibo,
        tipo_origen,
        contratante,
        GROUP_CONCAT(DISTINCT archivo ORDER BY fecha_subida DESC SEPARATOR ' | ') AS archivo,
        COUNT(*) AS cantidad_archivos,
        MAX(fecha_subida) AS ultima_fecha,
        ramo,
        producto,
        usuario,
        compania,
        poliza_padre_id,
        cupon,
        NULL AS cuota_id,
        MAX(poliza_id) AS poliza_id
    FROM (
        -- Archivos de pólizas (origen != 'CUOTA')
        SELECT
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
                p.poliza
            ) COLLATE utf8mb4_0900_ai_ci AS identificador,
            'POLIZA' AS tipo_origen,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
                c.razon_social
            ) COLLATE utf8mb4_0900_ai_ci AS contratante,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
                p.recibo
            ) COLLATE utf8mb4_0900_ai_ci AS recibo,
            pa.creado_en AS fecha_subida,
            p.ramo COLLATE utf8mb4_0900_ai_ci AS ramo,
            p.ramos_producto COLLATE utf8mb4_0900_ai_ci AS producto,
            COALESCE(NULLIF(TRIM(ur.nombre), ''), p.usuario_registro) COLLATE utf8mb4_0900_ai_ci AS usuario,
            p.cia COLLATE utf8mb4_0900_ai_ci AS compania,
            pa.nombre_original COLLATE utf8mb4_0900_ai_ci AS archivo,
            NULL AS poliza_padre_id,
            NULL AS cupon,
            p.idPoliza AS poliza_id
        FROM poliza_archivos pa
        INNER JOIN polizas p ON pa.poliza_id = p.idPoliza
        INNER JOIN clientes c ON p.cliente_id = c.idCliente
        LEFT JOIN usuarios ur ON ur.username = p.usuario_registro OR ur.nombre = p.usuario_registro
        WHERE (pa.origen IS NULL OR pa.origen != 'CUOTA')
          AND (p_busqueda IS NULL OR p_busqueda = ''
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR), p.poliza) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR), c.razon_social) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR pa.nombre_original LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.contrato_nro), @SIS_KEY) AS CHAR), p.contrato_nro) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR), p.recibo) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%'))

        UNION ALL

        -- Archivos de cuotas guardados en poliza_archivos con origen='CUOTA'
        SELECT
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
                p.poliza
            ) COLLATE utf8mb4_0900_ai_ci AS identificador,
            'CUOTA' AS tipo_origen,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(c.razon_social, @SIS_KEY) AS CHAR),
                c.razon_social
            ) COLLATE utf8mb4_0900_ai_ci AS contratante,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
                p.recibo
            ) COLLATE utf8mb4_0900_ai_ci AS recibo,
            pa.creado_en AS fecha_subida,
            p.ramo COLLATE utf8mb4_0900_ai_ci AS ramo,
            p.ramos_producto COLLATE utf8mb4_0900_ai_ci AS producto,
            pa.usuario COLLATE utf8mb4_0900_ai_ci AS usuario,
            p.cia COLLATE utf8mb4_0900_ai_ci AS compania,
            pa.nombre_original COLLATE utf8mb4_0900_ai_ci AS archivo,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
                p.poliza
            ) COLLATE utf8mb4_0900_ai_ci AS poliza_padre_id,
            -- Extraer cupon del nombre_original ("[CUOTA xxx] archivo.pdf")
            CASE
                WHEN pa.nombre_original LIKE '[CUOTA %] %'
                THEN TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(pa.nombre_original, '] ', 1), '[CUOTA ', -1))
                ELSE NULL
            END COLLATE utf8mb4_0900_ai_ci AS cupon,
            p.idPoliza AS poliza_id
        FROM poliza_archivos pa
        INNER JOIN polizas p ON pa.poliza_id = p.idPoliza
        INNER JOIN clientes c ON p.cliente_id = c.idCliente
        WHERE pa.origen = 'CUOTA'
          AND (p_busqueda IS NULL OR p_busqueda = ''
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR), p.poliza) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR), p.recibo) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR COALESCE(CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR), c.razon_social) LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%')
               OR pa.nombre_original LIKE CONCAT('%', p_busqueda COLLATE utf8mb4_0900_ai_ci, '%'))
    ) AS combined
    GROUP BY identificador, recibo, tipo_origen, contratante, ramo, producto, usuario, compania, poliza_padre_id, cupon
    ORDER BY
        COALESCE(poliza_padre_id, identificador) ASC,
        recibo ASC,
        tipo_origen ASC,
        ultima_fecha DESC
    LIMIT p_limite;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_list_cuotas_por_poliza(IN p_poliza VARCHAR(50))
BEGIN
    SELECT
        idCuota,
        COALESCE(CAST(AES_DECRYPT(FROM_BASE64(cupon), @SIS_KEY) AS CHAR), cupon) AS cupon,
        DATE_FORMAT(fecha_vencimiento, '%d-%m-%Y') AS fecha_vencimiento,
        moneda,
        FORMAT(importe, 2) AS importe,
        DATE_FORMAT(fecha_pago, '%d-%m-%Y') AS fecha_pago,
        factura,
        DATE_FORMAT(fecha_factura, '%d-%m-%Y %H:%i') AS fecha_factura,
        observacion
    FROM cuotas
    WHERE (
        CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR) = p_poliza
        OR poliza = p_poliza
    )
      AND activo = 1
    ORDER BY fecha_vencimiento ASC, idCuota ASC;
END$$
DELIMITER ;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_insert_cuota$$

CREATE PROCEDURE sp_insert_cuota(
    IN p_poliza VARCHAR(50),
    IN p_cupon VARCHAR(50),
    IN p_fecha_vencimiento DATE,
    IN p_moneda VARCHAR(10),
    IN p_importe DECIMAL(15,2),
    IN p_fecha_pago DATE,
    IN p_factura VARCHAR(50),
    IN p_fecha_factura DATETIME,
    IN p_observacion VARCHAR(255),
    IN p_usuario VARCHAR(100),
    IN p_numero_cuota INT
)
BEGIN
    DECLARE v_msg VARCHAR(255);
    DECLARE v_poliza_id INT;
    DECLARE v_usuario_nombre VARCHAR(100);
    DECLARE v_cia VARCHAR(100);

    -- Validar cupón duplicado por póliza
    IF p_cupon IS NOT NULL AND TRIM(p_cupon) <> '' THEN
        IF EXISTS (
            SELECT 1 
            FROM cuotas 
            WHERE TRIM(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR), poliza)) = TRIM(p_poliza) 
              AND TRIM(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(cupon), @SIS_KEY) AS CHAR), cupon)) = TRIM(p_cupon) 
              AND activo = 1
        ) THEN
            SET v_msg = CONCAT('El cupón ya existe para esta póliza: ', TRIM(p_cupon));
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
        END IF;
    END IF;

    -- Buscar idPoliza correspondiente
    -- Si hay cupón/proforma, buscar por póliza + recibo; de lo contrario, usar solo póliza
    IF p_cupon IS NOT NULL AND TRIM(p_cupon) <> '' THEN
        SELECT idPoliza
        INTO v_poliza_id
        FROM polizas
        WHERE TRIM(COALESCE(CONVERT(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) USING utf8mb4), poliza) COLLATE utf8mb4_0900_ai_ci) = TRIM(p_poliza COLLATE utf8mb4_0900_ai_ci)
          AND TRIM(COALESCE(CONVERT(AES_DECRYPT(FROM_BASE64(recibo), @SIS_KEY) USING utf8mb4), recibo) COLLATE utf8mb4_0900_ai_ci) = TRIM(p_cupon COLLATE utf8mb4_0900_ai_ci)
        ORDER BY creado_en DESC
        LIMIT 1;
    ELSE
        SELECT idPoliza
        INTO v_poliza_id
        FROM polizas
        WHERE TRIM(COALESCE(CONVERT(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) USING utf8mb4), poliza) COLLATE utf8mb4_0900_ai_ci) = TRIM(p_poliza COLLATE utf8mb4_0900_ai_ci)
        ORDER BY creado_en DESC
        LIMIT 1;
    END IF;

    SET v_cia = NULL;
    IF v_poliza_id IS NOT NULL THEN
        SELECT cia INTO v_cia
        FROM polizas
        WHERE idPoliza = v_poliza_id
        LIMIT 1;
    END IF;

    IF p_factura IS NOT NULL AND TRIM(p_factura) <> '' THEN
        IF p_cupon IS NOT NULL AND TRIM(p_cupon) <> '' THEN
            IF EXISTS (
                SELECT 1
                FROM cuotas q
                INNER JOIN polizas p ON p.idPoliza = q.poliza_id
                WHERE q.activo = 1
                  AND TRIM(COALESCE(q.factura, '')) COLLATE utf8mb4_0900_ai_ci = TRIM(p_factura) COLLATE utf8mb4_0900_ai_ci
                  AND TRIM(COALESCE(CONVERT(AES_DECRYPT(FROM_BASE64(q.poliza), @SIS_KEY) USING utf8mb4), q.poliza) COLLATE utf8mb4_0900_ai_ci) = TRIM(p_poliza) COLLATE utf8mb4_0900_ai_ci
                  AND TRIM(COALESCE(CONVERT(AES_DECRYPT(FROM_BASE64(q.cupon), @SIS_KEY) USING utf8mb4), q.cupon) COLLATE utf8mb4_0900_ai_ci) = TRIM(p_cupon) COLLATE utf8mb4_0900_ai_ci
                  AND (v_cia IS NULL OR TRIM(COALESCE(p.cia, '')) COLLATE utf8mb4_0900_ai_ci = TRIM(v_cia) COLLATE utf8mb4_0900_ai_ci)
                LIMIT 1
            ) THEN
                SET v_msg = CONCAT('El número de factura ya existe: ', TRIM(p_factura));
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
            END IF;
        ELSE
            IF EXISTS (
                SELECT 1
                FROM cuotas q
                INNER JOIN polizas p ON p.idPoliza = q.poliza_id
                WHERE q.activo = 1
                  AND TRIM(COALESCE(q.factura, '')) COLLATE utf8mb4_0900_ai_ci = TRIM(p_factura) COLLATE utf8mb4_0900_ai_ci
                  AND TRIM(COALESCE(CONVERT(AES_DECRYPT(FROM_BASE64(q.poliza), @SIS_KEY) USING utf8mb4), q.poliza) COLLATE utf8mb4_0900_ai_ci) = TRIM(p_poliza) COLLATE utf8mb4_0900_ai_ci
                  AND (q.cupon IS NULL OR q.cupon = '')
                  AND (v_cia IS NULL OR TRIM(COALESCE(p.cia, '')) COLLATE utf8mb4_0900_ai_ci = TRIM(v_cia) COLLATE utf8mb4_0900_ai_ci)
                LIMIT 1
            ) THEN
                SET v_msg = CONCAT('El número de factura ya existe: ', TRIM(p_factura));
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
            END IF;
        END IF;
    END IF;

    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    INSERT INTO cuotas (
        poliza_id, poliza, cupon, fecha_vencimiento, moneda, importe,
        fecha_pago, factura, fecha_factura, observacion, usuario_registro, creado_en, numero_cuota, activo
    ) VALUES (
        v_poliza_id, COALESCE(TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)), p_poliza), COALESCE(TO_BASE64(AES_ENCRYPT(p_cupon, @SIS_KEY)), p_cupon), p_fecha_vencimiento, p_moneda, COALESCE(p_importe, 0.0),
        p_fecha_pago, p_factura, p_fecha_factura, p_observacion, v_usuario_nombre, CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', '-05:00'), p_numero_cuota, 1
    );

    IF p_fecha_pago IS NOT NULL THEN
        IF p_cupon IS NOT NULL AND TRIM(p_cupon) <> '' THEN
            UPDATE polizas
            SET estado = 'PAGADO'
            WHERE TRIM(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR), poliza)) = TRIM(p_poliza)
              AND TRIM(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(recibo), @SIS_KEY) AS CHAR), recibo)) = TRIM(p_cupon);
        ELSE
            UPDATE polizas
            SET estado = 'PAGADO'
            WHERE TRIM(COALESCE(CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR), poliza)) = TRIM(p_poliza);
        END IF;
    END IF;
END$$

DELIMITER ;

-- NEW PROCEDURES FOR EDITING

DELIMITER $$
CREATE PROCEDURE sp_get_poliza_by_id(IN p_id INT)
BEGIN
    SELECT
        p.*,
        c.razon_social AS cliente_razon_social,
        c.tipo_documento AS cliente_tipo_documento,
        c.numero_documento AS cliente_numero_documento,
        c.telefono AS cliente_telefono
    FROM polizas p
    INNER JOIN clientes c ON c.idCliente = p.cliente_id
    WHERE p.idPoliza = p_id;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_update_poliza(
    IN p_idPoliza INT,
    IN p_asegurado VARCHAR(150),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_poliza VARCHAR(50),
    IN p_moneda VARCHAR(20),
    IN p_fecha_emision DATE,
    IN p_vig_desde DATE,
    IN p_vig_hasta DATE,
    IN p_sub_agente VARCHAR(250),
    IN p_ejecutivo VARCHAR(250),
    IN p_asegurada VARCHAR(150),
    IN p_motivo VARCHAR(200),
    IN p_prima_comercial DECIMAL(15,2),
    IN p_prima_neta DECIMAL(15,2),
    IN p_prima_comercial_igv DECIMAL(15,2),
    IN p_prima_total DECIMAL(15,2),
    IN p_porc_compania DECIMAL(5,2),
    IN p_imp_compania DECIMAL(15,2),
    IN p_porc_subagente DECIMAL(5,2),
    IN p_imp_subagente DECIMAL(15,2),
    IN p_ramos_producto VARCHAR(120),
    IN p_tipo_doc VARCHAR(10),
    IN p_estado VARCHAR(20),
    IN p_nro VARCHAR(50), -- Nuevo
    IN p_forma_pago VARCHAR(30), -- Nuevo
    IN p_recibo VARCHAR(50), -- Nuevo
    IN p_tipo_vigencia VARCHAR(50), -- Nuevo
    IN p_endosatario VARCHAR(150), -- Nuevo
    IN p_pdf_path VARCHAR(255), -- Nuevo
    IN p_usuario_edicion VARCHAR(100),
    IN p_datos_adicionales JSON            -- NUEVO: datos extra en JSON
)
BEGIN
    DECLARE v_usuario_edicion_nombre VARCHAR(100);
    SET v_usuario_edicion_nombre = NULL;
    IF p_usuario_edicion IS NOT NULL AND TRIM(p_usuario_edicion) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_edicion_nombre
        FROM usuarios
        WHERE username COLLATE utf8mb4_0900_ai_ci = p_usuario_edicion COLLATE utf8mb4_0900_ai_ci
        LIMIT 1;
    END IF;
    IF v_usuario_edicion_nombre IS NULL OR v_usuario_edicion_nombre = '' THEN
        SET v_usuario_edicion_nombre = p_usuario_edicion;
    END IF;

    UPDATE polizas SET
        usuario_edicion = v_usuario_edicion_nombre,
        asegurado = p_asegurado,
        cia = p_cia,
        ramo = p_ramo,
        poliza = p_poliza,
        moneda = p_moneda,
        fecha_emision = p_fecha_emision,
        vig_desde = p_vig_desde,
        vig_hasta = p_vig_hasta,
        sub_agente = p_sub_agente,
        ejecutivo = p_ejecutivo,
        asegurada = p_asegurada,
        motivo = p_motivo,
        prima_comercial = p_prima_comercial,
        prima_neta = p_prima_neta,
        prima_comercial_igv = p_prima_comercial_igv,
        prima_total = p_prima_total,
        porc_compania = p_porc_compania,
        imp_compania = p_imp_compania,
        porc_subagente = p_porc_subagente,
        imp_subagente = p_imp_subagente,
        ramos_producto = p_ramos_producto,
        tipo_doc = p_tipo_doc,
        estado = p_estado,
        nro = p_nro,
        forma_pago = p_forma_pago,
        recibo = p_recibo,
        tipo_vigencia = p_tipo_vigencia,
        endosatario = p_endosatario,
        datos_adicionales = p_datos_adicionales
    WHERE idPoliza = p_idPoliza;

    IF p_pdf_path IS NOT NULL AND p_pdf_path <> '' THEN
        INSERT INTO poliza_archivos (poliza_id, numero_poliza, ruta_archivo, nombre_original, origen, ramo, producto, usuario, compania)
        VALUES (p_idPoliza, p_poliza, p_pdf_path, SUBSTRING_INDEX(p_pdf_path, '/', -1), 'EDICION', p_ramo, p_ramos_producto, v_usuario_edicion_nombre, p_cia);
    END IF;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_reporte_vencimientos;
DELIMITER $$

CREATE PROCEDURE sp_reporte_vencimientos(
    IN p_usuarios VARCHAR(255),
    IN p_ejecutivo TEXT,
    IN p_estado VARCHAR(50),
    IN p_fecha_desde DATE,
    IN p_fecha_hasta DATE,
    IN p_ramo TEXT,
    IN p_search TEXT,
    IN p_limit INT,
    IN p_offset INT
)
BEGIN
    DECLARE v_limit INT DEFAULT 20;
    DECLARE v_offset INT DEFAULT 0;

    SET v_limit = GREATEST(COALESCE(p_limit, 20), 1);
    SET v_offset = GREATEST(COALESCE(p_offset, 0), 0);

    DROP TEMPORARY TABLE IF EXISTS tmp_reporte_vencimientos;

    CREATE TEMPORARY TABLE tmp_reporte_vencimientos AS
    WITH base_rows AS (
        SELECT
            p.idPoliza,
            p.cia AS compania,
            p.ramo,
            p.ramos_producto AS producto,
            COALESCE(NULLIF(TRIM(p.ejecutivo), ''), '') AS ejecutivo,
            c.tipo_documento,
            TRIM(
                COALESCE(
                    CAST(AES_DECRYPT(FROM_BASE64(c.numero_documento), @SIS_KEY) AS CHAR),
                    CAST(AES_DECRYPT(c.numero_documento, @SIS_KEY) AS CHAR),
                    c.numero_documento,
                    ''
                )
            ) AS numero_documento,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(c.razon_social), @SIS_KEY) AS CHAR),
                c.razon_social
            ) AS contratante,
            TRIM(
                COALESCE(
                    CAST(AES_DECRYPT(FROM_BASE64(p.poliza), @SIS_KEY) AS CHAR),
                    CAST(AES_DECRYPT(p.poliza, @SIS_KEY) AS CHAR),
                    p.poliza,
                    ''
                )
            ) AS poliza,
            COALESCE(
                CAST(AES_DECRYPT(FROM_BASE64(p.recibo), @SIS_KEY) AS CHAR),
                CAST(AES_DECRYPT(p.recibo, @SIS_KEY) AS CHAR),
                p.recibo
            ) AS aviso_cobranza,
            (
                SELECT COALESCE(
                    CAST(AES_DECRYPT(FROM_BASE64(q.cupon), @SIS_KEY) AS CHAR),
                    CAST(AES_DECRYPT(q.cupon, @SIS_KEY) AS CHAR),
                    q.cupon
                )
                FROM cuotas q
                WHERE q.poliza_id = p.idPoliza
                  AND q.activo = 1
                ORDER BY q.fecha_vencimiento DESC, q.idCuota DESC
                LIMIT 1
            ) AS cupon,
            p.vig_desde,
            p.vig_hasta,
            (
                SELECT DATE_FORMAT(MAX(q.fecha_pago), '%d/%m/%Y')
                FROM cuotas q
                WHERE q.poliza_id = p.idPoliza
                  AND (
                        (p.recibo IS NULL OR TRIM(p.recibo) = '')
                        OR (q.cupon IS NOT NULL AND TRIM(q.cupon) = TRIM(p.recibo))
                      )
            ) AS fecha_pago,
            (
                SELECT COUNT(*)
                FROM cuotas q
                WHERE q.activo = 1
                  AND q.poliza_id = p.idPoliza
            ) AS cuotas_count,
            p.moneda,
            COALESCE(p.prima_neta, 0) AS prima_neta,
            COALESCE(p.prima_comercial_igv, 0) AS prima_total,
            p.estado
        FROM polizas p
        INNER JOIN clientes c
            ON c.idCliente = p.cliente_id
        LEFT JOIN usuarios ur
            ON CONVERT(ur.username USING utf8mb4) COLLATE utf8mb4_unicode_ci =
               CONVERT(p.usuario_registro USING utf8mb4) COLLATE utf8mb4_unicode_ci
            OR CONVERT(ur.nombre USING utf8mb4) COLLATE utf8mb4_unicode_ci =
               CONVERT(p.usuario_registro USING utf8mb4) COLLATE utf8mb4_unicode_ci
        WHERE p.activo = 1
          AND p.anulado = 0
          AND COALESCE(p.prima_anulada, 0) = 0
          AND (
                p_usuarios IS NULL
                OR TRIM(CONVERT(p_usuarios USING utf8mb4) COLLATE utf8mb4_unicode_ci) = ''
                OR FIND_IN_SET(
                    CONVERT(COALESCE(ur.username, p.usuario_registro) USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                    CONVERT(p_usuarios USING utf8mb4) COLLATE utf8mb4_unicode_ci
                ) > 0
                OR FIND_IN_SET(
                    CONVERT(COALESCE(NULLIF(TRIM(ur.nombre), ''), p.usuario_registro) USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                    CONVERT(p_usuarios USING utf8mb4) COLLATE utf8mb4_unicode_ci
                ) > 0
          )
          AND (
                p_estado IS NULL
                OR TRIM(CONVERT(p_estado USING utf8mb4) COLLATE utf8mb4_unicode_ci) = ''
                OR CONVERT(p.estado USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                   CONVERT(p_estado USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
          AND (
                p_ejecutivo IS NULL
                OR TRIM(CONVERT(p_ejecutivo USING utf8mb4) COLLATE utf8mb4_unicode_ci) = ''
                OR FIND_IN_SET(
                    CONVERT(COALESCE(NULLIF(TRIM(p.ejecutivo), ''), '') USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                    CONVERT(p_ejecutivo USING utf8mb4) COLLATE utf8mb4_unicode_ci
                ) > 0
          )
          AND (
                (p_fecha_desde IS NULL AND p_fecha_hasta IS NULL)
                OR (
                    p.vig_hasta BETWEEN COALESCE(p_fecha_desde, '1900-01-01')
                                   AND COALESCE(p_fecha_hasta, '2900-12-31')
                )
          )
          AND (
                p_ramo IS NULL
                OR TRIM(CONVERT(p_ramo USING utf8mb4) COLLATE utf8mb4_unicode_ci) = ''
                OR FIND_IN_SET(
                    CONVERT(p.ramo USING utf8mb4) COLLATE utf8mb4_unicode_ci,
                    CONVERT(p_ramo USING utf8mb4) COLLATE utf8mb4_unicode_ci
                ) > 0
          )
    ),
    ranked_rows AS (
        SELECT
            base_rows.*,
            MIN(base_rows.vig_desde) OVER (PARTITION BY base_rows.poliza) AS min_vig_desde,
            MAX(base_rows.vig_hasta) OVER (PARTITION BY base_rows.poliza) AS max_vig_hasta,
            SUM(base_rows.prima_neta) OVER (PARTITION BY base_rows.poliza) AS sum_prima_neta,
            SUM(base_rows.prima_total) OVER (PARTITION BY base_rows.poliza) AS sum_prima_total,
            ROW_NUMBER() OVER (
                PARTITION BY base_rows.poliza
                ORDER BY base_rows.vig_hasta DESC, base_rows.idPoliza DESC
            ) AS rn
        FROM base_rows
    )
    SELECT
        idPoliza,
        compania,
        ramo,
        producto,
        ejecutivo,
        tipo_documento,
        numero_documento,
        contratante,
        poliza,
        aviso_cobranza,
        cupon,
        DATE_FORMAT(min_vig_desde, '%d/%m/%Y') AS vig_desde,
        DATE_FORMAT(max_vig_hasta, '%d/%m/%Y') AS vig_hasta,
        max_vig_hasta AS sort_vig_hasta,
        fecha_pago,
        cuotas_count,
        moneda,
        sum_prima_neta AS prima_neta,
        sum_prima_total AS prima_total,
        estado
    FROM ranked_rows
    WHERE rn = 1;

    SELECT COUNT(*) AS total
    FROM tmp_reporte_vencimientos t
    WHERE (
            p_search IS NULL
            OR TRIM(CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci) = ''
            OR CONVERT(COALESCE(t.poliza, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci LIKE CONCAT('%', CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci, '%')
            OR CONVERT(COALESCE(t.aviso_cobranza, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci LIKE CONCAT('%', CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci, '%')
            OR CONVERT(COALESCE(t.cupon, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci LIKE CONCAT('%', CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci, '%')
          );

    SELECT
        t.idPoliza,
        t.compania,
        t.ramo,
        t.producto,
        t.ejecutivo,
        t.tipo_documento,
        t.numero_documento,
        t.contratante,
        t.poliza,
        t.aviso_cobranza,
        t.cupon,
        t.vig_desde,
        t.vig_hasta,
        t.fecha_pago,
        t.cuotas_count,
        t.moneda,
        t.prima_neta,
        t.prima_total,
        t.estado
    FROM tmp_reporte_vencimientos t
    WHERE (
            p_search IS NULL
            OR TRIM(CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci) = ''
            OR CONVERT(COALESCE(t.poliza, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci LIKE CONCAT('%', CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci, '%')
            OR CONVERT(COALESCE(t.aviso_cobranza, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci LIKE CONCAT('%', CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci, '%')
            OR CONVERT(COALESCE(t.cupon, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci LIKE CONCAT('%', CONVERT(p_search USING utf8mb4) COLLATE utf8mb4_unicode_ci, '%')
          )
    ORDER BY t.sort_vig_hasta ASC, t.idPoliza DESC
    LIMIT v_limit OFFSET v_offset;

    DROP TEMPORARY TABLE IF EXISTS tmp_reporte_vencimientos;
END$$
DELIMITER ;

DELIMITER $$

CREATE PROCEDURE sp_get_idProductor_por_abreviacion(IN p_abreviacion VARCHAR(100))
BEGIN
SELECT idProductor
FROM SubAgente
WHERE abreviacion = p_abreviacion
    LIMIT 1;
END$$
DELIMITER ;

DELIMITER $$

CREATE PROCEDURE sp_update_cliente (
    IN p_idCliente INT,
    IN p_razon_social VARCHAR(255),
    IN p_tipo_documento VARCHAR(20),
    IN p_numero_documento VARCHAR(100),
    IN p_telefono VARCHAR(100),
    IN p_celular VARCHAR(20),
    IN p_telefono_sec VARCHAR(20),
    IN p_subagente VARCHAR(250),
    IN p_idProductor INT,
    IN p_email VARCHAR(255),
    IN p_direccion VARCHAR(200),
    IN p_departamento VARCHAR(100),
    IN p_provincia VARCHAR(100),
    IN p_distrito VARCHAR(100),
    IN p_estado VARCHAR(20),
    IN p_tipo_persona TINYINT,
    IN p_profesion VARCHAR(150),
    IN p_fecha_ingreso DATE,
    IN p_fecha_nacimiento DATE,
    IN p_licencia_num VARCHAR(50),
    IN p_licencia_venc DATE,
    IN p_grupo_economico VARCHAR(100),
    IN p_giro_negocio VARCHAR(100),
    IN p_referencia VARCHAR(200),
    IN p_recomendado_por VARCHAR(150),
    IN p_recibir_notificaciones TINYINT,
    IN p_contacto_nombre VARCHAR(150),
    IN p_contacto_email VARCHAR(150),
    IN p_contacto_telefono VARCHAR(20),
    IN p_usuario_modificacion VARCHAR(50)
)
BEGIN
    DECLARE v_current_num_raw VARCHAR(100);
    DECLARE v_current_num_plain VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    DECLARE v_new_num_plain VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    SELECT numero_documento
    INTO v_current_num_raw
    FROM clientes
    WHERE idCliente = p_idCliente
    LIMIT 1;

    IF v_current_num_raw IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cliente no encontrado';
    END IF;

    SET v_current_num_plain = CONVERT(
        COALESCE(
            CAST(AES_DECRYPT(FROM_BASE64(v_current_num_raw), @SIS_KEY) AS CHAR(100) CHARACTER SET utf8mb4),
            CAST(AES_DECRYPT(v_current_num_raw, @SIS_KEY) AS CHAR(100) CHARACTER SET utf8mb4),
            CONVERT(v_current_num_raw USING utf8mb4)
        )
        USING utf8mb4
    ) COLLATE utf8mb4_unicode_ci;

    SET v_new_num_plain = NULLIF(TRIM(CONVERT(p_numero_documento USING utf8mb4)), '') COLLATE utf8mb4_unicode_ci;

    UPDATE clientes
    SET razon_social = CASE
                          WHEN p_razon_social IS NULL OR TRIM(p_razon_social) = '' THEN razon_social
                          ELSE TO_BASE64(AES_ENCRYPT(p_razon_social, @SIS_KEY))
                       END,
        tipo_documento = p_tipo_documento,
        numero_documento = CASE
                              WHEN v_new_num_plain IS NULL OR v_new_num_plain = v_current_num_plain THEN numero_documento
                              ELSE TO_BASE64(AES_ENCRYPT(v_new_num_plain, @SIS_KEY))
                           END,
        telefono = CASE
                      WHEN p_telefono IS NULL OR TRIM(p_telefono) = '' THEN telefono
                      ELSE TO_BASE64(AES_ENCRYPT(p_telefono, @SIS_KEY))
                   END,
        celular = p_celular,
        telefono_sec = p_telefono_sec,
        subagente = p_subagente,
        idProductor = p_idProductor,
        email = CASE
                   WHEN p_email IS NULL OR TRIM(p_email) = '' THEN email
                   ELSE TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY))
                END,
        direccion = p_direccion,
        departamento = p_departamento,
        provincia = p_provincia,
        distrito = p_distrito,
        estado = p_estado,
        tipo_persona = p_tipo_persona,
        profesion = p_profesion,
        fecha_ingreso = p_fecha_ingreso,
        fecha_nacimiento = p_fecha_nacimiento,
        licencia_num = p_licencia_num,
        licencia_venc = p_licencia_venc,
        grupo_economico = p_grupo_economico,
        giro_negocio = p_giro_negocio,
        referencia = p_referencia,
        recomendado_por = p_recomendado_por,
        recibir_notificaciones = p_recibir_notificaciones,
        contacto_nombre = p_contacto_nombre,
        contacto_email = p_contacto_email,
        contacto_telefono = p_contacto_telefono,
        usuario_modificacion = p_usuario_modificacion,
        fecha_modificacion = NOW()
    WHERE idCliente = p_idCliente;
END$$

DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_delete_cliente(
    IN p_idCliente INT,
    IN p_usuario_modificacion VARCHAR(50)
)
BEGIN
    UPDATE clientes
    SET
        activo = 0,
        usuario_modificacion = p_usuario_modificacion,
        fecha_modificacion = NOW()
    WHERE idCliente = p_idCliente
      AND activo = 1;

    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;
DELIMITER $$
CREATE PROCEDURE sp_restore_cliente(
    IN p_idCliente INT,
    IN p_usuario_modificacion VARCHAR(50)
)
BEGIN
    UPDATE clientes
    SET
        activo = 1,
        usuario_modificacion = p_usuario_modificacion,
        fecha_modificacion = NOW()
    WHERE idCliente = p_idCliente
      AND activo = 0;

    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

-- =====================================================
-- ELIMINACIÓN FÍSICA (solo BROKER) — irreversible
-- =====================================================
DELIMITER $$
CREATE PROCEDURE sp_hard_delete_cuota(IN p_idCuota INT)
BEGIN
    DELETE FROM cuotas WHERE idCuota = p_idCuota;
    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_hard_delete_poliza(IN p_idPoliza INT)
BEGIN
    DELETE FROM cuotas WHERE poliza_id = p_idPoliza;
    DELETE FROM poliza_anulaciones WHERE poliza_id = p_idPoliza;
    DELETE FROM polizas WHERE idPoliza = p_idPoliza;
    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_hard_delete_cliente(IN p_idCliente INT)
BEGIN
    DELETE c FROM cuotas c
        INNER JOIN polizas p ON c.poliza_id = p.idPoliza
        WHERE p.cliente_id = p_idCliente;
    DELETE pa FROM poliza_anulaciones pa
        INNER JOIN polizas p ON pa.poliza_id = p.idPoliza
        WHERE p.cliente_id = p_idCliente;
    DELETE FROM polizas WHERE cliente_id = p_idCliente;
    DELETE FROM clientes WHERE idCliente = p_idCliente;
    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

-- Índices de auditoría para consultas de auditoría
ALTER TABLE clientes
  ADD INDEX idx_usuario_creacion (usuario_creacion),
  ADD INDEX idx_usuario_modificacion (usuario_modificacion);

-- =====================================================
-- MÓDULO DE SINIESTROS
-- Tablas y procedimientos para gestión de siniestros
-- =====================================================


CREATE TABLE siniestros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    grupo_ramo VARCHAR(50) NOT NULL COMMENT 'RRGG, VEHICULOS, RRHH, OTROS',

    -- Relación robusta
    -- poliza_id es NULL al insertar; el controlador Python lo resuelve desde
    -- el número de póliza y lo actualiza justo después del INSERT.
    poliza_id INT NULL,
    poliza VARCHAR(50) NOT NULL, -- opcional, solo para consulta rápida/visual

    cia VARCHAR(100) NOT NULL COMMENT 'Compañía aseguradora',
    ramo VARCHAR(120) NOT NULL,
    contratante VARCHAR(150) NOT NULL,
    asegurado VARCHAR(150) NOT NULL,

    fec_presentacion_broker DATE COMMENT 'Fecha presentación al Broker',
    fec_aviso_cia DATE COMMENT 'Fecha aviso a compañía',
    fec_presentacion_cia DATE COMMENT 'Fecha presentación a compañía',
    fec_stro DATE COMMENT 'Fecha del siniestro',
    fec_atencion_medica DATE COMMENT 'Fecha atención médica (RRHH)',
    fec_notificacion_broker DATE COMMENT 'Fecha notificación broker (VEHICULOS)',

    hora_siniestro VARCHAR(20),
    quien_reporta VARCHAR(150),
    email TEXT,
    telefonos VARCHAR(100),

    lugar_siniestro TEXT,
    causa TEXT,
    descripcion_hechos TEXT,
    siniestro_no VARCHAR(50) COMMENT 'Número de siniestro de la CIA',
    ejecutivo_cia VARCHAR(100),
    estado VARCHAR(50) DEFAULT 'PENDIENTE' COMMENT 'PENDIENTE, EN_PROCESO, CERRADO, RECHAZADO',

    liquidador_ajustador VARCHAR(150),
    conductor VARCHAR(150),
    tercero VARCHAR(150),
    comisaria VARCHAR(150),
    numero_denuncia VARCHAR(50),
    fec_denuncia_policial DATE,
    fec_entrega_doc_ajustador DATE,
    fec_entrega_doc_cia DATE,
    fec_cia_consentido DATE,
    numero_ajuste VARCHAR(50),

    hora_contacto VARCHAR(20),
    hora_culminacion VARCHAR(20),
    tipo_atencion VARCHAR(50),
    situacion VARCHAR(50),
    placa VARCHAR(20),

    tipo_persona VARCHAR(20),
    titular VARCHAR(150),
    paciente VARCHAR(150),
    diagnostico TEXT,
    coaseguro DECIMAL(15,2) DEFAULT 0.00,
    no_cubierto DECIMAL(15,2) DEFAULT 0.00,

    moneda VARCHAR(10) DEFAULT 'US$',
    monto_siniestro DECIMAL(15,2) DEFAULT 0.00,
    deducible DECIMAL(15,2) DEFAULT 0.00,
    descripcion_deducible TEXT,
    total_indemnizar DECIMAL(15,2) DEFAULT 0.00,
    fec_pago DATE,
    forma_pago VARCHAR(50),
    numero_cheque VARCHAR(50),
    banco VARCHAR(100),

    numero_factura VARCHAR(50),
    monto_pagar_factura DECIMAL(15,2) DEFAULT 0.00,
    fec_vencimiento_factura DATE,
    fec_pago_factura DATE,

    datos_vehiculo JSON,
    datos_denuncia JSON,
    datos_conductor JSON,
    datos_copiloto JSON,
    datos_tercero JSON,
    gastos_presentados JSON,

    usuario_registro VARCHAR(100),
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    usuario_modificacion VARCHAR(100),
    fecha_modificacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    eliminado TINYINT(1) DEFAULT 0,

    INDEX idx_poliza_id (poliza_id),
    INDEX idx_poliza (poliza),
    INDEX idx_grupo_ramo (grupo_ramo),
    INDEX idx_contratante (contratante),
    INDEX idx_estado (estado),
    INDEX idx_fecha_siniestro (fec_stro),
    INDEX idx_cia (cia),
    INDEX idx_eliminado (eliminado),

    CONSTRAINT fk_siniestro_poliza_id
        FOREIGN KEY (poliza_id)
        REFERENCES polizas(idPoliza)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



-- =====================================================
-- TABLAS RELACIONADAS PARA DOCUMENTOS Y BITÁCORA
-- =====================================================


CREATE TABLE siniestro_documentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    siniestro_id INT NOT NULL,
    tipo_documento VARCHAR(100) NOT NULL COMMENT 'INFORME MEDICO, RECETA, PROFORMA, etc.',
    nombre_documento VARCHAR(255),
    numero_documento VARCHAR(50),
    fecha_documento DATE,
    monto DECIMAL(15,2) DEFAULT 0.00,
    archivo_path VARCHAR(500) COMMENT 'Ruta del archivo si está digitalizado',
    observaciones TEXT,
    usuario_registro VARCHAR(100),
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    eliminado TINYINT(1) DEFAULT 0,

    INDEX idx_siniestro (siniestro_id),
    INDEX idx_tipo (tipo_documento),

    CONSTRAINT fk_documento_siniestro FOREIGN KEY (siniestro_id)
        REFERENCES siniestros(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Documentos relacionados a siniestros (principalmente para RRHH)';



CREATE TABLE siniestro_bitacora (
    id INT AUTO_INCREMENT PRIMARY KEY,
    siniestro_id INT NOT NULL,
    fecha DATE NOT NULL,
    hora VARCHAR(20),
    descripcion TEXT NOT NULL,
    responsable VARCHAR(100),
    tipo_actividad VARCHAR(50) COMMENT 'LLAMADA, EMAIL, REUNION, VISITA, etc.',
    usuario_registro VARCHAR(100),
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    eliminado TINYINT(1) DEFAULT 0,

    INDEX idx_siniestro (siniestro_id),
    INDEX idx_fecha (fecha),
    INDEX idx_tipo (tipo_actividad),

    CONSTRAINT fk_bitacora_siniestro FOREIGN KEY (siniestro_id)
        REFERENCES siniestros(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Bitácora de seguimiento de siniestros';



CREATE TABLE siniestro_archivos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    siniestro_id INT NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    tipo_archivo VARCHAR(100) COMMENT 'PDF, IMAGEN, EXCEL, WORD, etc.',
    descripcion TEXT,
    ruta_archivo VARCHAR(500) NOT NULL,
    tamano_bytes BIGINT,
    usuario_subida VARCHAR(100),
    fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP,
    eliminado TINYINT(1) DEFAULT 0,

    INDEX idx_siniestro (siniestro_id),
    INDEX idx_tipo (tipo_archivo),

    CONSTRAINT fk_archivo_siniestro FOREIGN KEY (siniestro_id)
        REFERENCES siniestros(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Archivos adjuntos relacionados a siniestros';

-- =====================================================
-- PROCEDIMIENTOS PARA INSERTAR DATOS RELACIONADOS
-- =====================================================

-- Stored procedures para grupo OTROS: insertar y actualizar
DROP PROCEDURE IF EXISTS sp_insert_siniestro_otros;
DELIMITER $$
CREATE PROCEDURE sp_insert_siniestro_otros(
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_gastos_presentados TEXT,
    IN p_usuario VARCHAR(100)
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    INSERT INTO siniestros (
        grupo_ramo, poliza, cia, ramo, contratante, asegurado,
        fec_stro, hora_siniestro, quien_reporta, email, telefonos,
        lugar_siniestro, causa, descripcion_hechos, siniestro_no, ejecutivo_cia, estado,
        moneda, monto_siniestro, deducible, descripcion_deducible, total_indemnizar,
        fec_pago, forma_pago, numero_cheque, banco,
        numero_factura, monto_pagar_factura, fec_vencimiento_factura, fec_pago_factura,
        gastos_presentados, usuario_registro
    ) VALUES (
        'OTROS', p_poliza, p_cia, p_ramo, p_contratante, p_asegurado,
        p_fec_stro, p_hora_siniestro, p_quien_reporta, p_email, p_telefonos,
        p_lugar_siniestro, p_causa, p_descripcion_hechos, p_siniestro_no, p_ejecutivo_cia, p_estado,
        p_moneda, p_monto_siniestro, p_deducible, p_descripcion_deducible, p_total_indemnizar,
        p_fec_pago, p_forma_pago, p_numero_cheque, p_banco,
        p_numero_factura, p_monto_pagar_factura, p_fec_vencimiento_factura, p_fec_pago_factura,
        p_gastos_presentados, v_usuario_nombre
    );
    SELECT LAST_INSERT_ID() AS id;
END $$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_update_siniestro_otros;
DELIMITER $$
CREATE PROCEDURE sp_update_siniestro_otros(
    IN p_id INT,
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_gastos_presentados TEXT,
    IN p_usuario_edicion VARCHAR(50)
)
BEGIN
    UPDATE siniestros SET
        grupo_ramo = 'OTROS',
        poliza = p_poliza,
        cia = p_cia,
        ramo = p_ramo,
        contratante = p_contratante,
        asegurado = p_asegurado,
        fec_stro = p_fec_stro,
        hora_siniestro = p_hora_siniestro,
        quien_reporta = p_quien_reporta,
        email = p_email,
        telefonos = p_telefonos,
        lugar_siniestro = p_lugar_siniestro,
        causa = p_causa,
        descripcion_hechos = p_descripcion_hechos,
        siniestro_no = p_siniestro_no,
        ejecutivo_cia = p_ejecutivo_cia,
        estado = p_estado,
        moneda = p_moneda,
        monto_siniestro = p_monto_siniestro,
        deducible = p_deducible,
        descripcion_deducible = p_descripcion_deducible,
        total_indemnizar = p_total_indemnizar,
        fec_pago = p_fec_pago,
        forma_pago = p_forma_pago,
        numero_cheque = p_numero_cheque,
        banco = p_banco,
        numero_factura = p_numero_factura,
        monto_pagar_factura = p_monto_pagar_factura,
        fec_vencimiento_factura = p_fec_vencimiento_factura,
        fec_pago_factura = p_fec_pago_factura,
        usuario_edicion = p_usuario_edicion
    WHERE id = p_id;

    SELECT ROW_COUNT() AS affected_rows;
END $$
DELIMITER ;

-- Procedimiento para insertar documento
DROP PROCEDURE IF EXISTS sp_insert_siniestro_documento;

DELIMITER $$
CREATE PROCEDURE sp_insert_siniestro_documento(
    IN p_siniestro_id INT,
    IN p_tipo_documento VARCHAR(100),
    IN p_nombre_documento VARCHAR(255),
    IN p_numero_documento VARCHAR(50),
    IN p_fecha_documento DATE,
    IN p_monto DECIMAL(15,2),
    IN p_archivo_path VARCHAR(500),
    IN p_observaciones TEXT,
    IN p_usuario VARCHAR(50)
)
BEGIN
    INSERT INTO siniestro_documentos (
        siniestro_id, tipo_documento, nombre_documento, numero_documento,
        fecha_documento, monto, archivo_path, observaciones, usuario_registro
    ) VALUES (
        p_siniestro_id, p_tipo_documento, p_nombre_documento, p_numero_documento,
        p_fecha_documento, p_monto, p_archivo_path, p_observaciones, p_usuario
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- Procedimiento para insertar bitácora
DROP PROCEDURE IF EXISTS sp_insert_siniestro_bitacora;

DELIMITER $$
CREATE PROCEDURE sp_insert_siniestro_bitacora(
    IN p_siniestro_id INT,
    IN p_fecha DATE,
    IN p_hora VARCHAR(20),
    IN p_descripcion TEXT,
    IN p_responsable VARCHAR(100),
    IN p_tipo_actividad VARCHAR(50),
    IN p_usuario VARCHAR(50)
)
BEGIN
    INSERT INTO siniestro_bitacora (
        siniestro_id, fecha, hora, descripcion, responsable, tipo_actividad, usuario_registro
    ) VALUES (
        p_siniestro_id, p_fecha, p_hora, p_descripcion, p_responsable, p_tipo_actividad, p_usuario
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- Procedimiento para insertar archivo
DROP PROCEDURE IF EXISTS sp_insert_siniestro_archivo;

DELIMITER $$
CREATE PROCEDURE sp_insert_siniestro_archivo(
    IN p_siniestro_id INT,
    IN p_nombre_archivo VARCHAR(255),
    IN p_tipo_archivo VARCHAR(100),
    IN p_descripcion TEXT,
    IN p_ruta_archivo VARCHAR(500),
    IN p_tamano_bytes BIGINT,
    IN p_usuario VARCHAR(50)
)
BEGIN
    INSERT INTO siniestro_archivos (
        siniestro_id, nombre_archivo, tipo_archivo, descripcion,
        ruta_archivo, tamano_bytes, usuario_subida
    ) VALUES (
        p_siniestro_id, p_nombre_archivo, p_tipo_archivo, p_descripcion,
        p_ruta_archivo, p_tamano_bytes, p_usuario
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- =====================================================
-- VISTAS ÚTILES
-- =====================================================

-- Se mantienen los DROP VIEW para no causar errores si existen vistas previas,
-- las definiciones de las vistas han sido eliminadas a petición del usuario.

DROP VIEW IF EXISTS v_siniestros_resumen;
-- Vista consolidada de siniestros eliminada del script.

DROP VIEW IF EXISTS v_siniestros_rrgg;
-- Vista para siniestros RRGG eliminada del script.

DROP VIEW IF EXISTS v_siniestros_vehiculos;
-- Vista para siniestros VEHICULOS eliminada del script.

DROP VIEW IF EXISTS v_siniestros_rrhh;
-- Vista para siniestros RRHH eliminada del script.

-- =====================================================
-- PROCEDIMIENTOS DE ACTUALIZACIÓN DE SINIESTROS (RRGG / RRHH / VEHICULOS)
-- Estos procedimientos se nombran como sp_update_siniestro_* para coincidir con los controladores.
-- =====================================================

DROP PROCEDURE IF EXISTS sp_update_siniestro_rrgg;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_update_siniestro_rrgg(
    IN p_id INT,
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_presentacion_broker DATE,
    IN p_fec_aviso_cia DATE,
    IN p_fec_presentacion_cia DATE,
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_liquidador_ajustador VARCHAR(150),
    IN p_conductor VARCHAR(150),
    IN p_tercero VARCHAR(150),
    IN p_comisaria VARCHAR(150),
    IN p_numero_denuncia VARCHAR(50),
    IN p_fec_denuncia_policial DATE,
    IN p_fec_entrega_doc_ajustador DATE,
    IN p_fec_entrega_doc_cia DATE,
    IN p_fec_cia_consentido DATE,
    IN p_numero_ajuste VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_usuario_modificacion VARCHAR(50)
)
BEGIN
    UPDATE siniestros SET
        poliza = p_poliza,
        cia = p_cia,
        ramo = p_ramo,
        contratante = p_contratante,
        asegurado = p_asegurado,
        fec_presentacion_broker = p_fec_presentacion_broker,
        fec_aviso_cia = p_fec_aviso_cia,
        fec_presentacion_cia = p_fec_presentacion_cia,
        fec_stro = p_fec_stro,
        hora_siniestro = p_hora_siniestro,
        quien_reporta = p_quien_reporta,
        email = p_email,
        telefonos = p_telefonos,
        lugar_siniestro = p_lugar_siniestro,
        causa = p_causa,
        descripcion_hechos = p_descripcion_hechos,
        siniestro_no = p_siniestro_no,
        ejecutivo_cia = p_ejecutivo_cia,
        estado = p_estado,
        liquidador_ajustador = p_liquidador_ajustador,
        conductor = p_conductor,
        tercero = p_tercero,
        comisaria = p_comisaria,
        numero_denuncia = p_numero_denuncia,
        fec_denuncia_policial = p_fec_denuncia_policial,
        fec_entrega_doc_ajustador = p_fec_entrega_doc_ajustador,
        fec_entrega_doc_cia = p_fec_entrega_doc_cia,
        fec_cia_consentido = p_fec_cia_consentido,
        numero_ajuste = p_numero_ajuste,
        moneda = p_moneda,
        monto_siniestro = p_monto_siniestro,
        deducible = p_deducible,
        descripcion_deducible = p_descripcion_deducible,
        total_indemnizar = p_total_indemnizar,
        fec_pago = p_fec_pago,
        forma_pago = p_forma_pago,
        numero_cheque = p_numero_cheque,
        banco = p_banco,
        numero_factura = p_numero_factura,
        monto_pagar_factura = p_monto_pagar_factura,
        fec_vencimiento_factura = p_fec_vencimiento_factura,
        fec_pago_factura = p_fec_pago_factura,
        usuario_modificacion = p_usuario_modificacion,
        fecha_modificacion = NOW()
    WHERE id = p_id;

    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;
DROP PROCEDURE IF EXISTS sp_update_siniestro_vehiculos;
DELIMITER $$

CREATE DEFINER=`root`@`localhost` PROCEDURE sp_update_siniestro_vehiculos(
    IN p_id INT,
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_presentacion_broker DATE,
    IN p_fec_aviso_cia DATE,
    IN p_fec_presentacion_cia DATE,
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_tipo_atencion VARCHAR(50),
    IN p_situacion VARCHAR(50),
    IN p_placa VARCHAR(20),
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_usuario_modificacion VARCHAR(50)
)
BEGIN
    UPDATE siniestros SET
        poliza = p_poliza,
        cia = p_cia,
        ramo = p_ramo,
        contratante = p_contratante,
        asegurado = p_asegurado,
        fec_presentacion_broker = p_fec_presentacion_broker,
        fec_aviso_cia = p_fec_aviso_cia,
        fec_presentacion_cia = p_fec_presentacion_cia,
        fec_stro = p_fec_stro,
        hora_siniestro = p_hora_siniestro,
        quien_reporta = p_quien_reporta,
        email = p_email,
        telefonos = p_telefonos,
        lugar_siniestro = p_lugar_siniestro,
        causa = p_causa,
        tipo_atencion = p_tipo_atencion,
        situacion = p_situacion,
        placa = p_placa,
        siniestro_no = p_siniestro_no,
        ejecutivo_cia = p_ejecutivo_cia,
        estado = p_estado,
        moneda = p_moneda,
        monto_siniestro = p_monto_siniestro,
        deducible = p_deducible,
        total_indemnizar = p_total_indemnizar,
        fec_pago = p_fec_pago,
        forma_pago = p_forma_pago,
        numero_cheque = p_numero_cheque,
        banco = p_banco,
        numero_factura = p_numero_factura,
        monto_pagar_factura = p_monto_pagar_factura,
        fec_vencimiento_factura = p_fec_vencimiento_factura,
        fec_pago_factura = p_fec_pago_factura,
        usuario_modificacion = p_usuario_modificacion,
        fecha_modificacion = NOW()
    WHERE id = p_id;

    SELECT ROW_COUNT() AS affected_rows;
END$$

DELIMITER ;

DROP PROCEDURE IF EXISTS sp_update_siniestro_rrhh;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_update_siniestro_rrhh(
    IN p_id INT,
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_presentacion_broker DATE,
    IN p_fec_aviso_cia DATE,
    IN p_fec_presentacion_cia DATE,
    IN p_fec_stro DATE,
    IN p_fec_atencion_medica DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_coaseguro DECIMAL(15,2),
    IN p_no_cubierto DECIMAL(15,2),
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_gastos_presentados JSON,
    IN p_usuario_modificacion VARCHAR(50)
)
BEGIN
    UPDATE siniestros SET
        poliza = p_poliza,
        cia = p_cia,
        ramo = p_ramo,
        contratante = p_contratante,
        asegurado = p_asegurado,
        fec_presentacion_broker = p_fec_presentacion_broker,
        fec_aviso_cia = p_fec_aviso_cia,
        fec_presentacion_cia = p_fec_presentacion_cia,
        fec_stro = p_fec_stro,
        fec_atencion_medica = p_fec_atencion_medica,
        hora_siniestro = p_hora_siniestro,
        quien_reporta = p_quien_reporta,
        email = p_email,
        telefonos = p_telefonos,
        lugar_siniestro = p_lugar_siniestro,
        causa = p_causa,
        descripcion_hechos = p_descripcion_hechos,
        siniestro_no = p_siniestro_no,
        ejecutivo_cia = p_ejecutivo_cia,
        estado = p_estado,
        moneda = p_moneda,
        monto_siniestro = p_monto_siniestro,
        deducible = p_deducible,
        descripcion_deducible = p_descripcion_deducible,
        coaseguro = p_coaseguro,
        no_cubierto = p_no_cubierto,
        total_indemnizar = p_total_indemnizar,
        fec_pago = p_fec_pago,
        forma_pago = p_forma_pago,
        numero_cheque = p_numero_cheque,
        banco = p_banco,
        numero_factura = p_numero_factura,
        monto_pagar_factura = p_monto_pagar_factura,
        fec_vencimiento_factura = p_fec_vencimiento_factura,
        fec_pago_factura = p_fec_pago_factura,
        gastos_presentados = p_gastos_presentados,
        usuario_modificacion = p_usuario_modificacion,
        fecha_modificacion = NOW()
    WHERE id = p_id;

    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;



CREATE TABLE IF NOT EXISTS usos (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    estado ENUM('Activado','Inactivo') NOT NULL DEFAULT 'Activado',
    PRIMARY KEY (id),
    UNIQUE KEY uq_usos_nombre (nombre),
    KEY idx_usos_estado (estado),
    KEY idx_usos_nombre (nombre)
) ENGINE=InnoDB   DEFAULT CHARSET=utf8mb4   COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS clases (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(150) NOT NULL,
    costo_soat DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    estado ENUM('Activado','Inactivo') NOT NULL DEFAULT 'Activado',
    PRIMARY KEY (id),
    UNIQUE KEY uq_clases_nombre (nombre),
    KEY idx_clases_estado (estado),
    KEY idx_clases_nombre (nombre)
) ENGINE=InnoDB   DEFAULT CHARSET=utf8mb4   COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS marcas (
    id INT NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(120) NOT NULL,
    estado ENUM('Activado','Inactivo') NOT NULL DEFAULT 'Activado',
    PRIMARY KEY (id),
    UNIQUE KEY uq_marcas_nombre (nombre),
    KEY idx_marcas_estado (estado),
    KEY idx_marcas_nombre (nombre)
) ENGINE=InnoDB   DEFAULT CHARSET=utf8mb4   COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS modelos (
    id INT NOT NULL AUTO_INCREMENT,
    marca_id INT NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    estado ENUM('Activado','Inactivo') NOT NULL DEFAULT 'Activado',
    PRIMARY KEY (id),
    KEY idx_modelos_marca_id (marca_id),
    KEY idx_modelos_estado (estado),
    KEY idx_modelos_nombre (nombre),
    KEY idx_modelos_marca_estado (marca_id, estado),
    UNIQUE KEY uq_modelo_por_marca (marca_id, nombre),
    CONSTRAINT fk_modelos_marcas
        FOREIGN KEY (marca_id) REFERENCES marcas(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB   DEFAULT CHARSET=utf8mb4   COLLATE=utf8mb4_unicode_ci;


CREATE OR REPLACE VIEW vw_modelos_marcas AS SELECT
    mo.id AS modelo_id,
    mo.nombre AS modelo_nombre,
    mo.estado AS modelo_estado,
    ma.id AS marca_id,
    ma.nombre AS marca_nombre,
    ma.estado AS marca_estado
FROM modelos mo
JOIN marcas ma ON ma.id = mo.marca_id;



DROP PROCEDURE IF EXISTS sp_listar_usos;
DELIMITER $$
CREATE PROCEDURE sp_listar_usos()
BEGIN
    SELECT id, nombre, estado
    FROM usos
    ORDER BY nombre ASC;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_insertar_uso;
DELIMITER $$
CREATE PROCEDURE sp_insertar_uso(
    IN p_nombre VARCHAR(120),
    OUT p_new_id INT )
BEGIN
    IF TRIM(p_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre de uso no puede estar vacío';
    END IF;

    INSERT INTO usos (nombre)
    VALUES (TRIM(p_nombre))
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

    SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_delete_uso;
DELIMITER $$
CREATE PROCEDURE sp_delete_uso(
    IN p_id INT,
    OUT p_deleted INT )
BEGIN
    DELETE FROM usos WHERE id = p_id;
    SET p_deleted = ROW_COUNT();
END$$
DELIMITER ;

-- =========================================================
-- PROCEDIMIENTOS: CLASES
-- =========================================================

DROP PROCEDURE IF EXISTS sp_listar_clases;
DELIMITER $$
CREATE PROCEDURE sp_listar_clases()
BEGIN
    SELECT id, nombre, costo_soat, estado
    FROM clases
    ORDER BY nombre ASC;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_insertar_clase;
DELIMITER $$
CREATE PROCEDURE sp_insertar_clase(
    IN p_nombre VARCHAR(150),
    IN p_costo_soat DECIMAL(10,2),
    OUT p_new_id INT )
BEGIN
    IF TRIM(p_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre de clase no puede estar vacío';
    END IF;

    INSERT INTO clases (nombre, costo_soat)
    VALUES (TRIM(p_nombre), IFNULL(p_costo_soat, 0.00))
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

    SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_delete_clase;
DELIMITER $$
CREATE PROCEDURE sp_delete_clase(
    IN p_id INT,
    OUT p_deleted INT )
BEGIN
    DELETE FROM clases WHERE id = p_id;
    SET p_deleted = ROW_COUNT();
END$$
DELIMITER ;

-- =========================================================
-- PROCEDIMIENTOS: MARCAS
-- =========================================================

DROP PROCEDURE IF EXISTS sp_listar_marcas;
DELIMITER $$
CREATE PROCEDURE sp_listar_marcas()
BEGIN
    SELECT id, nombre, estado
    FROM marcas
    ORDER BY nombre ASC;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_insertar_marca;
DELIMITER $$
CREATE PROCEDURE sp_insertar_marca(
    IN p_nombre VARCHAR(120),
    OUT p_new_id INT )
BEGIN
    IF TRIM(p_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre de marca no puede estar vacío';
    END IF;

    INSERT INTO marcas (nombre)
    VALUES (TRIM(p_nombre))
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

    SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_delete_marca;
DELIMITER $$
CREATE PROCEDURE sp_delete_marca(
    IN p_id INT,
    OUT p_deleted INT )
BEGIN
    IF EXISTS (SELECT 1 FROM modelos WHERE marca_id = p_id) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'No se puede eliminar la marca: existen modelos asociados';
    END IF;

    DELETE FROM marcas WHERE id = p_id;
    SET p_deleted = ROW_COUNT();
END$$
DELIMITER ;

-- =========================================================
-- PROCEDIMIENTOS: MODELOS
-- =========================================================

DROP PROCEDURE IF EXISTS sp_listar_modelos;
DELIMITER $$
CREATE PROCEDURE sp_listar_modelos()
BEGIN
    SELECT
        mo.id AS modelo_id,
        ma.id AS marca_id,
        ma.nombre AS marca,
        mo.nombre AS modelo,
        mo.estado
    FROM modelos mo
    JOIN marcas ma ON ma.id = mo.marca_id
    ORDER BY ma.nombre, mo.nombre;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_insertar_modelo;
DELIMITER $$
CREATE PROCEDURE sp_insertar_modelo(
    IN p_marca_id INT,
    IN p_nombre VARCHAR(150),
    OUT p_new_id INT )
BEGIN
    IF TRIM(p_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre de modelo no puede estar vacío';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM marcas WHERE id = p_marca_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La marca indicada no existe';
    END IF;

    INSERT INTO modelos (marca_id, nombre)
    VALUES (p_marca_id, TRIM(p_nombre))
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

    SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

-- Inserta modelo resolviendo marca por nombre (sin tabla temporal)
DROP PROCEDURE IF EXISTS sp_insertar_modelo_por_nombres;
DELIMITER $$
CREATE PROCEDURE sp_insertar_modelo_por_nombres(
    IN  p_marca_nombre  VARCHAR(120),
    IN  p_modelo_nombre VARCHAR(150),
    OUT p_marca_id      INT,
    OUT p_modelo_id     INT )
BEGIN
    IF TRIM(p_marca_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre de marca no puede estar vacío';
    END IF;

    IF TRIM(p_modelo_nombre) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El nombre de modelo no puede estar vacío';
    END IF;

    INSERT INTO marcas (nombre)
    VALUES (TRIM(p_marca_nombre))
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

    SET p_marca_id = LAST_INSERT_ID();

    INSERT INTO modelos (marca_id, nombre)
    VALUES (p_marca_id, TRIM(p_modelo_nombre))
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

    SET p_modelo_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_delete_modelo;
DELIMITER $$
CREATE PROCEDURE sp_delete_modelo(
    IN p_id INT,
    OUT p_deleted INT )
BEGIN
    DELETE FROM modelos WHERE id = p_id;
    SET p_deleted = ROW_COUNT();
END$$
DELIMITER ;

-- =====================================================
-- SP ADICIONALES MÓDULO SINIESTROS (compatibilidad)
-- Pegar debajo del final de tu script actual
-- =====================================================

-- 1) Obtener siniestro por ID
DROP PROCEDURE IF EXISTS sp_get_siniestro_by_id;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_get_siniestro_by_id(IN p_id INT)
BEGIN
    SELECT
        id, grupo_ramo,
        COALESCE(CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR), poliza) AS poliza,
        cia, ramo, contratante, asegurado,
        fec_presentacion_broker, fec_aviso_cia, fec_presentacion_cia,
        fec_stro, hora_siniestro,
        quien_reporta,
        COALESCE(CAST(AES_DECRYPT(FROM_BASE64(email), @SIS_KEY) AS CHAR), email) AS email,
        COALESCE(CAST(AES_DECRYPT(FROM_BASE64(telefonos), @SIS_KEY) AS CHAR), telefonos) AS telefonos,
        lugar_siniestro, causa, descripcion_hechos,
        siniestro_no, ejecutivo_cia, estado,
        liquidador_ajustador, conductor, tercero, comisaria, numero_denuncia,
        fec_denuncia_policial, fec_entrega_doc_ajustador, fec_entrega_doc_cia, fec_cia_consentido,
        numero_ajuste,
        fec_notificacion_broker, hora_contacto, hora_culminacion, tipo_atencion,
        situacion, placa,
        fec_atencion_medica, tipo_persona, titular, paciente, diagnostico,
        coaseguro, no_cubierto,
        moneda, monto_siniestro, deducible, descripcion_deducible, total_indemnizar,
        fec_pago, forma_pago, numero_cheque,
        COALESCE(CAST(AES_DECRYPT(FROM_BASE64(banco), @SIS_KEY) AS CHAR), banco) AS banco,
        numero_factura, monto_pagar_factura, fec_vencimiento_factura, fec_pago_factura,
        datos_vehiculo, datos_denuncia, datos_conductor, datos_copiloto, datos_tercero,
        gastos_presentados,
        usuario_registro, usuario_modificacion,
        fecha_registro, fecha_modificacion,
        eliminado, poliza_id
    FROM siniestros
    WHERE id = p_id
    LIMIT 1;
END$$
DELIMITER ;

-- 2) Eliminar siniestro (físico)
DROP PROCEDURE IF EXISTS sp_delete_siniestro;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_delete_siniestro(IN p_id INT)
BEGIN
    DELETE FROM siniestros
    WHERE id = p_id;

    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

-- 3) Insert genérico siniestro
DROP PROCEDURE IF EXISTS sp_insert_siniestro;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_insert_siniestro(
    IN p_grupo_ramo VARCHAR(20),
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_presentacion_broker DATE,
    IN p_fec_aviso_cia DATE,
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_liquidador_ajustador VARCHAR(150),
    IN p_conductor VARCHAR(150),
    IN p_tercero VARCHAR(150),
    IN p_comisaria VARCHAR(150),
    IN p_numero_denuncia VARCHAR(50),
    IN p_fec_denuncia_policial DATE,
    IN p_fec_entrega_doc_ajustador DATE,
    IN p_fec_entrega_doc_cia DATE,
    IN p_fec_cia_consentido DATE,
    IN p_numero_ajuste VARCHAR(50),
    IN p_fec_notificacion_broker DATE,
    IN p_hora_contacto VARCHAR(20),
    IN p_hora_culminacion VARCHAR(20),
    IN p_tipo_atencion VARCHAR(50),
    IN p_fec_presentacion_cia DATE,
    IN p_situacion VARCHAR(50),
    IN p_placa VARCHAR(20),
    IN p_fec_atencion_medica DATE,
    IN p_tipo_persona VARCHAR(20),
    IN p_titular VARCHAR(150),
    IN p_paciente VARCHAR(150),
    IN p_diagnostico TEXT,
    IN p_coaseguro DECIMAL(15,2),
    IN p_no_cubierto DECIMAL(15,2),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_datos_vehiculo JSON,
    IN p_datos_denuncia JSON,
    IN p_datos_conductor JSON,
    IN p_datos_copiloto JSON,
    IN p_datos_tercero JSON,
    IN p_gastos_presentados JSON,
    IN p_usuario_registro VARCHAR(100)
)
BEGIN
    DECLARE v_usuario_registro_nombre VARCHAR(100);
    SET v_usuario_registro_nombre = NULL;
    IF p_usuario_registro IS NOT NULL AND TRIM(p_usuario_registro) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_registro_nombre
        FROM usuarios
        WHERE username = p_usuario_registro
        LIMIT 1;
    END IF;
    IF v_usuario_registro_nombre IS NULL OR v_usuario_registro_nombre = '' THEN
        SET v_usuario_registro_nombre = p_usuario_registro;
    END IF;

    INSERT INTO siniestros (
        grupo_ramo, poliza, cia, ramo, contratante, asegurado,
        fec_presentacion_broker, fec_aviso_cia, fec_stro, hora_siniestro,
        quien_reporta, email, telefonos, lugar_siniestro, causa, descripcion_hechos,
        siniestro_no, ejecutivo_cia, estado,
        liquidador_ajustador, conductor, tercero, comisaria, numero_denuncia,
        fec_denuncia_policial, fec_entrega_doc_ajustador, fec_entrega_doc_cia,
        fec_cia_consentido, numero_ajuste,
        fec_notificacion_broker, hora_contacto, hora_culminacion, tipo_atencion,
        fec_presentacion_cia, situacion, placa,
        fec_atencion_medica, tipo_persona, titular, paciente, diagnostico,
        coaseguro, no_cubierto,
        moneda, monto_siniestro, deducible, descripcion_deducible, total_indemnizar,
        fec_pago, forma_pago, numero_cheque, banco,
        numero_factura, monto_pagar_factura, fec_vencimiento_factura, fec_pago_factura,
        datos_vehiculo, datos_denuncia, datos_conductor, datos_copiloto, datos_tercero,
        gastos_presentados,
        usuario_registro
    ) VALUES (
        p_grupo_ramo, TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)), p_cia, p_ramo, p_contratante, p_asegurado,
        p_fec_presentacion_broker, p_fec_aviso_cia, p_fec_stro, p_hora_siniestro,
        p_quien_reporta, TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_telefonos, @SIS_KEY)), p_lugar_siniestro, p_causa, p_descripcion_hechos,
        p_siniestro_no, p_ejecutivo_cia, p_estado,
        p_liquidador_ajustador, p_conductor, p_tercero, p_comisaria, p_numero_denuncia,
        p_fec_denuncia_policial, p_fec_entrega_doc_ajustador, p_fec_entrega_doc_cia,
        p_fec_cia_consentido, p_numero_ajuste,
        p_fec_notificacion_broker, p_hora_contacto, p_hora_culminacion, p_tipo_atencion,
        p_fec_presentacion_cia, p_situacion, p_placa,
        p_fec_atencion_medica, p_tipo_persona, p_titular, p_paciente, p_diagnostico,
        p_coaseguro, p_no_cubierto,
        p_moneda, p_monto_siniestro, p_deducible, p_descripcion_deducible, p_total_indemnizar,
        p_fec_pago, p_forma_pago, p_numero_cheque, TO_BASE64(AES_ENCRYPT(p_banco, @SIS_KEY)),
        p_numero_factura, p_monto_pagar_factura, p_fec_vencimiento_factura, p_fec_pago_factura,
        p_datos_vehiculo, p_datos_denuncia, p_datos_conductor, p_datos_copiloto, p_datos_tercero,
        p_gastos_presentados,
        v_usuario_registro_nombre
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- 4) Insertar siniestro OTROS
DROP PROCEDURE IF EXISTS sp_insert_siniestro_otros;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_insert_siniestro_otros(
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_gastos_presentados TEXT,
    IN p_usuario VARCHAR(100)
)
BEGIN
    DECLARE v_usuario_nombre VARCHAR(100);
    SET v_usuario_nombre = NULL;
    IF p_usuario IS NOT NULL AND TRIM(p_usuario) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_nombre
        FROM usuarios
        WHERE username = p_usuario
        LIMIT 1;
    END IF;
    IF v_usuario_nombre IS NULL OR v_usuario_nombre = '' THEN
        SET v_usuario_nombre = p_usuario;
    END IF;

    INSERT INTO siniestros (
        grupo_ramo, poliza, cia, ramo, contratante, asegurado,
        fec_stro, hora_siniestro, quien_reporta, email, telefonos,
        lugar_siniestro, causa, descripcion_hechos, siniestro_no, ejecutivo_cia, estado,
        moneda, monto_siniestro, deducible, descripcion_deducible, total_indemnizar,
        fec_pago, forma_pago, numero_cheque, banco,
        numero_factura, monto_pagar_factura, fec_vencimiento_factura, fec_pago_factura,
        gastos_presentados, usuario_registro
    ) VALUES (
        'OTROS', TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)), p_cia, p_ramo, p_contratante, p_asegurado,
        p_fec_stro, p_hora_siniestro, p_quien_reporta, TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_telefonos, @SIS_KEY)),
        p_lugar_siniestro, p_causa, p_descripcion_hechos, p_siniestro_no, p_ejecutivo_cia, p_estado,
        p_moneda, p_monto_siniestro, p_deducible, p_descripcion_deducible, p_total_indemnizar,
        p_fec_pago, p_forma_pago, p_numero_cheque, TO_BASE64(AES_ENCRYPT(p_banco, @SIS_KEY)),
        p_numero_factura, p_monto_pagar_factura, p_fec_vencimiento_factura, p_fec_pago_factura,
        CAST(p_gastos_presentados AS JSON), v_usuario_nombre
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- 5) Insertar siniestro RRGG
DROP PROCEDURE IF EXISTS sp_insert_siniestro_rrgg;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_insert_siniestro_rrgg(
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_presentacion_broker DATE,
    IN p_fec_aviso_cia DATE,
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_liquidador_ajustador VARCHAR(150),
    IN p_conductor VARCHAR(150),
    IN p_tercero VARCHAR(150),
    IN p_comisaria VARCHAR(150),
    IN p_numero_denuncia VARCHAR(50),
    IN p_fec_denuncia_policial DATE,
    IN p_fec_entrega_doc_ajustador DATE,
    IN p_fec_entrega_doc_cia DATE,
    IN p_fec_cia_consentido DATE,
    IN p_numero_ajuste VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_usuario_registro VARCHAR(50)
)
BEGIN
    INSERT INTO siniestros (
        grupo_ramo, poliza, cia, ramo, contratante, asegurado,
        fec_presentacion_broker, fec_aviso_cia, fec_stro, hora_siniestro,
        quien_reporta, email, telefonos, lugar_siniestro, causa, descripcion_hechos,
        siniestro_no, ejecutivo_cia, estado,
        liquidador_ajustador, conductor, tercero, comisaria, numero_denuncia,
        fec_denuncia_policial, fec_entrega_doc_ajustador, fec_entrega_doc_cia,
        fec_cia_consentido, numero_ajuste,
        moneda, monto_siniestro, deducible, descripcion_deducible, total_indemnizar,
        fec_pago, forma_pago, numero_cheque, banco,
        numero_factura, monto_pagar_factura, fec_vencimiento_factura, fec_pago_factura,
        usuario_registro
    ) VALUES (
        'RRGG', TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)), p_cia, p_ramo, p_contratante, p_asegurado,
        p_fec_presentacion_broker, p_fec_aviso_cia, p_fec_stro, p_hora_siniestro,
        p_quien_reporta, TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_telefonos, @SIS_KEY)), p_lugar_siniestro, p_causa, p_descripcion_hechos,
        p_siniestro_no, p_ejecutivo_cia, p_estado,
        p_liquidador_ajustador, p_conductor, p_tercero, p_comisaria, p_numero_denuncia,
        p_fec_denuncia_policial, p_fec_entrega_doc_ajustador, p_fec_entrega_doc_cia,
        p_fec_cia_consentido, p_numero_ajuste,
        p_moneda, p_monto_siniestro, p_deducible, p_descripcion_deducible, p_total_indemnizar,
        p_fec_pago, p_forma_pago, p_numero_cheque, TO_BASE64(AES_ENCRYPT(p_banco, @SIS_KEY)),
        p_numero_factura, p_monto_pagar_factura, p_fec_vencimiento_factura, p_fec_pago_factura,
        p_usuario_registro
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- 6) Insertar siniestro RRHH
DROP PROCEDURE IF EXISTS sp_insert_siniestro_rrhh;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_insert_siniestro_rrhh(
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_presentacion_broker DATE,
    IN p_fec_atencion_medica DATE,
    IN p_fec_aviso_cia DATE,
    IN p_fec_presentacion_cia DATE,
    IN p_fec_cia_consentido DATE,
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_tipo_persona VARCHAR(20),
    IN p_titular VARCHAR(150),
    IN p_paciente VARCHAR(150),
    IN p_diagnostico TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_coaseguro DECIMAL(15,2),
    IN p_no_cubierto DECIMAL(15,2),
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_gastos_presentados JSON,
    IN p_usuario_registro VARCHAR(50)
)
BEGIN
    INSERT INTO siniestros (
        grupo_ramo, poliza, cia, ramo, contratante, asegurado,
        fec_presentacion_broker, fec_atencion_medica, fec_aviso_cia, fec_presentacion_cia, fec_cia_consentido,
        quien_reporta, email, telefonos, tipo_persona, titular, paciente, diagnostico,
        siniestro_no, ejecutivo_cia, estado,
        moneda, monto_siniestro, deducible, descripcion_deducible, coaseguro, no_cubierto, total_indemnizar,
        fec_pago, forma_pago, numero_cheque, banco,
        numero_factura, monto_pagar_factura, fec_vencimiento_factura, fec_pago_factura,
        gastos_presentados, usuario_registro
    ) VALUES (
        'RRHH', TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)), p_cia, p_ramo, p_contratante, p_asegurado,
        p_fec_presentacion_broker, p_fec_atencion_medica, p_fec_aviso_cia, p_fec_presentacion_cia, p_fec_cia_consentido,
        p_quien_reporta, TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_telefonos, @SIS_KEY)), p_tipo_persona, p_titular, p_paciente, p_diagnostico,
        p_siniestro_no, p_ejecutivo_cia, p_estado,
        p_moneda, p_monto_siniestro, p_deducible, p_descripcion_deducible, p_coaseguro, p_no_cubierto, p_total_indemnizar,
        p_fec_pago, p_forma_pago, p_numero_cheque, TO_BASE64(AES_ENCRYPT(p_banco, @SIS_KEY)),
        p_numero_factura, p_monto_pagar_factura, p_fec_vencimiento_factura, p_fec_pago_factura,
        p_gastos_presentados, p_usuario_registro
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- 7) Insertar siniestro VEHICULOS
DROP PROCEDURE IF EXISTS sp_insert_siniestro_vehiculos;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_insert_siniestro_vehiculos(
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_notificacion_broker DATE,
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email VARCHAR(100),
    IN p_telefonos VARCHAR(100),
    IN p_hora_contacto VARCHAR(20),
    IN p_hora_culminacion VARCHAR(20),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_tipo_atencion VARCHAR(50),
    IN p_fec_presentacion_cia DATE,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_situacion VARCHAR(50),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_datos_vehiculo JSON,
    IN p_datos_denuncia JSON,
    IN p_datos_conductor JSON,
    IN p_datos_copiloto JSON,
    IN p_datos_tercero JSON,
    IN p_usuario_registro VARCHAR(50)
)
BEGIN
    INSERT INTO siniestros (
        grupo_ramo, poliza, cia, ramo, contratante, asegurado,
        fec_notificacion_broker, fec_stro, hora_siniestro,
        quien_reporta, email, telefonos, hora_contacto, hora_culminacion,
        lugar_siniestro, causa, tipo_atencion, fec_presentacion_cia,
        siniestro_no, ejecutivo_cia, estado, situacion,
        moneda, monto_siniestro, deducible, descripcion_deducible, total_indemnizar,
        fec_pago, forma_pago, numero_cheque, banco,
        numero_factura, monto_pagar_factura, fec_vencimiento_factura, fec_pago_factura,
        datos_vehiculo, datos_denuncia, datos_conductor, datos_copiloto, datos_tercero,
        usuario_registro
    ) VALUES (
        'VEHICULOS', TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)), p_cia, p_ramo, p_contratante, p_asegurado,
        p_fec_notificacion_broker, p_fec_stro, p_hora_siniestro,
        p_quien_reporta, TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_telefonos, @SIS_KEY)), p_hora_contacto, p_hora_culminacion,
        p_lugar_siniestro, p_causa, p_tipo_atencion, p_fec_presentacion_cia,
        p_siniestro_no, p_ejecutivo_cia, p_estado, p_situacion,
        p_moneda, p_monto_siniestro, p_deducible, p_descripcion_deducible, p_total_indemnizar,
        p_fec_pago, p_forma_pago, p_numero_cheque, TO_BASE64(AES_ENCRYPT(p_banco, @SIS_KEY)),
        p_numero_factura, p_monto_pagar_factura, p_fec_vencimiento_factura, p_fec_pago_factura,
        p_datos_vehiculo, p_datos_denuncia, p_datos_conductor, p_datos_copiloto, p_datos_tercero,
        p_usuario_registro
    );

    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- 8) Listar siniestros
DROP PROCEDURE IF EXISTS sp_list_siniestros;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_list_siniestros()
BEGIN
    SELECT
        id, grupo_ramo, contratante, poliza, cia, ramo, fec_stro,
        causa, siniestro_no, monto_siniestro, estado, ejecutivo_cia, placa,
        fecha_registro AS creado_en
    FROM siniestros
    WHERE eliminado = 0
    ORDER BY fecha_registro DESC;
END$$
DELIMITER ;

-- 9) Listar siniestros por póliza
DROP PROCEDURE IF EXISTS sp_list_siniestros_por_poliza;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_list_siniestros_por_poliza(IN p_poliza VARCHAR(50))
BEGIN
    SELECT
        id, grupo_ramo, contratante, poliza, cia, ramo, fec_stro,
        causa, siniestro_no, monto_siniestro, estado, ejecutivo_cia, placa,
        fecha_registro AS creado_en
    FROM siniestros
    WHERE poliza = p_poliza
      AND eliminado = 0
    ORDER BY fec_stro DESC;
END$$
DELIMITER ;

-- 10) Update genérico siniestro
DROP PROCEDURE IF EXISTS sp_update_siniestro;
DELIMITER $$
CREATE DEFINER=`root`@`localhost` PROCEDURE sp_update_siniestro(
    IN p_id INT,
    IN p_grupo_ramo VARCHAR(20),
    IN p_poliza VARCHAR(50),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_contratante VARCHAR(150),
    IN p_asegurado VARCHAR(150),
    IN p_fec_presentacion_broker DATE,
    IN p_fec_aviso_cia DATE,
    IN p_fec_stro DATE,
    IN p_hora_siniestro VARCHAR(20),
    IN p_quien_reporta VARCHAR(150),
    IN p_email TEXT,
    IN p_telefonos VARCHAR(100),
    IN p_lugar_siniestro TEXT,
    IN p_causa TEXT,
    IN p_descripcion_hechos TEXT,
    IN p_siniestro_no VARCHAR(50),
    IN p_ejecutivo_cia VARCHAR(100),
    IN p_estado VARCHAR(50),
    IN p_liquidador_ajustador VARCHAR(150),
    IN p_conductor VARCHAR(150),
    IN p_tercero VARCHAR(150),
    IN p_comisaria VARCHAR(150),
    IN p_numero_denuncia VARCHAR(50),
    IN p_fec_denuncia_policial DATE,
    IN p_fec_entrega_doc_ajustador DATE,
    IN p_fec_entrega_doc_cia DATE,
    IN p_fec_cia_consentido DATE,
    IN p_numero_ajuste VARCHAR(50),
    IN p_fec_notificacion_broker DATE,
    IN p_hora_contacto VARCHAR(20),
    IN p_hora_culminacion VARCHAR(20),
    IN p_tipo_atencion VARCHAR(50),
    IN p_fec_presentacion_cia DATE,
    IN p_situacion VARCHAR(50),
    IN p_placa VARCHAR(20),
    IN p_fec_atencion_medica DATE,
    IN p_tipo_persona VARCHAR(20),
    IN p_titular VARCHAR(150),
    IN p_paciente VARCHAR(150),
    IN p_diagnostico TEXT,
    IN p_coaseguro DECIMAL(15,2),
    IN p_no_cubierto DECIMAL(15,2),
    IN p_moneda VARCHAR(10),
    IN p_monto_siniestro DECIMAL(15,2),
    IN p_deducible DECIMAL(15,2),
    IN p_descripcion_deducible TEXT,
    IN p_total_indemnizar DECIMAL(15,2),
    IN p_fec_pago DATE,
    IN p_forma_pago VARCHAR(50),
    IN p_numero_cheque VARCHAR(50),
    IN p_banco VARCHAR(100),
    IN p_numero_factura VARCHAR(50),
    IN p_monto_pagar_factura DECIMAL(15,2),
    IN p_fec_vencimiento_factura DATE,
    IN p_fec_pago_factura DATE,
    IN p_datos_vehiculo JSON,
    IN p_datos_denuncia JSON,
    IN p_datos_conductor JSON,
    IN p_datos_copiloto JSON,
    IN p_datos_tercero JSON,
    IN p_gastos_presentados JSON,
    IN p_usuario_edicion VARCHAR(50)
)
BEGIN
    UPDATE siniestros SET
        grupo_ramo = p_grupo_ramo,
        poliza = TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)),
        cia = p_cia,
        ramo = p_ramo,
        contratante = p_contratante,
        asegurado = p_asegurado,
        fec_presentacion_broker = p_fec_presentacion_broker,
        fec_aviso_cia = p_fec_aviso_cia,
        fec_stro = p_fec_stro,
        hora_siniestro = p_hora_siniestro,
        quien_reporta = p_quien_reporta,
        email = TO_BASE64(AES_ENCRYPT(p_email, @SIS_KEY)),
        telefonos = TO_BASE64(AES_ENCRYPT(p_telefonos, @SIS_KEY)),
        lugar_siniestro = p_lugar_siniestro,
        causa = p_causa,
        descripcion_hechos = p_descripcion_hechos,
        siniestro_no = p_siniestro_no,
        ejecutivo_cia = p_ejecutivo_cia,
        estado = p_estado,
        liquidador_ajustador = p_liquidador_ajustador,
        conductor = p_conductor,
        tercero = p_tercero,
        comisaria = p_comisaria,
        numero_denuncia = p_numero_denuncia,
        fec_denuncia_policial = p_fec_denuncia_policial,
        fec_entrega_doc_ajustador = p_fec_entrega_doc_ajustador,
        fec_entrega_doc_cia = p_fec_entrega_doc_cia,
        fec_cia_consentido = p_fec_cia_consentido,
        numero_ajuste = p_numero_ajuste,
        fec_notificacion_broker = p_fec_notificacion_broker,
        hora_contacto = p_hora_contacto,
        hora_culminacion = p_hora_culminacion,
        tipo_atencion = p_tipo_atencion,
        fec_presentacion_cia = p_fec_presentacion_cia,
        situacion = p_situacion,
        placa = p_placa,
        fec_atencion_medica = p_fec_atencion_medica,
        tipo_persona = p_tipo_persona,
        titular = p_titular,
        paciente = p_paciente,
        diagnostico = p_diagnostico,
        coaseguro = p_coaseguro,
        no_cubierto = p_no_cubierto,
        moneda = p_moneda,
        monto_siniestro = p_monto_siniestro,
        deducible = p_deducible,
        descripcion_deducible = p_descripcion_deducible,
        total_indemnizar = p_total_indemnizar,
        fec_pago = p_fec_pago,
        forma_pago = p_forma_pago,
        numero_cheque = p_numero_cheque,
        banco = TO_BASE64(AES_ENCRYPT(p_banco, @SIS_KEY)),
        numero_factura = p_numero_factura,
        monto_pagar_factura = p_monto_pagar_factura,
        fec_vencimiento_factura = p_fec_vencimiento_factura,
        fec_pago_factura = p_fec_pago_factura,
        datos_vehiculo = p_datos_vehiculo,
        datos_denuncia = p_datos_denuncia,
        datos_conductor = p_datos_conductor,
        datos_copiloto = p_datos_copiloto,
        datos_tercero = p_datos_tercero,
        gastos_presentados = p_gastos_presentados,
        usuario_modificacion = p_usuario_edicion,
        fecha_modificacion = NOW()
    WHERE id = p_id;

    SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;

-- rol 
-- 1. Create roles table
CREATE TABLE IF NOT EXISTS roles (
    idRol INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Insert default roles
INSERT INTO roles (nombre, descripcion) VALUES
('BROKER', 'Todo acceso'),
('EJECUTIVO DE CUENTAS', 'Acceso a todo, menos a maestros y solo mira y ELIMINA'),
('OPERADOR', 'Acceso a todo, menos a maestros, adiciona, actualiza, NO ELIMINA, Reportes sin comisiones'),
('SUB AGENTE', 'Acceso a solo sus cuentas, NO maestros, adiciona, NO ELIMINA, Reporte estado de cuenta y producción')
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion);

-- 3. Add id_rol to usuarios table if it doesn't exist
-- We use a stored procedure to check if column exists to avoid errors on re-run or just run ALTER and ignore error
SET @dbname = DATABASE();
SET @tablename = 'usuarios';
SET @columnname = 'id_rol';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE usuarios ADD COLUMN id_rol INT NULL AFTER password;'
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add foreign key if not exists (similar logic or just try add)
-- For simplicity, we assume it might fail if exists, but in a script we'd check constraint_name.
-- Here we just run it, if it fails it fails (or we wrap in block).
-- Let's try to be safe.
SET @constraintname = 'fk_usuarios_roles';
SET @preparedStatementFK = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (constraint_name = @constraintname)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE usuarios ADD CONSTRAINT fk_usuarios_roles FOREIGN KEY (id_rol) REFERENCES roles(idRol);'
));
PREPARE addFK FROM @preparedStatementFK;
EXECUTE addFK;
DEALLOCATE PREPARE addFK;

-- 3.1. Add foto_perfil and color_avatar if they don't exist
SET @columnname_foto = 'foto_perfil';
SET @preparedStatementFoto = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname_foto)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE usuarios ADD COLUMN foto_perfil VARCHAR(255) NULL AFTER nombre;'
));
PREPARE addFoto FROM @preparedStatementFoto;
EXECUTE addFoto;
DEALLOCATE PREPARE addFoto;

SET @columnname_color = 'color_avatar';
SET @preparedStatementColor = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname_color)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE usuarios ADD COLUMN color_avatar VARCHAR(20) DEFAULT "#3b82f6" AFTER foto_perfil;'
));
PREPARE addColor FROM @preparedStatementColor;
EXECUTE addColor;
DEALLOCATE PREPARE addColor;


-- Add id_ejecutivo column to usuarios and FK to ejecutivos (if not exists)
SET @dbname = DATABASE();
SET @tablename = 'usuarios';
SET @columnname = 'id_ejecutivo';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE usuarios ADD COLUMN id_ejecutivo INT NULL AFTER id_rol;'
));
PREPARE alterIfNotExists2 FROM @preparedStatement;
EXECUTE alterIfNotExists2;
DEALLOCATE PREPARE alterIfNotExists2;

-- Add FK constraint to ejecutivos.idEjecutivo if not exists
SET @constraintname2 = 'fk_usuarios_ejecutivos';
SET @preparedStatementFK2 = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (constraint_name = @constraintname2)
  ) > 0,
  'SELECT 1',
  'ALTER TABLE usuarios ADD CONSTRAINT fk_usuarios_ejecutivos FOREIGN KEY (id_ejecutivo) REFERENCES ejecutivos(idEjecutivo);'
));
PREPARE addFK2 FROM @preparedStatementFK2;
EXECUTE addFK2;
DEALLOCATE PREPARE addFK2;


-- 4. Update sp_login_usuario to return role info
DROP PROCEDURE IF EXISTS sp_login_usuario;
DELIMITER $$
CREATE PROCEDURE sp_login_usuario(IN p_username VARCHAR(50))
BEGIN
    SELECT u.id, u.username, u.password, u.id_rol, u.nombre, u.foto_perfil, u.color_avatar, r.nombre as rol_nombre
    FROM usuarios u
    LEFT JOIN roles r ON u.id_rol = r.idRol
    WHERE u.username = p_username
    LIMIT 1;
END$$
DELIMITER ;

-- 5. Update sp_listar_usuarios to return role info
DROP PROCEDURE IF EXISTS sp_listar_usuarios;
DELIMITER $$
CREATE PROCEDURE sp_listar_usuarios()
BEGIN
    SELECT u.id, u.username, u.nombre, u.estado, u.id_rol, r.nombre as rol
    FROM usuarios u
    LEFT JOIN roles r ON u.id_rol = r.idRol
    ORDER BY COALESCE(NULLIF(TRIM(u.nombre), ''), u.username) ASC;
END$$
DELIMITER ;

-- 6. Procedure to update user role
DROP PROCEDURE IF EXISTS sp_actualizar_usuario_rol;
DELIMITER $$
CREATE PROCEDURE sp_actualizar_usuario_rol(
    IN p_id INT,
    IN p_id_rol INT
)
BEGIN
    UPDATE usuarios SET id_rol = p_id_rol WHERE id = p_id;
END$$
DELIMITER ;

-- 7. Procedure to list roles
DROP PROCEDURE IF EXISTS sp_listar_roles;
DELIMITER $$
CREATE PROCEDURE sp_listar_roles()
BEGIN
    SELECT idRol, nombre, descripcion FROM roles ORDER BY idRol;
END$$
DELIMITER ;


-- =====================================================
-- STORED PROCEDURE PARA CARGA MASIVA DE SOAT
-- =====================================================
DROP PROCEDURE IF EXISTS sp_insert_poliza_soat_masivo;
DELIMITER $$
CREATE PROCEDURE sp_insert_poliza_soat_masivo (
    IN p_numero_documento VARCHAR(20),
    IN p_tipo_doc VARCHAR(10),
    IN p_asegurado VARCHAR(150),
    IN p_cia VARCHAR(100),
    IN p_ramo VARCHAR(120),
    IN p_poliza VARCHAR(50),
    IN p_recibo VARCHAR(50),
    IN p_contrato_nro VARCHAR(50),
    IN p_nro VARCHAR(50),
    IN p_moneda VARCHAR(20),
    IN p_fecha_emision DATE,
    IN p_vig_desde DATE,
    IN p_vig_hasta DATE,
    IN p_ultimo_dia_pago DATE,
    IN p_fecha_vencimiento DATE,
    IN p_tipo_vigencia VARCHAR(50),
    IN p_endosatario VARCHAR(150),
    IN p_forma_pago VARCHAR(30),
    IN p_sub_agente VARCHAR(250),
    IN p_ejecutivo VARCHAR(250),
    IN p_asegurada VARCHAR(150),
    IN p_motivo VARCHAR(200),
    IN p_prima_comercial DECIMAL(15,2),
    IN p_prima_neta DECIMAL(15,2),
    IN p_prima_comercial_igv DECIMAL(15,2),
    IN p_prima_total DECIMAL(15,2),
    IN p_porc_compania DECIMAL(10,3),
    IN p_imp_compania DECIMAL(15,3),
    IN p_porc_subagente DECIMAL(10,3),
    IN p_imp_subagente DECIMAL(15,3),
    IN p_ramos_producto VARCHAR(120),
    IN p_estado VARCHAR(20),
    IN p_pdf_path VARCHAR(255),
    IN p_usuario_registro VARCHAR(100),
    IN p_datos_vehiculo JSON,
    IN p_codigo_agente VARCHAR(50)
)
BEGIN
    DECLARE v_cliente_id INT;
    DECLARE v_exists INT DEFAULT 0;
    DECLARE v_msg VARCHAR(255);
    DECLARE v_key VARCHAR(50);
    DECLARE v_poliza_id INT;
    DECLARE v_usuario_registro_nombre VARCHAR(100);

    -- Validar que el cliente existe
    SELECT idCliente INTO v_cliente_id
    FROM clientes
    WHERE (
            CAST(AES_DECRYPT(FROM_BASE64(numero_documento), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR CAST(AES_DECRYPT(numero_documento, @SIS_KEY) AS CHAR)            COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
         OR numero_documento COLLATE utf8mb4_0900_ai_ci = p_numero_documento COLLATE utf8mb4_0900_ai_ci
    )
      AND activo = 1
    LIMIT 1;

    IF v_cliente_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Cliente no existe';
    END IF;

    -- Normalizar clave de duplicado
    SET v_key = NULLIF(TRIM(IFNULL(p_contrato_nro, '')), '');
    IF v_key IS NULL THEN
        SET v_key = NULLIF(TRIM(IFNULL(p_recibo, '')), '');
    END IF;

    -- Validación de duplicados: poliza + (contrato_nro|recibo), acotado por cliente
    IF COALESCE(p_poliza, '') <> '' AND COALESCE(v_key, '') <> '' THEN
        SELECT COUNT(*) INTO v_exists
        FROM polizas
        WHERE cliente_id = v_cliente_id
          AND (
            CAST(AES_DECRYPT(FROM_BASE64(poliza), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
            OR CAST(AES_DECRYPT(poliza, @SIS_KEY) AS CHAR)           COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
            OR poliza                                               COLLATE utf8mb4_0900_ai_ci = p_poliza COLLATE utf8mb4_0900_ai_ci
          )
          AND (
            CAST(AES_DECRYPT(FROM_BASE64(contrato_nro), @SIS_KEY) AS CHAR) COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
            OR CAST(AES_DECRYPT(contrato_nro, @SIS_KEY) AS CHAR)           COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
            OR contrato_nro                                               COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
            OR CAST(AES_DECRYPT(FROM_BASE64(recibo), @SIS_KEY) AS CHAR)    COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
            OR CAST(AES_DECRYPT(recibo, @SIS_KEY) AS CHAR)                COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
            OR recibo                                                     COLLATE utf8mb4_0900_ai_ci = v_key COLLATE utf8mb4_0900_ai_ci
          );

        IF v_exists > 0 THEN
            SET v_msg = CONCAT('Póliza ya existe: ', p_poliza);
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
        END IF;
    END IF;

    SET v_usuario_registro_nombre = NULL;
    IF p_usuario_registro IS NOT NULL AND TRIM(p_usuario_registro) <> '' THEN
        SELECT COALESCE(NULLIF(TRIM(nombre), ''), username)
        INTO v_usuario_registro_nombre
        FROM usuarios
        WHERE username COLLATE utf8mb4_0900_ai_ci = p_usuario_registro COLLATE utf8mb4_0900_ai_ci
        LIMIT 1;
    END IF;
    IF v_usuario_registro_nombre IS NULL OR v_usuario_registro_nombre = '' THEN
        SET v_usuario_registro_nombre = p_usuario_registro;
    END IF;

    -- Insertar póliza
    INSERT INTO polizas (
        cliente_id, asegurado, cia, ramo,
        poliza, recibo, contrato_nro, nro,
        moneda, fecha_emision, vig_desde, vig_hasta, ultimo_dia_pago,
        fecha_vencimiento, tipo_vigencia, endosatario, forma_pago,
        sub_agente, ejecutivo, tipo_doc,
        asegurada, motivo, prima_comercial, prima_neta, prima_comercial_igv, prima_total,
        porc_compania, imp_compania, porc_subagente, imp_subagente,
        ramos_producto, estado, usuario_registro, datos_vehiculo, codigo_agente
    ) VALUES (
        v_cliente_id, TO_BASE64(AES_ENCRYPT(p_asegurado, @SIS_KEY)), p_cia, p_ramo,
        TO_BASE64(AES_ENCRYPT(p_poliza, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_recibo, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_contrato_nro, @SIS_KEY)), TO_BASE64(AES_ENCRYPT(p_nro, @SIS_KEY)),
        p_moneda, p_fecha_emision, p_vig_desde, p_vig_hasta, p_ultimo_dia_pago,
        p_fecha_vencimiento, p_tipo_vigencia, p_endosatario, p_forma_pago,
        p_sub_agente, p_ejecutivo, p_tipo_doc,
        p_asegurada, p_motivo, p_prima_comercial, p_prima_neta, p_prima_comercial_igv, p_prima_total,
        p_porc_compania, p_imp_compania, p_porc_subagente, p_imp_subagente,
        p_ramos_producto, p_estado, v_usuario_registro_nombre, p_datos_vehiculo, p_codigo_agente
    );

    SET v_poliza_id = LAST_INSERT_ID();

    -- Insertar archivo si existe
    IF p_pdf_path IS NOT NULL AND p_pdf_path <> '' THEN
        INSERT INTO poliza_archivos (poliza_id, numero_poliza, ruta_archivo, nombre_original, ramo, producto, usuario, compania)
        VALUES (v_poliza_id, p_poliza, p_pdf_path, SUBSTRING_INDEX(p_pdf_path, '/', -1), p_ramo, p_ramos_producto, v_usuario_registro_nombre, p_cia);
    END IF;

    SELECT v_poliza_id AS id;

END$$
DELIMITER ;


-- =========================================================
-- TABLA: AGENTES/VENDEDORES
-- =========================================================
-- =========================================================
-- TABLA: AGENTES/VENDEDORES
-- =========================================================
CREATE TABLE IF NOT EXISTS agentes (
                                       id INT NOT NULL AUTO_INCREMENT,
                                       codigo_agente VARCHAR(50) NOT NULL,
    nombre_vendedor VARCHAR(255) NOT NULL,
    tipo_menor DECIMAL(10,2) NOT NULL DEFAULT 0,
    tipo_regular DECIMAL(10,2) NOT NULL DEFAULT 0,
    estado ENUM('ACTIVO','INACTIVO') NOT NULL DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_agentes_codigo (codigo_agente),
    KEY idx_agentes_estado (estado),
    KEY idx_agentes_nombre (nombre_vendedor)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =========================================================
-- PROCEDIMIENTOS: AGENTES/VENDEDORES
-- =========================================================

DROP PROCEDURE IF EXISTS sp_listar_agentes;
DELIMITER $$
CREATE PROCEDURE sp_listar_agentes()
BEGIN
SELECT id,
       codigo_agente,
       nombre_vendedor,
       tipo_menor,
       tipo_regular,
       estado
FROM agentes
ORDER BY nombre_vendedor ASC;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_insertar_agente;
DELIMITER $$
CREATE PROCEDURE sp_insertar_agente(
    IN p_codigo_agente VARCHAR(50),
    IN p_nombre_vendedor VARCHAR(255),
    IN p_tipo_menor DECIMAL(10,2),
    IN p_tipo_regular DECIMAL(10,2),
    OUT p_new_id INT
)
BEGIN
    IF TRIM(p_codigo_agente) = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El código de agente no puede estar vacío';
END IF;

    IF TRIM(p_nombre_vendedor) = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El nombre del vendedor no puede estar vacío';
END IF;

INSERT INTO agentes (codigo_agente, nombre_vendedor, tipo_menor, tipo_regular)
VALUES (TRIM(p_codigo_agente),
        TRIM(p_nombre_vendedor),
        IFNULL(p_tipo_menor,0),
        IFNULL(p_tipo_regular,0))
    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id);

SET p_new_id = LAST_INSERT_ID();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_delete_agente;
DELIMITER $$
CREATE PROCEDURE sp_delete_agente(
    IN p_id INT,
    OUT p_deleted INT
)
BEGIN
    DELETE FROM agentes WHERE id = p_id;
    SET p_deleted = ROW_COUNT();
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_editar_agente;
DELIMITER $$
CREATE PROCEDURE sp_editar_agente(
    IN p_id            INT,
    IN p_codigo_agente VARCHAR(50),
    IN p_nombre_vendedor VARCHAR(255),
    IN p_tipo_menor    DECIMAL(10,2),
    IN p_tipo_regular  DECIMAL(10,2),
    IN p_estado        ENUM('ACTIVO','INACTIVO')
)
BEGIN
    IF TRIM(p_codigo_agente) = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El código de agente no puede estar vacío';
END IF;

    IF TRIM(p_nombre_vendedor) = '' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'El nombre del vendedor no puede estar vacío';
END IF;

UPDATE agentes
SET codigo_agente   = TRIM(p_codigo_agente),
    nombre_vendedor = TRIM(p_nombre_vendedor),
    tipo_menor      = IFNULL(p_tipo_menor, 0),
    tipo_regular    = IFNULL(p_tipo_regular, 0),
    estado          = IFNULL(p_estado, 'ACTIVO')
WHERE id = p_id;

SELECT ROW_COUNT() AS affected_rows;
END$$
DELIMITER ;
-- ========================================
-- MIGRACIONES Y ALTERACIONES DE TABLAS
-- ========================================

-- Agregar columna datos_vehiculo si no existe
SET @dbname = DATABASE();
SET @tablename = 'polizas';
SET @columnname = 'datos_vehiculo';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' JSON NULL COMMENT ''Datos del vehículo para pólizas SOAT'' AFTER ramos_producto;')
));
PREPARE alterStatement FROM @preparedStatement;
EXECUTE alterStatement;
DEALLOCATE PREPARE alterStatement;

SET @dbname = DATABASE();
SET @tablename = 'comisiones_temp';
SET @columnname = 'qualitas';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' DECIMAL(5,2) NULL AFTER grandia_eps;')
));
PREPARE alterStatement2 FROM @preparedStatement;
EXECUTE alterStatement2;
DEALLOCATE PREPARE alterStatement2;


-- =============================================
-- NUEVA ESTRUCTURA PARA COMISIONES SOAT
-- =============================================

-- 1. Tabla de Tipos de SOAT (Menor / Regular)
CREATE TABLE IF NOT EXISTS tipos_soat (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE, 
    tasa_aas DECIMAL(5,2) NOT NULL,
    tasa_vendedor DECIMAL(5,2) NOT NULL,
    estado ENUM('Activo','Inactivo') DEFAULT 'Activo'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Tabla de Configuracion de Comision Extra
CREATE TABLE IF NOT EXISTS configuracion_comision_extra (
    id INT AUTO_INCREMENT PRIMARY KEY,
    descripcion VARCHAR(150) NOT NULL,
    porcentaje DECIMAL(5,2) NOT NULL,
    estado ENUM('Activo','Inactivo') DEFAULT 'Activo'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Tabla Principal de Configuracion SOAT (Matriz Tipo-Uso-Clase)
CREATE TABLE IF NOT EXISTS configuracion_soat (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo_soat_id INT NOT NULL,
    uso_id INT NOT NULL,
    clase_id INT NOT NULL,
    tasa_final_override DECIMAL(5,2) NULL COMMENT 'Opcional: Si se define, sobrescribe la tasa calculada',
    estado ENUM('Activo','Inactivo') DEFAULT 'Activo',
    
    CONSTRAINT fk_conf_soat_tipo FOREIGN KEY (tipo_soat_id) REFERENCES tipos_soat(id) ON DELETE RESTRICT,
    CONSTRAINT fk_conf_soat_uso FOREIGN KEY (uso_id) REFERENCES usos(id) ON DELETE CASCADE,
    CONSTRAINT fk_conf_soat_clase FOREIGN KEY (clase_id) REFERENCES clases(id) ON DELETE CASCADE,
    
    UNIQUE KEY uq_conf_soat_uso_clase (uso_id, clase_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =============================================
-- DATOS INICIALES (SEMILLA)
-- =============================================

INSERT INTO tipos_soat (nombre, tasa_aas, tasa_vendedor) VALUES
('Menor', 0.10, 0.60),
('Regular', 0.18, 0.70)
ON DUPLICATE KEY UPDATE tasa_aas=VALUES(tasa_aas), tasa_vendedor=VALUES(tasa_vendedor);

INSERT INTO configuracion_comision_extra (descripcion, porcentaje) VALUES
('Socopur y Promotora Genesis', 0.03),
('Cliente filtrado', 0.05)
ON DUPLICATE KEY UPDATE porcentaje=VALUES(porcentaje);

-- Insertar Clases Completas
INSERT IGNORE INTO clases (nombre) VALUES
('Vehiculo Menor'),
('Mototaxi'),
('Automovil'),
('Station Wagon'),
('Cmta. Pick Up/Doble Cabina'),
('Cmta. Pick Up/Cabina Simple'),
('Camioneta Rural hasta 9 Astos'),
('Camioneta Rural Mayor de 9 Astos'),
('Furgoneta'),
('Camioneta panel'),
('Camion Baranda'),
('Camion Furgon'),
('Camion < 12 Ton'),
('Remolcador > 12 Ton'),
('Volquete < 12 Ton'),
('Volquete > 12 Ton'),
('Omnibus');

-- Insertar Usos Completos
INSERT IGNORE INTO usos (nombre) VALUES
('Particular'),
('Urbano'),
('Carga'),
('Interprovincial'),
('Comercial'),
('Transporte personal');

-- =============================================
-- MAPEO DE COMISIONES (CLASE + USO -> TIPO)
-- =============================================

-- 1. CASOS "MENOR" (10% AAS, 60% Vendedor)
-- Motos y Vehiculos Menores (Todos los usos)
INSERT IGNORE INTO configuracion_soat (tipo_soat_id, uso_id, clase_id)
SELECT t.id, u.id, c.id
FROM tipos_soat t
JOIN usos u ON 1=1
JOIN clases c ON c.nombre IN ('Vehiculo Menor', 'Mototaxi')
WHERE t.nombre = 'Menor';

-- Taxis y Urbanos (Station Wagon y Automovil en uso Urbano)
INSERT IGNORE INTO configuracion_soat (tipo_soat_id, uso_id, clase_id)
SELECT t.id, u.id, c.id
FROM tipos_soat t
JOIN usos u ON u.nombre = 'Urbano'
JOIN clases c ON c.nombre IN ('Automovil', 'Station Wagon')
WHERE t.nombre = 'Menor';


-- 2. CASOS "REGULAR" (18% AAS, 70% Vendedor)
-- Automoviles y SW (Uso Particular)
INSERT IGNORE INTO configuracion_soat (tipo_soat_id, uso_id, clase_id)
SELECT t.id, u.id, c.id
FROM tipos_soat t
JOIN usos u ON u.nombre = 'Particular'
JOIN clases c ON c.nombre IN ('Automovil', 'Station Wagon')
WHERE t.nombre = 'Regular';

-- Camionetas y Pick Ups (Multiples usos: Particular, Carga, Comercial, etc)
INSERT IGNORE INTO configuracion_soat (tipo_soat_id, uso_id, clase_id)
SELECT t.id, u.id, c.id
FROM tipos_soat t
JOIN usos u ON u.nombre IN ('Particular', 'Carga', 'Comercial', 'Transporte personal')
JOIN clases c ON c.nombre IN (
    'Cmta. Pick Up/Doble Cabina',
    'Cmta. Pick Up/Cabina Simple',
    'Camioneta Rural hasta 9 Astos',
    'Camioneta Rural Mayor de 9 Astos',
    'Furgoneta',
    'Camioneta panel'
)
WHERE t.nombre = 'Regular';

-- Vehiculos Pesados (Carga)
INSERT IGNORE INTO configuracion_soat (tipo_soat_id, uso_id, clase_id)
SELECT t.id, u.id, c.id
FROM tipos_soat t
JOIN usos u ON u.nombre = 'Carga'
JOIN clases c ON c.nombre IN (
    'Camion Baranda',
    'Camion Furgon',
    'Camion < 12 Ton',
    'Remolcador > 12 Ton',
    'Volquete < 12 Ton',
    'Volquete > 12 Ton'
)
WHERE t.nombre = 'Regular';

-- Omnibus (Interprovincial, Transporte Personal, Urbano)
INSERT IGNORE INTO configuracion_soat (tipo_soat_id, uso_id, clase_id)
SELECT t.id, u.id, c.id
FROM tipos_soat t
JOIN usos u ON u.nombre IN ('Interprovincial', 'Transporte personal', 'Urbano')
JOIN clases c ON c.nombre = 'Omnibus'
WHERE t.nombre = 'Regular';



-- =============================================
-- PROCEDIMIENTO ALMACENADO PARA CALCULO
-- =============================================

DROP PROCEDURE IF EXISTS sp_calcular_comision_soat;
DELIMITER $$
CREATE PROCEDURE sp_calcular_comision_soat(
    IN p_clase_id    INT,
    IN p_uso_id      INT,
    IN p_precio_soat DECIMAL(10,2),
    IN p_extra_ids   VARCHAR(255),
    IN p_codigo_agente VARCHAR(50)   -- porcentaje vendedor viene de tabla agentes
)
BEGIN
    DECLARE v_tipo_soat_nom     VARCHAR(50);
    DECLARE v_tasa_aas          DECIMAL(5,2)  DEFAULT 0;
    DECLARE v_tasa_vendedor     DECIMAL(10,2) DEFAULT 0;
    DECLARE v_factor_aas        DECIMAL(10,6) DEFAULT 0;
    DECLARE v_factor_vendedor   DECIMAL(10,6) DEFAULT 0;
    DECLARE v_comision_aas      DECIMAL(10,2);
    DECLARE v_comision_vendedor DECIMAL(10,2);
    DECLARE v_utilidad          DECIMAL(10,2);
    DECLARE v_extra_total       DECIMAL(10,2) DEFAULT 0.00;

    -- 1. Obtener tasas del tipo SOAT desde configuracion_soat
    SELECT t.nombre, t.tasa_aas, t.tasa_vendedor
    INTO v_tipo_soat_nom, v_tasa_aas, v_tasa_vendedor
    FROM configuracion_soat cs
    JOIN tipos_soat t ON cs.tipo_soat_id = t.id
    WHERE cs.clase_id = p_clase_id AND cs.uso_id = p_uso_id
    LIMIT 1;

    IF v_tasa_aas IS NULL THEN
        SET v_tasa_aas = 0;
    END IF;

    -- 2. Obtener porcentaje vendedor desde tabla agentes según tipo SOAT.
    -- Si el agente no tiene valor configurado, se conserva la tasa general del tipo SOAT.
    IF p_codigo_agente IS NOT NULL AND TRIM(p_codigo_agente) <> '' THEN
        IF v_tipo_soat_nom = 'Menor' THEN
            SELECT COALESCE(NULLIF(tipo_menor, 0), v_tasa_vendedor) INTO v_tasa_vendedor FROM agentes
            WHERE codigo_agente = TRIM(p_codigo_agente) LIMIT 1;
        ELSE
            SELECT COALESCE(NULLIF(tipo_regular, 0), v_tasa_vendedor) INTO v_tasa_vendedor FROM agentes
            WHERE codigo_agente = TRIM(p_codigo_agente) LIMIT 1;
        END IF;
    END IF;

    SET v_tasa_vendedor = IFNULL(v_tasa_vendedor, 0);
    SET v_factor_aas = CASE
        WHEN ABS(v_tasa_aas) <= 1 THEN v_tasa_aas
        ELSE v_tasa_aas / 100
    END;
    SET v_factor_vendedor = CASE
        WHEN ABS(v_tasa_vendedor) <= 1 THEN v_tasa_vendedor
        ELSE v_tasa_vendedor / 100
    END;

    -- 3. Calcular montos
    SET v_comision_aas      = ROUND(p_precio_soat * v_factor_aas, 2);
    SET v_comision_vendedor = ROUND(v_comision_aas * v_factor_vendedor, 2);

    -- 4. Extras
    IF p_extra_ids IS NOT NULL AND LENGTH(p_extra_ids) > 0 THEN
        SELECT IFNULL(SUM(p_precio_soat * (porcentaje / 100)), 0)
        INTO v_extra_total
        FROM configuracion_comision_extra
        WHERE FIND_IN_SET(id, p_extra_ids);
    END IF;

    SET v_utilidad = v_comision_aas - v_comision_vendedor - v_extra_total;

    SELECT
        v_tasa_aas                    AS tasa_aas,
        v_tasa_vendedor               AS tasa_vendedor_pct,
        ROUND(v_comision_aas, 2)      AS monto_comision_aas,
        ROUND(v_comision_vendedor, 2) AS monto_comision_vendedor,
        ROUND(v_extra_total, 2)       AS monto_extras,
        ROUND(v_utilidad, 2)          AS utilidad_empresa;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS sp_recalcular_comisiones_soat_masivo;
DELIMITER $$
CREATE PROCEDURE sp_recalcular_comisiones_soat_masivo(
    IN p_solo_activos TINYINT
)
BEGIN
    -- Alinear tasas maestras al formato factor esperado: 0.10, 0.18, 0.60, 0.70
    UPDATE tipos_soat
    SET tasa_aas = CASE
                       WHEN nombre = 'Menor' THEN 0.10
                       WHEN nombre = 'Regular' THEN 0.18
                       ELSE tasa_aas
                   END,
        tasa_vendedor = CASE
                            WHEN nombre = 'Menor' THEN 0.60
                            WHEN nombre = 'Regular' THEN 0.70
                            ELSE tasa_vendedor
                        END
    WHERE nombre IN ('Menor', 'Regular');

    UPDATE polizas p
    INNER JOIN (
        SELECT
            base.idPoliza,
            base.prima_neta,
            base.tasa_aas,
            CASE
                WHEN base.tipo_soat_nom = 'Menor' AND COALESCE(base.tipo_menor_agente, 0) > 0 THEN base.tipo_menor_agente
                WHEN base.tipo_soat_nom <> 'Menor' AND COALESCE(base.tipo_regular_agente, 0) > 0 THEN base.tipo_regular_agente
                ELSE COALESCE(base.tasa_vendedor, 0)
            END AS tasa_subagente
        FROM (
            SELECT
                p2.idPoliza,
                COALESCE(p2.prima_neta, 0) AS prima_neta,
                COALESCE(a.tipo_menor, 0) AS tipo_menor_agente,
                COALESCE(a.tipo_regular, 0) AS tipo_regular_agente,
                COALESCE(
                    (
                        SELECT ts1.nombre
                        FROM configuracion_soat cs1
                        INNER JOIN tipos_soat ts1 ON ts1.id = cs1.tipo_soat_id
                        WHERE cs1.estado = 'Activo'
                          AND ts1.estado = 'Activo'
                          AND c.id IS NOT NULL
                          AND cs1.clase_id = c.id
                          AND u.id IS NOT NULL
                          AND cs1.uso_id = u.id
                        LIMIT 1
                    ),
                    (
                        SELECT ts2.nombre
                        FROM configuracion_soat cs2
                        INNER JOIN tipos_soat ts2 ON ts2.id = cs2.tipo_soat_id
                        WHERE cs2.estado = 'Activo'
                          AND ts2.estado = 'Activo'
                          AND c.id IS NOT NULL
                          AND cs2.clase_id = c.id
                        LIMIT 1
                    ),
                    ''
                ) AS tipo_soat_nom,
                COALESCE(
                    (
                        SELECT ts1.tasa_aas
                        FROM configuracion_soat cs1
                        INNER JOIN tipos_soat ts1 ON ts1.id = cs1.tipo_soat_id
                        WHERE cs1.estado = 'Activo'
                          AND ts1.estado = 'Activo'
                          AND c.id IS NOT NULL
                          AND cs1.clase_id = c.id
                          AND u.id IS NOT NULL
                          AND cs1.uso_id = u.id
                        LIMIT 1
                    ),
                    (
                        SELECT ts2.tasa_aas
                        FROM configuracion_soat cs2
                        INNER JOIN tipos_soat ts2 ON ts2.id = cs2.tipo_soat_id
                        WHERE cs2.estado = 'Activo'
                          AND ts2.estado = 'Activo'
                          AND c.id IS NOT NULL
                          AND cs2.clase_id = c.id
                        LIMIT 1
                    ),
                    0
                ) AS tasa_aas,
                COALESCE(
                    (
                        SELECT ts1.tasa_vendedor
                        FROM configuracion_soat cs1
                        INNER JOIN tipos_soat ts1 ON ts1.id = cs1.tipo_soat_id
                        WHERE cs1.estado = 'Activo'
                          AND ts1.estado = 'Activo'
                          AND c.id IS NOT NULL
                          AND cs1.clase_id = c.id
                          AND u.id IS NOT NULL
                          AND cs1.uso_id = u.id
                        LIMIT 1
                    ),
                    (
                        SELECT ts2.tasa_vendedor
                        FROM configuracion_soat cs2
                        INNER JOIN tipos_soat ts2 ON ts2.id = cs2.tipo_soat_id
                        WHERE cs2.estado = 'Activo'
                          AND ts2.estado = 'Activo'
                          AND c.id IS NOT NULL
                          AND cs2.clase_id = c.id
                        LIMIT 1
                    ),
                    0
                ) AS tasa_vendedor
            FROM polizas p2
            LEFT JOIN clases c
                ON CONVERT(c.nombre USING utf8mb4) COLLATE utf8mb4_0900_ai_ci =
                   CONVERT(JSON_UNQUOTE(JSON_EXTRACT(p2.datos_vehiculo, '$.clase')) USING utf8mb4) COLLATE utf8mb4_0900_ai_ci
            LEFT JOIN usos u
                ON CONVERT(u.nombre USING utf8mb4) COLLATE utf8mb4_0900_ai_ci =
                   CONVERT(JSON_UNQUOTE(JSON_EXTRACT(p2.datos_vehiculo, '$.uso')) USING utf8mb4) COLLATE utf8mb4_0900_ai_ci
            LEFT JOIN agentes a
                ON a.codigo_agente = TRIM(COALESCE(p2.codigo_agente, ''))
               AND a.estado = 'ACTIVO'
            WHERE (
                    CONVERT(COALESCE(p2.ramo, '') USING utf8mb4) COLLATE utf8mb4_0900_ai_ci LIKE '%SOAT%'
                    OR CONVERT(COALESCE(p2.ramos_producto, '') USING utf8mb4) COLLATE utf8mb4_0900_ai_ci LIKE '%SOAT%'
                  )
              AND (
                    COALESCE(p_solo_activos, 1) = 0
                    OR (
                        p2.activo = 1
                        AND COALESCE(p2.anulado, 0) = 0
                        AND COALESCE(p2.prima_anulada, 0) = 0
                    )
                  )
        ) base
    ) calc
        ON calc.idPoliza = p.idPoliza
    SET p.porc_compania = CASE
                              WHEN ABS(COALESCE(calc.tasa_aas, 0)) > 0 AND ABS(COALESCE(calc.tasa_aas, 0)) <= 1
                                  THEN ROUND(calc.tasa_aas * 100, 2)
                              ELSE ROUND(COALESCE(calc.tasa_aas, 0), 2)
                          END,
        p.imp_compania = ROUND(
            COALESCE(calc.prima_neta, 0) *
            CASE
                WHEN ABS(COALESCE(calc.tasa_aas, 0)) <= 1 THEN COALESCE(calc.tasa_aas, 0)
                ELSE COALESCE(calc.tasa_aas, 0) / 100
            END,
            2
        ),
        p.porc_subagente = CASE
                               WHEN ABS(COALESCE(calc.tasa_subagente, 0)) > 0 AND ABS(COALESCE(calc.tasa_subagente, 0)) <= 1
                                   THEN ROUND(calc.tasa_subagente * 100, 2)
                               ELSE ROUND(COALESCE(calc.tasa_subagente, 0), 2)
                           END,
        p.imp_subagente = ROUND(
            ROUND(
                COALESCE(calc.prima_neta, 0) *
                CASE
                    WHEN ABS(COALESCE(calc.tasa_aas, 0)) <= 1 THEN COALESCE(calc.tasa_aas, 0)
                    ELSE COALESCE(calc.tasa_aas, 0) / 100
                END,
                2
            ) *
            CASE
                WHEN ABS(COALESCE(calc.tasa_subagente, 0)) <= 1 THEN COALESCE(calc.tasa_subagente, 0)
                ELSE COALESCE(calc.tasa_subagente, 0) / 100
            END,
            2
        );

    SELECT ROW_COUNT() AS polizas_actualizadas;
END$$
DELIMITER ;

-- Agregar columna codigo_agente si no existe
SET @dbname = DATABASE();
SET @tablename = 'polizas';
SET @columnname = 'codigo_agente';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(50) NULL COMMENT ''Código de agente/vendedor'' AFTER datos_vehiculo;')
));
PREPARE alterStatement FROM @preparedStatement;
EXECUTE alterStatement;
DEALLOCATE PREPARE alterStatement;

-- ============================================================
-- ALTER TABLE para agregar columna datos_adicionales JSON
-- EJECUTA ESTA CONSULTA EN TU BD EXISTENTE:
-- ============================================================
SET @tablename = 'polizas';
SET @columnname = 'datos_adicionales';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_name = @tablename)
      AND (table_schema = @dbname)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' JSON NULL COMMENT ''Campos adicionales (flete, fob, sobreseguro, nro_factura, ip_ipl_ipf, origen, destino, etd, eta, proveedor, ruta, puerto_embarque, embalaje, certificado, descripcion, cupon, factura, fecha_pago, importe, cuotas)'' AFTER datos_vehiculo;')
));
PREPARE alterStatement FROM @preparedStatement;
EXECUTE alterStatement;
DEALLOCATE PREPARE alterStatement;

CREATE TABLE ubigeo (
    id INT PRIMARY KEY,
    ubigeo CHAR(6) NOT NULL,
    iddist CHAR(2) NOT NULL,
    idprov CHAR(2) NOT NULL,
    iddep CHAR(2) NOT NULL,
    nombdep VARCHAR(100) NOT NULL,
    nombprov VARCHAR(100) NOT NULL,
    nombdist VARCHAR(150) NOT NULL,

    INDEX idx_ubigeo (ubigeo),
    INDEX idx_departamento (iddep),
    INDEX idx_provincia (idprov),
    INDEX idx_distrito (iddist)
);

INSERT INTO agentes 
(codigo_agente, nombre_vendedor, tipo_menor, tipo_regular)
VALUES
('4806','YORK PAMELA PANDURO HIDALGO',0,0),
('12943','PAMELA ARROYO RAMOS',0,0),
('12951','CALDERON LOZADA, WILLIAMS MERCEDES',70,70),
('72575','GABRIELA RUIZ CESPEDES',0,0),
('72576','KEVIN MURRIETA RENGIFO',0,0),
('72830','ANDION RUIZ, MONICA',60,70),
('81566','SAN BENTO AREVALO, SAHARA ISABEL',50,50),
('83550','ENRIQUE INOCENCIO FLORES HUAMANI',0,0),
('86784','CESAR AUGUSTO ARIAS MURGADO',0,0),
('87838','NUNEZ, ENRIQUE',60,70),
('88674','NUNEZ MERMAO, VERONICA DEL PILAR',60,70),
('83122','GABY CAPILLO',50,50),
('7325','THELMA PUJAY',60,70),
('47651','ALOMIA CIELO MAGNA',0,0)
ON DUPLICATE KEY UPDATE
nombre_vendedor = VALUES(nombre_vendedor),
tipo_menor = VALUES(tipo_menor),
tipo_regular = VALUES(tipo_regular);
