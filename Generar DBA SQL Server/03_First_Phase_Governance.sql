SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRANSACTION;

IF COL_LENGTH('dbo.Scripts', 'max_retries') IS NULL
    ALTER TABLE dbo.Scripts ADD max_retries SMALLINT NOT NULL CONSTRAINT DF_Scripts_max_retries DEFAULT (0);
IF COL_LENGTH('dbo.Scripts', 'retry_delay_seconds') IS NULL
    ALTER TABLE dbo.Scripts ADD retry_delay_seconds INT NOT NULL CONSTRAINT DF_Scripts_retry_delay DEFAULT (60);
IF COL_LENGTH('dbo.Scripts', 'retry_backoff_factor') IS NULL
    ALTER TABLE dbo.Scripts ADD retry_backoff_factor DECIMAL(6,2) NOT NULL CONSTRAINT DF_Scripts_retry_backoff DEFAULT (1.00);
IF COL_LENGTH('dbo.Scripts', 'alert_on_success') IS NULL
    ALTER TABLE dbo.Scripts ADD alert_on_success BIT NOT NULL CONSTRAINT DF_Scripts_alert_success DEFAULT (0);
IF COL_LENGTH('dbo.Scripts', 'alert_on_failure') IS NULL
    ALTER TABLE dbo.Scripts ADD alert_on_failure BIT NOT NULL CONSTRAINT DF_Scripts_alert_failure DEFAULT (1);
IF COL_LENGTH('dbo.Scripts', 'alert_recipients') IS NULL
    ALTER TABLE dbo.Scripts ADD alert_recipients NVARCHAR(MAX) NULL;

IF COL_LENGTH('dbo.ExecutionQueue', 'available_at') IS NULL
    ALTER TABLE dbo.ExecutionQueue ADD available_at DATETIME2(0) NULL;
IF COL_LENGTH('dbo.ExecutionQueue', 'triggered_by_user_id') IS NULL
    ALTER TABLE dbo.ExecutionQueue ADD triggered_by_user_id INT NULL;
IF COL_LENGTH('dbo.ExecutionQueue', 'trigger_type') IS NULL
    ALTER TABLE dbo.ExecutionQueue ADD trigger_type NVARCHAR(20) NULL;
IF COL_LENGTH('dbo.ExecutionQueue', 'retry_attempt') IS NULL
    ALTER TABLE dbo.ExecutionQueue ADD retry_attempt SMALLINT NOT NULL CONSTRAINT DF_ExecutionQueue_retry_attempt DEFAULT (0);
IF COL_LENGTH('dbo.ExecutionQueue', 'parent_execution_id') IS NULL
    ALTER TABLE dbo.ExecutionQueue ADD parent_execution_id INT NULL;

IF OBJECT_ID('dbo.ScriptAccess', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ScriptAccess (
        script_id INT NOT NULL,
        user_id INT NOT NULL,
        can_view BIT NOT NULL CONSTRAINT DF_ScriptAccess_view DEFAULT (1),
        can_execute BIT NOT NULL CONSTRAINT DF_ScriptAccess_execute DEFAULT (0),
        can_edit BIT NOT NULL CONSTRAINT DF_ScriptAccess_edit DEFAULT (0),
        can_schedule BIT NOT NULL CONSTRAINT DF_ScriptAccess_schedule DEFAULT (0),
        granted_by_user_id INT NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_ScriptAccess_created DEFAULT (SYSUTCDATETIME()),
        updated_at DATETIME2(0) NOT NULL CONSTRAINT DF_ScriptAccess_updated DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_ScriptAccess PRIMARY KEY (script_id, user_id),
        CONSTRAINT FK_ScriptAccess_Script FOREIGN KEY (script_id) REFERENCES dbo.Scripts(id),
        CONSTRAINT FK_ScriptAccess_User FOREIGN KEY (user_id) REFERENCES dbo.Users(id)
    );
END;

IF OBJECT_ID('dbo.AuditEvents', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AuditEvents (
        id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_AuditEvents PRIMARY KEY,
        user_id INT NULL,
        username NVARCHAR(150) NULL,
        action_key NVARCHAR(150) NOT NULL,
        entity_type NVARCHAR(100) NOT NULL,
        entity_id NVARCHAR(150) NULL,
        old_value NVARCHAR(MAX) NULL,
        new_value NVARCHAR(MAX) NULL,
        ip_address NVARCHAR(80) NULL,
        user_agent NVARCHAR(500) NULL,
        created_at DATETIME2(0) NOT NULL CONSTRAINT DF_AuditEvents_created DEFAULT (SYSUTCDATETIME())
    );
    CREATE INDEX IX_AuditEvents_entity ON dbo.AuditEvents(entity_type, entity_id, created_at DESC);
    CREATE INDEX IX_AuditEvents_user ON dbo.AuditEvents(user_id, created_at DESC);
END;

MERGE dbo.Permissions AS target
USING (VALUES
    ('scripts.view', 'scripts', 'view', 'Ver scripts y su historial'),
    ('scripts.execute', 'scripts', 'execute', 'Ejecutar scripts'),
    ('scripts.edit', 'scripts', 'edit', 'Editar scripts, políticas y versiones'),
    ('scripts.schedule', 'scripts', 'schedule', 'Crear y editar programaciones'),
    ('scripts.manage_access', 'scripts', 'manage_access', 'Administrar permisos por script'),
    ('audit.view', 'audit', 'view', 'Consultar auditoría general')
) AS source(permission_key, module_key, action_key, description)
ON target.permission_key = source.permission_key
WHEN NOT MATCHED THEN
    INSERT(permission_key, module_key, action_key, description)
    VALUES(source.permission_key, source.module_key, source.action_key, source.description);

INSERT INTO dbo.RolePermissions(role_id, permission_id)
SELECT r.id, p.id
FROM dbo.Roles r
CROSS JOIN dbo.Permissions p
WHERE r.role_name = 'Super Administrador'
  AND p.permission_key IN ('scripts.view','scripts.execute','scripts.edit','scripts.schedule','scripts.manage_access','audit.view')
  AND NOT EXISTS (
      SELECT 1 FROM dbo.RolePermissions rp WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );

INSERT INTO dbo.RolePermissions(role_id, permission_id)
SELECT DISTINCT existing.role_id, target.id
FROM dbo.RolePermissions existing
JOIN dbo.Permissions source ON source.id = existing.permission_id
JOIN dbo.Permissions target ON target.permission_key =
    CASE
        WHEN source.permission_key = 'schedules.create' THEN 'scripts.schedule'
        WHEN source.permission_key = 'scripts.edit' THEN 'scripts.manage_access'
        WHEN source.permission_key = 'settings.manage' THEN 'audit.view'
    END
WHERE source.permission_key IN ('schedules.create', 'scripts.edit', 'settings.manage')
  AND NOT EXISTS (
      SELECT 1 FROM dbo.RolePermissions rp
      WHERE rp.role_id = existing.role_id AND rp.permission_id = target.id
  );

COMMIT TRANSACTION;

PRINT 'Migración de gobierno, reintentos, alertas y auditoría aplicada correctamente.';
