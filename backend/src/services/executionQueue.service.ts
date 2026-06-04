import { getPool, sql } from "../db/sql";
import { runScript } from "./scriptRunner";

let isProcessingQueue = false;

export async function processExecutionQueue(): Promise<void> {
  if (isProcessingQueue) {
    return;
  }

  isProcessingQueue = true;

  try {
    const pool = await getPool();

    const maxResult = await pool.request()
      .input("environment_id", sql.Int, 3)
      .query(`
        SELECT TOP 1 setting_value
        FROM dbo.SystemSettings
        WHERE environment_id = @environment_id
          AND setting_key = 'MAX_CONCURRENT_EXECUTIONS'
      `);

    const maxConcurrentExecutions = Number(
      maxResult.recordset[0]?.setting_value || 3
    );

    const runningResult = await pool.request().query(`
      SELECT COUNT(*) AS running
      FROM dbo.ScriptExecutions
      WHERE status = 'Ejecutando'
    `);

    const running = Number(
      runningResult.recordset[0]?.running || 0
    );

    if (running >= maxConcurrentExecutions) {
      return;
    }

    const pendingResult = await pool.request().query(`
      SELECT TOP 1 *
      FROM dbo.ExecutionQueue WITH (READPAST)
      WHERE status = 'PENDING'
      ORDER BY created_at ASC
    `);

    if (!pendingResult.recordset.length) {
      return;
    }

    const queueItem = pendingResult.recordset[0];

    await pool.request()
      .input("id", sql.Int, queueItem.id)
      .query(`
        UPDATE dbo.ExecutionQueue
        SET status = 'RUNNING'
        WHERE id = @id AND status = 'PENDING'
      `);

    try {
      const parameters =
        queueItem.parameters_json
          ? JSON.parse(queueItem.parameters_json)
          : {};

    await runScript(
        queueItem.script_id,
        undefined,
        parameters,
        true,
        queueItem.schedule_id || undefined,
        queueItem.schedule_id ? 'schedule' : 'queue'
      );

      await pool.request()
        .input("id", sql.Int, queueItem.id)
        .query(`
          UPDATE dbo.ExecutionQueue
          SET status = 'COMPLETED'
          WHERE id = @id
        `);

      console.log(
        `[QUEUE] Script ${queueItem.script_id} ejecutado desde cola`
      );
    } catch (error) {

      await pool.request()
        .input("id", sql.Int, queueItem.id)
        .query(`
          UPDATE dbo.ExecutionQueue
          SET status = 'FAILED'
          WHERE id = @id
        `);

      console.error(
        `[QUEUE] Error procesando cola ${queueItem.id}`,
        error
      );
    }

  } catch (error) {
    console.error(
      "[QUEUE] Error general procesando cola:",
      error
    );
  } finally {
    isProcessingQueue = false;
  }
}