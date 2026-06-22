import { Router } from 'express';
import multer from 'multer';
import fs from 'fs';
import path from 'path';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';
import { auditEvent } from '../services/audit.service';
import { requireAuth, requirePermission, requireScriptAccess } from '../services/security.service';
import { createVersionSnapshot, resolveManagedScriptPath, restoreVersion } from '../services/versioning.service';
import { extractPyflowParams, syncScriptParameters } from '../services/scriptParameters.service';

const router = Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 25 * 1024 * 1024 } });
router.use(requireAuth);

router.get('/audit', requirePermission('audit.view'), async (req, res, next) => {
  try {
    const pool = await getPool();
    const result = await pool.request().query(`
      SELECT TOP 300 audit_key, user_id, username, action_key, entity_type,
             entity_id, old_value, new_value, ip_address, created_at
      FROM (
        SELECT CONCAT('event-', id) audit_key, user_id, username, action_key,
               entity_type, entity_id, old_value, new_value, ip_address, created_at
        FROM dbo.AuditEvents
        UNION ALL
        SELECT CONCAT('config-', id), NULL, changed_by, 'configuration.update',
               module_key, setting_key, old_value, new_value, ip_address, changed_at
        FROM dbo.ConfigurationAudit
        UNION ALL
        SELECT CONCAT('login-', id), user_id, username,
               CASE WHEN success=1 THEN 'login.success' ELSE 'login.failure' END,
               'user', CONVERT(NVARCHAR(150), user_id), NULL, message, ip_address, created_at
        FROM dbo.LoginAudit
      ) audit
      ORDER BY created_at DESC
    `);
    res.json(result.recordset);
  } catch (error) { next(error); }
});

router.get('/scripts/:id', requireScriptAccess('view'), async (req, res, next) => {
  try {
    const scriptId = Number(req.params.id);
    const pool = await getPool();
    const script = await pool.request().input('id', sql.Int, scriptId).query(`
      SELECT id, name, current_version, max_retries, retry_delay_seconds,
             retry_backoff_factor, alert_on_success, alert_on_failure, alert_recipients
      FROM dbo.Scripts WHERE id = @id
    `);
    if (!script.recordset.length) return res.status(404).json({ message: 'Script no encontrado.' });

    const versions = await pool.request().input('id', sql.Int, scriptId).query(`
      SELECT v.id, v.version, v.checksum_sha256, v.change_notes, v.created_at,
             v.is_current, ISNULL(u.username, 'Sistema') created_by
      FROM dbo.ScriptVersions v
      LEFT JOIN dbo.Users u ON u.id = v.created_by_user_id
      WHERE v.script_id = @id ORDER BY v.created_at DESC, v.id DESC
    `);
    const access = await pool.request().input('id', sql.Int, scriptId).query(`
      SELECT sa.user_id, u.username, u.display_name, sa.can_view, sa.can_execute,
             sa.can_edit, sa.can_schedule
      FROM dbo.ScriptAccess sa JOIN dbo.Users u ON u.id = sa.user_id
      WHERE sa.script_id = @id ORDER BY u.display_name
    `);
    const users = await pool.request().query(`
      SELECT id, username, display_name, email FROM dbo.Users WHERE is_active = 1 ORDER BY display_name
    `);
    res.json({ policy: script.recordset[0], versions: versions.recordset, access: access.recordset, users: users.recordset });
  } catch (error) { next(error); }
});

router.put('/scripts/:id/policy', requireScriptAccess('edit'), async (req, res, next) => {
  try {
    const scriptId = Number(req.params.id);
    const body = req.body || {};
    const pool = await getPool();
    const before = await pool.request().input('id', sql.Int, scriptId).query('SELECT * FROM dbo.Scripts WHERE id = @id');
    if (!before.recordset.length) return res.status(404).json({ message: 'Script no encontrado.' });
    const policy = {
      max_retries: Math.max(0, Math.min(10, Number(body.max_retries || 0))),
      retry_delay_seconds: Math.max(1, Math.min(86400, Number(body.retry_delay_seconds || 60))),
      retry_backoff_factor: Math.max(1, Math.min(10, Number(body.retry_backoff_factor || 1))),
      alert_on_success: !!body.alert_on_success,
      alert_on_failure: !!body.alert_on_failure,
      alert_recipients: String(body.alert_recipients || '').trim()
    };
    await pool.request()
      .input('id', sql.Int, scriptId)
      .input('max_retries', sql.SmallInt, policy.max_retries)
      .input('retry_delay', sql.Int, policy.retry_delay_seconds)
      .input('backoff', sql.Decimal(6, 2), policy.retry_backoff_factor)
      .input('alert_success', sql.Bit, policy.alert_on_success)
      .input('alert_failure', sql.Bit, policy.alert_on_failure)
      .input('recipients', sql.NVarChar(sql.MAX), policy.alert_recipients || null)
      .query(`UPDATE dbo.Scripts SET max_retries=@max_retries, retry_delay_seconds=@retry_delay,
              retry_backoff_factor=@backoff, alert_on_success=@alert_success,
              alert_on_failure=@alert_failure, alert_recipients=@recipients,
              updated_at=SYSUTCDATETIME() WHERE id=@id`);
    await auditEvent(req, 'script.policy.update', 'script', scriptId, before.recordset[0], policy);
    res.json({ ok: true, policy });
  } catch (error) { next(error); }
});

router.put('/scripts/:id/access', requireScriptAccess('manage_access'), async (req, res, next) => {
  const scriptId = Number(req.params.id);
  const entries = Array.isArray(req.body?.entries) ? req.body.entries : [];
  try {
    const pool = await getPool();
    const before = await pool.request().input('id', sql.Int, scriptId)
      .query('SELECT * FROM dbo.ScriptAccess WHERE script_id=@id');
    const tx = new sql.Transaction(pool);
    await tx.begin();
    try {
      await new sql.Request(tx).input('id', sql.Int, scriptId)
        .query('DELETE FROM dbo.ScriptAccess WHERE script_id=@id');
      for (const entry of entries) {
        if (!Number(entry.user_id)) continue;
        await new sql.Request(tx)
          .input('script_id', sql.Int, scriptId)
          .input('user_id', sql.Int, Number(entry.user_id))
          .input('view', sql.Bit, !!entry.can_view)
          .input('execute', sql.Bit, !!entry.can_execute)
          .input('edit', sql.Bit, !!entry.can_edit)
          .input('schedule', sql.Bit, !!entry.can_schedule)
          .input('granted_by', sql.Int, (req as any).user?.id || null)
          .query(`INSERT INTO dbo.ScriptAccess(script_id,user_id,can_view,can_execute,can_edit,can_schedule,granted_by_user_id)
                  VALUES(@script_id,@user_id,@view,@execute,@edit,@schedule,@granted_by)`);
      }
      await tx.commit();
    } catch (error) { await tx.rollback(); throw error; }
    await auditEvent(req, 'script.access.update', 'script', scriptId, before.recordset, entries);
    res.json({ ok: true });
  } catch (error) { next(error); }
});

router.post('/scripts/:id/versions', requireScriptAccess('edit'), upload.single('file'), async (req, res, next) => {
  const scriptId = Number(req.params.id);
  let temporaryPath = '';
  try {
    if (!req.file || path.extname(req.file.originalname).toLowerCase() !== '.py') {
      return res.status(400).json({ message: 'Debes seleccionar un archivo Python .py.' });
    }
    extractPyflowParams(req.file.buffer.toString('utf8'));
    const pool = await getPool();
    const script = await pool.request().input('id', sql.Int, scriptId)
      .query('SELECT id,file_path,current_version FROM dbo.Scripts WHERE id=@id');
    if (!script.recordset.length) return res.status(404).json({ message: 'Script no encontrado.' });
    const uploadDir = path.resolve(env.runtime.scriptsDir, '.uploads');
    fs.mkdirSync(uploadDir, { recursive: true });
    temporaryPath = path.join(uploadDir, `${scriptId}_${Date.now()}.py`);
    fs.writeFileSync(temporaryPath, req.file.buffer);
    const version = await createVersionSnapshot(
      scriptId, String(req.body?.version || ''), temporaryPath,
      (req as any).user?.id || null, String(req.body?.notes || '') || null
    );
    fs.copyFileSync(temporaryPath, resolveManagedScriptPath(script.recordset[0].file_path));
    await syncScriptParameters(scriptId, req.file.buffer.toString('utf8'));
    await auditEvent(req, 'script.version.create', 'script', scriptId, script.recordset[0].current_version, version.version);
    res.status(201).json(version);
  } catch (error) { next(error); }
  finally { if (temporaryPath && fs.existsSync(temporaryPath)) fs.unlinkSync(temporaryPath); }
});

router.post('/scripts/:id/versions/:versionId/restore', requireScriptAccess('edit'), async (req, res, next) => {
  try {
    const scriptId = Number(req.params.id);
    const pool = await getPool();
    const selected = await pool.request()
      .input('script_id', sql.Int, scriptId)
      .input('version_id', sql.Int, Number(req.params.versionId))
      .query('SELECT file_path FROM dbo.ScriptVersions WHERE script_id=@script_id AND id=@version_id');
    if (!selected.recordset.length) return res.status(404).json({ message: 'Version no encontrada.' });
    extractPyflowParams(fs.readFileSync(selected.recordset[0].file_path, 'utf8'));
    const version = await restoreVersion(scriptId, Number(req.params.versionId));
    const script = await pool.request().input('id', sql.Int, scriptId)
      .query('SELECT file_path FROM dbo.Scripts WHERE id=@id');
    const content = fs.readFileSync(resolveManagedScriptPath(script.recordset[0].file_path), 'utf8');
    await syncScriptParameters(scriptId, content);
    await auditEvent(req, 'script.version.restore', 'script', scriptId, null, version.version);
    res.json({ ok: true, version: version.version });
  } catch (error) { next(error); }
});

export default router;
