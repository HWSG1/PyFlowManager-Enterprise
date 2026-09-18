import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';
import { runScript } from '../services/scriptRunner';
import { exec, execFile } from 'child_process';
import path from 'path';
import multer from 'multer';
import fs from 'fs';
import { createVersionSnapshot } from '../services/versioning.service';
import { auditEvent } from '../services/audit.service';
import { requireAuth, requireExecutionAccess, requirePermission, requireScriptAccess } from '../services/security.service';
import { extractPyflowParams, syncScriptParameters } from '../services/scriptParameters.service';
import { addExecutionLog } from '../services/dbLogService';
import { emitExecutionLog } from '../services/logBus';
import { listGenesysFlows, listGenesysCatalog, isGenesysCatalog } from '../services/genesysFlows.service';

const router = Router();

const scriptsDir = path.resolve(env.runtime.scriptsDir);

function controlWindowsProcess(pid: number, action: 'suspend' | 'resume'): Promise<void> {
  const method = action === 'suspend' ? 'Suspend' : 'Resume';
  const orderedPids = action === 'suspend'
    ? '$targetPids = @($children.ToArray()) + @($rootId)'
    : '$targetPids = @($rootId) + @($children.ToArray())';
  const script = `
$ErrorActionPreference = 'Stop'
$code = @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class PyFlowProcessControl
{
    [DllImport("ntdll.dll")]
    private static extern int NtSuspendProcess(IntPtr processHandle);

    [DllImport("ntdll.dll")]
    private static extern int NtResumeProcess(IntPtr processHandle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint processAccess, bool bInheritHandle, int processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);

    private const uint PROCESS_SUSPEND_RESUME = 0x0800;

    public static void Suspend(int pid)
    {
        Control(pid, true);
    }

    public static void Resume(int pid)
    {
        Control(pid, false);
    }

    private static void Control(int pid, bool suspend)
    {
        IntPtr handle = OpenProcess(PROCESS_SUSPEND_RESUME, false, pid);
        if (handle == IntPtr.Zero)
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        try
        {
            int result = suspend ? NtSuspendProcess(handle) : NtResumeProcess(handle);
            if (result != 0)
            {
                throw new InvalidOperationException("Nt process control failed: " + result);
            }
        }
        finally
        {
            CloseHandle(handle);
        }
    }
}
'@
Add-Type -TypeDefinition $code
$rootId = ${pid}
$all = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
$children = New-Object System.Collections.Generic.List[int]
$queue = New-Object System.Collections.Generic.Queue[int]
$queue.Enqueue($rootId)
while ($queue.Count -gt 0) {
  $current = $queue.Dequeue()
  foreach ($proc in $all | Where-Object { $_.ParentProcessId -eq $current }) {
    if (-not $children.Contains([int]$proc.ProcessId)) {
      $children.Add([int]$proc.ProcessId)
      $queue.Enqueue([int]$proc.ProcessId)
    }
  }
}
${orderedPids}
foreach ($targetPid in $targetPids) {
  $process = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
  if ($process) {
    [PyFlowProcessControl]::${method}([int]$targetPid)
  }
}
`;

  return new Promise((resolve, reject) => {
    execFile(
      'powershell.exe',
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script],
      { windowsHide: true, timeout: 15000 },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(stderr?.trim() || stdout?.trim() || error.message));
          return;
        }

        resolve();
      }
    );
  });
}

if (!fs.existsSync(scriptsDir)) {
  fs.mkdirSync(scriptsDir, { recursive: true });
}

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 25 * 1024 * 1024 }
});

function safePathSegment(value: string, fallback: string): string {
  const clean = String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^0-9A-Za-z._-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 120);

  return clean || fallback;
}

function getAvailableScriptFolder(baseName: string): string {
  const withoutPythonExtension = String(baseName || '').replace(/\.py$/i, '');
  const safeBase = safePathSegment(withoutPythonExtension, 'script');
  let folderName = safeBase;
  let counter = 2;

  while (fs.existsSync(path.join(scriptsDir, folderName))) {
    folderName = `${safeBase}_${counter}`;
    counter += 1;
  }

  return folderName;
}

function inspectScriptInputSchema(
  pythonCommand: string,
  scriptPath: string,
  workingDirectory: string,
  sourceSheet: string
): Promise<any> {
  const args = ['-u', scriptPath, '--inspect-input-schema'];
  if (sourceSheet) {
    args.push('--source-sheet', sourceSheet);
  }

  return new Promise((resolve, reject) => {
    execFile(
      pythonCommand,
      args,
      {
        cwd: workingDirectory,
        windowsHide: true,
        timeout: 30000,
        maxBuffer: 10 * 1024 * 1024,
        env: {
          ...process.env,
          PYFLOW_SCRIPT_DIR: workingDirectory
        }
      },
      (error, stdout, stderr) => {
        const output = `${stdout || ''}\n${stderr || ''}`;
        const schemaLine = output
          .split(/\r?\n/)
          .find(line => line.startsWith('PYFLOW_INPUT_SCHEMA='));

        if (schemaLine) {
          try {
            resolve(JSON.parse(schemaLine.substring('PYFLOW_INPUT_SCHEMA='.length)));
            return;
          } catch {
            reject(new Error('El script devolvió un esquema de entrada inválido.'));
            return;
          }
        }

        const errorLine = output
          .split(/\r?\n/)
          .find(line => line.startsWith('PYFLOW_INPUT_SCHEMA_ERROR='));

        if (errorLine) {
          reject(new Error(errorLine.substring('PYFLOW_INPUT_SCHEMA_ERROR='.length).trim()));
          return;
        }

        reject(new Error(
          String(stderr || stdout || error?.message || 'No se pudo inspeccionar el archivo de entrada.').trim()
        ));
      }
    );
  });
}

router.get('/', requireAuth, async (req, res, next) => {
  try {
    const pool = await getPool();
    const user = (req as any).user;

    const result = await pool.request()
      .input('user_id', sql.Int, user.id)
      .input('is_super_admin', sql.Bit, !!user.is_super_admin)
      .query(`
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
      WHERE @is_super_admin = 1 OR (
        EXISTS (
          SELECT 1 FROM dbo.UserRoles ur
          JOIN dbo.RolePermissions rp ON rp.role_id = ur.role_id
          JOIN dbo.Permissions p ON p.id = rp.permission_id
          WHERE ur.user_id = @user_id AND p.permission_key = 'scripts.view'
        )
        AND (
          NOT EXISTS (SELECT 1 FROM dbo.ScriptAccess sa WHERE sa.script_id = vw_ScriptsSummary.id)
          OR EXISTS (
            SELECT 1 FROM dbo.ScriptAccess sa
            WHERE sa.script_id = vw_ScriptsSummary.id AND sa.user_id = @user_id AND sa.can_view = 1
          )
        )
      )
      ORDER BY name
    `);

    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.post('/', requireAuth, requirePermission('scripts.create'), upload.single('file'), async (req, res, next) => {
  let createdScriptDirectory: string | null = null;

  try {
    const body = req.body || {};
    const pool = await getPool();
    const uploadedFile = req.file;

    if (uploadedFile?.buffer) {
      const extension = path.extname(uploadedFile.originalname).toLowerCase();
      if (extension !== '.py') {
        return res.status(400).json({ message: 'Solo se permite importar archivos Python .py.' });
      }

      extractPyflowParams(uploadedFile.buffer.toString('utf8'));
    }

    const rawFilePath = uploadedFile
      ? path.basename(uploadedFile.originalname)
      : body.file_path || body.path || body.name;

    const cleanFileName = safePathSegment(path.basename(rawFilePath.replace(/\\/g, '/')), 'script.py');
    const scriptBaseName = path.basename(cleanFileName, path.extname(cleanFileName));
    const scriptFolderName = uploadedFile
      ? getAvailableScriptFolder(body.name || scriptBaseName)
      : '';
    const cleanFilePath = uploadedFile
      ? path.posix.join(scriptFolderName, cleanFileName)
      : path.basename(rawFilePath.replace(/\\/g, '/'));
    const finalUploadedPath = uploadedFile
      ? path.join(scriptsDir, scriptFolderName, cleanFileName)
      : null;

    if (uploadedFile?.buffer && finalUploadedPath) {
      createdScriptDirectory = path.dirname(finalUploadedPath);
      fs.mkdirSync(path.join(createdScriptDirectory, 'config'), { recursive: true });
      fs.mkdirSync(path.join(createdScriptDirectory, 'input'), { recursive: true });
      fs.mkdirSync(path.join(createdScriptDirectory, 'output'), { recursive: true });
      fs.writeFileSync(finalUploadedPath, uploadedFile.buffer, { flag: 'wx' });
    }

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

    if (finalUploadedPath) {
      await createVersionSnapshot(
        scriptId,
        body.version || '1.0.0',
        finalUploadedPath,
        (req as any).user?.id || body.created_by_user_id || env.defaultUserId,
        body.change_notes || 'Versión inicial'
      );
      const content = fs.readFileSync(finalUploadedPath, 'utf8');
      await syncScriptParameters(scriptId, content);
    }

    await auditEvent(req, 'script.create', 'script', scriptId, null, {
      name: insertedScript.name,
      version: body.version || '1.0.0'
    });

    res.status(201).json(insertedScript);
  } catch (err) {
    if (createdScriptDirectory && fs.existsSync(createdScriptDirectory)) {
      fs.rmSync(createdScriptDirectory, { recursive: true, force: true });
    }

    next(err);
  }
});

router.get('/:id/input-schema', requireAuth, requireScriptAccess('view'), async (req, res, next) => {
  try {
    const pool = await getPool();
    const scriptId = Number(req.params.id);
    const sourceSheet = String(req.query.sheet || '').trim();

    const result = await pool.request()
      .input('script_id', sql.Int, scriptId)
      .query(`
        SELECT TOP 1
          file_path,
          working_directory,
          python_interpreter
        FROM dbo.Scripts
        WHERE id = @script_id
      `);

    const script = result.recordset[0];
    if (!script) {
      return res.status(404).json({ message: 'Script no encontrado.' });
    }

    const allowedDir = path.resolve(env.runtime.scriptsDir);
    const scriptPath = path.resolve(
      path.isAbsolute(script.file_path)
        ? script.file_path
        : path.join(allowedDir, script.file_path)
    );

    if (scriptPath === allowedDir || !scriptPath.startsWith(`${allowedDir}${path.sep}`)) {
      return res.status(400).json({ message: 'Ruta de script fuera del directorio permitido.' });
    }
    if (!fs.existsSync(scriptPath)) {
      return res.status(404).json({ message: 'El archivo del script no existe.' });
    }

    const workingDirectory = script.working_directory
      ? path.resolve(script.working_directory)
      : path.dirname(scriptPath);
    const pythonCommand = String(script.python_interpreter || env.pythonCommand || '').trim()
      .replace(/^"(.*)"$/, '$1');

    const schema = await inspectScriptInputSchema(
      pythonCommand,
      scriptPath,
      workingDirectory,
      sourceSheet
    );

    return res.json(schema);
  } catch (err: any) {
    const message = err?.message || 'No se pudo inspeccionar el archivo de entrada.';
    if (
      message.includes('carpeta input') ||
      message.includes('carpeta de entrada') ||
      message.includes('un solo archivo') ||
      message.includes('hoja seleccionada')
    ) {
      return res.status(422).json({ message });
    }
    next(err);
  }
});

router.get('/:id/genesys-catalog/:catalog', requireAuth, requireScriptAccess('view'), async (req, res) => {
  if (!isGenesysCatalog(req.params.catalog)) return res.status(400).json({ message: 'Catálogo no válido.' });
  try { return res.json(await listGenesysCatalog(Number(req.params.id), req.params.catalog)); }
  catch (err: any) { return res.status(502).json({ message: err?.message || 'No se pudo consultar el catálogo.' }); }
});

router.get('/:id/genesys-flows', requireAuth, requireScriptAccess('view'), async (req, res) => {
  try {
    return res.json(await listGenesysFlows(Number(req.params.id)));
  } catch (err: any) {
    return res.status(502).json({ message: err?.message || 'No se pudieron consultar los flujos.' });
  }
});

router.get('/:id/parameters', requireAuth, requireScriptAccess('view'), async (req, res, next) => {
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
          AND (
            s.name <> 'GNS_Colas_y_Volumenes.py'
            OR sp.param_key NOT IN (
              'DATE',
              'START_LOCAL',
              'END_LOCAL',
              'QUEUE_PAGE_SIZE',
              'HANA_BATCH_SIZE',
              'REQUEST_TIMEOUT',
              'API_SLEEP_SECONDS',
              'MAX_RETRIES',
              'DRY_RUN'
            )
          )
          AND (
            s.name <> 'GNS_Performance.py'
            OR sp.param_key NOT IN (
              'DATE',
              'BATCH_SIZE_USERS',
              'HANA_BATCH_SIZE',
              'REQUEST_TIMEOUT',
              'API_SLEEP_SECONDS',
              'MAX_RETRIES',
              'DRY_RUN',
              'OUTPUT_CSV'
            )
          )
          AND (
            s.name <> 'GNS_Adherencia.py'
            OR sp.param_key NOT IN (
              'DATE',
              'START_UTC',
              'END_UTC',
              'HANA_BATCH_SIZE',
              'REQUEST_TIMEOUT',
              'POLL_SECONDS',
              'MAX_POLL_ATTEMPTS',
              'MAX_API_RETRIES',
              'FAIL_ON_MU_ERROR',
              'DRY_RUN'
            )
          )
          AND (
            s.name <> 'GNS_Estados_Agentes.py'
            OR sp.param_key NOT IN (
              'BATCH_SIZE_USERS',
              'DRY_RUN',
              'OUTPUT_CSV',
              'REQUEST_TIMEOUT_SECONDS'
            )
          )
        ORDER BY sp.id
      `);

    const rows = result.recordset;
    const isGnsIvr = rows.some((row: any) => row.script_name === 'GNS_IVR.py');
    const isTranscriptionExtractor = rows.some((row: any) => row.script_name === 'GNS_Extractor_Transcripciones.py');
    const isGnsColasVolumenes = rows.some((row: any) => row.script_name === 'GNS_Colas_y_Volumenes.py');
    const isGnsPerformance = rows.some((row: any) => row.script_name === 'GNS_Performance.py');
    const isGnsAdherencia = rows.some((row: any) => row.script_name === 'GNS_Adherencia.py');
    const isGnsEstadosAgentes = rows.some((row: any) => row.script_name === 'GNS_Estados_Agentes.py');

    if (isTranscriptionExtractor) {
      // Lee los nuevos controles desde el archivo sin borrar parámetros guardados.
      const source = path.join(scriptsDir, 'GNS_Extractor_Transcripciones', 'GNS_Extractor_Transcripciones.py');
      const definitions = extractPyflowParams(fs.readFileSync(source, 'utf8'));
      for (const key of ['FLOW_SELECTION_ID', 'FLOW_ID', 'MEDIA_TYPE', 'PARTICIPANT_PURPOSE', 'ORIGINAL_DIRECTION', 'USER_NAME', 'QUEUE_NAME', 'CAMPAIGN_NAME', 'CONTACT_LIST_NAME', 'WRAPUP_CODE_NAME']) {
        const definition = definitions[key];
        if (!definition) continue;
        let row = rows.find((item: any) => item.param_key === key);
        if (!row) {
          row = { id: `extractor-${key}`, script_id: scriptId, param_key: key, param_value: definition.default || '', param_type: 'env', is_required: false, global_key: null };
          rows.push(row);
        }
        row.control_type = definition.type;
        row.label = definition.label;
        row.options_json = definition.options ? JSON.stringify(definition.options) : null;
      }
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
        if (tagParams.has(row.param_key) && !String(row.control_type).startsWith('genesys_')) {
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

    if (isGnsColasVolumenes) {
      const hasParam = (key: string) => rows.some((row: any) => row.param_key === key);
      let syntheticId = rows.length ? Math.max(...rows.map((row: any) => Number(row.id) || 0)) + 1 : 1;

      const forceGlobalParam = (key: string, label: string) => {
        const param = rows.find((row: any) => row.param_key === key);
        if (!param) return;

        param.param_type = 'global';
        param.control_type = 'global';
        param.global_key = key;
        param.label = label;
      };

      const addGlobalIfMissing = (key: string, label: string, secret = false) => {
        forceGlobalParam(key, label);
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
          is_required: false,
          is_secret: secret,
          global_key: key,
          script_name: 'GNS_Colas_y_Volumenes.py'
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
          existing.param_type = 'env';
          existing.global_key = null;
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
          script_name: 'GNS_Colas_y_Volumenes.py'
        });
      };

      addGlobalIfMissing('GRAPH_TENANT_ID', 'Microsoft Graph Tenant ID');
      addGlobalIfMissing('GRAPH_CLIENT_ID', 'Microsoft Graph Client ID');
      addGlobalIfMissing('GRAPH_CLIENT_SECRET', 'Microsoft Graph Client Secret', true);
      addGlobalIfMissing('GRAPH_SENDER_EMAIL', 'Correo remitente Graph');
      addInputIfMissing('REPORT_OUTPUT_FORMAT', 'Generar archivo de reporte', 'select', '', ['csv', 'xlsx']);
      addInputIfMissing('ATTACH_REPORT_FILE', 'Adjuntar archivo al correo', 'select', 'false', ['false', 'true']);
      addInputIfMissing('REPORT_OUTPUT_DIR', 'Carpeta de salida del reporte');
      addInputIfMissing('QUEUE_VOLUME_REPORT_EMAIL_TO', 'Destinatarios reporte colas/volúmenes', 'tags');
      addInputIfMissing('QUEUE_VOLUME_REPORT_EMAIL_CC', 'Copias reporte colas/volúmenes', 'tags');
      addInputIfMissing('QUEUE_VOLUME_REPORT_SUBJECT', 'Asunto reporte colas/volúmenes', 'text', 'Reporte de Colas y Volúmenes');
    }

    if (isGnsPerformance) {
      const hasParam = (key: string) => rows.some((row: any) => row.param_key === key);
      let syntheticId = rows.length ? Math.max(...rows.map((row: any) => Number(row.id) || 0)) + 1 : 1;

      const forceGlobalParam = (key: string, label: string) => {
        const param = rows.find((row: any) => row.param_key === key);
        if (!param) return;

        param.param_type = 'global';
        param.control_type = 'global';
        param.global_key = key;
        param.label = label;
      };

      const addGlobalIfMissing = (key: string, label: string, secret = false) => {
        forceGlobalParam(key, label);
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
          is_required: false,
          is_secret: secret,
          global_key: key,
          script_name: 'GNS_Performance.py'
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
          existing.param_type = 'env';
          existing.global_key = null;
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
          script_name: 'GNS_Performance.py'
        });
      };

      addGlobalIfMissing('GRAPH_TENANT_ID', 'Microsoft Graph Tenant ID');
      addGlobalIfMissing('GRAPH_CLIENT_ID', 'Microsoft Graph Client ID');
      addGlobalIfMissing('GRAPH_CLIENT_SECRET', 'Microsoft Graph Client Secret', true);
      addGlobalIfMissing('GRAPH_SENDER_EMAIL', 'Correo remitente Graph');
      addInputIfMissing('REPORT_OUTPUT_FORMAT', 'Generar archivo de reporte', 'select', '', ['csv', 'xlsx']);
      addInputIfMissing('ATTACH_REPORT_FILE', 'Adjuntar archivo al correo', 'select', 'false', ['false', 'true']);
      addInputIfMissing('REPORT_OUTPUT_DIR', 'Carpeta de salida del reporte');
      addInputIfMissing('PERFORMANCE_REPORT_EMAIL_TO', 'Destinatarios reporte performance', 'tags');
      addInputIfMissing('PERFORMANCE_REPORT_EMAIL_CC', 'Copias reporte performance', 'tags');
      addInputIfMissing('PERFORMANCE_REPORT_SUBJECT', 'Asunto reporte performance', 'text', 'Reporte de Performance Genesys');
    }

    if (isGnsAdherencia) {
      const hasParam = (key: string) => rows.some((row: any) => row.param_key === key);
      let syntheticId = rows.length ? Math.max(...rows.map((row: any) => Number(row.id) || 0)) + 1 : 1;

      const forceGlobalParam = (key: string, label: string) => {
        const param = rows.find((row: any) => row.param_key === key);
        if (!param) return;

        param.param_type = 'global';
        param.control_type = 'global';
        param.global_key = key;
        param.label = label;
      };

      const addGlobalIfMissing = (key: string, label: string, secret = false) => {
        forceGlobalParam(key, label);
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
          is_required: false,
          is_secret: secret,
          global_key: key,
          script_name: 'GNS_Adherencia.py'
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
          existing.param_type = 'env';
          existing.global_key = null;
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
          script_name: 'GNS_Adherencia.py'
        });
      };

      addGlobalIfMissing('GRAPH_TENANT_ID', 'Microsoft Graph Tenant ID');
      addGlobalIfMissing('GRAPH_CLIENT_ID', 'Microsoft Graph Client ID');
      addGlobalIfMissing('GRAPH_CLIENT_SECRET', 'Microsoft Graph Client Secret', true);
      addGlobalIfMissing('GRAPH_SENDER_EMAIL', 'Correo remitente Graph');
      addInputIfMissing('REPORT_OUTPUT_FORMAT', 'Generar archivo de reporte', 'select', '', ['csv', 'xlsx']);
      addInputIfMissing('ATTACH_REPORT_FILE', 'Adjuntar archivo al correo', 'select', 'false', ['false', 'true']);
      addInputIfMissing('REPORT_OUTPUT_DIR', 'Carpeta de salida del reporte');
      addInputIfMissing('ADHERENCIA_REPORT_EMAIL_TO', 'Destinatarios reporte adherencia', 'tags');
      addInputIfMissing('ADHERENCIA_REPORT_EMAIL_CC', 'Copias reporte adherencia', 'tags');
      addInputIfMissing('ADHERENCIA_REPORT_SUBJECT', 'Asunto reporte adherencia', 'text', 'Reporte de Adherencia Genesys');
    }

    if (isGnsEstadosAgentes) {
      const hasParam = (key: string) => rows.some((row: any) => row.param_key === key);
      let syntheticId = rows.length ? Math.max(...rows.map((row: any) => Number(row.id) || 0)) + 1 : 1;

      const forceGlobalParam = (key: string, label: string) => {
        const param = rows.find((row: any) => row.param_key === key);
        if (!param) return;

        param.param_type = 'global';
        param.control_type = 'global';
        param.global_key = key;
        param.label = label;
      };

      const addGlobalIfMissing = (key: string, label: string, secret = false) => {
        forceGlobalParam(key, label);
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
          is_required: false,
          is_secret: secret,
          global_key: key,
          script_name: 'GNS_Estados_Agentes.py'
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
          existing.param_type = 'env';
          existing.global_key = null;
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
          script_name: 'GNS_Estados_Agentes.py'
        });
      };

      addGlobalIfMissing('GRAPH_TENANT_ID', 'Microsoft Graph Tenant ID');
      addGlobalIfMissing('GRAPH_CLIENT_ID', 'Microsoft Graph Client ID');
      addGlobalIfMissing('GRAPH_CLIENT_SECRET', 'Microsoft Graph Client Secret', true);
      addGlobalIfMissing('GRAPH_SENDER_EMAIL', 'Correo remitente Graph');
      addInputIfMissing('REPORT_OUTPUT_FORMAT', 'Generar archivo de reporte', 'select', '', ['csv', 'xlsx']);
      addInputIfMissing('ATTACH_REPORT_FILE', 'Adjuntar archivo al correo', 'select', 'false', ['false', 'true']);
      addInputIfMissing('REPORT_OUTPUT_DIR', 'Carpeta de salida del reporte');
      addInputIfMissing('AGENT_STATUS_REPORT_EMAIL_TO', 'Destinatarios reporte estados', 'tags');
      addInputIfMissing('AGENT_STATUS_REPORT_EMAIL_CC', 'Copias reporte estados', 'tags');
      addInputIfMissing('AGENT_STATUS_REPORT_SUBJECT', 'Asunto reporte estados', 'text', 'Reporte de Estados de Agentes Genesys');
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
      forceGlobalParam('GRAPH_TENANT_ID', 'Microsoft Graph Tenant ID');
      forceGlobalParam('GRAPH_CLIENT_ID', 'Microsoft Graph Client ID');
      forceGlobalParam('GRAPH_CLIENT_SECRET', 'Microsoft Graph Client Secret');
      forceGlobalParam('GRAPH_SENDER_EMAIL', 'Correo remitente Graph');

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

      addGlobalIfMissing('GRAPH_TENANT_ID', 'Microsoft Graph Tenant ID');
      addGlobalIfMissing('GRAPH_CLIENT_ID', 'Microsoft Graph Client ID');
      addGlobalIfMissing('GRAPH_CLIENT_SECRET', 'Microsoft Graph Client Secret', false, true);
      addGlobalIfMissing('GRAPH_SENDER_EMAIL', 'Correo remitente Graph');
      addInputIfMissing('SURVEY_REPORT_EMAIL_TO', 'Destinatarios reporte encuestas', 'tags');
      addInputIfMissing('SURVEY_REPORT_EMAIL_CC', 'Copias reporte encuestas', 'tags');
      addInputIfMissing('SURVEY_REPORT_SUBJECT', 'Asunto reporte encuestas', 'text', 'Reporte de Encuesta de Satisfacción - Autoservicio');
    }

    res.json(rows);
  } catch (err) {
    next(err);
  }
});

router.patch('/:id/toggle', requireAuth, requireScriptAccess('edit'), async (req, res, next) => {
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
    await auditEvent(req, 'script.status.toggle', 'script', id, null, result.recordset[0]?.is_active);
  } catch (err) {
    next(err);
  }
});

router.delete('/:id', requireAuth, requireScriptAccess('edit'), async (req, res, next) => {
  try {
    const pool = await getPool();
    const id = Number(req.params.id);
    const before = await pool.request().input('id', sql.Int, id)
      .query('SELECT id,name,is_active FROM dbo.Scripts WHERE id=@id');

    await pool.request()
      .input('id', sql.Int, id)
      .query(`
        UPDATE dbo.Scripts
        SET is_active = 0,
            updated_at = SYSUTCDATETIME()
        WHERE id = @id
      `);

    await auditEvent(req, 'script.delete', 'script', id, before.recordset[0] || null, { is_active: false });
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

router.delete('/:id/definitive', requireAuth, requireScriptAccess('edit'), async (req, res, next) => {
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

    const deletedScript = scriptResult.recordset[0];
    const filePath = deletedScript.file_path;
    const allowedDir = path.resolve(env.runtime.scriptsDir);
    const fullPath = filePath
      ? path.resolve(path.isAbsolute(filePath) ? filePath : path.join(allowedDir, filePath))
      : null;
    if (fullPath && fullPath !== allowedDir && !fullPath.startsWith(`${allowedDir}${path.sep}`)) {
      return res.status(400).json({ message: 'Ruta de archivo fuera del directorio permitido.' });
    }

    await tx.begin();

    const request = new sql.Request(tx);
    request.input('script_id', sql.Int, scriptId);

    await request.query(`
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

      DELETE FROM dbo.ScheduleParameters
      WHERE schedule_id IN (
        SELECT id FROM dbo.Schedules WHERE script_id = @script_id
      );

      DELETE FROM dbo.Schedules
      WHERE script_id = @script_id;

      DELETE FROM dbo.ScriptAccess
      WHERE script_id = @script_id;

      DELETE FROM dbo.ScriptParameters
      WHERE script_id = @script_id;

      DELETE FROM dbo.ScriptVersions
      WHERE script_id = @script_id;

      DELETE FROM dbo.Scripts
      WHERE id = @script_id;
    `);

    await tx.commit();

    if (fullPath) {
      if (fs.existsSync(fullPath)) {
        fs.unlinkSync(fullPath);
      }

      const scriptDirectory = path.dirname(fullPath);
      const isScriptOwnDirectory =
        path.dirname(scriptDirectory) === allowedDir &&
        path.basename(scriptDirectory) !== '.versions';

      if (isScriptOwnDirectory && fs.existsSync(scriptDirectory)) {
        fs.rmSync(scriptDirectory, { recursive: true, force: true });
      }
    }

    const versionsRoot = path.resolve(env.runtime.scriptsDir, '.versions');
    const scriptVersionsDirectory = path.resolve(versionsRoot, String(scriptId));
    if (
      scriptVersionsDirectory.startsWith(`${versionsRoot}${path.sep}`) &&
      fs.existsSync(scriptVersionsDirectory)
    ) {
      fs.rmSync(scriptVersionsDirectory, { recursive: true, force: true });
    }

    await auditEvent(req, 'script.delete.definitive', 'script', scriptId, deletedScript, null);
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

router.post('/:id/run', requireAuth, requireScriptAccess('execute'), async (req, res, next) => {
  try {
    const id = Number(req.params.id);

    const result = await runScript(
      id,
      (req as any).user?.id || req.body?.triggered_by_user_id || env.defaultUserId,
      req.body?.parameters || {}
    );

    const runResult: any = result;

    const executionId =
      runResult?.executionId ??
      runResult?.execution_id ??
      runResult?.id ??
      runResult?.recordset?.[0]?.id;

    if (!executionId) {
      console.error('runScript no devolvió executionId:', runResult);

      return res.status(500).json({
        message: 'runScript no devolvió executionId',
        result: runResult
      });
    }

    console.log('Resultado runScript:', runResult);
    console.log('executionId normalizado:', executionId);

    res.status(202).json({
      ...runResult,
      executionId,
      execution_id: executionId,
      id: executionId
    });
  } catch (err) {
    next(err);
  }
});

router.post('/executions/:id/rerun', requireAuth, requireExecutionAccess('execute'), async (req, res, next) => {
  try {
    const executionId = Number(req.params.id);
    const pool = await getPool();

    const executionResult = await pool.request()
      .input('id', sql.Int, executionId)
      .query(`
        SELECT TOP 1 id, script_id, status
        FROM dbo.ScriptExecutions
        WHERE id = @id
      `);

    if (!executionResult.recordset.length) {
      return res.status(404).json({ message: 'Ejecución no encontrada.' });
    }

    const previousExecution = executionResult.recordset[0];

    if (!['Error', 'Cancelado'].includes(previousExecution.status)) {
      return res.status(400).json({
        message: 'Solo se pueden volver a ejecutar ejecuciones en Error o Cancelado.'
      });
    }

    const paramsResult = await pool.request()
      .input('execution_id', sql.Int, executionId)
      .input('script_id', sql.Int, previousExecution.script_id)
      .query(`
        SELECT
          ep.param_key,
          ep.param_value
        FROM dbo.ExecutionParameters ep
        JOIN dbo.ScriptParameters sp
          ON sp.script_id = @script_id
          AND sp.param_key = ep.param_key
        WHERE ep.execution_id = @execution_id
          AND ISNULL(sp.control_type, '') <> 'global'
          AND ISNULL(sp.param_type, '') <> 'global'
          AND ISNULL(ep.param_value, '') <> '********'
        ORDER BY ep.param_key
      `);

    const parameters: Record<string, string> = {};
    for (const row of paramsResult.recordset) {
      parameters[row.param_key] = row.param_value ?? '';
    }

    const result = await runScript(
      Number(previousExecution.script_id),
      (req as any).user?.id || env.defaultUserId,
      parameters
    );

    await auditEvent(req, 'execution.rerun', 'execution', result.executionId, {
      previous_execution_id: executionId,
      previous_status: previousExecution.status
    }, {
      script_id: previousExecution.script_id,
      parameters_count: Object.keys(parameters).length
    });

    res.status(202).json({
      ...result,
      executionId: result.executionId,
      execution_id: result.executionId,
      id: result.executionId,
      previousExecutionId: executionId
    });
  } catch (err) {
    next(err);
  }
});

router.post('/executions/:id/cancel', requireAuth, requirePermission('executions.cancel'), requireExecutionAccess('execute'), async (req, res, next) => {
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

    if (!['Ejecutando', 'Pausado'].includes(execution.status)) {
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

    await auditEvent(req, 'execution.cancel', 'execution', executionId, { status: execution.status }, { status: 'Cancelado' });

    res.json({ ok: true, message: 'Ejecución cancelada correctamente.' });
  } catch (err) {
    next(err);
  }
});

router.post('/executions/:id/pause', requireAuth, requireExecutionAccess('execute'), async (req, res, next) => {
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
      return res.status(400).json({ message: 'La ejecución no está en proceso.' });
    }

    if (!execution.process_id) {
      return res.status(400).json({ message: 'La ejecución no tiene proceso asociado para pausar.' });
    }

    await controlWindowsProcess(Number(execution.process_id), 'suspend');

    await pool.request()
      .input('execution_id', sql.Int, executionId)
      .input('status', sql.NVarChar(20), 'Pausado')
      .query(`
        UPDATE dbo.ScriptExecutions
        SET status = @status
        WHERE id = @execution_id
          AND status = 'Ejecutando'
      `);

    await addExecutionLog(executionId, 'WARNING', 'Ejecución pausada manualmente desde PyFlow Manager.');
    emitExecutionLog(executionId, {
      level: 'WARNING',
      message: 'Ejecución pausada manualmente desde PyFlow Manager.',
      status: 'Pausado',
      paused: true,
      source: 'runner'
    });

    await auditEvent(req, 'execution.pause', 'execution', executionId, { status: 'Ejecutando' }, { status: 'Pausado' });

    res.json({ ok: true, message: 'Ejecución pausada correctamente.' });
  } catch (err) {
    next(err);
  }
});

router.post('/executions/:id/resume', requireAuth, requireExecutionAccess('execute'), async (req, res, next) => {
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

    if (execution.status !== 'Pausado') {
      return res.status(400).json({ message: 'La ejecución no está pausada.' });
    }

    if (execution.process_id) {
      await controlWindowsProcess(Number(execution.process_id), 'resume');
    }

    const controlDirectory = path.resolve(env.runtime.controlDir, 'executions', String(executionId));
    const resumeFile = path.join(controlDirectory, 'resume.flag');
    fs.mkdirSync(controlDirectory, { recursive: true });
    fs.writeFileSync(resumeFile, new Date().toISOString(), 'utf8');

    await pool.request()
      .input('execution_id', sql.Int, executionId)
      .input('status', sql.NVarChar(20), 'Ejecutando')
      .query(`
        UPDATE dbo.ScriptExecutions
        SET status = @status
        WHERE id = @execution_id
          AND status = 'Pausado'
      `);

    await addExecutionLog(executionId, 'INFO', 'Continuar solicitado desde PyFlow Manager.');
    emitExecutionLog(executionId, {
      level: 'INFO',
      message: 'Continuar solicitado desde PyFlow Manager.',
      status: 'Ejecutando',
      resumed: true,
      source: 'runner'
    });

    await auditEvent(req, 'execution.resume', 'execution', executionId, { status: 'Pausado' }, { status: 'Ejecutando' });

    res.json({ ok: true, message: 'Señal de continuar enviada correctamente.' });
  } catch (err) {
    next(err);
  }
});

export default router;
