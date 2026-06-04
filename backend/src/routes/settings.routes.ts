import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { requireAuth, requirePermission, validateAdminPin } from '../services/security.service';

const router = Router();

router.get('/', async (_req, res, next) => {
  try {
    const pool = await getPool();

    const globalVars = await pool.request().query(`
      SELECT id, var_key, CASE WHEN is_secret = 1 THEN '********' ELSE var_value END AS var_value,
             is_secret, description, created_at, updated_at
      FROM dbo.GlobalVariables ORDER BY var_key
    `);

    const systemSettings = await pool.request().query(`
      SELECT
        id,
        environment_id,
        setting_key,
        CASE WHEN setting_type='secret' THEN '********' ELSE setting_value END setting_value,
        setting_type,
        category,
        description,
        is_critical,
        updated_at
      FROM dbo.SystemSettings
      ORDER BY environment_id, category, setting_key
    `);

    res.json({ globalVars: globalVars.recordset, systemSettings: systemSettings.recordset });
  } catch (err) { next(err); }
});

router.post('/system', requireAuth, requirePermission('settings.manage'), async (req, res, next) => {
  try {
    const { settings = [], adminPin } = req.body || {};
    if (!await validateAdminPin(adminPin)) return res.status(403).json({ message: 'PIN administrativo inválido.' });
    const pool = await getPool();
    const user = (req as any).user;

    for (const item of Array.isArray(settings) ? settings : []) {
      const key = String(item.setting_key || '').trim();
      if (!key) continue;
      const oldRow = await pool.request().input('setting_key', sql.NVarChar(150), key).query(`SELECT TOP 1 * FROM dbo.SystemSettings WHERE setting_key=@setting_key`);
      const oldValue = oldRow.recordset[0]?.setting_value ?? null;
      const type = item.setting_type || oldRow.recordset[0]?.setting_type || 'string';
      const newValue = type === 'secret' && item.setting_value === '********' ? oldValue : String(item.setting_value ?? '');

      await pool.request()
        .input('setting_key', sql.NVarChar(150), key)
        .input('setting_value', sql.NVarChar(sql.MAX), newValue)
        .input('setting_type', sql.NVarChar(50), type)
        .input('category', sql.NVarChar(80), item.category || 'general')
        .input('description', sql.NVarChar(500), item.description || null)
        .input('is_critical', sql.Bit, item.is_critical ? 1 : 0)
        .input('updated_by', sql.NVarChar(150), user?.username || 'system')
        .query(`MERGE dbo.SystemSettings AS t USING (SELECT @setting_key setting_key) s ON t.setting_key=s.setting_key
          WHEN MATCHED THEN UPDATE SET setting_value=@setting_value, setting_type=@setting_type, category=@category, description=@description, is_critical=@is_critical, updated_by=@updated_by, updated_at=GETDATE()
          WHEN NOT MATCHED THEN INSERT(setting_key, setting_value, setting_type, category, description, is_critical, updated_by) VALUES(@setting_key,@setting_value,@setting_type,@category,@description,@is_critical,@updated_by);`);

      await pool.request()
        .input('module_key', sql.NVarChar(100), 'settings')
        .input('setting_key', sql.NVarChar(150), key)
        .input('old_value', sql.NVarChar(sql.MAX), oldValue)
        .input('new_value', sql.NVarChar(sql.MAX), newValue)
        .input('changed_by', sql.NVarChar(150), user?.username || 'system')
        .input('ip_address', sql.NVarChar(80), req.ip || '')
        .input('user_agent', sql.NVarChar(500), req.headers['user-agent'] || '')
        .query(`INSERT INTO dbo.ConfigurationAudit(module_key,setting_key,old_value,new_value,changed_by,ip_address,user_agent) VALUES(@module_key,@setting_key,@old_value,@new_value,@changed_by,@ip_address,@user_agent)`);
    }
    res.json({ ok: true });
  } catch (err) { next(err); }
});

router.get('/audit', requireAuth, requirePermission('settings.manage'), async (_req, res, next) => {
  try { const pool = await getPool(); const r = await pool.request().query(`SELECT TOP 100 * FROM dbo.ConfigurationAudit ORDER BY changed_at DESC`); res.json(r.recordset); }
  catch (err) { next(err); }
});

router.post('/global-variables', async (req, res, next) => {
  try {
    const variables = Array.isArray(req.body?.variables) ? req.body.variables : [];
    const pool = await getPool();
    for (const item of variables) {
      const id = item.id ? Number(item.id) : null;
      const varKey = String(item.var_key || item.key || '').trim();
      const varValue = item.var_value ?? item.value ?? '';
      const isSecret = item.is_secret ? 1 : 0;
      const description = item.description || null;
      if (!varKey) continue;
      if (id) {
        await pool.request().input('id', sql.Int, id).input('var_key', sql.NVarChar(150), varKey).input('var_value', sql.NVarChar(sql.MAX), String(varValue)).input('is_secret', sql.Bit, isSecret).input('description', sql.NVarChar(500), description).query(`UPDATE dbo.GlobalVariables SET var_key=@var_key, var_value=CASE WHEN is_secret=1 AND @var_value='********' THEN var_value ELSE @var_value END, is_secret=@is_secret, description=@description, updated_at=GETDATE() WHERE id=@id`);
      } else {
        await pool.request().input('var_key', sql.NVarChar(150), varKey).input('var_value', sql.NVarChar(sql.MAX), String(varValue)).input('is_secret', sql.Bit, isSecret).input('description', sql.NVarChar(500), description).query(`INSERT INTO dbo.GlobalVariables(var_key,var_value,is_secret,description) VALUES(@var_key,@var_value,@is_secret,@description)`);
      }
    }
    res.json({ ok: true });
  } catch (err) { next(err); }
});

router.delete('/global-variables/:id', async (req, res, next) => {
  try { const pool = await getPool(); await pool.request().input('id', sql.Int, Number(req.params.id)).query(`DELETE FROM dbo.GlobalVariables WHERE id=@id`); res.json({ ok: true }); }
  catch (err) { next(err); }
});

export default router;
