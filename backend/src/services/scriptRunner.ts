import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';
import { addExecutionLog } from './dbLogService';
import { emitExecutionLog } from './logBus';

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

export async function runScript(
  scriptId: number,
  triggeredByUserId?: number,
  parameters: Record<string, string> = {},
  skipQueueCheck = false,
  scheduleId?: number,
  triggerType: 'manual' | 'schedule' | 'queue' = 'manual',
): Promise<{ executionId: number }> {
  const pool = await getPool();

  const scriptResult = await pool.request()
    .input('id', sql.Int, scriptId)
    .query(`
      SELECT TOP 1
        id,
        environment_id,
        name,
        file_path,
        working_directory,
        python_interpreter,
        is_active
      FROM dbo.Scripts
      WHERE id = @id
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
      .query(`
        INSERT INTO dbo.ExecutionQueue (
          script_id,
          schedule_id,
          parameters_json,
          status,
          created_at
        )
        OUTPUT INSERTED.id
        VALUES (
          @script_id,
          @schedule_id,
          @parameters_json,
          @status,
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
    .input('script_version_id', sql.Int, null)
    .input('schedule_id', sql.Int, scheduleId || null)
    .input('triggered_by_user_id', sql.Int, triggeredByUserId || env.defaultUserId)
    .input('parent_execution_id', sql.Int, null)
    .input('trigger_type', sql.NVarChar(20), triggerType)
    .input('command_line', sql.NVarChar(sql.MAX), commandLine)
    .input('working_directory', sql.NVarChar(1000), workingDirectory)
    .input('machine_name', sql.NVarChar(255), os.hostname())
    .input('process_id', sql.Int, null)
    .output('execution_id', sql.Int);

  const startResult = await startRequest.execute('dbo.usp_StartScriptExecution');
  const executionId = startResult.output.execution_id as number;

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

  child.stdout.on('data', async (data: string) => {
    const lines = data.split(/\r?\n/).filter(Boolean);

    for (const line of lines) {
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

    await addExecutionLog(executionId, 'ERROR', msg);

    await pool.request()
      .input('execution_id', sql.Int, executionId)
      .input('status', sql.NVarChar(20), 'Error')
      .input('exit_code', sql.Int, -1)
      .input('error_message', sql.NVarChar(sql.MAX), msg)
      .execute('dbo.usp_FinishScriptExecution');

    emitExecutionLog(executionId, {
      level: 'ERROR',
      message: msg,
      done: true,
      status: 'Error'
    });
  });

  child.on('close', async (code) => {
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
    const msg = `Proceso finalizado con código ${exitCode}`;

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

    emitExecutionLog(executionId, {
      level: exitCode === 0 ? 'INFO' : 'ERROR',
      message: msg,
      done: true,
      status
    });
  });

  return { executionId };
}