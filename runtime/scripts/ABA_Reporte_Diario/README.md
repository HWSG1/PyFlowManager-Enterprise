# Reporte diario ABA

El módulo consulta SAP HANA, genera `Data ABA.xlsx`, calcula métricas por
`ORDEN_ID`, renderiza una plantilla HTML y envía el reporte mediante
Microsoft Graph.

## Parámetros visibles en PyFlow

El formulario solicita únicamente:

- `FECHA_INICIO`: fecha inicial del reporte.
- `FECHA_FIN`: fecha final del reporte.
- `OUTPUT_FOLDER`: carpeta de salida.
- `OUTPUT_FILE`: nombre del Excel.
- `EMAIL_TO`: destinatarios.
- `EMAIL_CC`: destinatarios opcionales en copia.

Las fechas usan el formato `aaaa-mm-dd`. La fecha inicial no puede ser
posterior a la fecha final.

Las credenciales HANA y Microsoft Graph continúan como variables globales,
mostradas por PyFlow en su sección separada:

- `HPR_HOST_ESPEJO`, `HPR_PORT`, `HPR_USER` y `HPR_PASSWORD`.
- `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` y
  `GRAPH_SENDER_EMAIL`.

## Configuración interna

Estos valores ya no aparecen en el formulario:

- Ambiente HANA: `ESPEJO`.
- SQL: `ABA_Reclamos_En_Tramite.sql`.
- Hoja Excel: `Data ABA`.
- Envío de correo: habilitado.
- Asunto: `[Data ABA] Órdenes de Servicio CRM - {fecha_reporte}`.
- Título: `Órdenes de Servicio CRM · ABA`.
- Proceso: `Proceso automático Data ABA`.

El argumento de consola `--no-email` sigue disponible para una prueba segura
sin envío.

## Carpeta `input`

El script no solicita rutas para el logo ni la plantilla. Los detecta
automáticamente dentro de `input`:

- `input/Logo_Banco_Atlantida_Email.png`
- `input/plantilla_correo_ordenes_aba.html`

También admite un único `.png`, `.jpg` o `.jpeg` como logo y un único `.html`
o `.htm` como plantilla. Si hay varios archivos posibles sin los nombres
predeterminados, el proceso se detiene para evitar seleccionar uno
incorrecto.

La plantilla usa marcadores simples como `{{FECHA_INICIO}}`, `{{KPI_ROWS}}`
y `{{LOGO_HTML}}`. El script valida que todos los marcadores requeridos estén
presentes antes de enviar el correo.

## Filtro SQL por fechas

El SQL contiene los marcadores `{{FECHA_INICIO}}` y `{{FECHA_FIN}}`. El
script los sustituye únicamente con fechas ISO ya validadas.

El rango se aplica a:

- Creación de la orden.
- Creación y planificación de pasos.
- Comentarios de orden y de pasos.

La fecha final es inclusiva.

## Criterio de métricas

La unidad del resumen es `ORDEN_ID` distinto. Esto evita contar una orden
varias veces cuando el resultado contiene más de un paso.

Clientes únicos y cumplimiento SLA se muestran únicamente si el SQL devuelve
sus columnas correspondientes. No se inventan valores.

La consulta conserva estos filtros funcionales:

- Gestión `Reclamo ABA`.
- Motivo `Reclamo agente atlantida` o `Reclamo usuario final`.
- Paso `Solicitar vaucher`.
- Estado actual `En tramite`.

## Instalación y prueba

```powershell
python -m pip install -r requirements.txt

$env:FECHA_INICIO = "2026-07-01"
$env:FECHA_FIN = "2026-07-24"
python ABA_Reporte_Diario.py --no-email
```

Para ejecutar las pruebas:

```powershell
python test_ABA_Reporte_Diario.py -v
```

Las credenciales deben permanecer en variables globales o de entorno, nunca
en el código.
