import { Router } from "express";
import { getPool, sql } from "../db/sql";
import os from "os";

const router = Router();


router.get("/summary", async (_req, res) => {
  try {
    const pool = await getPool();

    const summary = await pool.request().query(`
    DECLARE @todayStart DATETIME = DATEADD(HOUR, -6, CAST(CAST(GETDATE() AS DATE) AS DATETIME));
    DECLARE @tomorrowStart DATETIME = DATEADD(DAY, 1, @todayStart);

    SELECT
        (SELECT COUNT(*) FROM Scripts) AS totalScripts,

        (SELECT COUNT(*) FROM Scripts WHERE is_active = 1) AS activeScripts,

        (SELECT COUNT(*)
        FROM ScriptExecutions
        WHERE start_time >= DATEADD(HOUR,-24,GETDATE())
        ) AS executionsToday,

        (SELECT COUNT(*)
        FROM ScriptExecutions
        WHERE status = 'Exitoso'
        AND start_time >= DATEADD(HOUR,-24,GETDATE())
        ) AS successToday,

        (SELECT COUNT(*)
        FROM ScriptExecutions
        WHERE status = 'Error'
        AND start_time >= DATEADD(HOUR,-24,GETDATE())
        ) AS errorsToday,

        (SELECT COUNT(*)
        FROM ScriptExecutions
        WHERE status IN ('Ejecutando', 'RUNNING')
        ) AS runningCount,

        (SELECT COUNT(*)
        FROM ExecutionQueue
        WHERE status IN ('PENDING', 'Pendiente', 'En Cola')
        ) AS queuedCount,

        ISNULL((
        SELECT AVG(ISNULL(duration_seconds, 0))
        FROM ScriptExecutions
        WHERE start_time >= @todayStart
            AND start_time < @tomorrowStart
        ), 0) AS avgDurationSeconds
    `);

    const lastExecutions = await pool.request().query(`
      SELECT TOP 8
        e.id,
        s.name AS script,
        e.status,
        e.start_time AS startTime,
        e.end_time AS endTime,
        ISNULL(e.duration_seconds, 0) AS durationSeconds,
        ISNULL(CONVERT(VARCHAR(20), e.triggered_by_user_id), 'Sistema') AS [user]
      FROM ScriptExecutions e
      INNER JOIN Scripts s
        ON s.id = e.script_id
      ORDER BY e.id DESC
    `);

    const nextSchedules = await pool.request().query(`
        SELECT TOP 5
            sc.id,
            s.name AS script,
            sc.frequency_label,
            sc.timezone_name,
            sc.next_run_at,
            sc.last_run_at,
            sc.last_status
        FROM Schedules sc
        INNER JOIN Scripts s
            ON s.id = sc.script_id
        WHERE sc.is_active = 1
            AND sc.next_run_at IS NOT NULL
        ORDER BY sc.next_run_at ASC
    `);

    const chart = await pool.request().query(`
    SELECT
        CAST(start_time AS DATE) AS executionDate,

        SUM(CASE WHEN status = 'Exitoso' THEN 1 ELSE 0 END) AS successCount,
        SUM(CASE WHEN status = 'Error' THEN 1 ELSE 0 END) AS errorCount

    FROM ScriptExecutions
    WHERE start_time >= DATEADD(DAY, -6, GETDATE())
    GROUP BY CAST(start_time AS DATE)
    ORDER BY executionDate
    `);

    const last7Days = [];

    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);

        const key = d.toISOString().substring(0, 10);

        const existing = chart.recordset.find((r: any) =>
            r.executionDate.toISOString().substring(0, 10) === key
        );

        last7Days.push({
            executionDate: d,
            successCount: existing?.successCount || 0,
            errorCount: existing?.errorCount || 0
        });
    }

    const totalMem = os.totalmem();
    const freeMem = os.freemem();
    const memoryUsed = ((totalMem - freeMem) / totalMem) * 100;

    const settings = await pool.request()
    .input("environment_id", sql.Int, 3)
    .query(`
        SELECT setting_key, setting_value
        FROM SystemSettings
        WHERE environment_id = @environment_id
    `);

    const settingsMap = Object.fromEntries(
    settings.recordset.map((x: any) => [
        x.setting_key,
        x.setting_value
    ])
    );

    const maxConcurrentExecutions =
    Number(settingsMap.MAX_CONCURRENT_EXECUTIONS || 3);

    res.json({
        ...summary.recordset[0],
        lastExecutions: lastExecutions.recordset,
        executionsLast7Days: last7Days,
        nextSchedules: nextSchedules.recordset,
        maxConcurrentExecutions,
        schedulerStatus: "Activo",
        systemHealth: {
        backend: true,
        scheduler: true,
        database: true,
        memoryUsage: memoryUsed.toFixed(2),
        cpuCount: os.cpus().length
        },
      lastUpdate: new Date()
    });
  } catch (error) {
    console.error("Error dashboard summary:", error);

    res.status(500).json({
      message: "Error obteniendo dashboard",
      error: error instanceof Error ? error.message : String(error)
    });
  }
});

export default router;