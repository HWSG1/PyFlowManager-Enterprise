# PyFlow Manager - Scripts para Azure SQL Database

Este paquete contiene una versión adaptada de los scripts de SQL Server para Azure SQL Database.

## Archivos

1. `01_Create_Database_AzureSQL.sql`
   - Se ejecuta conectado a la base `master` del servidor lógico de Azure SQL.
   - Crea la base `PyFlowManager` si no existe.

2. `02_Create_Schema_Seed_User_AzureSQL.sql`
   - Se ejecuta conectado directamente a la base `PyFlowManager`.
   - Crea tablas, índices, vistas, procedimientos almacenados, catálogos iniciales y el usuario administrador de la aplicación.
   - Crea el usuario contenido `pyflow_app` para que el backend se conecte a la base.

## Orden de ejecución

### Paso 1 - Crear base

Conectarse a `master` en Azure SQL y ejecutar:

```sql
01_Create_Database_AzureSQL.sql
```

Si la base ya existe, este paso puede omitirse.

### Paso 2 - Crear objetos y semilla

Abrir una nueva conexión directamente a la base:

```text
PyFlowManager
```

Luego ejecutar:

```sql
02_Create_Schema_Seed_User_AzureSQL.sql
```

## Usuario de aplicación

El script crea un usuario contenido de base de datos:

```text
pyflow_app
```

Este usuario no requiere `CREATE LOGIN` en `master`.

Antes de ejecutar en producción, cambiar esta contraseña dentro del archivo 02:

```sql
CREATE USER [pyflow_app]
WITH PASSWORD = N'CAMBIAR_PASSWORD_SEGURO_2026!';
```

Permiso asignado:

```sql
ALTER ROLE db_owner ADD MEMBER [pyflow_app];
```

El permiso queda limitado únicamente a la base `PyFlowManager`.

## Usuario administrador de la aplicación

El script mantiene el usuario inicial del sistema PyFlow Manager:

```text
Usuario: admin
Contraseña inicial: PyFlow123*
```

La contraseña está almacenada como hash PBKDF2 en la tabla `Users`.

## .env sugerido para backend en Azure SQL

```env
DB_SERVER=tu-servidor.database.windows.net
DB_PORT=1433
DB_DATABASE=PyFlowManager
DB_USER=pyflow_app
DB_PASSWORD=CAMBIAR_PASSWORD_SEGURO_2026!
DB_ENCRYPT=true
DB_TRUST_SERVER_CERTIFICATE=false
```

## Diferencias principales contra SQL Server on-premise

- No se usa `USE [master]` ni `USE [PyFlowManager]` dentro del archivo 02.
- No se usa `CREATE LOGIN` para la aplicación.
- Se usa usuario contenido de base de datos: `CREATE USER ... WITH PASSWORD`.
- No se configuran rutas físicas MDF/LDF.
- No se requiere puerto dinámico ni instancia nombrada; Azure SQL usa puerto 1433.
