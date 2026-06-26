import { Router } from 'express';
import { getPool, sql } from '../db/sql';
import { hashPassword, requireAuth, requirePermission } from '../services/security.service';
import { auditEvent } from '../services/audit.service';
import { ensureUserPasswordPolicyColumns, normalizeRoleIds, replaceUserRoles } from '../services/userSchema.service';

const router = Router();
router.use(requireAuth);

function normalizeAuthProvider(value: any) {
  const raw = String(value || 'local').toLowerCase();
  const map: Record<string, string> = {
    local: 'local',
    mixed: 'local',
    entra: 'entra_id',
    entra_id: 'entra_id',
    azure: 'entra_id',
    azure_ad: 'entra_id',
    active_directory: 'active_directory',
    ad: 'active_directory'
  };
  return map[raw] || 'local';
}

function toBit(value: any, defaultValue = true) {
  if (value === undefined || value === null || value === '') return defaultValue;
  return value === true || value === 1 || value === '1' || value === 'true' || value === 'ACTIVE';
}

router.get('/', async (_req, res, next) => {
  try {
    const pool = await getPool();
    await ensureUserPasswordPolicyColumns(pool);
    const result = await pool.request().query(`
      SELECT
        u.id,
        u.username,
        u.email,
        u.display_name,
        u.is_active,
        u.auth_provider,
        u.theme_key,
        u.must_change_password,
        STRING_AGG(r.role_name, ', ') roles,
        STRING_AGG(CONVERT(varchar(20), r.id), ',') role_ids
      FROM dbo.Users u
      LEFT JOIN dbo.UserRoles ur ON ur.user_id = u.id
      LEFT JOIN dbo.Roles r ON r.id = ur.role_id
      GROUP BY
        u.id,
        u.username,
        u.email,
        u.display_name,
        u.is_active,
        u.auth_provider,
        u.theme_key,
        u.must_change_password
      ORDER BY u.display_name
    `);
    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.get('/roles', async (_req, res, next) => {
  try {
    const pool = await getPool();
    const result = await pool.request().query('SELECT * FROM dbo.Roles ORDER BY role_name');
    res.json(result.recordset);
  } catch (err) {
    next(err);
  }
});

router.post('/', requirePermission('users.manage'), async (req, res, next) => {
  const pool = await getPool();
  await ensureUserPasswordPolicyColumns(pool);
  const transaction = new sql.Transaction(pool);

  try {
    const b = req.body || {};
    const authProvider = normalizeAuthProvider(b.auth_provider);
    const roleIds = normalizeRoleIds(b.role_ids);

    await transaction.begin();

    const result = await new sql.Request(transaction)
      .input('username', sql.NVarChar(150), b.username)
      .input('email', sql.NVarChar(255), b.email)
      .input('display_name', sql.NVarChar(255), b.display_name)
      .input('password_hash', sql.NVarChar(sql.MAX), hashPassword(b.password || 'PyFlow123*'))
      .input('is_active', sql.Bit, toBit(b.is_active, true))
      .input('auth_provider', sql.NVarChar(50), authProvider)
      .input('theme_key', sql.NVarChar(80), b.theme_key || 'dark-blue')
      .input('must_change_password', sql.Bit, authProvider === 'local' ? 1 : 0)
      .query(`
        INSERT INTO dbo.Users(
          username,
          email,
          display_name,
          password_hash,
          is_active,
          auth_provider,
          theme_key,
          must_change_password
        )
        OUTPUT INSERTED.id
        VALUES(
          @username,
          @email,
          @display_name,
          @password_hash,
          @is_active,
          @auth_provider,
          @theme_key,
          @must_change_password
        )
      `);

    const userId = result.recordset[0].id;
    await replaceUserRoles(transaction, userId, roleIds);
    await transaction.commit();

    await auditEvent(req, 'user.create', 'user', userId, null, {
      username: b.username,
      email: b.email,
      display_name: b.display_name,
      role_ids: roleIds
    });
    res.json({ ok: true, id: userId });
  } catch (err) {
    try { await transaction.rollback(); } catch {}
    next(err);
  }
});

router.put('/:id', requirePermission('users.manage'), async (req, res, next) => {
  const pool = await getPool();
  await ensureUserPasswordPolicyColumns(pool);
  const transaction = new sql.Transaction(pool);

  try {
    const b = req.body || {};
    const userId = Number(req.params.id);
    const authProvider = normalizeAuthProvider(b.auth_provider);
    const roleIds = normalizeRoleIds(b.role_ids);

    const before = await pool.request()
      .input('id', sql.Int, userId)
      .query(`
        SELECT id, email, display_name, is_active, auth_provider, theme_key, must_change_password
        FROM dbo.Users
        WHERE id = @id
      `);

    await transaction.begin();

    await new sql.Request(transaction)
      .input('id', sql.Int, userId)
      .input('email', sql.NVarChar(255), b.email)
      .input('display_name', sql.NVarChar(255), b.display_name)
      .input('is_active', sql.Bit, toBit(b.is_active, true))
      .input('auth_provider', sql.NVarChar(50), authProvider)
      .input('theme_key', sql.NVarChar(80), b.theme_key || 'dark-blue')
      .input('must_change_password', sql.Bit, b.must_change_password ? 1 : 0)
      .query(`
        UPDATE dbo.Users
        SET
          email = @email,
          display_name = @display_name,
          is_active = @is_active,
          auth_provider = @auth_provider,
          theme_key = @theme_key,
          must_change_password = @must_change_password,
          updated_at = GETDATE()
        WHERE id = @id
      `);

    await replaceUserRoles(transaction, userId, roleIds);
    await transaction.commit();

    await auditEvent(req, 'user.update', 'user', userId, before.recordset[0], {
      email: b.email,
      display_name: b.display_name,
      is_active: b.is_active,
      auth_provider: authProvider,
      theme_key: b.theme_key,
      must_change_password: !!b.must_change_password,
      role_ids: roleIds
    });
    res.json({ ok: true });
  } catch (err) {
    try { await transaction.rollback(); } catch {}
    next(err);
  }
});

router.post('/:id/password', requirePermission('users.manage'), async (req, res, next) => {
  try {
    const password = String(req.body?.password || '').trim();
    if (password.length < 8) {
      return res.status(400).json({ message: 'La contraseña debe tener al menos 8 caracteres.' });
    }

    const pool = await getPool();
    await ensureUserPasswordPolicyColumns(pool);
    await pool.request()
      .input('id', sql.Int, Number(req.params.id))
      .input('password_hash', sql.NVarChar(sql.MAX), hashPassword(password))
      .query(`
        UPDATE dbo.Users
        SET
          password_hash = @password_hash,
          must_change_password = 1,
          updated_at = GETDATE()
        WHERE id = @id
      `);
    await auditEvent(req, 'user.password.reset', 'user', req.params.id);
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

export default router;
