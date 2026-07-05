USE [PyFlowManager];
GO

IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = 'CK_Executions_status'
      AND parent_object_id = OBJECT_ID('dbo.ScriptExecutions')
)
BEGIN
    ALTER TABLE [dbo].[ScriptExecutions] DROP CONSTRAINT [CK_Executions_status];
END
GO

ALTER TABLE [dbo].[ScriptExecutions] WITH CHECK ADD CONSTRAINT [CK_Executions_status]
CHECK (([status]='Pausado' OR [status]='Cancelado' OR [status]='Error' OR [status]='Exitoso' OR [status]='Ejecutando'));
GO

ALTER TABLE [dbo].[ScriptExecutions] CHECK CONSTRAINT [CK_Executions_status];
GO

IF EXISTS (
    SELECT 1
    FROM sys.check_constraints
    WHERE name = 'CK_Schedules_status'
      AND parent_object_id = OBJECT_ID('dbo.Schedules')
)
BEGIN
    ALTER TABLE [dbo].[Schedules] DROP CONSTRAINT [CK_Schedules_status];
END
GO

ALTER TABLE [dbo].[Schedules] WITH CHECK ADD CONSTRAINT [CK_Schedules_status]
CHECK (([last_status] IS NULL OR ([last_status]='Pausado' OR [last_status]='Ejecutando' OR [last_status]='Cancelado' OR [last_status]='Error' OR [last_status]='Exitoso')));
GO

ALTER TABLE [dbo].[Schedules] CHECK CONSTRAINT [CK_Schedules_status];
GO
