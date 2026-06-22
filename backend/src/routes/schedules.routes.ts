import { Router } from 'express';
import { CronExpressionParser } from 'cron-parser';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';
import { requireAuth, requireScriptAccess } from '../services/security.service';
import { auditEvent } from '../services/audit.service';

const router = Router();
const TIMEZONE = 'America/Tegucigalpa';
router.use(requireAuth);

function calculateNextRunAt(cronExpression: string, fromDate: Date = new Date()): Date {
  const interval = CronExpressionParser.parse(cronExpression, {
    currentDate: fromDate,
    tz: TIMEZONE
  });

  return interval.next().toDate();
}

function normalizeParameters(parameters: any): Record<string, string> {
  const result: Record<string, string> = {};

  if (!parameters || typeof parameters !== 'object') {
    return result;
  }

  for (const [key, value] of Object.entries(parameters)) {
    result[String(key)] = value === null || value === undefined ? '' : String(value);
  }

  return result;
}

router.get('/', async (req, res, next) => {
  try {
    const pool = await getPool();
    const user = (req as any).user;

    const result = await pool.request()
      .input('user_id', sql.Int, user.id)
      .input('is_super_admin', sql.Bit, !!user.is_super_admin)
      .query(`
      SELECT
        sch.id,
        sch.script_id,
        s.name AS script_name,
        sch.cron_expression,
        sch.frequency_label,
        sch.next_run_at,
        sch.last_run_at,
        sch.last_status,
        sch.is_active
      FROM dbo.Schedules sch
      JOIN dbo.Scripts s ON s.id = sch.script_id
      WHERE sch.is_active = 1
        AND (@is_super_admin = 1 OR (
          EXISTS (
            SELECT 1 FROM dbo.UserRoles ur
            JOIN dbo.RolePermissions rp ON rp.role_id = ur.role_id
            JOIN dbo.Permissions p ON p.id = rp.permission_id
            WHERE ur.user_id = @user_id AND p.permission_key = 'scripts.view'
          )
          AND (
            NOT EXISTS (SELECT 1 FROM dbo.ScriptAccess sa WHERE sa.script_id = sch.script_id)
            OR EXISTS (
              SELECT 1 FROM dbo.ScriptAccess sa
              WHERE sa.script_id = sch.script_id AND sa.user_id = @user_id AND sa.can_view = 1
            )
          )
        ))
      ORDER BY sch.next_run_at
    `);

    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.post('/', requireScriptAccess('schedule'), async (req, res, next) => {
  try {
    const body = req.body || {};

    const scriptId = Number(body.scriptId || body.script_id);
    const cronExpression = String(body.cronExpression || body.cron_expression || '').trim();
    const parameters = normalizeParameters(body.parameters);

    if (!scriptId) {
      return res.status(400).json({
        error: true,
        message: 'Debe seleccionar un script.'
      });
    }

    if (!cronExpression) {
      return res.status(400).json({
        error: true,
        message: 'Debe ingresar una expresión CRON.'
      });
    }

    let nextRunAt: Date;

    try {
      nextRunAt = calculateNextRunAt(cronExpression);
    } catch {
      return res.status(400).json({
        error: true,
        message: 'La expresión CRON no es válida.'
      });
    }

    const pool = await getPool();
    const transaction = new sql.Transaction(pool);

    await transaction.begin();

    try {
      const request = new sql.Request(transaction);

      const result = await request
        .input('script_id', sql.Int, scriptId)
        .input('created_by_user_id', sql.Int, body.created_by_user_id || env.defaultUserId)
        .input('cron_expression', sql.NVarChar(100), cronExpression)
        .input('frequency_label', sql.NVarChar(150), body.frequency || body.frequency_label || null)
        .input('next_run_at', sql.DateTime2, nextRunAt)
        .query(`
          INSERT INTO dbo.Schedules (
            script_id,
            created_by_user_id,
            cron_expression,
            frequency_label,
            next_run_at,
            is_active,
            created_at,
            updated_at
          )
          OUTPUT INSERTED.*
          VALUES (
            @script_id,
            @created_by_user_id,
            @cron_expression,
            @frequency_label,
            @next_run_at,
            1,
            SYSUTCDATETIME(),
            SYSUTCDATETIME()
          )
        `);

      const schedule = result.recordset[0];

      for (const [key, value] of Object.entries(parameters)) {
        await new sql.Request(transaction)
          .input('schedule_id', sql.Int, schedule.id)
          .input('param_key', sql.NVarChar(150), key)
          .input('param_value', sql.NVarChar(sql.MAX), value)
          .query(`
            INSERT INTO dbo.ScheduleParameters (
              schedule_id,
              param_key,
              param_value
            )
            VALUES (
              @schedule_id,
              @param_key,
              @param_value
            )
          `);
      }

      await transaction.commit();
      await auditEvent(req, 'schedule.create', 'schedule', schedule.id, null, {
        script_id: scriptId,
        cron_expression: cronExpression,
        parameters
      });
      res.status(201).json(schedule);
    } catch (err) {
      await transaction.rollback();
      throw err;
    }
  } catch (err) {
    next(err);
  }
});

router.delete('/:id', requireScriptAccess('schedule'), async (req, res, next) => {
  try {
    const scheduleId = Number(req.params.id);
    const pool = await getPool();
    const before = await pool.request().input('id', sql.Int, scheduleId)
      .query('SELECT * FROM dbo.Schedules WHERE id=@id');

    await pool.request()
      .input('id', sql.Int, scheduleId)
      .query(`
        UPDATE dbo.Schedules
        SET
          is_active = 0,
          updated_at = SYSUTCDATETIME()
        WHERE id = @id
      `);

    await auditEvent(req, 'schedule.delete', 'schedule', scheduleId, before.recordset[0] || null, { is_active: false });
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

router.patch('/:id/toggle', requireScriptAccess('schedule'), async (req, res, next) => {
  try {
    const pool = await getPool();
    const id = Number(req.params.id);
    const before = await pool.request().input('id', sql.Int, id)
      .query('SELECT * FROM dbo.Schedules WHERE id=@id');

    await pool.request()
      .input('id', sql.Int, id)
      .query(`
        UPDATE dbo.Schedules
        SET
          is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
          updated_at = SYSUTCDATETIME()
        WHERE id = @id
      `);

    await auditEvent(req, 'schedule.toggle', 'schedule', id, before.recordset[0] || null, {
      is_active: !before.recordset[0]?.is_active
    });
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

router.get('/:id', requireScriptAccess('view'), async (req, res, next) => {
  try {
    const pool = await getPool();
    const scheduleId = Number(req.params.id);

    const schedule = await pool.request()
      .input('id', sql.Int, scheduleId)
      .query(`
        SELECT *
        FROM dbo.Schedules
        WHERE id = @id
      `);

    if (!schedule.recordset.length) {
      return res.status(404).json({
        error: true,
        message: 'Programación no encontrada.'
      });
    }

    const params = await pool.request()
      .input('id', sql.Int, scheduleId)
      .query(`
        SELECT
          param_key,
          param_value
        FROM dbo.ScheduleParameters
        WHERE schedule_id = @id
      `);

    res.json({
      schedule: schedule.recordset[0],
      parameters: params.recordset
    });
  } catch (err) {
    next(err);
  }
});

router.put('/:id', requireScriptAccess('schedule'), async (req, res, next) => {
  try {
    const pool = await getPool();
    const scheduleId = Number(req.params.id);
    const body = req.body || {};
    const before = await pool.request().input('id', sql.Int, scheduleId)
      .query(`SELECT s.*, (SELECT param_key,param_value FROM dbo.ScheduleParameters WHERE schedule_id=s.id FOR JSON PATH) parameters_json
              FROM dbo.Schedules s WHERE s.id=@id`);

    const scriptId = Number(body.scriptId || body.script_id);
    const cronExpression = String(body.cronExpression || body.cron_expression || '').trim();
    const parameters = normalizeParameters(body.parameters);

    if (!scriptId) {
      return res.status(400).json({
        error: true,
        message: 'Debe seleccionar un script.'
      });
    }

    if (!cronExpression) {
      return res.status(400).json({
        error: true,
        message: 'Debe ingresar una expresión CRON.'
      });
    }

    let nextRunAt: Date;

    try {
      nextRunAt = calculateNextRunAt(cronExpression);
    } catch {
      return res.status(400).json({
        error: true,
        message: 'La expresión CRON no es válida.'
      });
    }

    const transaction = new sql.Transaction(pool);
    await transaction.begin();

    try {
      const updateResult = await new sql.Request(transaction)
        .input('id', sql.Int, scheduleId)
        .input('script_id', sql.Int, scriptId)
        .input('cron_expression', sql.NVarChar(100), cronExpression)
        .input('frequency_label', sql.NVarChar(150), body.frequency || body.frequency_label || null)
        .input('next_run_at', sql.DateTime2, nextRunAt)
        .query(`
          UPDATE dbo.Schedules
          SET
            script_id = @script_id,
            cron_expression = @cron_expression,
            frequency_label = @frequency_label,
            next_run_at = @next_run_at,
            last_error = NULL,
            updated_at = SYSUTCDATETIME()
          WHERE id = @id
        `);

      if (!updateResult.rowsAffected[0]) {
        await transaction.rollback();
        return res.status(404).json({
          error: true,
          message: 'Programación no encontrada.'
        });
      }

      await new sql.Request(transaction)
        .input('id', sql.Int, scheduleId)
        .query(`
          DELETE FROM dbo.ScheduleParameters
          WHERE schedule_id = @id
        `);

      for (const [key, value] of Object.entries(parameters)) {
        await new sql.Request(transaction)
          .input('schedule_id', sql.Int, scheduleId)
          .input('param_key', sql.NVarChar(150), key)
          .input('param_value', sql.NVarChar(sql.MAX), value)
          .query(`
            INSERT INTO dbo.ScheduleParameters (
              schedule_id,
              param_key,
              param_value
            )
            VALUES (
              @schedule_id,
              @param_key,
              @param_value
            )
          `);
      }

      await transaction.commit();
      await auditEvent(req, 'schedule.update', 'schedule', scheduleId, before.recordset[0] || null, {
        script_id: scriptId,
        cron_expression: cronExpression,
        frequency_label: body.frequency || body.frequency_label || null,
        next_run_at: nextRunAt,
        parameters
      });
      res.json({ ok: true, next_run_at: nextRunAt });
    } catch (err) {
      await transaction.rollback();
      throw err;
    }
  } catch (err) {
    next(err);
  }
});

export default router;
