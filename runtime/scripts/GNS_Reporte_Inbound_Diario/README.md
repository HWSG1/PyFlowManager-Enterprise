# Reporte diario de llamadas inbound

Registrado en PyFlow como `GNS_Reporte_Inbound_Diario`.

## Uso en PyFlow

1. Abrir el script y sus parametros.
2. Escribir manualmente los destinatarios en `REPORT_EMAIL_TO` y, opcionalmente,
   copias en `REPORT_EMAIL_CC`. Se pueden separar por coma o punto y coma.
3. Dejar `SEND_EMAIL=false` para generar la vista previa HTML y el detalle CSV
   dentro de `output`.
4. Para enviar, configurar `SEND_EMAIL=true` y ejecutar. Se envia el reporte HTML
   en el cuerpo del correo usando el remitente global de Microsoft Graph, con un
   Excel `.xlsx` adjunto y el logo integrado mediante CID.
5. Para automatizar, crear una programacion diaria desde PyFlow, elegir la hora
   y la zona `America/Tegucigalpa`, y guardar los destinatarios y `SEND_EMAIL=true`
   en los parametros de esa programacion. No se creo una programacion automaticamente.

La PC, SQL Server y el backend de PyFlow deben estar encendidos a la hora elegida.
El envio requiere que la aplicacion Graph tenga los permisos de envio del remitente.
La prueba realizada no envio correos ni verifico los permisos de Graph.
No configurar reintentos automaticos del job sin considerar posibles correos duplicados:
una respuesta perdida despues de aceptar sendMail no garantiza que no se haya enviado.

## Periodo y alcance

Por defecto: primer dia del mes de ayer hasta ayer inclusive, en horario de Honduras.
El primer dia de cada mes reporta el mes anterior completo. `REPORT_END_DATE` permite
elegir otro cierre anterior al dia actual. Se excluye el dia en curso.

`REPORT_QUEUE_IDS` muestra el listado de colas de Genesys con busqueda por nombre
y seleccion multiple, tanto al ejecutar como al programar. Vacio incluye todas
las colas accesibles con actividad de voz inbound. Los IDs se resuelven automaticamente;
tambien se aceptan valores anteriores con IDs separados por coma o punto y coma.
El alcance depende de las divisiones y permisos del cliente OAuth; no se presume que
incluya todas las colas de la organizacion.

El HTML presenta acumulado, evolucion diaria y las 20 colas de mayor volumen.
El Excel incluye todas las colas consultadas y tres hojas: Resumen, Diario y Detalle,
con filtros, fechas reales, porcentajes y formulas para promedios ponderados.
Detalle conserva conteos y sumas originales para permitir recalcular indicadores.
El CSV contiene
el detalle por fecha y cola con actividad. Los dias sin actividad aparecen en cero
en el resumen diario; los promedios sin denominador aparecen como raya.

Metricas: nOffered count, tAnswered count, tAbandon count, porcentaje de abandono,
tAnswered sum/count (espera media hasta atender), tHandle sum/count (gestion media).
Se convierten milisegundos a segundos y se ponderan promedios por cantidades.
Son eventos de cola: transferencias pueden contabilizar una conversacion en varias
colas. Las metricas se atribuyen a sus intervalos y pueden actualizarse tardíamente;
ofrecidas no tiene que igualar atendidas mas abandonadas.

Definiciones oficiales:
https://help.genesys.cloud/articles/view-available-columns-in-performance-views-by-category/

## Variables globales

Lee `GENESYS_CLIENT_ID`, `GENESYS_CLIENT_SECRET` y `GENESYS_REGION` desde PyFlow.
Solo al enviar utiliza `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`
y `GRAPH_SENDER_EMAIL`. No guarda credenciales en el codigo ni necesita HANA.

El CSV de restauracion se importo con `backend/scripts/import-global-variables.ps1`:
25 variables, 12 marcadas secretas. Tambien se marcaron `DEBMEDIA_SQL_PASSWORD`
y `BZ_HANA_PASSWORD`, que originalmente no estaban marcadas.
La marca secreta oculta los valores en la interfaz; no implica cifrado en SQL Server.

## Revision de los procesos existentes

- `GNS_Colas_y_Volumenes`: consulta catalogo y agregados de Genesys, carga HANA y
  manda un correo tecnico de ejecucion (filas cargadas y errores). Incluye varios
  medios y direcciones; no ofrece directamente este resumen inbound ejecutivo.
- `GNS_Performance`: orientado al rendimiento de agentes y carga a HANA.
- El nuevo proceso consulta Genesys en lectura y no ejecuta cargas ni borrados HANA.

## Verificacion

Python 3.9+ y paquete `tzdata` en Windows. La instalacion utilizada tiene Python 3.12
y tzdata; la ruta del interprete quedo guardada en el registro del script.

Se comprobaron fechas de cierre y cambio de mes, rechazo de dias incompletos,
filtros inbound/voice, zona horaria, promedios ponderados, divisiones por cero
y escape HTML. La vista previa real del 1 al 28 de octubre de 2026 termino
correctamente, sin enviar correo.

Si se reinstala Python, actualizar el interprete del script en PyFlow.

## Plantilla corporativa y Excel (1.1.0)

Encabezado rojo, logo blanco `input/logo-04.png` suministrado por el usuario y
fuente principal Neo Sans Std, con Arial como alternativa en el correo.
La fuente no venia en el ZIP y no se instala ni distribuye con el reporte.
El destinatario debe tenerla disponible para verla exactamente.

`config/build_excel.mjs` genera el Excel con `@oai/artifact-tool` desde el JSON de metricas
originales. Requiere Node.js en PATH (o `PYFLOW_NODE_COMMAND`) y esa biblioteca.
En esta PC, `node_modules` es una junction al runtime de bibliotecas de Codex.
Al mover el proceso a otra PC hay que provisionar esa dependencia y conservar
`config/build_excel.mjs` y `input` junto al script Python. No son secretos.

El archivo Excel es obligatorio para el envio: si no se puede generar, el proceso
falla antes de enviar el correo. El adjunto directo se limita a menos de 3 MB;
si supera ese tamaño, el proceso solicita reducir el alcance y no envia un correo
sin datos. Graph sendMail no se reintenta automaticamente para evitar duplicados.

Se verificaron las tres hojas renderizadas, formulas sin errores y conciliacion de
los totales con 1,251 filas de detalle en la prueba real. Se reviso visualmente el
HTML en navegador y se probo con un mock el payload de correo con Excel y logo CID.
No se realizo envio real ni comprobacion de renderizado en Outlook.

## Orden del correo (1.2.0)

KPI → resumen por cola → gráfico diario → tabla diaria.
El gráfico usa barras para ofrecidas (eje izquierdo) y una línea roja para
porcentaje de abandono (eje derecho). Los días sin ofrecidas no tienen tasa,
por lo que interrumpen la línea. Se genera localmente con Pillow como PNG y
se integra mediante CID en el correo. No requiere JavaScript ni servicios externos.
El Excel continúa adjunto. Las consultas, filtros y cálculos existentes no cambian.
