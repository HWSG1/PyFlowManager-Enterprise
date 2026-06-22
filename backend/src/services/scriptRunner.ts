import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';
import { addExecutionLog } from './dbLogService';
import { emitExecutionLog } from './logBus';
import { sendExecutionAlert } from './notification.service';
import { auditEvent } from './audit.service';

function resolveScriptPath(filePath: string): string {
  if (path.isAbsolute(filePath)) {
    return filePath;
  }

  const normalized = filePath.replace(/\\/g, '/');

  if (normalized.startsWith('runtime/scripts/')) {
    return path.resolve(normalized);
  }

  return path.resolve(env.runtime.scriptsDir, filePath);
}

function normalizeExitCode(code: number | null): number {
  if (typeof code !== 'number') return -1;
  if (!Number.isFinite(code)) return -1;
  if (code < -2147483648 || code > 2147483647) return -1;
  return Math.trunc(code);
}

function parseProgressLine(line: string): number | null {
  const match = line.trim().match(/^PYFLOW_PROGRESS=(\d{1,3})(?:\.\d+)?$/i);
  if (!match) return null;

  const progress = Number(match[1]);
  if (!Number.isFinite(progress)) return null;

  return Math.max(0, Math.min(100, progress));
}

function rememberLine(buffer: string[], line: string): void {
  const clean = String(line || '').trim();
  if (!clean) return;

  buffer.push(clean);
  if (buffer.length > 20) {
    buffer.shift();
  }
}

export async function runScript(
  scriptId: number,
  triggeredByUserId?: number,
  parameters: Record<string, string> = {},
  skipQueueCheck = false,
  scheduleId?: number,
  triggerType: 'manual' | 'schedule' | 'queue' | 'retry' = 'manual',
  retryAttempt = 0,
  parentExecutionId?: number,
): Promise<{ executionId: number }> {
  const pool = await getPool();

  const scriptResult = await pool.request()
    .input('id', sql.Int, scriptId)
    .query(`
      SELECT TOP 1
        s.id, s.environment_id, s.name, s.file_path, s.working_directory,
        s.python_interpreter, s.is_active, s.max_retries, s.retry_delay_seconds,
        s.retry_backoff_factor, s.alert_on_success, s.alert_on_failure,
        s.alert_recipients, v.id AS current_version_id
      FROM dbo.Scripts s
      OUTER APPLY (
        SELECT TOP 1 id FROM dbo.ScriptVersions
        WHERE script_id = s.id AND is_current = 1 ORDER BY id DESC
      ) v
      WHERE s.id = @id
    `);

  if (!scriptResult.recordset.length) {
    throw new Error(`Script no encontrado: ${scriptId}`);
  }

  const script = scriptResult.recordset[0];

  if (!script.is_active) {
    throw new Error('El script está inactivo.');
  }

  const environmentId = script.environment_id || 1;

  const resolvedPath = resolveScriptPath(script.file_path);

if (!skipQueueCheck) {
  const environmentId = script.environment_id || 1;

  const maxResult = await pool.request()
    .input('environment_id', sql.Int, environmentId)
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
    const queueResult = await pool.request()
      .input('script_id', sql.Int, scriptId)
      .input('schedule_id', sql.Int, scheduleId || null)
      .input('parameters_json', sql.NVarChar(sql.MAX), JSON.stringify(parameters || {}))
      .input('status', sql.NVarChar(30), 'PENDING')
      .input('triggered_by_user_id', sql.Int, triggeredByUserId || env.defaultUserId)
      .input('trigger_type', sql.NVarChar(20), triggerType)
      .input('retry_attempt', sql.SmallInt, retryAttempt)
      .input('parent_execution_id', sql.Int, parentExecutionId || null)
      .query(`
        INSERT INTO dbo.ExecutionQueue (
          script_id,
          schedule_id,
          parameters_json,
          status,
          available_at,
          triggered_by_user_id,
          trigger_type,
          retry_attempt,
          parent_execution_id,
          created_at
        )
        OUTPUT INSERTED.id
        VALUES (
          @script_id,
          @schedule_id,
          @parameters_json,
          @status,
          SYSUTCDATETIME(),
          @triggered_by_user_id,
          @trigger_type,
          @retry_attempt,
          @parent_execution_id,
          GETDATE()
        )
      `);

    const queueId = queueResult.recordset[0]?.id;

    throw new Error(
      `La ejecución fue enviada a cola. Queue ID: ${queueId}. Límite concurrente: ${running}/${maxConcurrentExecutions}`
    );
  }
}

  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`El archivo del script no existe: ${resolvedPath}`);
  }

  const globalParamResult = await pool.request()
    .input('script_id', sql.Int, scriptId)
    .query(`
      SELECT
        param_key,
        global_key,
        label,
        is_required
      FROM dbo.ScriptParameters
      WHERE script_id = @script_id
        AND control_type = 'global'
    `);

  const resolvedGlobalParams: Record<string, string> = {};

  for (const param of globalParamResult.recordset) {
    const globalKey = param.global_key || param.param_key;

    const globalValueResult = await pool.request()
      .input('var_key', sql.NVarChar(150), globalKey)
      .query(`
        SELECT TOP 1
          var_value
        FROM dbo.GlobalVariables
        WHERE var_key = @var_key
      `);

    const globalValue = globalValueResult.recordset[0]?.var_value;

    if (param.is_required && (globalValue === null || globalValue === undefined || String(globalValue).trim() === '')) {
      throw new Error(`Variable global requerida no configurada: ${globalKey}`);
    }

    resolvedGlobalParams[param.param_key] = String(globalValue ?? '');
  }

  const finalParameters: Record<string, string> = {
    ...resolvedGlobalParams,
    ...parameters
  };

  const workingDirectory = script.working_directory
    ? path.resolve(script.working_directory)
    : path.dirname(resolvedPath);

  const pythonCommand = script.python_interpreter || env.pythonCommand;

  const commandLine = `${pythonCommand} -u "${resolvedPath}"`;

  const startRequest = pool.request()
    .input('script_id', sql.Int, scriptId)
    .input('script_version_id', sql.Int, script.current_version_id || null)
    .input('schedule_id', sql.Int, scheduleId || null)
    .input('triggered_by_user_id', sql.Int, triggeredByUserId || env.defaultUserId)
    .input('parent_execution_id', sql.Int, parentExecutionId || null)
    .input('trigger_type', sql.NVarChar(20), triggerType)
    .input('command_line', sql.NVarChar(sql.MAX), commandLine)
    .input('working_directory', sql.NVarChar(1000), workingDirectory)
    .input('machine_name', sql.NVarChar(255), os.hostname())
    .input('process_id', sql.Int, null)
    .output('execution_id', sql.Int);

  const startResult = await startRequest.execute('dbo.usp_StartScriptExecution');
  const executionId = startResult.output.execution_id as number;

  await pool.request()
    .input('execution_id', sql.Int, executionId)
    .input('retry_attempt', sql.SmallInt, retryAttempt)
    .query('UPDATE dbo.ScriptExecutions SET retry_attempt=@retry_attempt WHERE id=@execution_id');

  for (const [key, value] of Object.entries(finalParameters)) {
    await pool.request()
      .input('execution_id', sql.Int, executionId)
      .input('param_key', sql.NVarChar(150), key)
      .input(
        'param_value',
        sql.NVarChar(sql.MAX),
        key.toUpperCase().includes('PASSWORD') ||
        key.toUpperCase().includes('SECRET') ||
        key.toUpperCase().includes('TOKEN')
          ? '********'
          : String(value ?? '')
      )
      .query(`
        INSERT INTO dbo.ExecutionParameters (
          execution_id,
          param_key,
          param_value
        )
        VALUES (
          @execution_id,
          @param_key,
          @param_value
        )
      `);
  }

  await addExecutionLog(executionId, 'INFO', `Iniciando ejecución: ${script.name}`);
  emitExecutionLog(executionId, {
    level: 'INFO',
    message: `Iniciando ejecución: ${script.name}`,
    source: 'runner'
  });

  const child = spawn(pythonCommand, ['-u', resolvedPath], {

    cwd: workingDirectory,
    shell: false,
    env: {
      ...process.env,
      ...finalParameters,
      PYTHONUNBUFFERED: '1',
      PYFLOW_EXECUTION_ID: String(executionId),
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
    }
  });

  await pool.request()
    .input('execution_id', sql.Int, executionId)
    .input('pid', sql.Int, child.pid || null)
    .query(`
      UPDATE dbo.ScriptExecutions
      SET process_id = @pid
      WHERE id = @execution_id
    `);

  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  const recentOutput: string[] = [];

  child.stdout.on('data', async (data: string) => {
    const lines = data.split(/\r?\n/).filter(Boolean);

    for (const line of lines) {
      const progress = parseProgressLine(line);
      if (progress !== null) {
        emitExecutionLog(executionId, {
          progress,
          source: 'progress'
        });
        continue;
      }

      rememberLine(recentOutput, line);
      await addExecutionLog(executionId, 'INFO', line);
      emitExecutionLog(executionId, {
        level: 'INFO',
        message: line,
        source: 'stdout'
      });
    }
  });

  child.stderr.on('data', async (data: string) => {
    const lines = data.split(/\r?\n/).filter(Boolean);

    for (const line of lines) {
      rememberLine(recentOutput, line);
      await addExecutionLog(executionId, 'ERROR', line);
      emitExecutionLog(executionId, {
        level: 'ERROR',
        message: line,
        source: 'stderr'
      });
    }
  });

  child.on('error', async (error) => {
    const msg = `Error iniciando proceso Python: ${error.message}`;
    rememberLine(recentOutput, msg);
    await addExecutionLog(executionId, 'ERROR', msg);
    emitExecutionLog(executionId, {
      level: 'ERROR',
      message: msg,
      source: 'runner'
    });
  });

  child.on('close', async (code, signal) => {
    const current = await pool.request()
      .input('execution_id', sql.Int, executionId)
      .query(`
        SELECT status
        FROM dbo.ScriptExecutions
        WHERE id = @execution_id
      `);

    const currentStatus = current.recordset[0]?.status;

    if (currentStatus === 'Cancelado') {
      await addExecutionLog(executionId, 'WARNING', 'Proceso detenido por cancelación manual.');

      emitExecutionLog(executionId, {
        level: 'WARNING',
        message: 'Proceso detenido por cancelación manual.',
        done: true,
        status: 'Cancelado'
      });

      return;
    }

    const exitCode = normalizeExitCode(code);

    const status = exitCode === 0 ? 'Exitoso' : 'Error';
    const signalText = signal ? ` | señal ${signal}` : '';
    const tail = recentOutput.length
      ? ` | Últimas líneas: ${recentOutput.slice(-5).join(' || ')}`
      : '';
    const msg = `Proceso finalizado con código ${exitCode}${exitCode === 0 ? '' : `${signalText}${tail}`}`;

    await addExecutionLog(
      executionId,
      code === 0 ? 'INFO' : 'ERROR',
      msg
    );

    await pool.request()
      .input('execution_id', sql.Int, executionId)
      .input('status', sql.NVarChar(20), status)
      .input('exit_code', sql.Int, exitCode)
      .input('error_message', sql.NVarChar(sql.MAX), exitCode === 0 ? null : msg)
      .execute('dbo.usp_FinishScriptExecution');

    await auditEvent(null, 'execution.finish', 'execution', executionId, null, {
      script_id: scriptId,
      status,
      exit_code: exitCode,
      retry_attempt: retryAttempt
    });

    const maxRetries = Math.max(0, Number(script.max_retries || 0));
    const shouldRetry = status === 'Error' && retryAttempt < maxRetries;

    if (shouldRetry) {
      const baseDelay = Math.max(1, Number(script.retry_delay_seconds || 60));
      const backoff = Math.max(1, Number(script.retry_backoff_factor || 1));
      const delaySeconds = Math.round(baseDelay * Math.pow(backoff, retryAttempt));
      const rootExecutionId = parentExecutionId || executionId;
      const retryMessage = `Reintento ${retryAttempt + 1}/${maxRetries} programado en ${delaySeconds} segundos.`;
      await addExecutionLog(executionId, 'WARNING', retryMessage);
      emitExecutionLog(executionId, { level: 'WARNING', message: retryMessage, retryScheduled: true });

      await pool.request()
        .input('script_id', sql.Int, scriptId)
        .input('schedule_id', sql.Int, scheduleId || null)
        .input('parameters_json', sql.NVarChar(sql.MAX), JSON.stringify(parameters || {}))
        .input('triggered_by_user_id', sql.Int, triggeredByUserId || env.defaultUserId)
        .input('retry_attempt', sql.SmallInt, retryAttempt + 1)
        .input('parent_execution_id', sql.Int, rootExecutionId)
        .input('delay_seconds', sql.Int, delaySeconds)
        .query(`
          INSERT INTO dbo.ExecutionQueue (
            script_id, schedule_id, parameters_json, status, created_at, available_at,
            triggered_by_user_id, trigger_type, retry_attempt, parent_execution_id
          ) VALUES (
            @script_id, @schedule_id, @parameters_json, 'PENDING', SYSUTCDATETIME(),
            DATEADD(SECOND, @delay_seconds, SYSUTCDATETIME()), @triggered_by_user_id,
            'retry', @retry_attempt, @parent_execution_id
          )
        `);
    }

    const shouldAlert =
      (status === 'Exitoso' && script.alert_on_success) ||
      (status === 'Error' && !shouldRetry && script.alert_on_failure);

    if (shouldAlert && script.alert_recipients) {
      const finished = await pool.request()
        .input('execution_id', sql.Int, executionId)
        .query('SELECT start_time,end_time,duration_seconds,error_message FROM dbo.ScriptExecutions WHERE id=@execution_id');
      const row = finished.recordset[0] || {};
      await sendExecutionAlert({
        executionId,
        scriptName: script.name,
        status,
        startedAt: row.start_time,
        endedAt: row.end_time,
        durationSeconds: row.duration_seconds,
        errorMessage: row.error_message,
        retryAttempt,
        recipients: script.alert_recipients
      });
    }

    emitExecutionLog(executionId, {
      level: exitCode === 0 ? 'INFO' : 'ERROR',
      message: msg,
      done: true,
      status
    });
  });

  return { executionId };
}
