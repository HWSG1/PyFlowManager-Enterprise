/*
PyFlow Manager - Script de creación limpia y semilla base.
Generado a partir del script SQL original y del manual adjunto.
Notas:
1) No incluye rutas físicas MDF/LDF para que SQL Server use su carpeta DATA predeterminada.
2) Crea el login SQL pyflow_user si no existe. Cambie la contraseña temporal según la política del entorno.
3) Usuario inicial de aplicación: admin / PyFlow123* con hash PBKDF2 indicado por el solicitante.
*/
/* ADVERTENCIA: ejecutar sobre una base nueva/vacía. Si PyFlowManager ya tiene objetos, respalde y elimine la base antes de recrearla. */
USE [master]
GO
IF DB_ID(N'PyFlowManager') IS NULL
BEGIN
    CREATE DATABASE [PyFlowManager];
END
GO
ALTER DATABASE [PyFlowManager] SET COMPATIBILITY_LEVEL = 150
GO
ALTER DATABASE [PyFlowManager] SET RECOVERY FULL
GO
ALTER DATABASE [PyFlowManager] SET PAGE_VERIFY CHECKSUM
GO
ALTER DATABASE [PyFlowManager] SET QUERY_STORE = ON
GO
USE [PyFlowManager]
GO
/****** Objeto: Table [dbo].[Schedules] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Schedules](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[script_id] [int] NOT NULL,
	[created_by_user_id] [int] NOT NULL,
	[cron_expression] [nvarchar](100) NOT NULL,
	[frequency_label] [nvarchar](150) NULL,
	[timezone_name] [nvarchar](100) NOT NULL,
	[next_run_at] [datetime2](0) NULL,
	[last_run_at] [datetime2](0) NULL,
	[last_status] [nvarchar](20) NULL,
	[last_error] [nvarchar](max) NULL,
	[run_on_startup] [bit] NOT NULL,
	[is_active] [bit] NOT NULL,
	[max_retries] [smallint] NOT NULL,
	[retry_delay_seconds] [int] NOT NULL,
	[created_at] [datetime2](0) NOT NULL,
	[updated_at] [datetime2](0) NULL,
 CONSTRAINT [PK_Schedules] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ScriptExecutions] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ScriptExecutions](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[script_id] [int] NOT NULL,
	[script_version_id] [int] NULL,
	[schedule_id] [int] NULL,
	[triggered_by_user_id] [int] NULL,
	[parent_execution_id] [int] NULL,
	[status] [nvarchar](20) NOT NULL,
	[trigger_type] [nvarchar](20) NOT NULL,
	[start_time] [datetime2](3) NOT NULL,
	[end_time] [datetime2](3) NULL,
	[duration_seconds] [int] NULL,
	[exit_code] [int] NULL,
	[retry_attempt] [smallint] NOT NULL,
	[process_id] [int] NULL,
	[machine_name] [nvarchar](255) NULL,
	[command_line] [nvarchar](max) NULL,
	[working_directory] [nvarchar](1000) NULL,
	[error_message] [nvarchar](max) NULL,
 CONSTRAINT [PK_ScriptExecutions] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[Environments] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Environments](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[name] [nvarchar](50) NOT NULL,
	[description] [nvarchar](255) NULL,
	[is_active] [bit] NOT NULL,
	[created_at] [datetime2](0) NOT NULL,
 CONSTRAINT [PK_Environments] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Environments_name] UNIQUE NONCLUSTERED 
(
	[name] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[Users] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Users](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[username] [nvarchar](100) NOT NULL,
	[email] [nvarchar](255) NOT NULL,
	[display_name] [nvarchar](255) NULL,
	[auth_provider] [nvarchar](30) NOT NULL,
	[azure_ad_object_id] [nvarchar](100) NULL,
	[domain_user] [nvarchar](150) NULL,
	[password_hash] [nvarchar](512) NULL,
	[role] [nvarchar](50) NOT NULL,
	[is_active] [bit] NOT NULL,
	[created_at] [datetime2](0) NOT NULL,
	[updated_at] [datetime2](0) NULL,
	[last_login] [datetime2](0) NULL,
	[theme_key] [nvarchar](100) NULL,
	[preferred_theme] [nvarchar](100) NULL,
	[must_change_password] [bit] NOT NULL,
 CONSTRAINT [PK_Users] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Users_email] UNIQUE NONCLUSTERED 
(
	[email] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Users_username] UNIQUE NONCLUSTERED 
(
	[username] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[Scripts] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Scripts](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[created_by_user_id] [int] NOT NULL,
	[environment_id] [int] NOT NULL,
	[name] [nvarchar](255) NOT NULL,
	[description] [nvarchar](1000) NULL,
	[category] [nvarchar](100) NOT NULL,
	[current_version] [nvarchar](30) NOT NULL,
	[file_path] [nvarchar](1000) NOT NULL,
	[working_directory] [nvarchar](1000) NULL,
	[python_interpreter] [nvarchar](1000) NULL,
	[author] [nvarchar](255) NULL,
	[is_active] [bit] NOT NULL,
	[allow_manual_run] [bit] NOT NULL,
	[created_at] [datetime2](0) NOT NULL,
	[updated_at] [datetime2](0) NOT NULL,
 CONSTRAINT [PK_Scripts] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Scripts_name_env] UNIQUE NONCLUSTERED 
(
	[name] ASC,
	[environment_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: View [dbo].[vw_ScriptsSummary] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   VIEW [dbo].[vw_ScriptsSummary]
AS
SELECT
    s.id,
    s.name,
    s.description,
    s.category,
    s.current_version,
    s.file_path,
    s.is_active,
    s.allow_manual_run,
    s.created_at,
    s.updated_at,
    e.name AS environment_name,
    u.username AS created_by,

    last_ex.id AS last_execution_id,
    last_ex.status AS last_execution_status,
    last_ex.start_time AS last_execution_start_time,
    last_ex.end_time AS last_execution_end_time,
    last_ex.duration_seconds AS last_duration_seconds,
    last_ex.error_message AS last_error_message,

    sch.id AS schedule_id,
    sch.cron_expression,
    sch.frequency_label,
    sch.next_run_at,

    success_count.total_success,
    error_count.total_errors
FROM dbo.Scripts s
JOIN dbo.Environments e
    ON e.id = s.environment_id
JOIN dbo.Users u
    ON u.id = s.created_by_user_id
OUTER APPLY (
    SELECT TOP 1
        ex.id,
        ex.status,
        ex.start_time,
        ex.end_time,
        ex.duration_seconds,
        ex.error_message
    FROM dbo.ScriptExecutions ex
    WHERE ex.script_id = s.id
    ORDER BY ex.start_time DESC
) last_ex
OUTER APPLY (
    SELECT COUNT(*) AS total_success
    FROM dbo.ScriptExecutions ex
    WHERE ex.script_id = s.id
      AND ex.status = 'Exitoso'
) success_count
OUTER APPLY (
    SELECT COUNT(*) AS total_errors
    FROM dbo.ScriptExecutions ex
    WHERE ex.script_id = s.id
      AND ex.status = 'Error'
) error_count
LEFT JOIN dbo.Schedules sch
    ON sch.script_id = s.id
   AND sch.is_active = 1;
GO
/****** Objeto: View [dbo].[vw_RunningExecutions] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   VIEW [dbo].[vw_RunningExecutions]
AS
SELECT
    ex.id AS execution_id,
    s.name AS script_name,
    s.category,
    env.name AS environment_name,
    u.username AS triggered_by,
    ex.trigger_type,
    ex.start_time,
    DATEDIFF(SECOND, ex.start_time, SYSUTCDATETIME()) AS elapsed_seconds,
    ex.process_id,
    ex.machine_name
FROM dbo.ScriptExecutions ex
JOIN dbo.Scripts s ON s.id = ex.script_id
JOIN dbo.Environments env ON env.id = s.environment_id
LEFT JOIN dbo.Users u ON u.id = ex.triggered_by_user_id
WHERE ex.status = 'Ejecutando';

GO
/****** Objeto: Table [dbo].[ExecutionFiles] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ExecutionFiles](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[execution_id] [int] NOT NULL,
	[file_name] [nvarchar](255) NOT NULL,
	[file_path] [nvarchar](1000) NOT NULL,
	[file_type] [nvarchar](30) NOT NULL,
	[mime_type] [nvarchar](150) NULL,
	[file_size_bytes] [bigint] NULL,
	[checksum_sha256] [nvarchar](128) NULL,
	[is_deleted] [bit] NOT NULL,
	[created_at] [datetime2](0) NOT NULL,
 CONSTRAINT [PK_ExecutionFiles] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: View [dbo].[vw_ExecutionFiles] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   VIEW [dbo].[vw_ExecutionFiles]
AS
SELECT
    f.id,
    f.execution_id,
    f.file_name,
    f.file_type,
    f.mime_type,
    f.file_path,
    CAST(f.file_size_bytes / 1048576.0 AS DECIMAL(18,2)) AS file_size_mb,
    f.created_at,
    s.name AS script_name,
    ex.status AS execution_status,
    ex.start_time AS execution_start_time
FROM dbo.ExecutionFiles f
JOIN dbo.ScriptExecutions ex ON ex.id = f.execution_id
JOIN dbo.Scripts s ON s.id = ex.script_id
WHERE f.is_deleted = 0;

GO
/****** Objeto: Table [dbo].[ExecutionLogs] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ExecutionLogs](
	[id] [bigint] IDENTITY(1,1) NOT NULL,
	[execution_id] [int] NOT NULL,
	[log_level] [nvarchar](10) NOT NULL,
	[message] [nvarchar](max) NOT NULL,
	[logged_at] [datetime2](3) NOT NULL,
	[line_number] [int] NULL,
	[source] [nvarchar](100) NULL,
 CONSTRAINT [PK_ExecutionLogs] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: View [dbo].[vw_RecentErrors] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   VIEW [dbo].[vw_RecentErrors]
AS
SELECT TOP 200
    ex.id AS execution_id,
    s.name AS script_name,
    env.name AS environment_name,
    ex.start_time,
    ex.end_time,
    ex.duration_seconds,
    ex.error_message,
    last_log.message AS last_error_log
FROM dbo.ScriptExecutions ex
JOIN dbo.Scripts s ON s.id = ex.script_id
JOIN dbo.Environments env ON env.id = s.environment_id
OUTER APPLY (
    SELECT TOP 1 l.message
    FROM dbo.ExecutionLogs l
    WHERE l.execution_id = ex.id
      AND l.log_level IN ('ERROR', 'CRITICAL')
    ORDER BY l.logged_at DESC
) last_log
WHERE ex.status = 'Error'
ORDER BY ex.start_time DESC;

GO
/****** Objeto: Table [dbo].[AuthMethods] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[AuthMethods](
	[method_key] [nvarchar](50) NOT NULL,
	[method_name] [nvarchar](120) NOT NULL,
	[is_enabled] [bit] NOT NULL,
	[config_json] [nvarchar](max) NULL,
PRIMARY KEY CLUSTERED 
(
	[method_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ConfigurationAudit] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ConfigurationAudit](
	[id] [bigint] IDENTITY(1,1) NOT NULL,
	[module_key] [nvarchar](100) NOT NULL,
	[setting_key] [nvarchar](150) NOT NULL,
	[old_value] [nvarchar](max) NULL,
	[new_value] [nvarchar](max) NULL,
	[changed_by] [nvarchar](150) NULL,
	[ip_address] [nvarchar](80) NULL,
	[user_agent] [nvarchar](500) NULL,
	[changed_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ExecutionParameters] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ExecutionParameters](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[execution_id] [int] NOT NULL,
	[param_key] [nvarchar](150) NOT NULL,
	[param_value] [nvarchar](max) NULL,
	[created_at] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ExecutionQueue] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ExecutionQueue](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[script_id] [int] NOT NULL,
	[schedule_id] [int] NULL,
	[parameters_json] [nvarchar](max) NULL,
	[status] [nvarchar](20) NULL,
	[created_at] [datetime2](7) NULL,
	[started_at] [datetime2](7) NULL,
	[completed_at] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[GlobalVariables] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[GlobalVariables](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[var_key] [nvarchar](150) NOT NULL,
	[var_value] [nvarchar](max) NULL,
	[is_secret] [bit] NOT NULL,
	[description] [nvarchar](500) NULL,
	[created_at] [datetime2](7) NOT NULL,
	[updated_at] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[var_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[LoginAudit] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[LoginAudit](
	[id] [bigint] IDENTITY(1,1) NOT NULL,
	[user_id] [int] NULL,
	[username] [nvarchar](150) NULL,
	[auth_method] [nvarchar](50) NULL,
	[success] [bit] NOT NULL,
	[ip_address] [nvarchar](80) NULL,
	[user_agent] [nvarchar](500) NULL,
	[message] [nvarchar](500) NULL,
	[created_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[PasswordResetTokens] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[PasswordResetTokens](
	[id] [bigint] IDENTITY(1,1) NOT NULL,
	[user_id] [int] NOT NULL,
	[token_hash] [nvarchar](128) NOT NULL,
	[channel] [nvarchar](20) NOT NULL,
	[expires_at] [datetime2](7) NOT NULL,
	[used_at] [datetime2](7) NULL,
	[created_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[Permissions] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Permissions](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[permission_key] [nvarchar](150) NOT NULL,
	[module_key] [nvarchar](100) NOT NULL,
	[action_key] [nvarchar](100) NOT NULL,
	[description] [nvarchar](500) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[permission_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[RoleAuthConfig] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[RoleAuthConfig](
	[role_id] [int] NOT NULL,
	[method_key] [nvarchar](50) NOT NULL,
	[is_required] [bit] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[role_id] ASC,
	[method_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[RolePermissions] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[RolePermissions](
	[role_id] [int] NOT NULL,
	[permission_id] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[role_id] ASC,
	[permission_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[Roles] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Roles](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[role_name] [nvarchar](120) NOT NULL,
	[description] [nvarchar](500) NULL,
	[auth_method] [nvarchar](50) NULL,
	[created_at] [datetime2](7) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[role_name] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ScheduleParameters] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ScheduleParameters](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[schedule_id] [int] NOT NULL,
	[param_key] [nvarchar](150) NOT NULL,
	[param_value] [nvarchar](max) NULL,
	[created_at] [datetime2](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ScriptDependencies] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ScriptDependencies](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[script_id] [int] NOT NULL,
	[depends_on_script_id] [int] NOT NULL,
	[execution_order] [smallint] NOT NULL,
	[dependency_type] [nvarchar](20) NOT NULL,
	[is_active] [bit] NOT NULL,
	[created_at] [datetime2](0) NOT NULL,
 CONSTRAINT [PK_ScriptDependencies] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_ScriptDependencies] UNIQUE NONCLUSTERED 
(
	[script_id] ASC,
	[depends_on_script_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ScriptParameters] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ScriptParameters](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[script_id] [int] NOT NULL,
	[secret_id] [int] NULL,
	[param_key] [nvarchar](150) NOT NULL,
	[param_value] [nvarchar](1000) NULL,
	[param_type] [nvarchar](30) NOT NULL,
	[is_secret] [bit] NOT NULL,
	[description] [nvarchar](500) NULL,
	[created_at] [datetime2](0) NOT NULL,
	[updated_at] [datetime2](0) NULL,
	[options_json] [nvarchar](max) NULL,
	[label] [nvarchar](255) NULL,
	[is_required] [bit] NOT NULL,
	[control_type] [nvarchar](30) NULL,
	[global_key] [nvarchar](150) NULL,
 CONSTRAINT [PK_ScriptParameters] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_ScriptParameters_key] UNIQUE NONCLUSTERED 
(
	[script_id] ASC,
	[param_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[ScriptVersions] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ScriptVersions](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[script_id] [int] NOT NULL,
	[version] [nvarchar](30) NOT NULL,
	[file_path] [nvarchar](1000) NOT NULL,
	[checksum_sha256] [nvarchar](128) NULL,
	[change_notes] [nvarchar](max) NULL,
	[created_by_user_id] [int] NULL,
	[created_at] [datetime2](0) NOT NULL,
	[is_current] [bit] NOT NULL,
 CONSTRAINT [PK_ScriptVersions] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_ScriptVersions_script_version] UNIQUE NONCLUSTERED 
(
	[script_id] ASC,
	[version] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[Secrets] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Secrets](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[secret_key] [nvarchar](150) NOT NULL,
	[encrypted_value] [varbinary](max) NOT NULL,
	[description] [nvarchar](500) NULL,
	[updated_by_user_id] [int] NULL,
	[updated_at] [datetime2](0) NOT NULL,
 CONSTRAINT [PK_Secrets] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Secrets_secret_key] UNIQUE NONCLUSTERED 
(
	[secret_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[SystemSettings] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[SystemSettings](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[environment_id] [int] NOT NULL,
	[setting_key] [nvarchar](150) NOT NULL,
	[setting_value] [nvarchar](1000) NOT NULL,
	[description] [nvarchar](500) NULL,
	[updated_by_user_id] [int] NULL,
	[updated_at] [datetime2](0) NOT NULL,
	[setting_type] [nvarchar](50) NULL,
	[category] [nvarchar](80) NULL,
	[is_critical] [bit] NOT NULL,
	[updated_by] [nvarchar](150) NULL,
	[created_at] [datetime2](7) NOT NULL,
 CONSTRAINT [PK_SystemSettings] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_SystemSettings_key_env] UNIQUE NONCLUSTERED 
(
	[setting_key] ASC,
	[environment_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[Themes] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Themes](
	[theme_key] [nvarchar](80) NOT NULL,
	[theme_name] [nvarchar](120) NOT NULL,
	[is_dark] [bit] NOT NULL,
	[tokens_json] [nvarchar](max) NULL,
	[is_enabled] [bit] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[theme_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[UserAuthConfig] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[UserAuthConfig](
	[user_id] [int] NOT NULL,
	[method_key] [nvarchar](50) NOT NULL,
	[is_required] [bit] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[user_id] ASC,
	[method_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[UserPreferences] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[UserPreferences](
	[user_id] [int] NOT NULL,
	[preference_key] [nvarchar](100) NOT NULL,
	[preference_value] [nvarchar](max) NULL,
PRIMARY KEY CLUSTERED 
(
	[user_id] ASC,
	[preference_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Objeto: Table [dbo].[UserRoles] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[UserRoles](
	[user_id] [int] NOT NULL,
	[role_id] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[user_id] ASC,
	[role_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ExecutionFiles_created_at] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ExecutionFiles_created_at] ON [dbo].[ExecutionFiles]
(
	[created_at] DESC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ExecutionFiles_execution_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ExecutionFiles_execution_id] ON [dbo].[ExecutionFiles]
(
	[execution_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Objeto: Index [IX_ExecutionFiles_file_type] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ExecutionFiles_file_type] ON [dbo].[ExecutionFiles]
(
	[file_type] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ExecutionLogs_execution_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ExecutionLogs_execution_id] ON [dbo].[ExecutionLogs]
(
	[execution_id] ASC,
	[logged_at] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Objeto: Index [IX_ExecutionLogs_level] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ExecutionLogs_level] ON [dbo].[ExecutionLogs]
(
	[log_level] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Schedules_is_active] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Schedules_is_active] ON [dbo].[Schedules]
(
	[is_active] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Schedules_next_run] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Schedules_next_run] ON [dbo].[Schedules]
(
	[next_run_at] ASC
)
WHERE ([is_active]=(1))
WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Schedules_script_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Schedules_script_id] ON [dbo].[Schedules]
(
	[script_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ScriptDep_depends_on] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ScriptDep_depends_on] ON [dbo].[ScriptDependencies]
(
	[depends_on_script_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ScriptDep_script_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ScriptDep_script_id] ON [dbo].[ScriptDependencies]
(
	[script_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Executions_schedule_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Executions_schedule_id] ON [dbo].[ScriptExecutions]
(
	[schedule_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Executions_script_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Executions_script_id] ON [dbo].[ScriptExecutions]
(
	[script_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Executions_start_time] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Executions_start_time] ON [dbo].[ScriptExecutions]
(
	[start_time] DESC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Objeto: Index [IX_Executions_status] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Executions_status] ON [dbo].[ScriptExecutions]
(
	[status] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ScriptParameters_script_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ScriptParameters_script_id] ON [dbo].[ScriptParameters]
(
	[script_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Objeto: Index [IX_Scripts_category] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Scripts_category] ON [dbo].[Scripts]
(
	[category] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Scripts_environment] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Scripts_environment] ON [dbo].[Scripts]
(
	[environment_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Scripts_is_active] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Scripts_is_active] ON [dbo].[Scripts]
(
	[is_active] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ScriptVersions_is_current] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ScriptVersions_is_current] ON [dbo].[ScriptVersions]
(
	[script_id] ASC,
	[is_current] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_ScriptVersions_script_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_ScriptVersions_script_id] ON [dbo].[ScriptVersions]
(
	[script_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Objeto: Index [IX_Secrets_secret_key] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Secrets_secret_key] ON [dbo].[Secrets]
(
	[secret_key] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Objeto: Index [IX_Users_azure_ad_object_id] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Users_azure_ad_object_id] ON [dbo].[Users]
(
	[azure_ad_object_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
SET ANSI_PADDING ON
GO
/****** Objeto: Index [IX_Users_email] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Users_email] ON [dbo].[Users]
(
	[email] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
/****** Objeto: Index [IX_Users_is_active] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
CREATE NONCLUSTERED INDEX [IX_Users_is_active] ON [dbo].[Users]
(
	[is_active] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, SORT_IN_TEMPDB = OFF, DROP_EXISTING = OFF, ONLINE = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
GO
ALTER TABLE [dbo].[AuthMethods] ADD  DEFAULT ((1)) FOR [is_enabled]
GO
ALTER TABLE [dbo].[ConfigurationAudit] ADD  DEFAULT (sysdatetime()) FOR [changed_at]
GO
ALTER TABLE [dbo].[Environments] ADD  CONSTRAINT [DF_Environments_is_active]  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Environments] ADD  CONSTRAINT [DF_Environments_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[ExecutionFiles] ADD  CONSTRAINT [DF_ExecutionFiles_is_deleted]  DEFAULT ((0)) FOR [is_deleted]
GO
ALTER TABLE [dbo].[ExecutionFiles] ADD  CONSTRAINT [DF_ExecutionFiles_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[ExecutionLogs] ADD  CONSTRAINT [DF_ExecutionLogs_level]  DEFAULT ('INFO') FOR [log_level]
GO
ALTER TABLE [dbo].[ExecutionLogs] ADD  CONSTRAINT [DF_ExecutionLogs_logged_at]  DEFAULT (sysutcdatetime()) FOR [logged_at]
GO
ALTER TABLE [dbo].[ExecutionParameters] ADD  DEFAULT (getdate()) FOR [created_at]
GO
ALTER TABLE [dbo].[ExecutionQueue] ADD  DEFAULT ('pending') FOR [status]
GO
ALTER TABLE [dbo].[ExecutionQueue] ADD  DEFAULT (getdate()) FOR [created_at]
GO
ALTER TABLE [dbo].[GlobalVariables] ADD  DEFAULT ((0)) FOR [is_secret]
GO
ALTER TABLE [dbo].[GlobalVariables] ADD  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[LoginAudit] ADD  DEFAULT (sysdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[PasswordResetTokens] ADD  DEFAULT ('email') FOR [channel]
GO
ALTER TABLE [dbo].[PasswordResetTokens] ADD  DEFAULT (sysdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[RoleAuthConfig] ADD  DEFAULT ((0)) FOR [is_required]
GO
ALTER TABLE [dbo].[Roles] ADD  DEFAULT (sysdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[ScheduleParameters] ADD  DEFAULT (getdate()) FOR [created_at]
GO
ALTER TABLE [dbo].[Schedules] ADD  CONSTRAINT [DF_Schedules_timezone]  DEFAULT ('America/Tegucigalpa') FOR [timezone_name]
GO
ALTER TABLE [dbo].[Schedules] ADD  CONSTRAINT [DF_Schedules_run_on_startup]  DEFAULT ((0)) FOR [run_on_startup]
GO
ALTER TABLE [dbo].[Schedules] ADD  CONSTRAINT [DF_Schedules_is_active]  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Schedules] ADD  CONSTRAINT [DF_Schedules_max_retries]  DEFAULT ((3)) FOR [max_retries]
GO
ALTER TABLE [dbo].[Schedules] ADD  CONSTRAINT [DF_Schedules_retry_delay]  DEFAULT ((60)) FOR [retry_delay_seconds]
GO
ALTER TABLE [dbo].[Schedules] ADD  CONSTRAINT [DF_Schedules_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[ScriptDependencies] ADD  CONSTRAINT [DF_ScriptDependencies_order]  DEFAULT ((1)) FOR [execution_order]
GO
ALTER TABLE [dbo].[ScriptDependencies] ADD  CONSTRAINT [DF_ScriptDependencies_type]  DEFAULT ('hard') FOR [dependency_type]
GO
ALTER TABLE [dbo].[ScriptDependencies] ADD  CONSTRAINT [DF_ScriptDependencies_is_active]  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[ScriptDependencies] ADD  CONSTRAINT [DF_ScriptDependencies_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[ScriptExecutions] ADD  CONSTRAINT [DF_ScriptExecutions_status]  DEFAULT ('Ejecutando') FOR [status]
GO
ALTER TABLE [dbo].[ScriptExecutions] ADD  CONSTRAINT [DF_ScriptExecutions_trigger]  DEFAULT ('manual') FOR [trigger_type]
GO
ALTER TABLE [dbo].[ScriptExecutions] ADD  CONSTRAINT [DF_ScriptExecutions_start_time]  DEFAULT (sysutcdatetime()) FOR [start_time]
GO
ALTER TABLE [dbo].[ScriptExecutions] ADD  CONSTRAINT [DF_ScriptExecutions_retry]  DEFAULT ((0)) FOR [retry_attempt]
GO
ALTER TABLE [dbo].[ScriptParameters] ADD  CONSTRAINT [DF_ScriptParameters_type]  DEFAULT ('env') FOR [param_type]
GO
ALTER TABLE [dbo].[ScriptParameters] ADD  CONSTRAINT [DF_ScriptParameters_is_secret]  DEFAULT ((0)) FOR [is_secret]
GO
ALTER TABLE [dbo].[ScriptParameters] ADD  CONSTRAINT [DF_ScriptParameters_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[ScriptParameters] ADD  DEFAULT ((0)) FOR [is_required]
GO
ALTER TABLE [dbo].[Scripts] ADD  CONSTRAINT [DF_Scripts_current_version]  DEFAULT ('1.0.0') FOR [current_version]
GO
ALTER TABLE [dbo].[Scripts] ADD  CONSTRAINT [DF_Scripts_is_active]  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Scripts] ADD  CONSTRAINT [DF_Scripts_allow_manual_run]  DEFAULT ((1)) FOR [allow_manual_run]
GO
ALTER TABLE [dbo].[Scripts] ADD  CONSTRAINT [DF_Scripts_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[Scripts] ADD  CONSTRAINT [DF_Scripts_updated_at]  DEFAULT (sysutcdatetime()) FOR [updated_at]
GO
ALTER TABLE [dbo].[ScriptVersions] ADD  CONSTRAINT [DF_ScriptVersions_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[ScriptVersions] ADD  CONSTRAINT [DF_ScriptVersions_is_current]  DEFAULT ((0)) FOR [is_current]
GO
ALTER TABLE [dbo].[Secrets] ADD  CONSTRAINT [DF_Secrets_updated_at]  DEFAULT (sysutcdatetime()) FOR [updated_at]
GO
ALTER TABLE [dbo].[SystemSettings] ADD  CONSTRAINT [DF_SystemSettings_updated_at]  DEFAULT (sysutcdatetime()) FOR [updated_at]
GO
ALTER TABLE [dbo].[SystemSettings] ADD  DEFAULT ('string') FOR [setting_type]
GO
ALTER TABLE [dbo].[SystemSettings] ADD  DEFAULT ((0)) FOR [is_critical]
GO
ALTER TABLE [dbo].[SystemSettings] ADD  DEFAULT (sysdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[Themes] ADD  DEFAULT ((1)) FOR [is_dark]
GO
ALTER TABLE [dbo].[Themes] ADD  DEFAULT ((1)) FOR [is_enabled]
GO
ALTER TABLE [dbo].[UserAuthConfig] ADD  DEFAULT ((0)) FOR [is_required]
GO
ALTER TABLE [dbo].[Users] ADD  CONSTRAINT [DF_Users_auth_provider]  DEFAULT ('local') FOR [auth_provider]
GO
ALTER TABLE [dbo].[Users] ADD  CONSTRAINT [DF_Users_role]  DEFAULT ('Viewer') FOR [role]
GO
ALTER TABLE [dbo].[Users] ADD  CONSTRAINT [DF_Users_is_active]  DEFAULT ((1)) FOR [is_active]
GO
ALTER TABLE [dbo].[Users] ADD  CONSTRAINT [DF_Users_created_at]  DEFAULT (sysutcdatetime()) FOR [created_at]
GO
ALTER TABLE [dbo].[Users] ADD  CONSTRAINT [DF_Users_must_change_password]  DEFAULT ((0)) FOR [must_change_password]
GO
ALTER TABLE [dbo].[ExecutionFiles]  WITH CHECK ADD  CONSTRAINT [FK_ExecutionFiles_Executions] FOREIGN KEY([execution_id])
REFERENCES [dbo].[ScriptExecutions] ([id])
ON DELETE CASCADE
GO
ALTER TABLE [dbo].[ExecutionFiles] CHECK CONSTRAINT [FK_ExecutionFiles_Executions]
GO
ALTER TABLE [dbo].[ExecutionLogs]  WITH CHECK ADD  CONSTRAINT [FK_ExecutionLogs_Executions] FOREIGN KEY([execution_id])
REFERENCES [dbo].[ScriptExecutions] ([id])
ON DELETE CASCADE
GO
ALTER TABLE [dbo].[ExecutionLogs] CHECK CONSTRAINT [FK_ExecutionLogs_Executions]
GO
ALTER TABLE [dbo].[ExecutionParameters]  WITH CHECK ADD  CONSTRAINT [FK_ExecutionParameters_Execution] FOREIGN KEY([execution_id])
REFERENCES [dbo].[ScriptExecutions] ([id])
GO
ALTER TABLE [dbo].[ExecutionParameters] CHECK CONSTRAINT [FK_ExecutionParameters_Execution]
GO
ALTER TABLE [dbo].[PasswordResetTokens]  WITH CHECK ADD FOREIGN KEY([user_id])
REFERENCES [dbo].[Users] ([id])
GO
ALTER TABLE [dbo].[RoleAuthConfig]  WITH CHECK ADD FOREIGN KEY([role_id])
REFERENCES [dbo].[Roles] ([id])
GO
ALTER TABLE [dbo].[RolePermissions]  WITH CHECK ADD FOREIGN KEY([permission_id])
REFERENCES [dbo].[Permissions] ([id])
GO
ALTER TABLE [dbo].[RolePermissions]  WITH CHECK ADD FOREIGN KEY([role_id])
REFERENCES [dbo].[Roles] ([id])
GO
ALTER TABLE [dbo].[ScheduleParameters]  WITH CHECK ADD  CONSTRAINT [FK_ScheduleParameters_Schedules] FOREIGN KEY([schedule_id])
REFERENCES [dbo].[Schedules] ([id])
GO
ALTER TABLE [dbo].[ScheduleParameters] CHECK CONSTRAINT [FK_ScheduleParameters_Schedules]
GO
ALTER TABLE [dbo].[Schedules]  WITH CHECK ADD  CONSTRAINT [FK_Schedules_Scripts] FOREIGN KEY([script_id])
REFERENCES [dbo].[Scripts] ([id])
ON DELETE CASCADE
GO
ALTER TABLE [dbo].[Schedules] CHECK CONSTRAINT [FK_Schedules_Scripts]
GO
ALTER TABLE [dbo].[Schedules]  WITH CHECK ADD  CONSTRAINT [FK_Schedules_Users] FOREIGN KEY([created_by_user_id])
REFERENCES [dbo].[Users] ([id])
GO
ALTER TABLE [dbo].[Schedules] CHECK CONSTRAINT [FK_Schedules_Users]
GO
ALTER TABLE [dbo].[ScriptDependencies]  WITH CHECK ADD  CONSTRAINT [FK_ScriptDep_DependsOn] FOREIGN KEY([depends_on_script_id])
REFERENCES [dbo].[Scripts] ([id])
GO
ALTER TABLE [dbo].[ScriptDependencies] CHECK CONSTRAINT [FK_ScriptDep_DependsOn]
GO
ALTER TABLE [dbo].[ScriptDependencies]  WITH CHECK ADD  CONSTRAINT [FK_ScriptDep_Script] FOREIGN KEY([script_id])
REFERENCES [dbo].[Scripts] ([id])
ON DELETE CASCADE
GO
ALTER TABLE [dbo].[ScriptDependencies] CHECK CONSTRAINT [FK_ScriptDep_Script]
GO
ALTER TABLE [dbo].[ScriptExecutions]  WITH CHECK ADD  CONSTRAINT [FK_Executions_Parent] FOREIGN KEY([parent_execution_id])
REFERENCES [dbo].[ScriptExecutions] ([id])
GO
ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [FK_Executions_Parent]
GO
ALTER TABLE [dbo].[ScriptExecutions]  WITH CHECK ADD  CONSTRAINT [FK_Executions_Schedules] FOREIGN KEY([schedule_id])
REFERENCES [dbo].[Schedules] ([id])
ON DELETE SET NULL
GO
ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [FK_Executions_Schedules]
GO
ALTER TABLE [dbo].[ScriptExecutions]  WITH CHECK ADD  CONSTRAINT [FK_Executions_Scripts] FOREIGN KEY([script_id])
REFERENCES [dbo].[Scripts] ([id])
GO
ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [FK_Executions_Scripts]
GO
ALTER TABLE [dbo].[ScriptExecutions]  WITH CHECK ADD  CONSTRAINT [FK_Executions_ScriptVersions] FOREIGN KEY([script_version_id])
REFERENCES [dbo].[ScriptVersions] ([id])
GO
ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [FK_Executions_ScriptVersions]
GO
ALTER TABLE [dbo].[ScriptExecutions]  WITH CHECK ADD  CONSTRAINT [FK_Executions_Users] FOREIGN KEY([triggered_by_user_id])
REFERENCES [dbo].[Users] ([id])
ON DELETE SET NULL
GO
ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [FK_Executions_Users]
GO
ALTER TABLE [dbo].[ScriptParameters]  WITH CHECK ADD  CONSTRAINT [FK_ScriptParameters_Scripts] FOREIGN KEY([script_id])
REFERENCES [dbo].[Scripts] ([id])
ON DELETE CASCADE
GO
ALTER TABLE [dbo].[ScriptParameters] CHECK CONSTRAINT [FK_ScriptParameters_Scripts]
GO
ALTER TABLE [dbo].[ScriptParameters]  WITH CHECK ADD  CONSTRAINT [FK_ScriptParameters_Secrets] FOREIGN KEY([secret_id])
REFERENCES [dbo].[Secrets] ([id])
ON DELETE SET NULL
GO
ALTER TABLE [dbo].[ScriptParameters] CHECK CONSTRAINT [FK_ScriptParameters_Secrets]
GO
ALTER TABLE [dbo].[Scripts]  WITH CHECK ADD  CONSTRAINT [FK_Scripts_Environments] FOREIGN KEY([environment_id])
REFERENCES [dbo].[Environments] ([id])
GO
ALTER TABLE [dbo].[Scripts] CHECK CONSTRAINT [FK_Scripts_Environments]
GO
ALTER TABLE [dbo].[Scripts]  WITH CHECK ADD  CONSTRAINT [FK_Scripts_Users] FOREIGN KEY([created_by_user_id])
REFERENCES [dbo].[Users] ([id])
GO
ALTER TABLE [dbo].[Scripts] CHECK CONSTRAINT [FK_Scripts_Users]
GO
ALTER TABLE [dbo].[ScriptVersions]  WITH CHECK ADD  CONSTRAINT [FK_ScriptVersions_Scripts] FOREIGN KEY([script_id])
REFERENCES [dbo].[Scripts] ([id])
ON DELETE CASCADE
GO
ALTER TABLE [dbo].[ScriptVersions] CHECK CONSTRAINT [FK_ScriptVersions_Scripts]
GO
ALTER TABLE [dbo].[ScriptVersions]  WITH CHECK ADD  CONSTRAINT [FK_ScriptVersions_Users] FOREIGN KEY([created_by_user_id])
REFERENCES [dbo].[Users] ([id])
ON DELETE SET NULL
GO
ALTER TABLE [dbo].[ScriptVersions] CHECK CONSTRAINT [FK_ScriptVersions_Users]
GO
ALTER TABLE [dbo].[Secrets]  WITH CHECK ADD  CONSTRAINT [FK_Secrets_Users] FOREIGN KEY([updated_by_user_id])
REFERENCES [dbo].[Users] ([id])
ON DELETE SET NULL
GO
ALTER TABLE [dbo].[Secrets] CHECK CONSTRAINT [FK_Secrets_Users]
GO
ALTER TABLE [dbo].[SystemSettings]  WITH CHECK ADD  CONSTRAINT [FK_SystemSettings_Environments] FOREIGN KEY([environment_id])
REFERENCES [dbo].[Environments] ([id])
GO
ALTER TABLE [dbo].[SystemSettings] CHECK CONSTRAINT [FK_SystemSettings_Environments]
GO
ALTER TABLE [dbo].[SystemSettings]  WITH CHECK ADD  CONSTRAINT [FK_SystemSettings_Users] FOREIGN KEY([updated_by_user_id])
REFERENCES [dbo].[Users] ([id])
ON DELETE SET NULL
GO
ALTER TABLE [dbo].[SystemSettings] CHECK CONSTRAINT [FK_SystemSettings_Users]
GO
ALTER TABLE [dbo].[UserAuthConfig]  WITH CHECK ADD FOREIGN KEY([user_id])
REFERENCES [dbo].[Users] ([id])
GO
ALTER TABLE [dbo].[UserPreferences]  WITH CHECK ADD FOREIGN KEY([user_id])
REFERENCES [dbo].[Users] ([id])
GO
ALTER TABLE [dbo].[UserRoles]  WITH CHECK ADD FOREIGN KEY([role_id])
REFERENCES [dbo].[Roles] ([id])
GO
ALTER TABLE [dbo].[UserRoles]  WITH CHECK ADD FOREIGN KEY([user_id])
REFERENCES [dbo].[Users] ([id])
GO
ALTER TABLE [dbo].[ExecutionFiles]  WITH CHECK ADD  CONSTRAINT [CK_ExecutionFiles_type] CHECK  (([file_type]='other' OR [file_type]='png' OR [file_type]='log' OR [file_type]='json' OR [file_type]='txt' OR [file_type]='zip' OR [file_type]='pdf' OR [file_type]='csv' OR [file_type]='xlsx'))
GO
ALTER TABLE [dbo].[ExecutionFiles] CHECK CONSTRAINT [CK_ExecutionFiles_type]
GO
ALTER TABLE [dbo].[ExecutionLogs]  WITH CHECK ADD  CONSTRAINT [CK_ExecutionLogs_level] CHECK  (([log_level]='CRITICAL' OR [log_level]='ERROR' OR [log_level]='WARNING' OR [log_level]='INFO' OR [log_level]='DEBUG'))
GO
ALTER TABLE [dbo].[ExecutionLogs] CHECK CONSTRAINT [CK_ExecutionLogs_level]
GO
ALTER TABLE [dbo].[Schedules]  WITH CHECK ADD  CONSTRAINT [CK_Schedules_retries] CHECK  (([max_retries]>=(0) AND [max_retries]<=(10)))
GO
ALTER TABLE [dbo].[Schedules] CHECK CONSTRAINT [CK_Schedules_retries]
GO
ALTER TABLE [dbo].[Schedules]  WITH CHECK ADD  CONSTRAINT [CK_Schedules_retry_delay] CHECK  (([retry_delay_seconds]>=(0) AND [retry_delay_seconds]<=(86400)))
GO
ALTER TABLE [dbo].[Schedules] CHECK CONSTRAINT [CK_Schedules_retry_delay]
GO
ALTER TABLE [dbo].[Schedules]  WITH CHECK ADD  CONSTRAINT [CK_Schedules_status] CHECK  (([last_status] IS NULL OR ([last_status]='Ejecutando' OR [last_status]='Cancelado' OR [last_status]='Error' OR [last_status]='Exitoso')))
GO
ALTER TABLE [dbo].[Schedules] CHECK CONSTRAINT [CK_Schedules_status]
GO
ALTER TABLE [dbo].[ScriptDependencies]  WITH CHECK ADD  CONSTRAINT [CK_ScriptDependencies_no_self] CHECK  (([script_id]<>[depends_on_script_id]))
GO
ALTER TABLE [dbo].[ScriptDependencies] CHECK CONSTRAINT [CK_ScriptDependencies_no_self]
GO
ALTER TABLE [dbo].[ScriptDependencies]  WITH CHECK ADD  CONSTRAINT [CK_ScriptDependencies_type] CHECK  (([dependency_type]='soft' OR [dependency_type]='hard'))
GO
ALTER TABLE [dbo].[ScriptDependencies] CHECK CONSTRAINT [CK_ScriptDependencies_type]
GO
ALTER TABLE [dbo].[ScriptExecutions]  WITH CHECK ADD  CONSTRAINT [CK_Executions_status] CHECK  (([status]='Cancelado' OR [status]='Error' OR [status]='Exitoso' OR [status]='Ejecutando'))
GO
ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [CK_Executions_status]
GO
ALTER TABLE [dbo].[ScriptExecutions]  WITH CHECK ADD  CONSTRAINT [CK_Executions_trigger] CHECK  (([trigger_type]='system' OR [trigger_type]='api' OR [trigger_type]='dependency' OR [trigger_type]='schedule' OR [trigger_type]='manual'))
GO
ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [CK_Executions_trigger]
GO
ALTER TABLE [dbo].[ScriptParameters]  WITH CHECK ADD  CONSTRAINT [CK_ScriptParameters_secret_consistency] CHECK  (([is_secret]=(0) AND [param_value] IS NOT NULL OR [is_secret]=(1) AND [secret_id] IS NOT NULL))
GO
ALTER TABLE [dbo].[ScriptParameters] CHECK CONSTRAINT [CK_ScriptParameters_secret_consistency]
GO
ALTER TABLE [dbo].[ScriptParameters]  WITH CHECK ADD  CONSTRAINT [CK_ScriptParameters_type] CHECK  (([param_type]='config' OR [param_type]='argv' OR [param_type]='env'))
GO
ALTER TABLE [dbo].[ScriptParameters] CHECK CONSTRAINT [CK_ScriptParameters_type]
GO
ALTER TABLE [dbo].[Users]  WITH CHECK ADD  CONSTRAINT [CK_Users_auth_provider] CHECK  (([auth_provider]='entra_id' OR [auth_provider]='active_directory' OR [auth_provider]='local'))
GO
ALTER TABLE [dbo].[Users] CHECK CONSTRAINT [CK_Users_auth_provider]
GO
ALTER TABLE [dbo].[Users]  WITH CHECK ADD  CONSTRAINT [CK_Users_password_provider] CHECK  (([auth_provider]='local' AND [password_hash] IS NOT NULL OR ([auth_provider]='entra_id' OR [auth_provider]='active_directory')))
GO
ALTER TABLE [dbo].[Users] CHECK CONSTRAINT [CK_Users_password_provider]
GO
ALTER TABLE [dbo].[Users]  WITH CHECK ADD  CONSTRAINT [CK_Users_role] CHECK  (([role]='Viewer' OR [role]='Operator' OR [role]='Developer' OR [role]='DataArchitect' OR [role]='Admin'))
GO
ALTER TABLE [dbo].[Users] CHECK CONSTRAINT [CK_Users_role]
GO
/****** Objeto: StoredProcedure [dbo].[usp_AddExecutionLog] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE   PROCEDURE [dbo].[usp_AddExecutionLog]
    @execution_id    INT,
    @log_level       NVARCHAR(10),
    @message         NVARCHAR(MAX),
    @line_number     INT = NULL,
    @source          NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.ExecutionLogs (
        execution_id,
        log_level,
        message,
        line_number,
        source
    )
    VALUES (
        @execution_id,
        @log_level,
        @message,
        @line_number,
        @source
    );
END;
GO
/****** Objeto: StoredProcedure [dbo].[usp_FinishScriptExecution] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE PROCEDURE [dbo].[usp_FinishScriptExecution]
    @execution_id INT,
    @status NVARCHAR(20),
    @exit_code INT = NULL,
    @error_message NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE dbo.ScriptExecutions
    SET
        status = @status,
        end_time = GETDATE(),
        exit_code = @exit_code,
        error_message = @error_message,
        duration_seconds = DATEDIFF(SECOND, start_time, GETDATE())
    WHERE id = @execution_id;
END;
GO
/****** Objeto: StoredProcedure [dbo].[usp_GetExecutionOrder] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

-- ============================================================
--  19. Stored procedures operationales
-- ============================================================

CREATE   PROCEDURE [dbo].[usp_GetExecutionOrder]
    @root_script_id INT
AS
BEGIN
    SET NOCOUNT ON;

    WITH DependencyChain AS (
        SELECT
            s.id,
            s.name,
            CAST(0 AS INT) AS depth,
            CAST(s.name AS NVARCHAR(MAX)) AS chain_path
        FROM dbo.Scripts s
        WHERE s.id = @root_script_id

        UNION ALL

        SELECT
            dep.depends_on_script_id,
            s2.name,
            dc.depth + 1,
            CAST(dc.chain_path + N' -> ' + s2.name AS NVARCHAR(MAX))
        FROM dbo.ScriptDependencies dep
        JOIN dbo.Scripts s2 ON s2.id = dep.depends_on_script_id
        JOIN DependencyChain dc ON dc.id = dep.script_id
        WHERE dep.is_active = 1
    )
    SELECT
        id AS script_id,
        name AS script_name,
        depth,
        chain_path
    FROM DependencyChain
    ORDER BY depth DESC, script_name;
END

GO
/****** Objeto: StoredProcedure [dbo].[usp_GetSecret] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   PROCEDURE [dbo].[usp_GetSecret]
    @secret_key NVARCHAR(150)
AS
BEGIN
    SET NOCOUNT ON;

    OPEN SYMMETRIC KEY PyFlowSecretsKey
    DECRYPTION BY CERTIFICATE PyFlowSecretsCert;

    SELECT
        id,
        secret_key,
        CONVERT(NVARCHAR(MAX), DecryptByKey(encrypted_value)) AS plain_value,
        description,
        updated_by_user_id,
        updated_at
    FROM dbo.Secrets
    WHERE secret_key = @secret_key;

    CLOSE SYMMETRIC KEY PyFlowSecretsKey;
END

GO
/****** Objeto: StoredProcedure [dbo].[usp_InsertSecret] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   PROCEDURE [dbo].[usp_InsertSecret]
    @secret_key          NVARCHAR(150),
    @plain_value         NVARCHAR(MAX),
    @description         NVARCHAR(500) = NULL,
    @updated_by_user_id  INT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    OPEN SYMMETRIC KEY PyFlowSecretsKey
    DECRYPTION BY CERTIFICATE PyFlowSecretsCert;

    MERGE dbo.Secrets AS target
    USING (SELECT @secret_key AS secret_key) AS source
        ON target.secret_key = source.secret_key
    WHEN MATCHED THEN
        UPDATE SET
            encrypted_value     = EncryptByKey(Key_GUID('PyFlowSecretsKey'), @plain_value),
            description         = COALESCE(@description, target.description),
            updated_by_user_id  = @updated_by_user_id,
            updated_at          = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (secret_key, encrypted_value, description, updated_by_user_id)
        VALUES (@secret_key, EncryptByKey(Key_GUID('PyFlowSecretsKey'), @plain_value), @description, @updated_by_user_id);

    CLOSE SYMMETRIC KEY PyFlowSecretsKey;
END

GO
/****** Objeto: StoredProcedure [dbo].[usp_StartScriptExecution] Fecha de script: 03/06/2026 07:53:14 p. m. ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE PROCEDURE [dbo].[usp_StartScriptExecution]
    @script_id INT,
    @script_version_id INT = NULL,
    @schedule_id INT = NULL,
    @triggered_by_user_id INT = NULL,
    @parent_execution_id INT = NULL,
    @trigger_type NVARCHAR(20),
    @command_line NVARCHAR(MAX),
    @working_directory NVARCHAR(1000),
    @machine_name NVARCHAR(255),
    @process_id INT = NULL,
    @execution_id INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.ScriptExecutions (
        script_id,
        script_version_id,
        schedule_id,
        triggered_by_user_id,
        parent_execution_id,
        trigger_type,
        status,
        command_line,
        working_directory,
        machine_name,
        process_id,
        start_time
    )
    VALUES (
        @script_id,
        @script_version_id,
        @schedule_id,
        @triggered_by_user_id,
        @parent_execution_id,
        @trigger_type,
        'Ejecutando',
        @command_line,
        @working_directory,
        @machine_name,
        @process_id,
        GETDATE()
    );

    SET @execution_id = SCOPE_IDENTITY();
END;
GO
USE [master]
GO
ALTER DATABASE [PyFlowManager] SET  READ_WRITE 
GO



-- ============================================================
--  SEMILLA BASE PYFLOW MANAGER
--  Incluye ambientes, autenticación, roles, permisos, temas,
--  parámetros del sistema y usuario administrador por defecto.
-- ============================================================

USE PyFlowManager
GO

SET XACT_ABORT ON;
BEGIN TRANSACTION;

SET IDENTITY_INSERT dbo.Environments ON;
IF NOT EXISTS (SELECT 1 FROM dbo.Environments WHERE id = 1) INSERT INTO dbo.Environments (id, name, description, is_active, created_at) VALUES (1, N'Development', N'Ambiente de desarrollo', 1, SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.Environments WHERE id = 2) INSERT INTO dbo.Environments (id, name, description, is_active, created_at) VALUES (2, N'QA', N'Ambiente de pruebas / QA', 1, SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.Environments WHERE id = 3) INSERT INTO dbo.Environments (id, name, description, is_active, created_at) VALUES (3, N'Production', N'Ambiente productivo', 1, SYSUTCDATETIME());
SET IDENTITY_INSERT dbo.Environments OFF;

IF NOT EXISTS (SELECT 1 FROM dbo.AuthMethods WHERE method_key = N'entra') INSERT INTO dbo.AuthMethods (method_key, method_name, is_enabled, config_json) VALUES (N'entra', N'Microsoft Entra ID / Azure AD', 1, NULL);
IF NOT EXISTS (SELECT 1 FROM dbo.AuthMethods WHERE method_key = N'local') INSERT INTO dbo.AuthMethods (method_key, method_name, is_enabled, config_json) VALUES (N'local', N'Usuario y contraseña', 1, NULL);
IF NOT EXISTS (SELECT 1 FROM dbo.AuthMethods WHERE method_key = N'mixed') INSERT INTO dbo.AuthMethods (method_key, method_name, is_enabled, config_json) VALUES (N'mixed', N'Autenticación mixta', 1, NULL);

SET IDENTITY_INSERT dbo.Roles ON;
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE id = 1) INSERT INTO dbo.Roles (id, role_name, description, auth_method, created_at) VALUES (1, N'Super Administrador', N'Acceso total', N'mixed', SYSDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE id = 2) INSERT INTO dbo.Roles (id, role_name, description, auth_method, created_at) VALUES (2, N'Administrador del Sistema', N'Administra configuración y usuarios', N'entra', SYSDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE id = 3) INSERT INTO dbo.Roles (id, role_name, description, auth_method, created_at) VALUES (3, N'Supervisor', N'Supervisión y operación', N'mixed', SYSDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE id = 4) INSERT INTO dbo.Roles (id, role_name, description, auth_method, created_at) VALUES (4, N'Operador', N'Operación de scripts', N'local', SYSDATETIME());
SET IDENTITY_INSERT dbo.Roles OFF;

SET IDENTITY_INSERT dbo.Permissions ON;
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 1) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (1, N'dashboard.view', N'dashboard', N'view', N'Ver dashboard');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 2) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (2, N'scripts.view', N'scripts', N'view', N'Ver scripts');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 3) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (3, N'scripts.create', N'scripts', N'create', N'Crear scripts');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 4) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (4, N'scripts.edit', N'scripts', N'edit', N'Editar scripts');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 5) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (5, N'scripts.execute', N'scripts', N'execute', N'Ejecutar scripts');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 6) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (6, N'executions.cancel', N'executions', N'cancel', N'Cancelar ejecuciones');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 7) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (7, N'logs.view', N'logs', N'view', N'Ver logs');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 8) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (8, N'schedules.create', N'schedules', N'create', N'Crear programaciones');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 9) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (9, N'schedules.delete', N'schedules', N'delete', N'Eliminar programaciones');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 10) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (10, N'users.manage', N'users', N'manage', N'Administrar usuarios');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 11) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (11, N'settings.manage', N'settings', N'manage', N'Administrar configuración');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 12) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (12, N'auth.manage', N'auth', N'manage', N'Cambiar métodos de autenticación');
IF NOT EXISTS (SELECT 1 FROM dbo.Permissions WHERE id = 13) INSERT INTO dbo.Permissions (id, permission_key, module_key, action_key, description) VALUES (13, N'themes.manage', N'themes', N'manage', N'Gestionar temas');
SET IDENTITY_INSERT dbo.Permissions OFF;

IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 1) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 2) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 2);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 3) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 3);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 4) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 4);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 5) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 5);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 6) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 6);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 7) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 7);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 8) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 8);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 9) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 9);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 10) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 10);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 11) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 11);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 12) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 12);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 1 AND permission_id = 13) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (1, 13);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 1) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 2) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 2);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 3) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 3);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 4) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 4);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 5) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 5);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 6) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 6);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 7) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 7);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 8) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 8);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 9) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 9);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 10) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 10);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 11) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 11);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 12) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 12);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 2 AND permission_id = 13) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (2, 13);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 3 AND permission_id = 1) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (3, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 3 AND permission_id = 2) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (3, 2);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 3 AND permission_id = 5) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (3, 5);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 3 AND permission_id = 6) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (3, 6);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 3 AND permission_id = 7) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (3, 7);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 3 AND permission_id = 8) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (3, 8);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 4 AND permission_id = 1) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (4, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 4 AND permission_id = 2) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (4, 2);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 4 AND permission_id = 5) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (4, 5);
IF NOT EXISTS (SELECT 1 FROM dbo.RolePermissions WHERE role_id = 4 AND permission_id = 7) INSERT INTO dbo.RolePermissions (role_id, permission_id) VALUES (4, 7);

SET IDENTITY_INSERT dbo.Users ON;
IF NOT EXISTS (SELECT 1 FROM dbo.Users WHERE id = 1 OR username = N'admin') INSERT INTO dbo.Users (id, username, email, display_name, auth_provider, azure_ad_object_id, domain_user, password_hash, role, is_active, created_at, updated_at, last_login, theme_key, preferred_theme) VALUES (1, N'admin', N'admin@pyflow.local', N'Administrador PyFlow', N'local', NULL, NULL, N'pbkdf2$120000$0c4c2254ea8ecfb455695492535ff7d9$10eea0514ad93e8ad1344114461ceca4fe10f9a9dac353a591d241f2d0b42c98df921f09875bca238be072a5918e9bd536e21a0d48b1076614625cfacc2e4f1f', N'Admin', 1, SYSUTCDATETIME(), SYSUTCDATETIME(), NULL, N'dark-blue', N'dark-blue');
SET IDENTITY_INSERT dbo.Users OFF;
IF NOT EXISTS (SELECT 1 FROM dbo.UserRoles WHERE user_id = 1 AND role_id = 1) INSERT INTO dbo.UserRoles (user_id, role_id) VALUES (1, 1);

IF NOT EXISTS (SELECT 1 FROM dbo.RoleAuthConfig WHERE role_id = 1 AND method_key = N'mixed') INSERT INTO dbo.RoleAuthConfig (role_id, method_key, is_required) VALUES (1, N'mixed', 1);
IF NOT EXISTS (SELECT 1 FROM dbo.RoleAuthConfig WHERE role_id = 2 AND method_key = N'entra') INSERT INTO dbo.RoleAuthConfig (role_id, method_key, is_required) VALUES (2, N'entra', 1);
IF NOT EXISTS (SELECT 1 FROM dbo.RoleAuthConfig WHERE role_id = 3 AND method_key = N'mixed') INSERT INTO dbo.RoleAuthConfig (role_id, method_key, is_required) VALUES (3, N'mixed', 1);
IF NOT EXISTS (SELECT 1 FROM dbo.RoleAuthConfig WHERE role_id = 4 AND method_key = N'local') INSERT INTO dbo.RoleAuthConfig (role_id, method_key, is_required) VALUES (4, N'local', 1);

IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'aurora') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'aurora', N'Aurora', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'banking-blue') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'banking-blue', N'Banking Blue', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'corporate-gray') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'corporate-gray', N'Corporate Gray', 0, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'crimson') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'crimson', N'Crimson', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'cyberpunk') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'cyberpunk', N'Cyberpunk', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'dark-blue') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'dark-blue', N'Dark Blue', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'dracula') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'dracula', N'Dracula', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'emerald') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'emerald', N'Emerald', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'github-dark') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'github-dark', N'GitHub Dark', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'gold') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'gold', N'Gold', 0, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'light') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'light', N'Light', 0, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'matrix') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'matrix', N'Matrix', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'monokai') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'monokai', N'Monokai', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'navy') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'navy', N'Navy', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'nord') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'nord', N'Nord', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'obsidian') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'obsidian', N'Obsidian', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'ocean') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'ocean', N'Ocean', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'purple') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'purple', N'Purple', 1, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'titanium') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'titanium', N'Titanium', 0, NULL, 1);
IF NOT EXISTS (SELECT 1 FROM dbo.Themes WHERE theme_key = N'vscode-dark') INSERT INTO dbo.Themes (theme_key, theme_name, is_dark, tokens_json, is_enabled) VALUES (N'vscode-dark', N'VS Code Dark', 1, NULL, 1);

SET IDENTITY_INSERT dbo.SystemSettings ON;
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'EMAIL_ENABLED' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (16, 1, N'EMAIL_ENABLED', N'true', N'Habilitar envío de correos DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'EXPORT_RETENTION_DAYS' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (15, 1, N'EXPORT_RETENTION_DAYS', N'60', N'Días de retención de exportaciones DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'exports_base_path' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (3, 1, N'exports_base_path', N'C:\PyFlow\prod\exports\', N'Carpeta de exportaciones DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'LOG_RETENTION_DAYS' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (14, 1, N'LOG_RETENTION_DAYS', N'120', N'Días de retención de logs DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'logs_base_path' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (2, 1, N'logs_base_path', N'C:\PyFlow\prod\logs\', N'Carpeta de logs DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'MAX_CONCURRENT_EXECUTIONS' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (13, 1, N'MAX_CONCURRENT_EXECUTIONS', N'10', N'Máximo de ejecuciones simultáneas DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'python_interpreter' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (4, 1, N'python_interpreter', N'py', N'Intérprete Python DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'scripts_base_path' AND environment_id = 1) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (1, 1, N'scripts_base_path', N'C:\PyFlow\prod\scripts\', N'Carpeta base de scripts DEV', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'EMAIL_ENABLED' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (20, 2, N'EMAIL_ENABLED', N'true', N'Habilitar envío de correos QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'EXPORT_RETENTION_DAYS' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (19, 2, N'EXPORT_RETENTION_DAYS', N'60', N'Días de retención de exportaciones QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'exports_base_path' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (7, 2, N'exports_base_path', N'C:\PyFlow\prod\exports\', N'Carpeta de exportaciones QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'LOG_RETENTION_DAYS' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (18, 2, N'LOG_RETENTION_DAYS', N'120', N'Días de retención de logs QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'logs_base_path' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (6, 2, N'logs_base_path', N'C:\PyFlow\prod\logs\', N'Carpeta de logs QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'MAX_CONCURRENT_EXECUTIONS' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (17, 2, N'MAX_CONCURRENT_EXECUTIONS', N'10', N'Máximo de ejecuciones simultáneas QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'python_interpreter' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (8, 2, N'python_interpreter', N'py', N'Intérprete Python QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'scripts_base_path' AND environment_id = 2) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (5, 2, N'scripts_base_path', N'C:\PyFlow\prod\scripts\', N'Carpeta base de scripts QA', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'AUTH_GLOBAL_METHOD' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (31, 3, N'AUTH_GLOBAL_METHOD', N'mixed', N'Método global de autenticación', 1, SYSUTCDATETIME(), N'string', N'auth', 1, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'EXECUTION_TIMEOUT_SECONDS' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (28, 3, N'EXECUTION_TIMEOUT_SECONDS', N'7200', N'Tiempo máximo por ejecución', 1, SYSUTCDATETIME(), N'number', N'execution', 1, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'MAX_CONCURRENT_EXECUTIONS_PER_SCRIPT' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (26, 3, N'MAX_CONCURRENT_EXECUTIONS_PER_SCRIPT', N'3', N'Máximo concurrente por script', 1, SYSUTCDATETIME(), N'number', N'execution', 1, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'MAX_CONCURRENT_EXECUTIONS_PER_USER' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (27, 3, N'MAX_CONCURRENT_EXECUTIONS_PER_USER', N'2', N'Máximo concurrente por usuario', 1, SYSUTCDATETIME(), N'number', N'execution', 1, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'EMAIL_ENABLED' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (24, 3, N'EMAIL_ENABLED', N'true', N'Habilitar envío de correos PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'EXPORT_RETENTION_DAYS' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (23, 3, N'EXPORT_RETENTION_DAYS', N'60', N'Días de retención de exportaciones PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'exports_base_path' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (11, 3, N'exports_base_path', N'C:\PyFlow\prod\exports\', N'Carpeta de exportaciones PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'LOG_RETENTION_DAYS' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (22, 3, N'LOG_RETENTION_DAYS', N'120', N'Días de retención de logs PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'logs_base_path' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (10, 3, N'logs_base_path', N'C:\PyFlow\prod\logs\', N'Carpeta de logs PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'MAX_CONCURRENT_EXECUTIONS' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (21, 3, N'MAX_CONCURRENT_EXECUTIONS', N'10', N'Máximo de ejecuciones simultáneas PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'python_interpreter' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (12, 3, N'python_interpreter', N'py', N'Intérprete Python PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'scripts_base_path' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (9, 3, N'scripts_base_path', N'C:\PyFlow\prod\scripts\', N'Carpeta base de scripts PROD', 1, SYSUTCDATETIME(), N'string', N'general', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'QUEUE_PROCESS_INTERVAL_MS' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (29, 3, N'QUEUE_PROCESS_INTERVAL_MS', N'30000', N'Intervalo de procesamiento de cola', 1, SYSUTCDATETIME(), N'number', N'queue', 1, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'ADMIN_SECURITY_PIN' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (32, 3, N'ADMIN_SECURITY_PIN', N'1234', N'PIN administrativo para cambios críticos', 1, SYSUTCDATETIME(), N'secret', N'security', 1, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'DEFAULT_THEME' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (33, 3, N'DEFAULT_THEME', N'dark-blue', N'Tema predeterminado', 1, SYSUTCDATETIME(), N'string', N'themes', 0, N'admin', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM dbo.SystemSettings WHERE setting_key = N'AUTO_REFRESH_INTERVAL_SECONDS' AND environment_id = 3) INSERT INTO dbo.SystemSettings (id, environment_id, setting_key, setting_value, description, updated_by_user_id, updated_at, setting_type, category, is_critical, updated_by, created_at) VALUES (30, 3, N'AUTO_REFRESH_INTERVAL_SECONDS', N'30', N'Intervalo de actualización automática por pantalla', 1, SYSUTCDATETIME(), N'number', N'ui', 0, N'admin', SYSUTCDATETIME());
SET IDENTITY_INSERT dbo.SystemSettings OFF;

IF NOT EXISTS (SELECT 1 FROM dbo.UserPreferences WHERE user_id = 1 AND preference_key = N'theme') INSERT INTO dbo.UserPreferences (user_id, preference_key, preference_value) VALUES (1, N'theme', N'dark-blue');

COMMIT TRANSACTION;
GO

/* Primera fase: gobierno, reintentos persistentes, alertas, permisos y auditoria. */
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
    ('scripts.edit', 'scripts', 'edit', 'Editar scripts, politicas y versiones'),
    ('scripts.schedule', 'scripts', 'schedule', 'Crear y editar programaciones'),
    ('scripts.manage_access', 'scripts', 'manage_access', 'Administrar permisos por script'),
    ('audit.view', 'audit', 'view', 'Consultar auditoria general')
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
GO


USE master;
GO

IF SUSER_ID(N'pyflow_user') IS NULL
    EXEC(N'CREATE LOGIN pyflow_user WITH PASSWORD = ''PyFlow@2026!'';');
ALTER LOGIN pyflow_user ENABLE;
GO

USE [PyFlowManager];
GO

IF DATABASE_PRINCIPAL_ID(N'pyflow_user') IS NULL
    CREATE USER pyflow_user FOR LOGIN pyflow_user;
GO

IF IS_ROLEMEMBER(N'db_owner', N'pyflow_user') <> 1
    ALTER ROLE db_owner ADD MEMBER pyflow_user;
GO
