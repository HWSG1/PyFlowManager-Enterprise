/*
PyFlow Manager - Usuarios, roles y política de contraseña inicial.

Ejecutar en bases existentes antes de usar:
- asignación de roles al crear/editar usuarios;
- cambio obligatorio de contraseña después del primer login;
- cambio de contraseña desde el front.
*/

IF COL_LENGTH('dbo.Users', 'must_change_password') IS NULL
BEGIN
    ALTER TABLE dbo.Users
        ADD must_change_password bit NOT NULL
            CONSTRAINT DF_Users_must_change_password DEFAULT (0);
END
GO

UPDATE dbo.Users
SET must_change_password = 0
WHERE must_change_password IS NULL;
GO
