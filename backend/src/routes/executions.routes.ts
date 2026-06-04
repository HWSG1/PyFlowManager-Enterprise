import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { logBus } from '../services/logBus';

const router = Router();

router.get('/', async (_req, res, next) => {
  try {
    const pool = await getPool();
    const result = await pool.request().query(`
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
      ORDER BY ex.start_time DESC
    `);
    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.get('/:id/logs', async (req, res, next) => {
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

router.get('/:id/parameters', async (req, res, next) => {
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

router.get('/:id/stream', async (req, res) => {
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
