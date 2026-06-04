/*
PyFlow Manager - Azure SQL Database
Archivo 01 - Creación de base de datos.

EJECUCIÓN:
1) Conectarse a la base [master] del servidor lógico de Azure SQL.
2) Ejecutar este script con el usuario administrador del servidor lógico o un usuario con permiso CREATE DATABASE.
3) Después de crear la base, abrir una nueva conexión directamente a [PyFlowManager] y ejecutar el archivo 02.

Nota: Si el DBA ya creó la base, omitir este archivo y ejecutar directamente el archivo 02 dentro de la base destino.
*/

IF DB_ID(N'PyFlowManager') IS NULL
BEGIN
    CREATE DATABASE [PyFlowManager];
END
GO

ALTER DATABASE [PyFlowManager] SET QUERY_STORE = ON;
GO

SELECT name, database_id, create_date
FROM sys.databases
WHERE name = N'PyFlowManager';
GO
