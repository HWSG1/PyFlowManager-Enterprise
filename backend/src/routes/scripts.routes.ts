import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';
import { runScript } from '../services/scriptRunner';
import { exec } from 'child_process';
import path from 'path';
import multer from 'multer';
import fs from 'fs';

const router = Router();

const scriptsDir = path.resolve(env.runtime.scriptsDir);

if (!fs.existsSync(scriptsDir)) {
  fs.mkdirSync(scriptsDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, scriptsDir),
  filename: (_req, file, cb) => cb(null, path.basename(file.originalname))
});

const upload = multer({ storage });

function extractPyflowParams(content: string): Record<string, any> {
  const startIndex = content.indexOf('PYFLOW_PARAMS');
  if (startIndex === -1) return {};

  const equalIndex = content.indexOf('=', startIndex);
  if (equalIndex === -1) return {};

  const braceStart = content.indexOf('{', equalIndex);
  if (braceStart === -1) return {};

  let depth = 0;
  let braceEnd = -1;

  for (let i = braceStart; i < content.length; i++) {
    if (content[i] === '{') depth++;
    if (content[i] === '}') depth--;

    if (depth === 0) {
      braceEnd = i;
      break;
    }
  }

  if (braceEnd === -1) return {};

  const pythonDict = content.substring(braceStart, braceEnd + 1);

  try {
    const jsonLike = pythonDict
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
      .replace(/\bNone\b/g, 'null')
      .replace(/'/g, '"');

    return JSON.parse(jsonLike);
  } catch (error) {
    console.error('Error parseando PYFLOW_PARAMS:', error);
    return {};
  }
}

router.get('/', async (_req, res, next) => {
  try {
    const pool = await getPool();

    const result = await pool.request().query(`
      SELECT
        id,
        name,
        description,
        category,
        file_path,
        current_version,
        is_active,
        created_at,
        updated_at,
        created_by,
        environment_name,
        last_execution_status,
        last_execution_start_time,
        next_run_at,
        total_success,
        total_errors,
        last_duration_seconds
      FROM dbo.vw_ScriptsSummary
      ORDER BY name
    `);

    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.post('/', upload.single('file'), async (req, res, next) => {
  try {
    const body = req.body || {};
    const pool = await getPool();
    const uploadedFile = req.file;

    const rawFilePath = uploadedFile
      ? uploadedFile.filename
      : body.file_path || body.path || body.name;

    const cleanFilePath = path.basename(rawFilePath.replace(/\\/g, '/'));

    const result = await pool.request()
      .input('created_by_user_id', sql.Int, body.created_by_user_id || env.defaultUserId)
      .input('environment_id', sql.Int, body.environment_id || env.defaultEnvironmentId)
      .input('name', sql.NVarChar(255), body.name || cleanFilePath)
      .input('description', sql.NVarChar(1000), body.description || null)
      .input('category', sql.NVarChar(100), body.category || 'ETL')
      .input('current_version', sql.NVarChar(30), body.version || '1.0.0')
      .input('file_path', sql.NVarChar(1000), cleanFilePath)
      .input('working_directory', sql.NVarChar(1000), body.working_directory || null)
      .input('python_interpreter', sql.NVarChar(1000), body.python_interpreter || env.pythonCommand)
      .input('author', sql.NVarChar(255), body.author || 'Admin_User')
      .query(`
        INSERT INTO dbo.Scripts (
          created_by_user_id,
          environment_id,
          name,
          description,
          category,
          current_version,
          file_path,
          working_directory,
          python_interpreter,
          author
        )
        OUTPUT INSERTED.*
        VALUES (
          @created_by_user_id,
          @environment_id,
          @name,
          @description,
          @category,
          @current_version,
          @file_path,
          @working_directory,
          @python_interpreter,
          @author
        )
      `);

    const insertedScript = result.recordset[0];
    const scriptId = insertedScript.id;

    if (uploadedFile?.path) {
      const content = fs.readFileSync(uploadedFile.path, 'utf8');
      const pyflowParams = extractPyflowParams(content);

      for (const [key, config] of Object.entries<any>(pyflowParams)) {
        await pool.request()
          .input('script_id', sql.Int, scriptId)
          .input('param_key', sql.NVarChar(150), key)
          .input('param_value', sql.NVarChar(1000), String(config.default ?? ''))
          .input('param_type', sql.NVarChar(30), 'env')
          .input('control_type', sql.NVarChar(30), config.type ?? 'text')
          .input('is_secret', sql.Bit, 0)
          .input('description', sql.NVarChar(500), config.description || config.label || null)
          .input('label', sql.NVarChar(255), config.label || key)
          .input('options_json', sql.NVarChar(sql.MAX), config.options ? JSON.stringify(config.options) : null)
          .input('is_required', sql.Bit, config.required ? 1 : 0)
          .query(`
            INSERT INTO dbo.ScriptParameters (
              script_id,
              param_key,
              param_value,
              param_type,
              control_type,
              is_secret,
              description,
              label,
              options_json,
              is_required
            )
            VALUES (
              @script_id,
              @param_key,
              @param_value,
              @param_type,
              @control_type,
              @is_secret,
              @description,
              @label,
              @options_json,
              @is_required
            )
          `);
      }
    }

    res.status(201).json(insertedScript);
  } catch (err) {
    next(err);
  }
});

router.get('/:id/parameters', async (req, res, next) => {
  try {
    const pool = await getPool();
    const scriptId = Number(req.params.id);

    const result = await pool.request()
      .input('script_id', sql.Int, scriptId)
      .query(`
        SELECT
          id,
          script_id,
          param_key,
          param_value,
          param_type,
          control_type,
          label,
          options_json,
          is_required,
          global_key
        FROM dbo.ScriptParameters
        WHERE script_id = @script_id
        ORDER BY id
      `);

    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.patch('/:id/toggle', async (req, res, next) => {
  try {
    const pool = await getPool();
    const id = Number(req.params.id);

    const result = await pool.request()
      .input('id', sql.Int, id)
      .query(`
        UPDATE dbo.Scripts
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
            updated_at = SYSUTCDATETIME()
        OUTPUT INSERTED.*
        WHERE id = @id
      `);

    res.json(result.recordset[0]);
  } catch (err) {
    next(err);
  }
});

router.delete('/:id', async (req, res, next) => {
  try {
    const pool = await getPool();
    const id = Number(req.params.id);

    await pool.request()
      .input('id', sql.Int, id)
      .query(`
        UPDATE dbo.Scripts
        SET is_active = 0,
            updated_at = SYSUTCDATETIME()
        WHERE id = @id
      `);

    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

router.delete('/:id/definitive', async (req, res, next) => {
  const pool = await getPool();
  const scriptId = Number(req.params.id);

  if (!scriptId) {
    return res.status(400).json({ message: 'ID de script inválido.' });
  }

  const tx = new sql.Transaction(pool);

  try {
    const scriptResult = await pool.request()
      .input('id', sql.Int, scriptId)
      .query(`
        SELECT TOP 1 id, file_path
        FROM dbo.Scripts
        WHERE id = @id
      `);

    if (!scriptResult.recordset.length) {
      return res.status(404).json({ message: 'Script no encontrado.' });
    }

    const filePath = scriptResult.recordset[0].file_path;

    await tx.begin();

    const request = new sql.Request(tx);
    request.input('script_id', sql.Int, scriptId);

    await request.query(`
      DELETE FROM dbo.ScheduleParameters
      WHERE schedule_id IN (
        SELECT id FROM dbo.Schedules WHERE script_id = @script_id
      );

      DELETE FROM dbo.Schedules
      WHERE script_id = @script_id;

      DELETE FROM dbo.ScriptParameters
      WHERE script_id = @script_id;

      DELETE FROM dbo.ScriptVersions
      WHERE script_id = @script_id;

      DELETE FROM dbo.ExecutionLogs
      WHERE execution_id IN (
        SELECT id FROM dbo.ScriptExecutions WHERE script_id = @script_id
      );

      DELETE FROM dbo.ExecutionParameters
      WHERE execution_id IN (
        SELECT id FROM dbo.ScriptExecutions WHERE script_id = @script_id
      );

      DELETE FROM dbo.ExecutionFiles
      WHERE execution_id IN (
        SELECT id FROM dbo.ScriptExecutions WHERE script_id = @script_id
      );

      DELETE FROM dbo.ExecutionQueue
      WHERE script_id = @script_id;

      DELETE FROM dbo.ScriptExecutions
      WHERE script_id = @script_id;

      DELETE FROM dbo.Scripts
      WHERE id = @script_id;
    `);

    await tx.commit();

    if (filePath) {
      const fullPath = path.isAbsolute(filePath)
        ? filePath
        : path.resolve(env.runtime.scriptsDir, filePath);

      const allowedDir = path.resolve(env.runtime.scriptsDir);

      if (!fullPath.startsWith(allowedDir)) {
        return res.status(400).json({
          message: 'Ruta de archivo fuera del directorio permitido.'
        });
      }

      if (fs.existsSync(fullPath)) {
        fs.unlinkSync(fullPath);
      }
    }

    return res.json({
      ok: true,
      message: 'Script eliminado definitivamente.'
    });
  } catch (err) {
    try {
      await tx.rollback();
    } catch {}

    next(err);
  }
});

router.post('/:id/run', async (req, res, next) => {
  try {
    const id = Number(req.params.id);

    const result = await runScript(
      id,
      req.body?.triggered_by_user_id || env.defaultUserId,
      req.body?.parameters || {}
    );

    res.status(202).json(result);
  } catch (err) {
    next(err);
  }
});

router.post('/executions/:id/cancel', async (req, res, next) => {
  try {
    const executionId = Number(req.params.id);
    const pool = await getPool();

    const result = await pool.request()
      .input('id', sql.Int, executionId)
      .query(`
        SELECT TOP 1 id, process_id, status
        FROM dbo.ScriptExecutions
        WHERE id = @id
      `);

    if (!result.recordset.length) {
      return res.status(404).json({ message: 'Ejecución no encontrada.' });
    }

    const execution = result.recordset[0];

    if (execution.status !== 'Ejecutando') {
      return res.json({ ok: true, message: 'La ejecución ya no está activa.' });
    }

    if (execution.process_id) {
      exec(`taskkill /PID ${execution.process_id} /T /F`);
    }

    await pool.request()
      .input('execution_id', sql.Int, executionId)
      .input('status', sql.NVarChar(20), 'Cancelado')
      .input('exit_code', sql.Int, -9)
      .input('error_message', sql.NVarChar(sql.MAX), 'Ejecución cancelada manualmente')
      .execute('dbo.usp_FinishScriptExecution');

    res.json({ ok: true, message: 'Ejecución cancelada correctamente.' });
  } catch (err) {
    next(err);
  }
});

export default router;