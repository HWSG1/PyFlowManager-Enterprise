import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { logBus } from '../services/logBus';
import { requireAuth, requireExecutionAccess } from '../services/security.service';

const router = Router();

router.get('/', requireAuth, async (req, res, next) => {
  try {
    const pool = await getPool();
    const user = (req as any).user;
    const result = await pool.request()
      .input('user_id', sql.Int, user.id)
      .input('is_super_admin', sql.Bit, !!user.is_super_admin)
      .query(`
      SELECT TOP 200
        ex.id,
        s.name AS script_name,
        ex.status,
        ex.trigger_type,
        ex.start_time,
        ex.end_time,
        ex.duration_seconds,
        ISNULL(u.username, 'Sistema') AS triggered_by,
        ex.error_message
      FROM dbo.ScriptExecutions ex
      JOIN dbo.Scripts s ON s.id = ex.script_id
      LEFT JOIN dbo.Users u ON u.id = ex.triggered_by_user_id
      WHERE @is_super_admin = 1 OR (
        EXISTS (
          SELECT 1 FROM dbo.UserRoles ur
          JOIN dbo.RolePermissions rp ON rp.role_id = ur.role_id
          JOIN dbo.Permissions p ON p.id = rp.permission_id
          WHERE ur.user_id = @user_id AND p.permission_key = 'scripts.view'
        )
        AND (
          NOT EXISTS (SELECT 1 FROM dbo.ScriptAccess sa WHERE sa.script_id = ex.script_id)
          OR EXISTS (
            SELECT 1 FROM dbo.ScriptAccess sa
            WHERE sa.script_id = ex.script_id AND sa.user_id = @user_id AND sa.can_view = 1
          )
        )
      )
      ORDER BY ex.start_time DESC
    `);
    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.get('/:id/logs', requireAuth, requireExecutionAccess('view'), async (req, res, next) => {
  try {
    const pool = await getPool();
    const id = Number(req.params.id);

    const result = await pool.request()
      .input('id', sql.Int, id)
      .query(`
        SELECT
          id,
          execution_id,
          log_level,
          message,
          logged_at,
          source
        FROM dbo.ExecutionLogs
        WHERE execution_id = @id
        ORDER BY logged_at ASC, id ASC
      `);

    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.get('/:id/parameters', requireAuth, requireExecutionAccess('view'), async (req, res, next) => {
  try {
    const pool = await getPool();

    const executionId = Number(req.params.id);

    const result = await pool.request()
      .input('execution_id', sql.Int, executionId)
      .query(`
        SELECT
          id,
          param_key,
          param_value,
          created_at
        FROM dbo.ExecutionParameters
        WHERE execution_id = @execution_id
        ORDER BY param_key
      `);

    res.json(result.recordset);

  } catch (err) {
    next(err);
  }
});

router.get('/:id/stream', requireAuth, requireExecutionAccess('view'), async (req, res) => {
  const executionId = Number(req.params.id);

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive'
  });

  const eventName = `execution:${executionId}`;

  const handler = (payload: any) => {
    res.write(`data: ${JSON.stringify(payload)}\n\n`);
  };

  logBus.on(eventName, handler);

  req.on('close', () => {
    logBus.off(eventName, handler);
  });
});

export default router;
