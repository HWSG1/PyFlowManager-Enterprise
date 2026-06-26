import { Router } from 'express';
import crypto from 'crypto';
import { getPool, sql } from '../db/sql';
import { auditLogin, hashPassword, requireAuth, signToken, verifyPassword } from '../services/security.service';
import { ensureUserPasswordPolicyColumns } from '../services/userSchema.service';

const router = Router();

router.post('/login', async (req, res, next) => {
  try {
    const { username, password, provider = 'local' } = req.body || {};
    const authProvider = String(provider || 'local').toLowerCase();

    if (authProvider === 'entra') {
      return res.status(202).json({
        message: 'Proveedor externo configurado como preparado. Conecta MSAL/Entra ID en producción.',
        provider: authProvider,
        redirectUrl: process.env.ENTRA_LOGIN_URL || null
      });
    }

    if (!username) return res.status(400).json({ message: 'Usuario requerido.' });

    const pool = await getPool();
    await ensureUserPasswordPolicyColumns(pool);

    const result = await pool.request()
      .input('username', sql.NVarChar(150), username)
      .query(`
        SELECT
            u.*,
            ISNULL(u.must_change_password, 0) AS must_change_password,
            ISNULL(roles.roles, '') AS roles
        FROM dbo.Users u
        OUTER APPLY (
            SELECT STRING_AGG(r.role_name, ',') AS roles
            FROM dbo.UserRoles ur
            INNER JOIN dbo.Roles r ON r.id = ur.role_id
            WHERE ur.user_id = u.id
        ) roles
        WHERE u.username = @username
           OR u.email = @username
      `);

    const user = result.recordset[0];

    const isActive =
      user?.is_active === true ||
      user?.is_active === 1 ||
      user?.is_active === '1';

    const isPasswordValid = user
      ? verifyPassword(String(password || ''), user.password_hash || '')
      : false;

    if (!user) {
      return res.status(401).json({ message: 'Usuario no encontrado.' });
    }

    if (authProvider !== 'local') {
      return res.status(400).json({ message: 'Proveedor de autenticación no soportado.' });
    }

    if (!isActive) {
      return res.status(401).json({ message: 'Usuario inactivo.' });
    }

    if (!isPasswordValid) {
      return res.status(401).json({ message: 'Contraseña inválida.' });
    }

    await auditLogin(user.id, username, 'local', true, req);
    await pool.request()
      .input('id', sql.Int, user.id)
      .query('UPDATE dbo.Users SET last_login = GETDATE() WHERE id = @id');

    const token = signToken({
      id: user.id,
      username: user.username,
      email: user.email,
      name: user.display_name,
      roles: user.roles || '',
      theme: user.theme_key,
      must_change_password: !!user.must_change_password,
      is_super_admin: String(user.roles || '').includes('Super Administrador')
    });

    res.json({
      token,
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        name: user.display_name,
        roles: user.roles || '',
        theme: user.theme_key,
        mustChangePassword: !!user.must_change_password
      },
      mustChangePassword: !!user.must_change_password
    });
  } catch (err) {
    next(err);
  }
});

router.get('/me', requireAuth, async (req, res) => res.json({ user: (req as any).user }));

router.post('/change-password', requireAuth, async (req, res, next) => {
  try {
    const user = (req as any).user;
    const { currentPassword, newPassword } = req.body || {};
    const nextPassword = String(newPassword || '');

    if (nextPassword.length < 8) {
      return res.status(400).json({ message: 'La nueva contraseña debe tener al menos 8 caracteres.' });
    }

    const pool = await getPool();
    await ensureUserPasswordPolicyColumns(pool);
    const row = await pool.request()
      .input('id', sql.Int, user.id)
      .query('SELECT TOP 1 id, password_hash FROM dbo.Users WHERE id = @id AND is_active = 1');

    const dbUser = row.recordset[0];
    if (!dbUser) return res.status(404).json({ message: 'Usuario no encontrado.' });

    if (!verifyPassword(String(currentPassword || ''), dbUser.password_hash || '')) {
      return res.status(400).json({ message: 'La contraseña actual no es correcta.' });
    }

    await pool.request()
      .input('id', sql.Int, user.id)
      .input('password_hash', sql.NVarChar(sql.MAX), hashPassword(nextPassword))
      .query(`
        UPDATE dbo.Users
        SET
          password_hash = @password_hash,
          must_change_password = 0,
          updated_at = GETDATE()
        WHERE id = @id
      `);

    const token = signToken({
      ...user,
      must_change_password: false
    });

    res.json({ ok: true, token, user: { ...user, mustChangePassword: false, must_change_password: false } });
  } catch (err) {
    next(err);
  }
});

router.post('/forgot-password', async (req, res, next) => {
  try {
    const { email, channel = 'email' } = req.body || {};
    const pool = await getPool();
    const user = await pool.request().input('email', sql.NVarChar(255), email).query(`SELECT TOP 1 id,email FROM dbo.Users WHERE email=@email AND is_active='1'`);
    if (user.recordset.length) {
      const token = crypto.randomBytes(32).toString('hex');
      const tokenHash = crypto.createHash('sha256').update(token).digest('hex');
      await pool.request()
        .input('user_id', sql.Int, user.recordset[0].id)
        .input('token_hash', sql.NVarChar(128), tokenHash)
        .input('channel', sql.NVarChar(20), channel)
        .query(`INSERT INTO dbo.PasswordResetTokens(user_id, token_hash, channel, expires_at) VALUES(@user_id,@token_hash,@channel,DATEADD(MINUTE,30,GETDATE()))`);
      return res.json({ ok: true, message: 'Token generado. Configura SMTP/SMS para enviarlo.', devToken: process.env.NODE_ENV === 'production' ? undefined : token });
    }
    res.json({ ok: true, message: 'Si el correo existe, se enviarán instrucciones.' });
  } catch (err) { next(err); }
});

router.post('/reset-password', async (req, res, next) => {
  try {
    const { token, password } = req.body || {};
    const tokenHash = crypto.createHash('sha256').update(String(token || '')).digest('hex');
    const pool = await getPool();
    const row = await pool.request().input('token_hash', sql.NVarChar(128), tokenHash).query(`SELECT TOP 1 * FROM dbo.PasswordResetTokens WHERE token_hash=@token_hash AND used_at IS NULL AND expires_at > GETDATE()`);
    if (!row.recordset.length) return res.status(400).json({ message: 'Token inválido o expirado.' });
    await ensureUserPasswordPolicyColumns(pool);
    await pool.request().input('id', sql.Int, row.recordset[0].user_id).input('password_hash', sql.NVarChar(sql.MAX), hashPassword(password)).query(`UPDATE dbo.Users SET password_hash=@password_hash, must_change_password=0, updated_at=GETDATE() WHERE id=@id`);
    await pool.request().input('id', sql.Int, row.recordset[0].id).query(`UPDATE dbo.PasswordResetTokens SET used_at=GETDATE() WHERE id=@id`);
    res.json({ ok: true });
  } catch (err) { next(err); }
});

export default router;
