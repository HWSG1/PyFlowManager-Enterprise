import { CronExpressionParser } from 'cron-parser';
import { getPool, sql } from '../db/sql';
import { runScript } from './scriptRunner';

const TIMEZONE = 'America/Tegucigalpa';
const SCHEDULER_INTERVAL_MS = 60_000;

let schedulerStarted = false;
let schedulerRunning = false;

function getNextRunAt(cronExpression: string, fromDate?: Date): Date {
  const now = new Date();
  let baseDate = fromDate && !Number.isNaN(fromDate.getTime()) ? fromDate : now;
  let nextRunAt: Date | null = null;

  // Si el backend estuvo detenido o el ciclo se atrasó, evitamos generar una fecha vencida.
  // Esto impide que un daily/weekly/interval se ejecute varias veces seguidas por el mismo next_run_at.
  for (let i = 0; i < 100; i++) {
    const interval = CronExpressionParser.parse(cronExpression, {
      currentDate: baseDate,
      tz: TIMEZONE
    });

    nextRunAt = interval.next().toDate();

    if (nextRunAt.getTime() > now.getTime()) {
      return nextRunAt;
    }

    baseDate = nextRunAt;
  }

  if (!nextRunAt) {
    throw new Error('No se pudo calcular la próxima ejecución.');
  }

  return nextRunAt;
}

export function startScheduler() {
  if (schedulerStarted) return;

  schedulerStarted = true;

  console.log('[SCHEDULER] Scheduler iniciado.');

  setInterval(async () => {
    if (schedulerRunning) return;

    schedulerRunning = true;

    try {
      const pool = await getPool();

      const result = await pool.request().query(`
        SELECT
          id,
          script_id,
          cron_expression,
          next_run_at
        FROM dbo.Schedules
        WHERE is_active = 1
          AND next_run_at <= SYSUTCDATETIME()
        ORDER BY next_run_at ASC
      `);

      for (const schedule of result.recordset) {
        let nextRunAt: Date;

        try {
          nextRunAt = getNextRunAt(
            schedule.cron_expression,
            schedule.next_run_at ? new Date(schedule.next_run_at) : new Date()
          );
        } catch (err: any) {
          console.error(`[SCHEDULER] CRON inválido schedule ${schedule.id}:`, err.message);

          await pool.request()
            .input('id', sql.Int, schedule.id)
            .input('error_message', sql.NVarChar(sql.MAX), err.message)
            .query(`
              UPDATE dbo.Schedules
              SET
                last_error = @error_message,
                is_active = 0,
                updated_at = SYSUTCDATETIME()
              WHERE id = @id
            `);

          continue;
        }

        // Reclamo atómico del schedule. Si otro ciclo/instancia ya lo tomó, rowsAffected será 0.
        const claimResult = await pool.request()
          .input('id', sql.Int, schedule.id)
          .input('next_run_at', sql.DateTime2, nextRunAt)
          .query(`
            UPDATE dbo.Schedules
            SET
              last_run_at = SYSUTCDATETIME(),
              next_run_at = @next_run_at,
              last_error = NULL,
              updated_at = SYSUTCDATETIME()
            WHERE id = @id
              AND is_active = 1
              AND next_run_at <= SYSUTCDATETIME()
          `);

        if (!claimResult.rowsAffected[0]) {
          continue;
        }

        try {
          console.log(`[SCHEDULER] Ejecutando schedule ${schedule.id}, script ${schedule.script_id}`);
          console.log(`[SCHEDULER] Próxima ejecución schedule ${schedule.id}: ${nextRunAt.toISOString()}`);

          const paramsResult = await pool.request()
            .input('schedule_id', sql.Int, schedule.id)
            .query(`
              SELECT
                param_key,
                param_value
              FROM dbo.ScheduleParameters
              WHERE schedule_id = @schedule_id
            `);

          const scheduleParameters: Record<string, string> = {};

          for (const p of paramsResult.recordset) {
            scheduleParameters[p.param_key] = String(p.param_value ?? '');
          }

          await runScript(
            schedule.script_id,
            undefined,
            scheduleParameters,
            false,
            schedule.id,
            'schedule'
          );
        } catch (err: any) {
          console.error(`[SCHEDULER] Error ejecutando schedule ${schedule.id}:`, err.message);

          await pool.request()
            .input('id', sql.Int, schedule.id)
            .input('error_message', sql.NVarChar(sql.MAX), err.message)
            .query(`
              UPDATE dbo.Schedules
              SET
                last_error = @error_message,
                updated_at = SYSUTCDATETIME()
              WHERE id = @id
            `);
        }
      }
    } catch (err: any) {
      console.error('[SCHEDULER] Error general:', err.message);
    } finally {
      schedulerRunning = false;
    }
  }, SCHEDULER_INTERVAL_MS);
}
