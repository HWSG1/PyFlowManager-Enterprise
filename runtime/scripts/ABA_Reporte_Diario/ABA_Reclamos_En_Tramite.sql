SELECT
	TO_CHAR(T.CREACION_GESTION,'dd') AS DIA
	, MONTH(T.CREACION_GESTION)  AS MES
	, YEAR(T.CREACION_GESTION) AS "AÑO"
	, T.ORDEN_ID
	, T.TAREA AS GESTION
	/*CASE
		WHEN T.TAREA IN ('Cambio de Limite TC Adicional',
	        'Canje de Megapuntos con Crédito a TC',
	        'Canje de puntos Cash',
	        'Canje Megapuntos Crédito a Cuenta',
	     --   'Constancia de pagos IP (2)',
	        'Constancia de Pagos Realizados al SAR',
	        'Constancia por Remesas',
	        'Constancia por Recaudaciones',
	        'Constancias de Pagos IP TGR-1',
	        'Disminución límite de Crédito TC Titular',
	        'Eliminación de Flotantes',
	        'Emisión de Estados de Cuenta',
	        'Reversión Cargo Adelanto de Efectivo',
	        'Reversión Cargo por Rehabilitación de Cuenta',
	        'Reversión Cargo por Reposición TC',
	        'Reversión Comisión Adelanto de Efectivo',
	        'Reversion Intereses Corrientes TC',
	        'Reversión Renovación de Membresía TC Adicional',
	        'Reversión Renovación Membresía TC Titular',
	        'Reversión Seguro de Saldo Deuda',
	        'Traslado de Saldo Misma Tarjeta',
	        'Traslado Megapuntos TC a TC',
	        'Customer care Reversión asistencias y seguros',
	        'Customer care Rev Cargos pasivos',
	        'Customer care Rev. Cargo HRE TD',
	        'Reversion de Cobro por pago duplicado PR'
	    ) THEN 'MIGRADAS'
	    ELSE 'NO MIGRADAS'
	    
	END AS TIPO_GESTION */
	/*, CASE WHEN T.TAREA IN ('Cancelación de préstamos por cliente fallecido',
'Cancelación TC por Cliente Fallecido',
'Cancelación TC por Titular',
'Cobro de Poliza Seguros Prestamos (Indemnización)',
'Consumo no Reconocido TC',
'Consumo No Reconocido TD',
'Contracargos ATM Adquirente BASA',
'Devolución Saldo a Favor',
'Reclamo ABA',
'Reclamo Déposito a Cuenta Erronea (Error Cliente)',
'Reclamo por Descuento no Aplicado a Puma',
'Reclamo por Prestamo',
'Reclamo/Activación de Seguros',
'Reclamos ATM MF Depositos',
'Reclamos ATM MF Pagos TC',
'Regularización de Saldos TC',
'Reversión Cargo Adelanto de Efectivo',
'Reversión Cargo Asistencias',
'Reversión Cargo HRE',
'Reversión Cargo por Rehabilitación de Cuenta',
'Reversión Cargo por Reposición TC',
'Reversión Comisión Adelanto de Efectivo',
'Reversión de Cheque de Caja y Certificado',
'Reversión de transacción de días anteriores',
'Reversion Intereses Corrientes TC',
'Reversión Renovación de Membresía TC Adicional',
'Reversión Renovación Membresía TC Titular',
'Reversión Seguro de Saldo Deuda',
'Reversión Tasa de Seguridad Cuenta de Detalle',
'Reversión Tasa de Seguridad TC',
'Quejas, Reconocimientos y Sugerencias',
'Constancia Citas de Pasaporte',
'Constancia de depósitos en agentes bancarios',
'Constancia de Órdenes de pago',
'Constancia de Pagos Realizados al SAR',
'Constancia de Remesas',
'Constancia de Transferencias Enviadas',
'Constancia Préstamos con Saldos Proyectados',
'Customer Care Constancia de Remesas',
'Customer Care Constancia de Remesas',
'Ampliación Límite de Crédito Titular',
'Asignación Megapuntos a TC',
'Asignación Megapuntos TC por Call Center',
'Cambio Categoría TD',
'Cambio de Ciclo',
'Cambio de Fecha de Pago de Prestamo',
'Cambio de Limite TC Adicional',
'Cambios de Productos',
'Cancelación Cuentas Ahorro a solicitud del titular',
'Cancelación TC por Carta Poder',
'Cancelación Total de ahorro programado',
'Cancelación/Mantenimientos de Seguros',
'Cancelaciones de Firma (Cuentas de ahorro y cheque',
'Canje de Megapuntos a Millas',
'Canje de Megapuntos con Crédito a TC',
'Canje de Puntos Cash',
'Canje de Puntos Online',
'Canje Megapuntos Crédito a Cuenta',
'Comprobante Pago de Préstamo',
'Constancias automáticas',
'Constancias de Cotización Cambiaria',
'Constancias de Préstamos Cancelados',
'Constancias No Obligaciones',
'Constancias Varias',
'Cuentas Exoneradas Tasa de Seguridad Entre Bancos',
'Cuotificación de Cargos',
'Customer Care Cambio de límite TC adicional',
'Customer Care Canje de Megapuntos con Credito TC',
'Customer Care Canje de puntos Cash',
'Customer Care Canje Megapuntos Crédito a cuenta',
'Customer Care Eliminación de Flotantes',
'Customer Care Emisión de estados de cuenta',
'Customer Care Rev Cargo por Rehabilitación de cta',
'Customer care Rev Cargos pasivos',
'Customer Care Rev Renov de Membresia TC Adicional',
'Customer Care Rev Renov Membresia TC Titular',
'Customer care Rev. Cargo HRE TD',
'Customer care Reversión asistencias y seguros',
'Customer Care Reversión cargo adelanto de efectivo',
'Customer Care Reversión Intereses Corrientes TC',
'Customer Care Reversión seguro saldo de Deuda',
'Customer Care Traslado de Saldo Misma Tarjeta',
'Customer Care Traslado Megapuntos TC A TC',
'Disminución límite de Crédito TC Titular',
'Eliminación de Flotantes',
'Emisión Tarjeta Débito Nueva/Renovación Mensajería',
'Emisión TD Adicional',
'Finiquitos de Prestamos (Con Pagaré)',
'Finiquitos de Tarjetas de Credito',
'Intra/extrafinanciamiento',
'Liberación de Fondos',
'Liberación de Garantia Hipotecaria',
'Liberación de Garantia Liquida (CDP)',
'Liberación de Garantia Prendaria (Vehiculo)',
'Ligar cuenta adicional a TD',
'Renovación Anticipada TC',
'Reposición PIN TC',
'Reposición PIN TD',
'Reposición TD TGU',
'Retiro ATM Sin Tarjeta/QR',
'Retiro Cajero Automático Basa',
'Retiro Cajero Automático Redes Externas-Internacio',
'Retiro Cajero Automático Redes Internas',
'Retiros ATM Redes externas',
'Solicitud Corta Cuotas TC Uno a Uno',
'Solicitud de Constancias Firmas Auditoras',
'Solicitud de TD nueva TGU',
'Solicitud Extrafinanciamiento',
'Solicitud TC Adicional',
'Solicitud TC Cafetería/Club Deportivo BASA',
'Traslado de Saldo Diferente Tarjeta',
'Traslado de Saldo Misma Tarjeta',
'Traslado Emisor Cambio Límite',
'Traslado Megapuntos TC a TC',
'Traslado TC Emisor Mismo Límite',
'Customer Care Cambio de límite TC adicional',
'Customer Care Canje de Megapuntos con Credito TC',
'Customer Care Canje de puntos Cash',
'Customer Care Canje Megapuntos Crédito a cuenta',
'Customer Care Eliminación de Flotantes',
'Customer Care Emisión de estados de cuenta',
'Customer Care Rev Cargo por Rehabilitación de cta',
'Customer care Rev Cargos pasivos',
'Customer Care Rev Renov de Membresia TC Adicional',
'Customer Care Rev Renov Membresia TC Titular',
'Customer care Rev. Cargo HRE TD',
'Customer care Reversión asistencias y seguros',
'Customer Care Reversión cargo adelanto de efectivo',
'Customer Care Reversión Intereses Corrientes TC',
'Customer Care Reversión seguro saldo de Deuda',
'Customer Care Traslado de Saldo Misma Tarjeta',
'Customer Care Traslado Megapuntos TC A TC' )THEN 'PQRS'
ELSE ' ' END AS TIPO_ORDEN*/
	
	, T.DESCRIPCION AS PASO
	, T.CONCLUSION AS DESENCADENADOR_REAL
	, CASE WHEN (T.DESENCADENADOR='')
		THEN T.CONCLUSION
		ELSE (CASE WHEN (T.DESENCADENADOR IN ('Aprobado (No requiere autorización)', 'Concluido','Cuenta con Disponible')) 	
			THEN 'Aprobado' ELSE T.DESENCADENADOR END) END AS RESOLUCION
	--, T.DEVUELTO
	, T.INGRESO_SIST
	, T.CREACION_GESTION
	, T.FIN_GESTION
	--, T.FECHA_CAMBIO_ESTADO
	, T.FECHA_CREACION_PASO
	, T.ULTIMA_FECHA_PASO
	--, T.FECHA_PLANEADA_PASO
	--, T.CODIGO_CLIENTE_CRM
	--, T.CODIGO_CLIENTE_IBS
	, T.MOTIVO
	--, T.CATEGORIA
	--, T.SUBCATEGORIA
	, T.UNIDAD_ORG
	, T.ESTADO
	, T.CREADO_POR
	--, T.ENCARGADO_PASO
	--, T.PRODUCTO
	--, T.DESCRIPCION_PRODUCTO
	--, T.COD_AGENCIA
	, T.ESTADO_ACTUAL
	--, T.ESTADO_PASO
	--, T.T_PLANEADO_SEG
	--, T.TIEMPO_PLANEADO
	--, T.UNIDAD_TIEMPO_PLANEADO
	--, T.TIEMPO_EXCEDIDO_HORAS
	--, T.TIEMPO_TARDADO_MINUTOS
	--, T.TIEMPO_EXCEDIDO_MINUTOS
	/*, CASE WHEN (CEH.AREA>'A'AND T.TAREA IN ('Emisión Tarjeta Débito Nueva/Renovación Mensajería','Eliminación de Flotantes','Cancelación Total de ahorro programado','Constancia de Remesas','Emisión de Estados de Cuenta','Reversión Comisión Adelanto de Efectivo','Constancia por Recaudaciones','Bloqueo Tarjeta de débito','Cancelación/Mantenimientos de Seguros','Activación Cuenta por Titular o Firma Autorizada','Actualización Clientes','Reposición TD TGU','Actualización Firmas y/o Beneficiarios','Cancelación Cuentas Ahorro a solicitud del titular','Solicitud de Chequeras','Notificación Uso TD en el Exterior','REPOSICIÓN LIBRETA DE AHORRO POR ROBO O EXTRAVÍO','Afiliación Débitos Automáticos','Cambio Categoría TD','Cancelación Cuenta de Cheques a Solcitud del Titul','Requerimiento AOL (Atlantida Online)','Cambio de Fecha de Pago de Prestamo','Consulta de Saldos Cta Ahorro/Cheque, TC, Préstamo','Reposición PIN TC Instantaneo','Bloqueo Tarjeta crédito','Cambio de Ciclo','Constancia Préstamos sin Obligaciones','Desbloqueo de Tarjeta de débito','Reimpresión  de CDP','Acceso Caja de Seguridad','Actualización Firmas / Beneficiarios en Cuentas','Constancia SIAFI','Afiliación AOL (Atlantida Online)','Cancelación Débitos Automáticos','Constancia Activos y Pasivos SIN Saldos ni Promedi','Desbloqueo de Tarjeta de crédito','Notificación Uso TC en el Exterior','Solicitud Cheque de Ventanilla','Constancia Activos y Pasivos CON Saldos y Promedio','Emisión Constancia Embajada Americana','Requerimiento Mensajitos Atlántida','Liberación de Garantia Hipotecaria','Consumo no Reconocido TC','Consumo No Reconocido TD','Reposición de TC','Liberación de Garantia Liquida (CDP)','Liberación de Garantia Prendaria (Vehiculo)','Cancelación TC por Titular','Reposición PIN TD','Cancelación Cta de Ahorro/Cheques cliente fallecid','Desembolso bajo línea de crédito','Liberación de Fondos','Reposición PIN TC','Cancelación TC por Cliente Fallecido','Creación Múltiple de Habilitantes','Emisión TD Nueva Instantánea','Solicitud de TD nueva TGU','Cancelación Caja de Seguridad','Envió TD y Docs. Cuenta Web al Extranjero','Renovación Anticipada TC','Cancelación Cuenta de Ahorro/Cheques carta poder','Emisión TD Adicional','Reclamos ATM MF Depósitos Cuenta Con PIN','Cancelación TC por Carta Poder','Desembolso Parcial','Emisión Tarjeta Débito de Sucursal/Agencia','Reclamos ATM MF Pagos TC','Activación de Cuentas con Carta Poder','Afiliación Tarjeta de Debito','Finiquitos de Tarjetas de Credito','Contracargos ATM Adquirente BASA','Reclamo por Prestamo','Reclamo/Activación de Seguros','Cancelación de CDP/Bono Caja Solicitud del Titular','Constancia para TC','Adición/Cancelación de Firma','Afiliación ahorro programado','Cambios de Productos','Constancia de Transferencias Enviadas','Constancia Préstamos con Saldos Proyectados','Constancias No Obligaciones','Finiquitos de Prestamos (Con Pagaré)','Ligar cuenta adicional a TD','Retiro Parcial de ahorro programado','Reversión Cargo Asistencias','Actualizacion de Cliente Onboarding','Cancelación de préstamos por cliente fallecido','Cancelaciones de Firma (Cuentas de ahorro y cheque','Constancias de Préstamos Cancelados','Constancias de Transferencias Recibidas','Emisión Tarjeta Débito Nueva (Mensajería)','Hoja de Reclamación','Impresión CDP/Bono caja por renovación automatica','Llamada de Bienvenida','Mantenimiento CDP/Bono de Caja','Rev. Tasa de Seguridad Cuenta Detalle (Dólar)','Reversión de transacción de días anteriores','Reversión Intereses Corrientes PPT','Solicitud Corta Cuotas TC (Pre Aprobado)','Suscripción Caja de Seguridad','Transacciones AOL no Reconocidas','Afiliacion de  LBTR','Aumentos de limite de TD (clientes en el exterior)','Cancelación de CDP/Bono Caja Cliente Fallecido','Comprobante Pago de Préstamo','Constancia Citas de Pasaporte','Constancia de Órdenes de pago','Constancias de Cotización Cambiaria','Embargos','Liberación de endoso AFP','Mantenimiento ACH PRONTO','Pago de Préstamos en Ventanilla','Quejas, reconocimientos y sugerencias','Reversión Adelanto de Efectivo en Ventanilla','Solicitud Intrafinanciamiento','Cambio Fechas de Pagos de Préstamos en Mismo Mes','Cancelación de CDP / Bono de caja','Cancelación de Cuentas','Canje de Megapuntos Crédito TC por Plan de Pagos','Impresión de CDP  por renovación automática','Notificaciones por Casos Phishing AOL','Reactivación Cuenta Por Titular o Firma','Reimpresión de CDP / Bono de Caja por Deterioro','Suspensión Pago Cheque propio','Transferencias al exterior','Traslado de Saldo Misma Tarjeta PPT','Afiliación de Pago de Remesas con autorización tel','Afiliación Mensajitos Atlántida','Afiliación Tarjeta de Débito','Aumento de Límite TC Preaprobado','Cambio ofici Retene CTA CKS/ Direc EC TC','Cancelación Depósito No Cuenta','Conciliación de cuentas','Constancia de depósitos en agentes bancarios','Digitalización-Indexado Documentos ATASA','Requerimiento AOL (Atlantida Online)/ACH','Solicitud TC Pre Aprobada','Traslado de Emisor Cambio Límite "Preaprobado"','Traslado de Saldo Diferente Tarjeta PPT','Venta de divisas','Afiliacion ACH Lading Page','Afiliación Servicios Digitales','Afiliacion VAP Landing Page','Bloqueo TC por Monitoreo','Cancelación Caja de Seguridad por Titular','Cancelación Cuenta por Cliente Fallecido','Cancelación de Prestamos','Despignoración / Liberación de CDP','Eliminación de Diferidos y Retenidos','Emisión de constancias varias','Envío de Remesas Moneygram','Gestiones tasa de seguridad','Liberación de vehículo /Traspaso SEASA','Nota de débito','Registro de Pago de Remesa con autorización telefó','Reimpresión estados cuenta en Agencia','Solicitud de Constancias de Pago de Impuestos','Solicitud de Impresión de Estados de Cuenta','Solicitud TC Cafetería/Club Deportivo BASA','Subasta de Divisas','Suspensión Pago Cheque a cargo Banco del Exterior','Traslado Emisor de Tarjeta de Débito'))
		 	THEN 'NO NECESITA'
		 WHEN (CEH.AREA>'A'AND T.TAREA IN ('Reversión Renovación Membresía TC Titular','Reversión Seguro de Saldo Deuda','Reversión Cargo HRE','Reversion Intereses Corrientes TC','Canje de Megapuntos con Crédito a TC','Canje Megapuntos Crédito a Cuenta','Reversión Cargo Adelanto de Efectivo','Reversión Cargo por Rehabilitación de Cuenta','Reversión Cargo por Reposición TC','Reversión Renovación de Membresía TC Adicional','Traslado de Saldo Misma Tarjeta','Cambio de Limite TC Adicional','Canje de Puntos Cash','Disminución límite de Crédito TC Titular','Traslado Megapuntos TC a TC','Retiro Cajero Automático Basa','Retiros ATM Redes externas','Solicitud TC Adicional','Traslado TC Emisor Mismo Límite','Retiro Cajero Automático Redes Internas','Traslado Emisor Cambio Límite','Cambio de Nombre a Embozar','Retiro Cajero Automático Redes Externas-Internacio','Cuotificación de Cargos','Solicitud Corta Cuotas TC Uno a Uno','Reversión Tasa de Seguridad','Ampliación Límite de Crédito Titular','Asignación Megapuntos a TC','Canje de Megapuntos a Millas','Devolución Saldo a Favor','Regularización de Saldos TC','Traslado de Saldo Diferente Tarjeta','Solicitud Extrafinanciamiento','Cancelación CDP Cliente Fallecido/Carta Poder','Reversión Tasa de Seguridad TC','Solicitud  Aumento Limite temporal (Override)','Reclamo ABA','Reclamo No se Reconoce el Cobro'))
			THEN 'SI'
		 ELSE 'N/A'	END AS "NOTIFICACION CONTACT"
	, CASE WHEN (CEH.AREA IS NULL AND T.TAREA IN ('Emisión Tarjeta Débito Nueva/Renovación Mensajería','Reclamo por Reversión de Cobro','Reposición Libreta de Ahorro','Emisión de Estados de Cuenta','Constancia por Recaudaciones','Bloqueo Tarjeta de débito','Cancelación/Mantenimientos de Seguros','Activación Cuenta por Titular o Firma Autorizada','Actualización Clientes','Reposición TD TGU','Actualización Firmas y/o Beneficiarios','Cancelación Cuentas Ahorro a solicitud del titular','Solicitud de Chequeras','Notificación Uso TD en el Exterior','REPOSICIÓN LIBRETA DE AHORRO POR ROBO O EXTRAVÍO','Afiliación Débitos Automáticos','Cancelación Cuenta de Cheques a Solcitud del Titul','Requerimiento AOL (Atlantida Online)','Cambio de Fecha de Pago de Prestamo','Consulta de Saldos Cta Ahorro/Cheque, TC, Préstamo','Reposición PIN TC Instantaneo','Bloqueo Tarjeta crédito','Constancia Préstamos sin Obligaciones','Desbloqueo de Tarjeta de débito','Reimpresión  de CDP','Acceso Caja de Seguridad','Actualización Firmas / Beneficiarios en Cuentas','Constancia SIAFI','Afiliación AOL (Atlantida Online)','Cancelación Débitos Automáticos','Constancia Activos y Pasivos SIN Saldos ni Promedi','Desbloqueo de Tarjeta de crédito','Notificación Uso TC en el Exterior','Solicitud Cheque de Ventanilla','Constancia Activos y Pasivos CON Saldos y Promedio','Emisión Constancia Embajada Americana','Requerimiento Mensajitos Atlántida','Liberación de Garantia Hipotecaria','Consumo no Reconocido TC','Consumo No Reconocido TD','Reposición de TC','Liberación de Garantia Liquida (CDP)','Liberación de Garantia Prendaria (Vehiculo)','Cancelación TC por Titular','Cancelación Cta de Ahorro/Cheques cliente fallecid','Desembolso bajo línea de crédito','Cancelación TC por Cliente Fallecido','Creación Múltiple de Habilitantes','Emisión TD Nueva Instantánea','Cancelación Caja de Seguridad','Envió TD y Docs. Cuenta Web al Extranjero','Cancelación Cuenta de Ahorro/Cheques carta poder','Emisión TD Adicional','Cancelación TC por Carta Poder','Emisión Tarjeta Débito de Sucursal/Agencia','Reclamos ATM MF Pagos TC','Activación de Cuentas con Carta Poder','Afiliación Tarjeta de Debito','Finiquitos de Tarjetas de Credito','Contracargos ATM Adquirente BASA','Reclamo por Prestamo','Cancelación de CDP/Bono Caja Solicitud del Titular','Constancia para TC','Adición/Cancelación de Firma','Cambios de Productos','Actualizacion de Cliente Onboarding','Cancelación de préstamos por cliente fallecido','Cancelaciones de Firma (Cuentas de ahorro y cheque','Emisión Tarjeta Débito Nueva (Mensajería)','Hoja de Reclamación','Impresión CDP/Bono caja por renovación automatica','Llamada de Bienvenida','Solicitud Corta Cuotas TC (Pre Aprobado)','Suscripción Caja de Seguridad','Transacciones AOL no Reconocidas','Afiliacion de  LBTR','Aumentos de limite de TD (clientes en el exterior)','Cancelación de CDP/Bono Caja Cliente Fallecido','Comprobante Pago de Préstamo','Constancia Citas de Pasaporte','Constancia de Órdenes de pago','Constancias de Cotización Cambiaria','Embargos','Liberación de endoso AFP','Mantenimiento ACH PRONTO','Pago de Préstamos en Ventanilla','Quejas, reconocimientos y sugerencias','Solicitud Intrafinanciamiento','Cancelación de CDP / Bono de caja','Cancelación de Cuentas','Canje de Megapuntos Crédito TC por Plan de Pagos','Reactivación Cuenta Por Titular o Firma','Reimpresión de CDP / Bono de Caja por Deterioro','Suspensión Pago Cheque propio','Transferencias al exterior','Traslado de Saldo Misma Tarjeta PPT','Afiliación de Pago de Remesas con autorización tel','Afiliación Mensajitos Atlántida','Afiliación Tarjeta de Débito','Aumento de Límite TC Preaprobado','Cambio ofici Retene CTA CKS/ Direc EC TC','Cancelación Depósito No Cuenta','Conciliación de cuentas','Constancia de depósitos en agentes bancarios','Digitalización-Indexado Documentos ATASA','Requerimiento AOL (Atlantida Online)/ACH','Solicitud TC Pre Aprobada','Traslado de Emisor Cambio Límite "Preaprobado"','Venta de divisas','Afiliacion ACH Lading Page','Afiliación Servicios Digitales','Afiliacion VAP Landing Page','Bloqueo TC por Monitoreo','Cancelación Caja de Seguridad por Titular','Despignoración / Liberación de CDP','Eliminación de Diferidos y Retenidos','Emisión de constancias varias','Envío de Remesas Moneygram','Gestiones tasa de seguridad','Liberación de vehículo /Traspaso SEASA','Nota de débito','Registro de Pago de Remesa con autorización telefó','Reimpresión estados cuenta en Agencia','Solicitud de Constancias de Pago de Impuestos','Solicitud de Impresión de Estados de Cuenta','Solicitud TC Cafetería/Club Deportivo BASA','Subasta de Divisas','Traslado Emisor de Tarjeta de Débito','Regularización de Saldos TC','Cancelación CDP Cliente Fallecido/Carta Poder','Reclamo No se Reconoce el Cobro','Constancia de Pagos Realizados al SAR','Cambio de Dirección/Retención Estado de Cuenta','Quejas, reconocimintos y sugerencias','Activación ACH Pronto','Reposición TC Urbana','Reposición de TC Mensajeria','Solicitud TC Adicional (CO) (Mensajería)','Traslado TC Emisor Mismo Límite (Urbana)','Traslado TC Emisor Mismo Límite (Mensajería)','Liberación garantía/Liqui/Hipo/Prentaria','Solicitud TC Adicional (CO) (Urbana)','Renovación Anticipada TC (Urbana)','Traslado Emisor Cambio Límite (Urbana)','Traslado Emisor Cambio Límite(Mensajería)','Arreglos de Pago de TC (Por Contacto)','Activación de Cuenta','Cambio de Nombre a Embozar (Mensajería)','Cambio de Nombre a Embozar (Urbana)','Renovación Anticipada TC (Mensajería)','Emisión TD por Migración (Mensajería)','Liberación de vehículo','Solicitud OMA (Otra TC Mant.actual) Urbana','Envío Firma Documentos Electrónicos','Reclamo por Reversiones Agentes (Días Anteriores)','Registro de Firma','Reposición TD Instantánea','Solicitud OMA (Otra TC Mant.actual) Mensajeria','Cambio de Status Cheques Certificados','Cambio de Status Cheques de Caja','Exclusión de Seguros TC','Mantenimiento de cuenta de ahorro y de cheques','Reclamo Comercios Afiliados','Activacion Tarjetas Enviadas al exterior','Copias de Comprobantes Transacciones Caja JTELLER','Habilitaciones de LBTR','Liberación de garantía hipotecaria','Reclamo de Facturación','Reclamo Duplicidad de Transacciones','Reimpresión  de Bono de Caja','Retiro POS Comercio tipo C','Reversión cobro por Emisión de Estado de Cuenta','Arreglos de Pago de TC (In Situ)','Cancelación de CDP','Constancia de Cancelacion de Adelanto Plus','Constancia pago de antecedentes penales','Constancias de Pagos IP TGR-1','Corrección de personalización de cuentas','Eliminación Fiador TC','Otras Constancias (Servicios Públicos)','Reclamos de chequeras','Refinanciamientos de Préstamo (in Situ)','Solicitud OMA (Otra TC Mant.actual) Foranea','Cambio de Status Documentos Varios Reclasificados','Comprobantes de Prestamo (Ricibo de prestamos)','Corrección de nombre en tarjeta de débito','Correción nombre Cita de Pasaporte','Emisión de TD Dólar','Envio de Tarjetas al exterior','Inclusión de Seguros TC','Liberaciones de fondos (por cheques a confirmar)','Pago de Cartera Administrada','Reclamo Déposito a Cuenta Erronea (Error Cliente)','Reclamo por Comisión de cheques devueltos','Reclamo por Reversión de Cobro','Reclamo Sobregiro de Cuenta','Reversiones de Pagos de Prestamos JTELLER','Soporte técnico ABAS','Suspensión Pago Cheque Certificado o de Caja','Cancelacion de prestamos por medio de CDP','Devolución de valores por citas de pasaporte','Documentación SUP (Copias)','Eliminar Registro Citas de Pasaporte','Embargo/Desembargo','Emisión de cheque por ordenes de pago','Inf. Oficios Juzgados, Entes y Otras Instituciones','Reclamos Reversión de Transacción','Reversión de pagos de servicios y Caja Empresarial','Reversión transacción día actual','Revisión docs para cambio fechas pagos de prestamo','Solicitud arreglo de pago TC','Solicitud de Constancias Firmas Auditoras','Solicitud TD de Inspección','Suministro de Informacion EC','Suscripción Pago Impuestos Tributarios vía AOL','Transferencia entre Cuentas'))
		 	THEN 'NO NECESITA'
		 WHEN (CEH.AREA IS NULL AND T.TAREA IN ('Eliminación de Flotantes','Cancelación Total de ahorro programado','Constancia de Remesas','Reversión Comisión Adelanto de Efectivo','Cambio Categoría TD','Cambio de Ciclo','Reposición PIN TD','Liberación de Fondos','Reposición PIN TC','Solicitud de TD nueva TGU','Renovación Anticipada TC','Reclamos ATM MF Depósitos Cuenta Con PIN','Reclamo/Activación de Seguros','Afiliación ahorro programado','Constancia de Transferencias Enviadas','Constancia Préstamos con Saldos Proyectados','Constancias No Obligaciones','Finiquitos de Prestamos (Con Pagaré)','Ligar cuenta adicional a TD','Retiro Parcial de ahorro programado','Reversión Cargo Asistencias','Constancias de Préstamos Cancelados','Constancias de Transferencias Recibidas','Mantenimiento CDP/Bono de Caja','Rev. Tasa de Seguridad Cuenta Detalle (Dólar)','Reversión de transacción de días anteriores','Reversión Intereses Corrientes PPT','Reversión Adelanto de Efectivo en Ventanilla','Reversión Renovación Membresía TC Titular','Reversión Seguro de Saldo Deuda','Reversión Cargo HRE','Reversion Intereses Corrientes TC','Canje de Megapuntos con Crédito a TC','Canje Megapuntos Crédito a Cuenta','Reversión Cargo Adelanto de Efectivo','Reversión Cargo por Rehabilitación de Cuenta','Reversión Cargo por Reposición TC','Reversión Renovación de Membresía TC Adicional','Traslado de Saldo Misma Tarjeta','Cambio de Limite TC Adicional','Canje de Puntos Cash','Disminución límite de Crédito TC Titular','Traslado Megapuntos TC a TC','Retiro Cajero Automático Basa','Retiros ATM Redes externas','Solicitud TC Adicional','Traslado TC Emisor Mismo Límite','Retiro Cajero Automático Redes Internas','Traslado Emisor Cambio Límite','Cambio de Nombre a Embozar','Retiro Cajero Automático Redes Externas-Internacio','Cuotificación de Cargos','Solicitud Corta Cuotas TC Uno a Uno','Reversión Tasa de Seguridad','Ampliación Límite de Crédito Titular','Asignación Megapuntos a TC','Canje de Megapuntos a Millas','Devolución Saldo a Favor','Traslado de Saldo Diferente Tarjeta','Solicitud Extrafinanciamiento','Reversión Tasa de Seguridad TC','Solicitud  Aumento Limite temporal (Override)','Reclamo ABA','Activación Adelanto Salarial','Asignación Megapuntos TC por Call Center','Cuentas Exoneradas Tasa de Seguridad Entre Bancos','Solicitud Corta Cuotas TC','Ingreso - Borrado de cuenta','Liberación de fondos por emision de cheques','Reclamo por Descuento no Aplicado a Puma','Reversión Cargo Auxilio Hogar','Reversión Cargo Auxilio Vial','Desembolso Parcial','Cambio Fechas de Pagos de Préstamos en Mismo Mes','Impresión de CDP  por renovación automática','Notificaciones por Casos Phishing AOL','Traslado de Saldo Diferente Tarjeta PPT','Cancelación Cuenta por Cliente Fallecido','Cancelación de Prestamos','Suspensión Pago Cheque a cargo Banco del Exterior','Extrafinanciamiento por Alivio de Deuda','Busqueda de comprobantes de operaciones','Otro','Reclamo por denegaciones Crédito(Carta Electrónic)','Solicitud/Requerimiento'))
			THEN 'SI'
		 ELSE 'N/A'	END AS "NOTIFICACION AGENCIA"
	, CASE WHEN (CEH.AREA>'A'AND T.TAREA IN ('Reversión Renovación Membresía TC Titular','Reversión Seguro de Saldo Deuda','Reversión Cargo HRE','Reversion Intereses Corrientes TC','Canje de Megapuntos con Crédito a TC','Canje Megapuntos Crédito a Cuenta','Reversión Cargo Adelanto de Efectivo','Reversión Cargo por Rehabilitación de Cuenta','Reversión Cargo por Reposición TC','Reversión Renovación de Membresía TC Adicional','Traslado de Saldo Misma Tarjeta','Cambio de Limite TC Adicional','Canje de Puntos Cash','Disminución límite de Crédito TC Titular','Traslado Megapuntos TC a TC','Retiro Cajero Automático Basa','Retiros ATM Redes externas','Solicitud TC Adicional','Traslado TC Emisor Mismo Límite','Retiro Cajero Automático Redes Internas','Traslado Emisor Cambio Límite','Cambio de Nombre a Embozar','Retiro Cajero Automático Redes Externas-Internacio','Cuotificación de Cargos','Solicitud Corta Cuotas TC Uno a Uno','Reversión Tasa de Seguridad','Ampliación Límite de Crédito Titular','Asignación Megapuntos a TC','Canje de Megapuntos a Millas','Devolución Saldo a Favor','Regularización de Saldos TC','Traslado de Saldo Diferente Tarjeta','Solicitud Extrafinanciamiento','Cancelación CDP Cliente Fallecido/Carta Poder','Reversión Tasa de Seguridad TC','Solicitud  Aumento Limite temporal (Override)','Reclamo ABA','Reclamo No se Reconoce el Cobro'))
			THEN 'SI'
	   	 WHEN (CEH.AREA IS NULL AND T.TAREA IN ('Eliminación de Flotantes','Cancelación Total de ahorro programado','Constancia de Remesas','Reversión Comisión Adelanto de Efectivo','Cambio Categoría TD','Cambio de Ciclo','Reposición PIN TD','Liberación de Fondos','Reposición PIN TC','Solicitud de TD nueva TGU','Renovación Anticipada TC','Reclamos ATM MF Depósitos Cuenta Con PIN','Reclamo/Activación de Seguros','Afiliación ahorro programado','Constancia de Transferencias Enviadas','Constancia Préstamos con Saldos Proyectados','Constancias No Obligaciones','Finiquitos de Prestamos (Con Pagaré)','Ligar cuenta adicional a TD','Retiro Parcial de ahorro programado','Reversión Cargo Asistencias','Constancias de Préstamos Cancelados','Constancias de Transferencias Recibidas','Mantenimiento CDP/Bono de Caja','Rev. Tasa de Seguridad Cuenta Detalle (Dólar)','Reversión de transacción de días anteriores','Reversión Intereses Corrientes PPT','Reversión Adelanto de Efectivo en Ventanilla','Reversión Renovación Membresía TC Titular','Reversión Seguro de Saldo Deuda','Reversión Cargo HRE','Reversion Intereses Corrientes TC','Canje de Megapuntos con Crédito a TC','Canje Megapuntos Crédito a Cuenta','Reversión Cargo Adelanto de Efectivo','Reversión Cargo por Rehabilitación de Cuenta','Reversión Cargo por Reposición TC','Reversión Renovación de Membresía TC Adicional','Traslado de Saldo Misma Tarjeta','Cambio de Limite TC Adicional','Canje de Puntos Cash','Disminución límite de Crédito TC Titular','Traslado Megapuntos TC a TC','Retiro Cajero Automático Basa','Retiros ATM Redes externas','Solicitud TC Adicional','Traslado TC Emisor Mismo Límite','Retiro Cajero Automático Redes Internas','Traslado Emisor Cambio Límite','Cambio de Nombre a Embozar','Retiro Cajero Automático Redes Externas-Internacio','Cuotificación de Cargos','Solicitud Corta Cuotas TC Uno a Uno','Reversión Tasa de Seguridad','Ampliación Límite de Crédito Titular','Asignación Megapuntos a TC','Canje de Megapuntos a Millas','Devolución Saldo a Favor','Traslado de Saldo Diferente Tarjeta','Solicitud Extrafinanciamiento','Reversión Tasa de Seguridad TC','Solicitud  Aumento Limite temporal (Override)','Reclamo ABA','Activación Adelanto Salarial','Asignación Megapuntos TC por Call Center','Cuentas Exoneradas Tasa de Seguridad Entre Bancos','Solicitud Corta Cuotas TC','Ingreso - Borrado de cuenta','Liberación de fondos por emision de cheques','Reclamo por Descuento no Aplicado a Puma','Reversión Cargo Auxilio Hogar','Reversión Cargo Auxilio Vial','Desembolso Parcial','Cambio Fechas de Pagos de Préstamos en Mismo Mes','Impresión de CDP  por renovación automática','Notificaciones por Casos Phishing AOL','Traslado de Saldo Diferente Tarjeta PPT','Cancelación Cuenta por Cliente Fallecido','Cancelación de Prestamos','Suspensión Pago Cheque a cargo Banco del Exterior','Extrafinanciamiento por Alivio de Deuda','Busqueda de comprobantes de operaciones','Otro','Reclamo por denegaciones Crédito(Carta Electrónic)','Solicitud/Requerimiento'))
			THEN 'SI'
		 WHEN (CEH.AREA>'A'AND T.TAREA IN ('Reclamo por Reversión de Cobro','Emisión Tarjeta Débito Nueva/Renovación Mensajería','Eliminación de Flotantes','Cancelación Total de ahorro programado','Constancia de Remesas','Emisión de Estados de Cuenta','Reversión Comisión Adelanto de Efectivo','Constancia por Recaudaciones','Bloqueo Tarjeta de débito','Cancelación/Mantenimientos de Seguros','Activación Cuenta por Titular o Firma Autorizada','Actualización Clientes','Reposición TD TGU','Actualización Firmas y/o Beneficiarios','Cancelación Cuentas Ahorro a solicitud del titular','Solicitud de Chequeras','Notificación Uso TD en el Exterior','REPOSICIÓN LIBRETA DE AHORRO POR ROBO O EXTRAVÍO','Afiliación Débitos Automáticos','Cambio Categoría TD','Cancelación Cuenta de Cheques a Solcitud del Titul','Requerimiento AOL (Atlantida Online)','Cambio de Fecha de Pago de Prestamo','Consulta de Saldos Cta Ahorro/Cheque, TC, Préstamo','Reposición PIN TC Instantaneo','Bloqueo Tarjeta crédito','Cambio de Ciclo','Constancia Préstamos sin Obligaciones','Desbloqueo de Tarjeta de débito','Reimpresión  de CDP','Acceso Caja de Seguridad','Actualización Firmas / Beneficiarios en Cuentas','Constancia SIAFI','Afiliación AOL (Atlantida Online)','Cancelación Débitos Automáticos','Constancia Activos y Pasivos SIN Saldos ni Promedi','Desbloqueo de Tarjeta de crédito','Notificación Uso TC en el Exterior','Solicitud Cheque de Ventanilla','Constancia Activos y Pasivos CON Saldos y Promedio','Emisión Constancia Embajada Americana','Requerimiento Mensajitos Atlántida','Liberación de Garantia Hipotecaria','Consumo no Reconocido TC','Consumo No Reconocido TD','Reposición de TC','Liberación de Garantia Liquida (CDP)','Liberación de Garantia Prendaria (Vehiculo)','Cancelación TC por Titular','Reposición PIN TD','Cancelación Cta de Ahorro/Cheques cliente fallecid','Desembolso bajo línea de crédito','Liberación de Fondos','Reposición PIN TC','Cancelación TC por Cliente Fallecido','Creación Múltiple de Habilitantes','Emisión TD Nueva Instantánea','Solicitud de TD nueva TGU','Cancelación Caja de Seguridad','Envió TD y Docs. Cuenta Web al Extranjero','Renovación Anticipada TC','Cancelación Cuenta de Ahorro/Cheques carta poder','Emisión TD Adicional','Reclamos ATM MF Depósitos Cuenta Con PIN','Cancelación TC por Carta Poder','Desembolso Parcial','Emisión Tarjeta Débito de Sucursal/Agencia','Reclamos ATM MF Pagos TC','Activación de Cuentas con Carta Poder','Afiliación Tarjeta de Debito','Finiquitos de Tarjetas de Credito','Contracargos ATM Adquirente BASA','Reclamo por Prestamo','Reclamo/Activación de Seguros','Cancelación de CDP/Bono Caja Solicitud del Titular','Constancia para TC','Adición/Cancelación de Firma','Afiliación ahorro programado','Cambios de Productos','Constancia de Transferencias Enviadas','Constancia Préstamos con Saldos Proyectados','Constancias No Obligaciones','Finiquitos de Prestamos (Con Pagaré)','Ligar cuenta adicional a TD','Retiro Parcial de ahorro programado','Reversión Cargo Asistencias','Actualizacion de Cliente Onboarding','Cancelación de préstamos por cliente fallecido','Cancelaciones de Firma (Cuentas de ahorro y cheque','Constancias de Préstamos Cancelados','Constancias de Transferencias Recibidas','Emisión Tarjeta Débito Nueva (Mensajería)','Hoja de Reclamación','Impresión CDP/Bono caja por renovación automatica','Llamada de Bienvenida','Mantenimiento CDP/Bono de Caja','Rev. Tasa de Seguridad Cuenta Detalle (Dólar)','Reversión de transacción de días anteriores','Reversión Intereses Corrientes PPT','Solicitud Corta Cuotas TC (Pre Aprobado)','Suscripción Caja de Seguridad','Transacciones AOL no Reconocidas','Afiliacion de  LBTR','Aumentos de limite de TD (clientes en el exterior)','Cancelación de CDP/Bono Caja Cliente Fallecido','Comprobante Pago de Préstamo','Constancia Citas de Pasaporte','Constancia de Órdenes de pago','Constancias de Cotización Cambiaria','Embargos','Liberación de endoso AFP','Mantenimiento ACH PRONTO','Pago de Préstamos en Ventanilla','Quejas, reconocimientos y sugerencias','Reversión Adelanto de Efectivo en Ventanilla','Solicitud Intrafinanciamiento','Cambio Fechas de Pagos de Préstamos en Mismo Mes','Cancelación de CDP / Bono de caja','Cancelación de Cuentas','Canje de Megapuntos Crédito TC por Plan de Pagos','Impresión de CDP  por renovación automática','Notificaciones por Casos Phishing AOL','Reactivación Cuenta Por Titular o Firma','Reimpresión de CDP / Bono de Caja por Deterioro','Suspensión Pago Cheque propio','Transferencias al exterior','Traslado de Saldo Misma Tarjeta PPT','Afiliación de Pago de Remesas con autorización tel','Afiliación Mensajitos Atlántida','Afiliación Tarjeta de Débito','Aumento de Límite TC Preaprobado','Cambio ofici Retene CTA CKS/ Direc EC TC','Cancelación Depósito No Cuenta','Conciliación de cuentas','Constancia de depósitos en agentes bancarios','Digitalización-Indexado Documentos ATASA','Requerimiento AOL (Atlantida Online)/ACH','Solicitud TC Pre Aprobada','Traslado de Emisor Cambio Límite "Preaprobado"','Traslado de Saldo Diferente Tarjeta PPT','Venta de divisas','Afiliacion ACH Lading Page','Afiliación Servicios Digitales','Afiliacion VAP Landing Page','Bloqueo TC por Monitoreo','Cancelación Caja de Seguridad por Titular','Cancelación Cuenta por Cliente Fallecido','Cancelación de Prestamos','Despignoración / Liberación de CDP','Eliminación de Diferidos y Retenidos','Emisión de constancias varias','Envío de Remesas Moneygram','Gestiones tasa de seguridad','Liberación de vehículo /Traspaso SEASA','Nota de débito','Registro de Pago de Remesa con autorización telefó','Reimpresión estados cuenta en Agencia','Solicitud de Constancias de Pago de Impuestos','Solicitud de Impresión de Estados de Cuenta','Solicitud TC Cafetería/Club Deportivo BASA','Subasta de Divisas','Suspensión Pago Cheque a cargo Banco del Exterior','Traslado Emisor de Tarjeta de Débito'))
		 	THEN 'NO NECESITA'
		 WHEN (CEH.AREA IS NULL AND T.TAREA IN ('Emisión Tarjeta Débito Nueva/Renovación Mensajería','Reclamo por Reversión de Cobro','Reposición Libreta de Ahorro','Emisión de Estados de Cuenta','Constancia por Recaudaciones','Bloqueo Tarjeta de débito','Cancelación/Mantenimientos de Seguros','Activación Cuenta por Titular o Firma Autorizada','Actualización Clientes','Reposición TD TGU','Actualización Firmas y/o Beneficiarios','Cancelación Cuentas Ahorro a solicitud del titular','Solicitud de Chequeras','Notificación Uso TD en el Exterior','REPOSICIÓN LIBRETA DE AHORRO POR ROBO O EXTRAVÍO','Afiliación Débitos Automáticos','Cancelación Cuenta de Cheques a Solcitud del Titul','Requerimiento AOL (Atlantida Online)','Cambio de Fecha de Pago de Prestamo','Consulta de Saldos Cta Ahorro/Cheque, TC, Préstamo','Reposición PIN TC Instantaneo','Bloqueo Tarjeta crédito','Constancia Préstamos sin Obligaciones','Desbloqueo de Tarjeta de débito','Reimpresión  de CDP','Acceso Caja de Seguridad','Actualización Firmas / Beneficiarios en Cuentas','Constancia SIAFI','Afiliación AOL (Atlantida Online)','Cancelación Débitos Automáticos','Constancia Activos y Pasivos SIN Saldos ni Promedi','Desbloqueo de Tarjeta de crédito','Notificación Uso TC en el Exterior','Solicitud Cheque de Ventanilla','Constancia Activos y Pasivos CON Saldos y Promedio','Emisión Constancia Embajada Americana','Requerimiento Mensajitos Atlántida','Liberación de Garantia Hipotecaria','Consumo no Reconocido TC','Consumo No Reconocido TD','Reposición de TC','Liberación de Garantia Liquida (CDP)','Liberación de Garantia Prendaria (Vehiculo)','Cancelación TC por Titular','Cancelación Cta de Ahorro/Cheques cliente fallecid','Desembolso bajo línea de crédito','Cancelación TC por Cliente Fallecido','Creación Múltiple de Habilitantes','Emisión TD Nueva Instantánea','Cancelación Caja de Seguridad','Envió TD y Docs. Cuenta Web al Extranjero','Cancelación Cuenta de Ahorro/Cheques carta poder','Emisión TD Adicional','Cancelación TC por Carta Poder','Emisión Tarjeta Débito de Sucursal/Agencia','Reclamos ATM MF Pagos TC','Activación de Cuentas con Carta Poder','Afiliación Tarjeta de Debito','Finiquitos de Tarjetas de Credito','Contracargos ATM Adquirente BASA','Reclamo por Prestamo','Cancelación de CDP/Bono Caja Solicitud del Titular','Constancia para TC','Adición/Cancelación de Firma','Cambios de Productos','Actualizacion de Cliente Onboarding','Cancelación de préstamos por cliente fallecido','Cancelaciones de Firma (Cuentas de ahorro y cheque','Emisión Tarjeta Débito Nueva (Mensajería)','Hoja de Reclamación','Impresión CDP/Bono caja por renovación automatica','Llamada de Bienvenida','Solicitud Corta Cuotas TC (Pre Aprobado)','Suscripción Caja de Seguridad','Transacciones AOL no Reconocidas','Afiliacion de  LBTR','Aumentos de limite de TD (clientes en el exterior)','Cancelación de CDP/Bono Caja Cliente Fallecido','Comprobante Pago de Préstamo','Constancia Citas de Pasaporte','Constancia de Órdenes de pago','Constancias de Cotización Cambiaria','Embargos','Liberación de endoso AFP','Mantenimiento ACH PRONTO','Pago de Préstamos en Ventanilla','Quejas, reconocimientos y sugerencias','Solicitud Intrafinanciamiento','Cancelación de CDP / Bono de caja','Cancelación de Cuentas','Canje de Megapuntos Crédito TC por Plan de Pagos','Reactivación Cuenta Por Titular o Firma','Reimpresión de CDP / Bono de Caja por Deterioro','Suspensión Pago Cheque propio','Transferencias al exterior','Traslado de Saldo Misma Tarjeta PPT','Afiliación de Pago de Remesas con autorización tel','Afiliación Mensajitos Atlántida','Afiliación Tarjeta de Débito','Aumento de Límite TC Preaprobado','Cambio ofici Retene CTA CKS/ Direc EC TC','Cancelación Depósito No Cuenta','Conciliación de cuentas','Constancia de depósitos en agentes bancarios','Digitalización-Indexado Documentos ATASA','Requerimiento AOL (Atlantida Online)/ACH','Solicitud TC Pre Aprobada','Traslado de Emisor Cambio Límite "Preaprobado"','Venta de divisas','Afiliacion ACH Lading Page','Afiliación Servicios Digitales','Afiliacion VAP Landing Page','Bloqueo TC por Monitoreo','Cancelación Caja de Seguridad por Titular','Despignoración / Liberación de CDP','Eliminación de Diferidos y Retenidos','Emisión de constancias varias','Envío de Remesas Moneygram','Gestiones tasa de seguridad','Liberación de vehículo /Traspaso SEASA','Nota de débito','Registro de Pago de Remesa con autorización telefó','Reimpresión estados cuenta en Agencia','Solicitud de Constancias de Pago de Impuestos','Solicitud de Impresión de Estados de Cuenta','Solicitud TC Cafetería/Club Deportivo BASA','Subasta de Divisas','Traslado Emisor de Tarjeta de Débito','Regularización de Saldos TC','Cancelación CDP Cliente Fallecido/Carta Poder','Reclamo No se Reconoce el Cobro','Constancia de Pagos Realizados al SAR','Cambio de Dirección/Retención Estado de Cuenta','Quejas, reconocimintos y sugerencias','Activación ACH Pronto','Reposición TC Urbana','Reposición de TC Mensajeria','Solicitud TC Adicional (CO) (Mensajería)','Traslado TC Emisor Mismo Límite (Urbana)','Traslado TC Emisor Mismo Límite (Mensajería)','Liberación garantía/Liqui/Hipo/Prentaria','Solicitud TC Adicional (CO) (Urbana)','Renovación Anticipada TC (Urbana)','Traslado Emisor Cambio Límite (Urbana)','Traslado Emisor Cambio Límite(Mensajería)','Arreglos de Pago de TC (Por Contacto)','Activación de Cuenta','Cambio de Nombre a Embozar (Mensajería)','Cambio de Nombre a Embozar (Urbana)','Renovación Anticipada TC (Mensajería)','Emisión TD por Migración (Mensajería)','Liberación de vehículo','Solicitud OMA (Otra TC Mant.actual) Urbana','Envío Firma Documentos Electrónicos','Reclamo por Reversiones Agentes (Días Anteriores)','Registro de Firma','Reposición TD Instantánea','Solicitud OMA (Otra TC Mant.actual) Mensajeria','Cambio de Status Cheques Certificados','Cambio de Status Cheques de Caja','Exclusión de Seguros TC','Mantenimiento de cuenta de ahorro y de cheques','Reclamo Comercios Afiliados','Activacion Tarjetas Enviadas al exterior','Copias de Comprobantes Transacciones Caja JTELLER','Habilitaciones de LBTR','Liberación de garantía hipotecaria','Reclamo de Facturación','Reclamo Duplicidad de Transacciones','Reimpresión  de Bono de Caja','Retiro POS Comercio tipo C','Reversión cobro por Emisión de Estado de Cuenta','Arreglos de Pago de TC (In Situ)','Cancelación de CDP','Constancia de Cancelacion de Adelanto Plus','Constancia pago de antecedentes penales','Constancias de Pagos IP TGR-1','Corrección de personalización de cuentas','Eliminación Fiador TC','Otras Constancias (Servicios Públicos)','Reclamos de chequeras','Refinanciamientos de Préstamo (in Situ)','Solicitud OMA (Otra TC Mant.actual) Foranea','Cambio de Status Documentos Varios Reclasificados','Comprobantes de Prestamo (Ricibo de prestamos)','Corrección de nombre en tarjeta de débito','Correción nombre Cita de Pasaporte','Emisión de TD Dólar','Envio de Tarjetas al exterior','Inclusión de Seguros TC','Liberaciones de fondos (por cheques a confirmar)','Pago de Cartera Administrada','Reclamo Déposito a Cuenta Erronea (Error Cliente)','Reclamo por Comisión de cheques devueltos','Reclamo por Reversión de Cobro','Reclamo Sobregiro de Cuenta','Reversiones de Pagos de Prestamos JTELLER','Soporte técnico ABAS','Suspensión Pago Cheque Certificado o de Caja','Cancelacion de prestamos por medio de CDP','Devolución de valores por citas de pasaporte','Documentación SUP (Copias)','Eliminar Registro Citas de Pasaporte','Embargo/Desembargo','Emisión de cheque por ordenes de pago','Inf. Oficios Juzgados, Entes y Otras Instituciones','Reclamos Reversión de Transacción','Reversión de pagos de servicios y Caja Empresarial','Reversión transacción día actual','Revisión docs para cambio fechas pagos de prestamo','Solicitud arreglo de pago TC','Solicitud de Constancias Firmas Auditoras','Solicitud TD de Inspección','Suministro de Informacion EC','Suscripción Pago Impuestos Tributarios vía AOL','Transferencia entre Cuentas'))
		 	THEN 'NO NECESITA'	
		 ELSE 'N/A'	END AS "NOTIFICACION"
	, CASE WHEN (T.TAREA LIKE '%Customer%')
			THEN 'CSI'
		 WHEN (T.TAREA IN ('Acceso Caja de Seguridad','Activación ACH Pronto','Activación Cuenta por Titular o Firma Autorizada','Actualización Clientes','Afiliación AOL (Atlantida Online)','Afiliación Débitos Automáticos','Bloqueo Tarjeta crédito','Bloqueo Tarjeta de débito','Cancelación Cuenta de Cheques a Solcitud del Titul','Cancelación Cuentas Ahorro a solicitud del titular','Constancia Activos y Pasivos CON Saldos y Promedio','Constancia Activos y Pasivos SIN Saldos ni Promedi','Constancia Préstamos sin Obligaciones','Constancia SIAFI','Consulta de Saldos Cta Ahorro/Cheque, TC, Préstamo','Desbloqueo de Tarjeta de crédito','Desbloqueo de Tarjeta de débito','Emisión Constancia Embajada Americana','Notificación Uso TC en el Exterior','Notificación Uso TD en el Exterior','Reposición Libreta de Ahorro','Reposición PIN TC Instantaneo','Reposición TD TGU','Requerimiento AOL (Atlantida Online)','Requerimiento Mensajitos Atlántida','Solicitud Cheque de Ventanilla','Actualizacion de Cliente Onboarding','Afiliacion ACH Lading Page','Afiliacion de  LBTR','Afiliación de Pago de Remesas con autorización tel','Afiliación Mensajitos Atlántida','Afiliación Servicios Digitales','Afiliación Tarjeta de Debito','Afiliación Tarjeta de Débito','Afiliacion VAP Landing Page','Bloqueo TC por Monitoreo','Cancelación Caja de Seguridad','Cancelación Caja de Seguridad por Titular','Cancelación de CDP','Cancelación de CDP / Bono de caja','Cancelación de CDP/Bono Caja Solicitud del Titular','Cancelación de Cuentas','Cancelación Depósito No Cuenta','Constancia para TC','Creación Múltiple de Habilitantes','Emisión de cheque por ordenes de pago','Emisión Tarjeta Débito de Sucursal/Agencia','Emisión TD Nueva Instantánea','Envío de Remesas Moneygram','Impresión CDP/Bono caja por renovación automatica','Impresión de CDP  por renovación automática','Llamada de Bienvenida','Mantenimiento ACH PRONTO','Registro de Pago de Remesa con autorización telefó','Reimpresión  de Bono de Caja','Reimpresión  de CDP','Reimpresión de CDP / Bono de Caja por Deterioro','Reposición TD Instantánea','Requerimiento AOL (Atlantida Online)/ACH','Solicitud de TD nueva TGU','Suspensión Pago Cheque propio'))	
			THEN 'FCR'
		 ELSE 'BACKOFFICE' END AS SEGMENTOS	*/
	, DUB.NOMBRE AS NOMBRE_OPERADOR	
	, DUB1.NOMBRE AS NOMBRE_ENCARGADO_PASO
	, CDC.PRIMER_NOMBRE AS FirstName
	, CDC.PRIMER_APELLIDO AS LastName
	--, cdc.IDENTIFICACION_1 AS ExternalReference
	--, cdc.E_MAIL
	--, CDC.TEL_CELULAR AS PHONE
	--, 'CRM' AS FUENTE
	, AGENCIA
	,COM_OS.desc_ord
	,T.desc_paso
 
	
	FROM (
		SELECT * from(
		------ TABLA PARA OBTENER DATOS UNICOS DE LA ORDEN--------	
			SELECT * FROM(
				SELECT
				CFS.OBJECT_ID AS ORDEN_ID
				, CFS.TAREA
				, CFS.ESTADO
				, CFS.ESTADO_ACTUAL
				, CFS.CODIGO_CLIENTE_CRM
				, CFS.CODIGO_CLIENTE_IBS
				, CFS.INICIO_GESTION
				, CFS.FIN_GESTION
				, CFS.CREACION_GESTION
				, CFS.INGRESO_SIST
				, CFS.MOTIVO
				, CFS.CATEGORIA
				, CFS.SUBCATEGORIA
				, CFS.UNIDAD_ORG
				, CFS.CREADO_POR
				, CFS.PRODUCTO
				, CFS.DESCRIPCION_PRODUCTO
				, CFS.COD_AGENCIA
				, CFS.FECHA_CAMBIO_ESTADO
				, cfs.AGENCIA
				, cfs.Valor
				, cfs.guid AS guid_ord
				, ROW_NUMBER () OVER(PARTITION BY CFS.OBJECT_ID ORDER BY CFS.FECHA_CAMBIO_ESTADO DESC) AS CON
				--SELECT *
				FROM  DS_STG.CRM_FACT_SRV CFS --WHERE object_id='8011086305'
				--Reclamo ABA
				-- motivo Reclamo agente atlantida, Reclamo usuario final
				WHERE CFS.CREACION_GESTION >= TO_DATE('{{FECHA_INICIO}}', 'YYYY-MM-DD')
				  AND CFS.CREACION_GESTION < ADD_DAYS(TO_DATE('{{FECHA_FIN}}', 'YYYY-MM-DD'), 1)
				--AND tarea='Reclamo ABA'
				--AND motivo IN ('Reclamo agente atlantida','Reclamo usuario final')
				)
			WHERE CON=1 ) AS OS
		LEFT JOIN (	
		SELECT * FROM(
			SELECT
			cdsp.OBJECT_ID AS ORDENES_ID
			, cdsp.usuario AS ENCARGADO_PASO
			, cdsp.DESCRIPCION
			, cdsp.ESTADO AS ESTADO_PASO
			, cdsp.ULTIMA_FECHA_PASO
			, cdsp.FECHA_CREACION_PASO
			, cdsp.FECHA_PLANEADA_PASO
			, cdsp.TIEMPO_PLANEADO
			, cdsp.UNIDAD_TIEMPO_PLANEADO
			, cdsp.TIEMPO_EXCEDIDO_HORAS
			, cdsp.TIEMPO_TARDADO_MINUTOS
			, cdsp.TIEMPO_EXCEDIDO_MINUTOS
			, cdsp.DESENCADENADOR AS CONCLUSION
			, cdsp.guid AS guid_paso
			, ROW_NUMBER () OVER(PARTITION BY CDSP.OBJECT_ID,cdsp.DESCRIPCION,cdsp.FECHA_CREACION_PASO ORDER BY cdsp.FECHA_CREACION_PASO DESC) AS CON
		    FROM  DS_STG.CRM_DIM_SRV_PASOS cdsp	-- WHERE DESCRIPCION='Solicitar vaucher'
			WHERE cdsp.FECHA_CREACION_PASO >= TO_DATE('{{FECHA_INICIO}}', 'YYYY-MM-DD')
			  AND cdsp.FECHA_CREACION_PASO < ADD_DAYS(TO_DATE('{{FECHA_FIN}}', 'YYYY-MM-DD'), 1))
			--AND cdsp.OBJECT_ID='8010665123')
		WHERE CON=1 ) AS PASOS ON OS.ORDEN_ID=PASOS.ORDENES_ID
		----------------------PARA TRAER LOS COMENTARIOS DE LOS PASOS--------------------------
		LEFT JOIN (
--QUERY PARA COMENTARIO DE PASOS
SELECT
	CDN2.GUID
	, cdn2.DESCRIPCION AS DESC_PASO
FROM DS_STG.CRM_DIM_NOTAS cdn2
WHERE CAST(cdn2.FECHA AS DATE) BETWEEN
      TO_DATE('{{FECHA_INICIO}}', 'YYYY-MM-DD')
      AND TO_DATE('{{FECHA_FIN}}', 'YYYY-MM-DD')
--AND GUID = '005056B71E791FD180908F121AE3FC93'
) AS COM_PASO ON LEFT(PASOS.guid_paso,32)=LEFT (COM_PASO.GUID,32)
		---- JOIN PARA CALCULAR EL TIEMPO PLANEADO, PASAR DE DIAS, HORAS, MINUTOS A SEGUNDOS-------------
		LEFT JOIN (
		SELECT * FROM (	
			SELECT
				ORD_PASOS2.OBJECT_ID
				, UNIDAD_TIEMPO_PLANEADO AS T_P_UNIDAD_TIEMPO_PLANEADO
				, DESCRIPCION AS D_T_PLANEADO
				, FECHA_CREACION_PASO AS T_P_FECHA_CREACION_PASO
				, CASE WHEN (ORD_PASOS2.UNIDAD_TIEMPO_PLANEADO='DAY') THEN (ORD_PASOS2.TIEMPO_PLANEADO*86400)
				WHEN (ORD_PASOS2.UNIDAD_TIEMPO_PLANEADO='HOUR' OR ORD_PASOS2.UNIDAD_TIEMPO_PLANEADO='HORAS') THEN (ORD_PASOS2.TIEMPO_PLANEADO*3600)
				WHEN (ORD_PASOS2.UNIDAD_TIEMPO_PLANEADO='MIN') THEN (ORD_PASOS2.TIEMPO_PLANEADO *60)
				ELSE 0 END AS T_PLANEADO_seg
				, ROW_NUMBER () OVER(PARTITION BY ORD_PASOS2.OBJECT_ID,ORD_PASOS2.DESCRIPCION,ORD_PASOS2.FECHA_CREACION_PASO ORDER BY ORD_PASOS2.FECHA_CREACION_PASO DESC) AS CON
			FROM DS_STG.CRM_DIM_SRV_PASOS ORD_PASOS2
			WHERE ORD_PASOS2.FECHA_CREACION_PASO >= TO_DATE('{{FECHA_INICIO}}', 'YYYY-MM-DD')
			  AND ORD_PASOS2.FECHA_CREACION_PASO < ADD_DAYS(TO_DATE('{{FECHA_FIN}}', 'YYYY-MM-DD'), 1))
			WHERE CON=1) AS t_planeado ON PASOS.ORDENES_ID = t_planeado.OBJECT_ID AND PASOS.DESCRIPCION=T_PLANEADO.D_T_PLANEADO AND PASOS.FECHA_CREACION_PASO=T_PLANEADO.T_P_FECHA_CREACION_PASO
		--------JOIN PARA MOSTRAR LA RESOLUCION DE LA ORDEN-------------
		LEFT JOIN (SELECT *
				FROM (
					SELECT
					  ORD2.OBJECT_ID AS R_OBJECT_ID,
					  ORD_PASOS1.DESENCADENADOR,
					  ROW_NUMBER () OVER(PARTITION BY ORD2.OBJECT_ID ORDER BY  ORD_PASOS1.FECHA_CREACION_PASO DESC) AS CON1
					  FROM DS_STG.CRM_FACT_SRV ORD2
					  LEFT JOIN DS_STG.CRM_DIM_SRV_PASOS ORD_PASOS1 ON ORD_PASOS1.OBJECT_ID = ORD2.OBJECT_ID
					  WHERE ORD_PASOS1.DESENCADENADOR IN ('Aprobado','Denegado','Devuelto') OR (ORD_PASOS1.DESENCADENADOR ='Cuenta con Disponible')
					  OR (ORD_PASOS1.DESENCADENADOR ='Concluido' AND ORD_PASOS1.DESCRIPCION='Aplicar Operación') OR ORD_PASOS1.DESENCADENADOR ='Aprobado (No requiere autorización)')
				WHERE CON1=1) AS ULT_DESE on ULT_DESE.R_OBJECT_ID=OS.ORDEN_ID
		-- JOIN PARA MOSTRAR SI LA ORDEN FUE DEVUELTA ALGUNA VEZ, ES INDEPENDIENTE DE LA RESOLUCION FINAL------
		LEFT JOIN (SELECT *
					FROM (SELECT
					  ORD2.OBJECT_ID AS D_ORDEN_ID,
					  ORD_PASOS1.DESENCADENADOR AS DEVUELTO,
					  ROW_NUMBER () OVER(PARTITION BY ORD2.OBJECT_ID ORDER BY  ORD_PASOS1.FECHA_CREACION_PASO DESC) AS CON1
					  FROM DS_STG.CRM_FACT_SRV ORD2
					  LEFT JOIN DS_STG.CRM_DIM_SRV_PASOS ORD_PASOS1 ON ORD_PASOS1.OBJECT_ID = ORD2.OBJECT_ID
					  WHERE ORD_PASOS1.DESENCADENADOR IN ('Devuelto'))
				WHERE CON1=1) AS DEVUELTO on DEVUELTO.D_ORDEN_ID=OS.ORDEN_ID) AS T
	LEFT JOIN BI_SS.MP_EMPLEADOS_HISTORICO ceh ON T.CREADO_POR=CEH.WINDOWS AND MONTH(T.CREACION_GESTION)= CEH.MES AND YEAR(T.CREACION_GESTION)= CEH.ANIO
	---- JOIN PARA TRAER EL NOMBRE DEL EMPLEADO CREA LA OS, SE HACE SUB QUERY POR DUPLICADOS DE USUARIO EN TABLA
	LEFT JOIN (
	SELECT DISTINCT
	NOMBRE_FORMAL AS NOMBRE
	, LEFT (NOMBRE_USUARIO, INSTR(NOMBRE_USUARIO,'@',1)-1) AS USUARIO
	FROM RRHH.DIM_INFORMACION_USUARIOS_RRHH DUB1)AS dub ON UPPER(T.CREADO_POR) = UPPER(DUB.USUARIO)
	--No se deja puesto de empleado por duplicidad de correo en distintos empleados y tabla no trae windows
	--LEFT JOIN RRHH.DIM_INFORMACION_USUARIOS_RRHH DIUR ON T.CREADO_POR=REPLACE(SUBSTR_BEFORE(DIUR.NOMBRE_USUARIO,'@'),' ','')	
		--WHERE (CEH.AREA='A1' OR T.COD_AGENCIA=114)
	---- JOIN PARA TRAER EL NOMBRE DEL EMPLEADO da seguimiento, SE HACE SUB QUERY POR DUPLICADOS DE USUARIO EN TABLA
	LEFT JOIN (
	SELECT DISTINCT
	NOMBRE_FORMAL AS NOMBRE
	, LEFT (NOMBRE_USUARIO, INSTR(NOMBRE_USUARIO,'@',1)-1) AS USUARIO
	FROM RRHH.DIM_INFORMACION_USUARIOS_RRHH DUB1)AS dub1 ON UPPER(T.ENCARGADO_PASO) = UPPER(DUB1.USUARIO)
	--JOIN PARA OBTENER DETALLE DE CLIENTE	
	LEFT JOIN DS_STG.CRM_DIM_CLIENTES CDC ON T.CODIGO_CLIENTE_CRM = CDC.COD_CLIENTE_CRM
----------------------PARA TRAER EL COMENTARIO DE LA ORDEN-------------------------------------------------	
	LEFT JOIN (
	SELECT * FROM (
	--QUERY PARA COMENTARIO DE ORDEN
SELECT
	CDN.GUID
	, cdn.DESCRIPCION AS DESC_ORD
	, ROW_NUMBER () OVER(PARTITION BY cdn.GUID ORDER BY CAST(cdn.FECHA AS DATE) DESC) AS CON
--SELECT CAST(FECHA AS DATE)
--	SELECT *
FROM DS_STG.CRM_DIM_NOTAS cdn
--WHERE GUID = '005056B71E791FD180908F121AE3FC93'
WHERE CAST(cdn.FECHA AS DATE) BETWEEN
      TO_DATE('{{FECHA_INICIO}}', 'YYYY-MM-DD')
      AND TO_DATE('{{FECHA_FIN}}', 'YYYY-MM-DD')
--AND GUID = '005056B71E791FD180908F121AE3FC93'
 
		) WHERE CON=1
) AS COM_OS ON T.guid_ord=COM_OS.GUID
---------------------------------------------
	WHERE  T.TAREA='Reclamo ABA'
	AND T.MOTIVO IN ('Reclamo agente atlantida','Reclamo usuario final')
	AND DESCRIPCION='Solicitar vaucher'
	AND T.ESTADO_ACTUAL='En tramite'
