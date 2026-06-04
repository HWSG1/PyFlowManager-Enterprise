import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { hashPassword, requireAuth, requirePermission } from '../services/security.service';

const router = Router();
router.use(requireAuth);

router.get('/', async (_req, res, next) => {
  try {
    const pool = await getPool();
    const result = await pool.request().query(`SELECT u.id,u.username,u.email,u.display_name,u.is_active,u.auth_provider,u.theme_key, STRING_AGG(r.role_name, ', ') roles
      FROM dbo.Users u LEFT JOIN dbo.UserRoles ur ON ur.user_id=u.id LEFT JOIN dbo.Roles r ON r.id=ur.role_id
      GROUP BY u.id,u.username,u.email,u.display_name,u.is_active,u.auth_provider,u.theme_key ORDER BY u.display_name`);
    res.json(result.recordset);
  } catch (err) { next(err); }
});

router.get('/roles', async (_req, res, next) => {
  try { const pool = await getPool(); const result = await pool.request().query(`SELECT * FROM dbo.Roles ORDER BY role_name`); res.json(result.recordset); }
  catch (err) { next(err); }
});

router.post('/', requirePermission('users.manage'), async (req, res, next) => {
  try {
    const b = req.body || {}; const pool = await getPool();
    const result = await pool.request()
      .input('username', sql.NVarChar(150), b.username)
      .input('email', sql.NVarChar(255), b.email)
      .input('display_name', sql.NVarChar(255), b.display_name)
      .input('password_hash', sql.NVarChar(sql.MAX), hashPassword(b.password || 'PyFlow123*'))
      .input('is_active', sql.NVarChar(30), b.is_active || 'ACTIVE')
      .input('auth_provider', sql.NVarChar(50), b.auth_provider || 'local')
      .input('theme_key', sql.NVarChar(80), b.theme_key || 'dark-blue')
      .query(`INSERT INTO dbo.Users(username,email,display_name,password_hash,is_active,auth_provider,theme_key)
              OUTPUT INSERTED.id VALUES(@username,@email,@display_name,@password_hash,@is_active,@auth_provider,@theme_key)`);
    res.json({ ok: true, id: result.recordset[0].id });
  } catch (err) { next(err); }
});

router.put('/:id', requirePermission('users.manage'), async (req, res, next) => {
  try {
    const b = req.body || {}; const pool = await getPool();
    const rawAuthProvider = String(b.auth_provider || 'local').toLowerCase();

    const authProviderMap: Record<string, string> = {
      local: 'local',
      mixed: 'local',
      entra: 'azure_ad',
      entra_id: 'azure_ad',
      azure: 'azure_ad',
      azure_ad: 'azure_ad',
      active_directory: 'ad',
      ad: 'ad'
    };

    const authProvider = authProviderMap[rawAuthProvider] || 'local';
    await pool.request()
      .input('id', sql.Int, Number(req.params.id))
      .input('email', sql.NVarChar(255), b.email)
      .input('display_name', sql.NVarChar(255), b.display_name)
      .input(
        'is_active',
        sql.Bit,
        b.is_active === true ||
        b.is_active === 1 ||
        b.is_active === '1' ||
        b.is_active === 'true' ||
        b.is_active === 'ACTIVE'
      )
      .input('auth_provider', sql.NVarChar(50), authProvider)
      .input('theme_key', sql.NVarChar(80), b.theme_key)
      .query(`UPDATE dbo.Users SET email=@email, display_name=@display_name, is_active=@is_active, auth_provider=@auth_provider, theme_key=@theme_key, updated_at=GETDATE() WHERE id=@id`);
    res.json({ ok: true });
  } catch (err) { next(err); }
});

router.post('/:id/password', requirePermission('users.manage'), async (req, res, next) => {
  try { const pool = await getPool(); await pool.request().input('id', sql.Int, Number(req.params.id)).input('password_hash', sql.NVarChar(sql.MAX), hashPassword(req.body?.password || 'PyFlow123*')).query(`UPDATE dbo.Users SET password_hash=@password_hash, updated_at=GETDATE() WHERE id=@id`); res.json({ ok: true }); }
  catch (err) { next(err); }
});

export default router;
