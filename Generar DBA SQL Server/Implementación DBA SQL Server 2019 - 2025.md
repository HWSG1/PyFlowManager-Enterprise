# README - Instalación Base de Datos PyFlow Manager

## 1. Objetivo

Este documento describe los pasos recomendados para preparar la base de datos de **PyFlow Manager** en SQL Server.

El script de creación de base de datos ya se encuentra validado. Este README sirve como guía para que el DBA o el equipo de infraestructura ejecute la creación, configure el usuario de aplicación y entregue la información necesaria para conectar el backend.

---

## 2. Requisitos previos

Antes de ejecutar el script, validar lo siguiente:

- SQL Server 2019 o superior.
- Acceso con un usuario administrador de la instancia SQL Server.
- Permisos para crear bases de datos.
- Permisos para crear login SQL Server o usuario equivalente.
- Nombre definido para la base de datos: `PyFlowManager`.
- Definición de ambiente: Desarrollo, QA o Producción.

---

## 3. Creación de la base de datos

El DBA debe ejecutar el script de creación de base de datos desde SQL Server Management Studio (SSMS) o herramienta equivalente.

Ejemplo:

```sql
CREATE DATABASE PyFlowManager;
GO
```

Luego debe cambiar el contexto a la base creada:

```sql
USE PyFlowManager;
GO
```

Posteriormente se debe ejecutar el script completo de estructura de PyFlow Manager, el cual crea:

- Tablas.
- Llaves primarias.
- Llaves foráneas.
- Índices.
- Vistas.
- Procedimientos almacenados.
- Catálogos iniciales.
- Roles y permisos del sistema.
- Parámetros base.
- Usuario administrador inicial de la aplicación.

---

## 4. Usuario SQL para la aplicación

Se recomienda crear un usuario exclusivo para que el backend de PyFlow Manager se conecte a la base de datos.

Nombre sugerido:

```text
pyflow_app
```

Este usuario debe ser utilizado únicamente por la aplicación, no por usuarios finales.

---

## 5. Creación del login SQL Server

El DBA debe crear el login a nivel de servidor.

Ejemplo:

```sql
USE master;
GO

CREATE LOGIN pyflow_app
WITH PASSWORD = 'CAMBIAR_PASSWORD_SEGURO';
GO
```

> La contraseña debe ser definida por el DBA según las políticas internas de seguridad.

---

## 6. Creación del usuario dentro de la base

Después de crear el login, el DBA debe crear el usuario dentro de la base `PyFlowManager`.

```sql
USE PyFlowManager;
GO

CREATE USER pyflow_app
FOR LOGIN pyflow_app;
GO
```

---

## 7. Permisos requeridos

Para la instalación inicial, el usuario necesita permisos suficientes para crear y modificar objetos de base de datos.

La opción recomendada durante instalación es asignar `db_owner` únicamente sobre la base `PyFlowManager`:

```sql
USE PyFlowManager;
GO

ALTER ROLE db_owner
ADD MEMBER pyflow_app;
GO
```

Este permiso permite:

- Crear tablas.
- Modificar tablas.
- Crear vistas.
- Crear procedimientos almacenados.
- Crear funciones.
- Crear índices.
- Ejecutar procedimientos.
- Insertar registros.
- Actualizar registros.
- Eliminar registros.
- Consultar información.

---

## 8. Permisos que NO requiere

El usuario `pyflow_app` no debe tener permisos administrativos sobre toda la instancia SQL Server.

No requiere:

- `sysadmin`.
- `serveradmin`.
- `securityadmin`.
- Acceso a otras bases de datos.
- Permisos sobre `master`, excepto los mínimos necesarios para autenticación.
- Permiso para crear otras bases de datos.
- Permiso para eliminar bases de datos.

---

## 9. Usuario administrador inicial de la aplicación

El script de PyFlow Manager debe insertar un usuario administrador inicial en la tabla `Users`.

Usuario de aplicación:

```text
admin
```

Contraseña inicial:

```text
PyFlow123*
```

La contraseña debe almacenarse en la tabla usando hash PBKDF2, no en texto plano.

Hash esperado:

```text
pbkdf2$120000$0c4c2254ea8ecfb455695492535ff7d9$10eea0514ad93e8ad1344114461ceca4fe10f9a9dac353a591d241f2d0b42c98df921f09875bca238be072a5918e9bd536e21a0d48b1076614625cfacc2e4f1f
```

Después del primer ingreso, se recomienda cambiar la contraseña del usuario `admin`.

---

## 10. Cadena de conexión del backend

Una vez creada la base y el usuario SQL, el DBA debe entregar al equipo técnico:

- Servidor SQL.
- Puerto.
- Nombre de la base de datos.
- Usuario de aplicación.
- Contraseña.
- Indicar si usa certificado SSL o conexión cifrada.
- Indicar si requiere VPN o red interna.

Ejemplo de variables de conexión:

```env
DB_HOST=SERVIDOR_SQL
DB_PORT=1433
DB_NAME=PyFlowManager
DB_USER=pyflow_app
DB_PASSWORD=CAMBIAR_PASSWORD_SEGURO
DB_ENCRYPT=false
DB_TRUST_SERVER_CERTIFICATE=true
```

En producción, los valores de cifrado deben ajustarse según las políticas de seguridad de la empresa.

---

## 11. Validación posterior a la instalación

Después de ejecutar el script, validar que existan las tablas principales:

```sql
USE PyFlowManager;
GO

SELECT name
FROM sys.tables
ORDER BY name;
GO
```

Validar que exista el usuario administrador de la aplicación:

```sql
SELECT username, is_active, auth_provider
FROM dbo.Users
WHERE username = 'admin';
GO
```

Validar que existan los ambientes:

```sql
SELECT *
FROM dbo.Environments;
GO
```

Validar que existan roles y permisos:

```sql
SELECT *
FROM dbo.Roles;

SELECT *
FROM dbo.Permissions;
GO
```

---

## 12. Recomendación de ejecución

Para ambientes corporativos se recomienda separar la instalación en tres archivos:

```text
01_CreateDatabase.sql
02_CreateSchema.sql
03_SeedData.sql
```

Responsabilidad sugerida:

- `01_CreateDatabase.sql`: ejecutado por DBA.
- `02_CreateSchema.sql`: ejecutado por DBA o usuario autorizado.
- `03_SeedData.sql`: ejecutado por DBA o usuario autorizado.

---

## 13. Consideraciones de seguridad

- No usar el usuario `sa` para la aplicación.
- No compartir contraseñas en texto plano por correo.
- No usar usuarios personales para la cadena de conexión.
- Usar un usuario exclusivo para PyFlow Manager.
- Cambiar la contraseña inicial del usuario `admin`.
- Restringir el acceso de red al servidor SQL.
- Permitir conexión únicamente desde el servidor de aplicación.
- Mantener respaldos periódicos de la base de datos.

---

## 14. Resumen para el DBA

Se solicita:

1. Crear base de datos `PyFlowManager`.
2. Ejecutar script de estructura e inicialización.
3. Crear login SQL `pyflow_app`.
4. Crear usuario `pyflow_app` dentro de `PyFlowManager`.
5. Asignar `db_owner` a `pyflow_app` únicamente sobre `PyFlowManager`.
6. Entregar cadena de conexión al equipo técnico.
7. Validar que el usuario `admin` exista en la tabla `Users`.

---

## 15. Contacto técnico

Sistema: PyFlow Manager  
Responsable técnico: Odair Josué Umanzor Murillo
Base de datos: SQL Server 2019 o superior
