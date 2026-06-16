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
      .replace(/'/g, '"')
      .replace(/,\s*([}\]])/g, '$1');

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
          .input('global_key', sql.NVarChar(150), config.global_key || null)
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
              is_required,
              global_key
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
              @is_required,
              @global_key
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
          sp.id,
          sp.script_id,
          sp.param_key,
          sp.param_value,
          sp.param_type,
          sp.control_type,
          sp.label,
          sp.options_json,
          sp.is_required,
          sp.global_key,
          s.name AS script_name
        FROM dbo.ScriptParameters sp
        INNER JOIN dbo.Scripts s
          ON s.id = sp.script_id
        WHERE sp.script_id = @script_id
          AND (
            s.name <> 'GNS_Usuarios.py'
            OR sp.param_key NOT IN (
              'PAGE_SIZE',
              'COMMIT_EVERY',
              'DRY_RUN',
              'REQUEST_TIMEOUT_SECONDS',
              'MAX_RETRIES'
            )
          )
          AND (
            s.name <> 'GNS_IVR.py'
            OR sp.param_key NOT IN (
              'DATE',
              'START_UTC',
              'END_UTC',
              'GENESYS_TIMEZONE',
              'MAX_RANGE_DAYS',
              'JOB_PAGE_SIZE',
              'REQUEST_TIMEOUT',
              'MAX_API_RETRIES',
              'POLL_SECONDS',
              'MAX_POLL_ATTEMPTS',
              'API_SLEEP_SECONDS',
              'HANA_BATCH_SIZE',
              'MAX_CONVERSATIONS',
              'ENRICH_CLIENTS_FROM_HANA',
              'ONLY_WITH_IVR',
              'DRY_RUN',
              'QUALTRICS_DELAY_SECONDS'
            )
          )
          AND (
            s.name <> 'GNS_Extractor_Transcripciones.py'
            OR sp.param_key NOT IN (
              'DATE',
              'PAGE_SIZE',
              'REQUEST_TIMEOUT',
              'MAX_RETRIES',
              'API_SLEEP_SECONDS',
              'JOB_POLL_SECONDS',
              'JOB_MAX_POLLS',
              'SAVE_TRANSCRIPT_JSON',
              'DRY_RUN'
            )
          )
        ORDER BY sp.id
      `);

    const rows = result.recordset;
    const isGnsIvr = rows.some((row: any) => row.script_name === 'GNS_IVR.py');
    const isTranscriptionExtractor = rows.some((row: any) => row.script_name === 'GNS_Extractor_Transcripciones.py');

    if (isTranscriptionExtractor) {
      const tagParams = new Set([
        'CONVERSATION_ID',
        'USER_ID',
        'USER_NAME',
        'QUEUE_ID',
        'QUEUE_NAME',
        'CAMPAIGN_ID',
        'CAMPAIGN_NAME',
        'CONTACT_LIST_ID',
        'CONTACT_LIST_NAME',
        'WRAPUP_CODE_ID',
        'WRAPUP_CODE_NAME'
      ]);

      for (const row of rows) {
        if (tagParams.has(row.param_key)) {
          row.control_type = 'tags';
        }
      }

      if (!rows.some((row: any) => row.param_key === 'WRAPUP_CODE_NAME')) {
        const baseId = rows.length ? Math.max(...rows.map((row: any) => Number(row.id) || 0)) + 1 : 1;
        rows.push({
          id: baseId,
          script_id: scriptId,
          param_key: 'WRAPUP_CODE_NAME',
          param_value: '',
          param_type: 'env',
          control_type: 'tags',
          label: 'Nombre de conclusión opcional',
          options_json: null,
          is_required: false,
          global_key: null,
          script_name: 'GNS_Extractor_Transcripciones.py'
        });
      }
    }

    if (isGnsIvr) {
      const runMode = rows.find((row: any) => row.param_key === 'RUN_MODE');
      if (runMode) {
        runMode.label = 'Modo de ejecucion';
        runMode.options_json = JSON.stringify([
          'Cargar a SAP HANA',
          'Análisis Autoservicio',
          'Enviar de Encuestas Autoservicio',
          'Análisis Abandono',
          'HANA + Análisis Autoservicio',
          'HANA + Envío de encuestas'
        ]);
      }

      const hasParam = (key: string) => rows.some((row: any) => row.param_key === key);
      const baseId = rows.length ? Math.max(...rows.map((row: any) => Number(row.id) || 0)) + 1 : 1;
      let syntheticId = baseId;
      const forceGlobalParam = (key: string, label: string) => {
        const param = rows.find((row: any) => row.param_key === key);
        if (!param) return;

        param.param_type = 'global';
        param.control_type = 'global';
        param.global_key = key;
        param.label = label;
      };

      forceGlobalParam('TOKEN_QUALTRICTS', 'Token Qualtrics');
      forceGlobalParam('POST_AUTOSERVICIO_QUALTRICTS_QA', 'Endpoint Qualtrics');
      forceGlobalParam('POST_AUTOSERVICIO_QUALTRICTS_IVR', 'Endpoint Qualtrics');
      forceGlobalParam('SMTP_HOST', 'SMTP Host');
      forceGlobalParam('SMTP_PORT', 'SMTP Port');
      forceGlobalParam('SMTP_USER', 'SMTP Usuario');
      forceGlobalParam('SMTP_PASSWORD', 'SMTP Password');
      forceGlobalParam('SMTP_FROM', 'SMTP Remitente');
      forceGlobalParam('SMTP_USE_TLS', 'SMTP Usar TLS');

      const addGlobalIfMissing = (key: string, label: string, required = false, secret = false) => {
        if (hasParam(key)) return;

        rows.push({
          id: syntheticId++,
          script_id: scriptId,
          param_key: key,
          param_value: '',
          param_type: 'global',
          control_type: 'global',
          label,
          options_json: null,
          is_required: required,
          is_secret: secret,
          global_key: key,
          script_name: 'GNS_IVR.py'
        });
      };

      const addInputIfMissing = (
        key: string,
        label: string,
        controlType = 'text',
        defaultValue = '',
        options: string[] | null = null
      ) => {
        const existing = rows.find((row: any) => row.param_key === key);
        if (existing) {
          existing.control_type = controlType;
          existing.label = label;
          if (options) {
            existing.options_json = JSON.stringify(options);
          }
          return;
        }

        rows.push({
          id: syntheticId++,
          script_id: scriptId,
          param_key: key,
          param_value: defaultValue,
          param_type: 'env',
          control_type: controlType,
          label,
          options_json: options ? JSON.stringify(options) : null,
          is_required: false,
          global_key: null,
          script_name: 'GNS_IVR.py'
        });
      };

      if (!hasParam('TOKEN_QUALTRICTS')) {
        rows.push({
          id: syntheticId++,
          script_id: scriptId,
          param_key: 'TOKEN_QUALTRICTS',
          param_value: '',
          param_type: 'global',
          control_type: 'global',
          label: 'Token Qualtrics',
          options_json: null,
          is_required: true,
          global_key: 'TOKEN_QUALTRICTS',
          script_name: 'GNS_IVR.py'
        });
      }

      if (!hasParam('POST_AUTOSERVICIO_QUALTRICTS_IVR')) {
        rows.push({
          id: syntheticId++,
          script_id: scriptId,
          param_key: 'POST_AUTOSERVICIO_QUALTRICTS_IVR',
          param_value: '',
          param_type: 'global',
          control_type: 'global',
          label: 'Endpoint Qualtrics',
          options_json: null,
          is_required: true,
          global_key: 'POST_AUTOSERVICIO_QUALTRICTS_IVR',
          script_name: 'GNS_IVR.py'
        });
      }

      addGlobalIfMissing('SMTP_HOST', 'SMTP Host');
      addGlobalIfMissing('SMTP_PORT', 'SMTP Port');
      addGlobalIfMissing('SMTP_USER', 'SMTP Usuario');
      addGlobalIfMissing('SMTP_PASSWORD', 'SMTP Password', false, true);
      addGlobalIfMissing('SMTP_FROM', 'SMTP Remitente');
      addGlobalIfMissing('SMTP_USE_TLS', 'SMTP Usar TLS');
      addInputIfMissing('SURVEY_REPORT_EMAIL_TO', 'Destinatarios reporte encuestas', 'tags');
      addInputIfMissing('SURVEY_REPORT_EMAIL_CC', 'Copias reporte encuestas', 'tags');
      addInputIfMissing('SURVEY_REPORT_SUBJECT', 'Asunto reporte encuestas', 'text', 'Reporte de Encuesta de Satisfacción - Autoservicio');
    }

    res.json(rows);
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
