import { Router } from "express";
import { getPool, sql } from "../db/sql";
import os from "os";
import osUtils from "os-utils";

const router = Router();
const DASHBOARD_TIMEZONE = "America/Tegucigalpa";
const MAX_CHART_RANGE_DAYS = 366;

function localIsoDate(date: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: DASHBOARD_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(date);
}

function addUtcDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function validIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function getCpuUsagePercent(): Promise<number> {
  return new Promise(resolve => {
    osUtils.cpuUsage(value => resolve(value * 100));
  });
}

router.get("/summary", async (req, res) => {
  try {
    const defaultDateTo = localIsoDate();
    const dateFrom = String(req.query.dateFrom || addUtcDays(defaultDateTo, -6));
    const dateTo = String(req.query.dateTo || defaultDateTo);

    if (!validIsoDate(dateFrom) || !validIsoDate(dateTo)) {
      return res.status(400).json({ message: "El rango de fechas no es válido." });
    }

    const rangeDays = Math.round(
      (new Date(`${dateTo}T00:00:00.000Z`).getTime() - new Date(`${dateFrom}T00:00:00.000Z`).getTime()) / 86_400_000
    ) + 1;

    if (rangeDays <= 0 || rangeDays > MAX_CHART_RANGE_DAYS) {
      return res.status(400).json({
        message: `El rango debe contener entre 1 y ${MAX_CHART_RANGE_DAYS} días.`
      });
    }

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

    const chart = await pool.request()
    .input("date_from", sql.Date, dateFrom)
    .input("date_to", sql.Date, dateTo)
    .query(`
    SELECT
        CAST(DATEADD(HOUR, -6, start_time) AS DATE) AS executionDate,

        SUM(CASE WHEN status = 'Exitoso' THEN 1 ELSE 0 END) AS successCount,
        SUM(CASE WHEN status = 'Error' THEN 1 ELSE 0 END) AS errorCount

    FROM ScriptExecutions
    WHERE start_time >= DATEADD(HOUR, 6, CAST(@date_from AS DATETIME2))
      AND start_time < DATEADD(HOUR, 6, DATEADD(DAY, 1, CAST(@date_to AS DATETIME2)))
    GROUP BY CAST(DATEADD(HOUR, -6, start_time) AS DATE)
    ORDER BY executionDate
    `);

    const executionsHistory = [];

    for (let i = 0; i < rangeDays; i++) {
        const key = addUtcDays(dateFrom, i);

        const existing = chart.recordset.find((r: any) =>
            r.executionDate.toISOString().substring(0, 10) === key
        );

        executionsHistory.push({
            executionDate: key,
            successCount: existing?.successCount || 0,
            errorCount: existing?.errorCount || 0
        });
    }

    const totalMem = os.totalmem();
    const freeMem = os.freemem();
    const usedMem = totalMem - freeMem;
    const memoryUsed = ((totalMem - freeMem) / totalMem) * 100;
    const cpuUsage = await getCpuUsagePercent();

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
        executionsHistory,
        executionsLast7Days: executionsHistory,
        chartDateFrom: dateFrom,
        chartDateTo: dateTo,
        nextSchedules: nextSchedules.recordset,
        maxConcurrentExecutions,
        schedulerStatus: "Activo",
        systemHealth: {
          backend: true,
          scheduler: true,
          database: true,
          memoryUsage: Number(memoryUsed.toFixed(2)),
          memoryUsedGb: Number((usedMem / 1024 / 1024 / 1024).toFixed(2)),
          memoryTotalGb: Number((totalMem / 1024 / 1024 / 1024).toFixed(2)),
          cpuUsage: Number(cpuUsage.toFixed(2)),
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
