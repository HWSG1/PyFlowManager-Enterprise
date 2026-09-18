import { Router } from 'express';
import crypto from 'crypto';
import { getPool, sql } from '../db/sql';
import { auditLogin, hashPassword, requireAuth, signToken, verifyPassword } from '../services/security.service';
import { ensureUserPasswordPolicyColumns } from '../services/userSchema.service';

const router = Router();

const ENTRA_DEFAULT_SCOPE = 'openid profile email User.Read';
const OAUTH_STATE_MAX_AGE_MS = 10 * 60 * 1000;

function toBoolean(value: any): boolean {
  if (value === true || value === 1) return true;
  const text = String(value ?? '').trim().toLowerCase();
  return text === '1' || text === 'true' || text === 'yes' || text === 'si' || text === 'sí';
}

function base64UrlEncode(input: Buffer | string) {
  return Buffer.from(input).toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

function base64UrlDecode(input: string) {
  const normalized = input.replace(/-/g, '+').replace(/_/g, '/');
  const padding = normalized.length % 4 ? '='.repeat(4 - (normalized.length % 4)) : '';
  return Buffer.from(normalized + padding, 'base64').toString('utf8');
}

function oauthSecret() {
  return process.env.JWT_SECRET || process.env.AUTH_TOKEN_SECRET || 'pyflow-dev-secret-change-me';
}

function signOAuthState(ts: number, nonce: string) {
  return crypto.createHmac('sha256', oauthSecret()).update(`${ts}.${nonce}`).digest('hex');
}

function createOAuthState() {
  const ts = Date.now();
  const nonce = crypto.randomBytes(16).toString('hex');
  const payload = { ts, nonce, sig: signOAuthState(ts, nonce) };
  return base64UrlEncode(JSON.stringify(payload));
}

function verifyOAuthState(state: any) {
  try {
    const payload = JSON.parse(base64UrlDecode(String(state || '')));
    const ts = Number(payload.ts || 0);
    const nonce = String(payload.nonce || '');
    const sig = String(payload.sig || '');
    if (!ts || !nonce || !sig || Date.now() - ts > OAUTH_STATE_MAX_AGE_MS) return false;
    const expected = signOAuthState(ts, nonce);
    return crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected));
  } catch {
    return false;
  }
}

function getRequiredEntraConfig() {
  const tenantId = process.env.ENTRA_TENANT_ID;
  const clientId = process.env.ENTRA_CLIENT_ID;
  const clientSecret = process.env.ENTRA_CLIENT_SECRET;
  const redirectUri = process.env.ENTRA_REDIRECT_URI;
  const missing = [
    !tenantId ? 'ENTRA_TENANT_ID' : '',
    !clientId ? 'ENTRA_CLIENT_ID' : '',
    !clientSecret ? 'ENTRA_CLIENT_SECRET' : '',
    !redirectUri ? 'ENTRA_REDIRECT_URI' : ''
  ].filter(Boolean);
  if (missing.length) {
    throw new Error(`Faltan variables Entra ID: ${missing.join(', ')}`);
  }
  return {
    tenantId: tenantId as string,
    clientId: clientId as string,
    clientSecret: clientSecret as string,
    redirectUri: redirectUri as string,
    scope: process.env.ENTRA_SCOPE || ENTRA_DEFAULT_SCOPE
  };
}

function buildEntraAuthorizeUrl() {
  const config = getRequiredEntraConfig();
  const authorizeUrl = new URL(`https://login.microsoftonline.com/${config.tenantId}/oauth2/v2.0/authorize`);
  authorizeUrl.searchParams.set('client_id', config.clientId);
  authorizeUrl.searchParams.set('response_type', 'code');
  authorizeUrl.searchParams.set('redirect_uri', config.redirectUri);
  authorizeUrl.searchParams.set('response_mode', 'query');
  authorizeUrl.searchParams.set('scope', config.scope);
  authorizeUrl.searchParams.set('state', createOAuthState());
  return authorizeUrl.toString();
}

function decodeJwtPayload(token: string) {
  const parts = String(token || '').split('.');
  if (parts.length < 2) throw new Error('Token Entra ID inválido.');
  return JSON.parse(base64UrlDecode(parts[1]));
}

function validateEntraIdToken(idToken: string, tenantId: string, clientId: string) {
  const payload = decodeJwtPayload(idToken);
  const now = Math.floor(Date.now() / 1000);
  if (payload.aud !== clientId) throw new Error('El token Entra ID no corresponde al Client ID configurado.');
  if (payload.tid && payload.tid !== tenantId) throw new Error('El token Entra ID no corresponde al Tenant ID configurado.');
  if (payload.exp && payload.exp < now) throw new Error('El token Entra ID está expirado.');
  if (payload.iss && !String(payload.iss).includes(tenantId)) throw new Error('Emisor Entra ID inválido.');
  return payload;
}

async function exchangeEntraCode(code: string) {
  const config = getRequiredEntraConfig();
  const body = new URLSearchParams();
  body.set('client_id', config.clientId);
  body.set('client_secret', config.clientSecret);
  body.set('code', code);
  body.set('redirect_uri', config.redirectUri);
  body.set('grant_type', 'authorization_code');
  body.set('scope', config.scope);

  const response = await fetch(`https://login.microsoftonline.com/${config.tenantId}/oauth2/v2.0/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body
  });
  const data: any = await response.json();
  if (!response.ok) {
    throw new Error(data?.error_description || data?.error || 'No se pudo obtener token desde Entra ID.');
  }
  return { ...data, config };
}

async function fetchGraphProfile(accessToken: string) {
  try {
    const response = await fetch('https://graph.microsoft.com/v1.0/me?$select=id,displayName,mail,userPrincipalName', {
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    if (!response.ok) return null;
    return await response.json() as any;
  } catch {
    return null;
  }
}

async function getUserWithRolesByLogin(login: string) {
  const pool = await getPool();
  await ensureUserPasswordPolicyColumns(pool);
  const result = await pool.request()
    .input('login', sql.NVarChar(255), login)
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
      WHERE u.username = @login
         OR u.email = @login
         OR u.domain_user = @login
    `);
  return result.recordset[0];
}

async function createEntraUser(profile: { email: string; name: string; objectId?: string }) {
  const pool = await getPool();
  await ensureUserPasswordPolicyColumns(pool);
  const defaultRoleName = String(process.env.ENTRA_DEFAULT_ROLE_NAME || '').trim();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();
    const insert = await new sql.Request(transaction)
      .input('username', sql.NVarChar(150), profile.email)
      .input('email', sql.NVarChar(255), profile.email)
      .input('display_name', sql.NVarChar(255), profile.name || profile.email)
      .input('password_hash', sql.NVarChar(sql.MAX), null)
      .input('auth_provider', sql.NVarChar(50), 'entra_id')
      .input('azure_ad_object_id', sql.NVarChar(100), profile.objectId || null)
      .input('theme_key', sql.NVarChar(80), process.env.DEFAULT_THEME_KEY || 'dark-blue')
      .query(`
        INSERT INTO dbo.Users(
          username,
          email,
          display_name,
          password_hash,
          is_active,
          auth_provider,
          azure_ad_object_id,
          theme_key,
          must_change_password
        )
        OUTPUT INSERTED.id
        VALUES(
          @username,
          @email,
          @display_name,
          @password_hash,
          1,
          @auth_provider,
          @azure_ad_object_id,
          @theme_key,
          0
        )
      `);

    if (defaultRoleName) {
      await new sql.Request(transaction)
        .input('user_id', sql.Int, insert.recordset[0].id)
        .input('role_name', sql.NVarChar(150), defaultRoleName)
        .query(`
          INSERT INTO dbo.UserRoles(user_id, role_id)
          SELECT @user_id, r.id
          FROM dbo.Roles r
          WHERE r.role_name = @role_name
            AND NOT EXISTS (
              SELECT 1 FROM dbo.UserRoles ur WHERE ur.user_id = @user_id AND ur.role_id = r.id
            )
        `);
    }

    await transaction.commit();
    return getUserWithRolesByLogin(profile.email);
  } catch (error) {
    try { await transaction.rollback(); } catch {}
    throw error;
  }
}

function isUserActive(user: any) {
  return user?.is_active === true || user?.is_active === 1 || user?.is_active === '1';
}

function buildClientUser(user: any) {
  const mustChangePassword = toBoolean(user.must_change_password);
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    name: user.display_name,
    roles: user.roles || '',
    theme: user.theme_key,
    mustChangePassword
  };
}

function buildPyFlowTokenUser(user: any) {
  const mustChangePassword = toBoolean(user.must_change_password);
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    name: user.display_name,
    roles: user.roles || '',
    theme: user.theme_key,
    must_change_password: mustChangePassword,
    is_super_admin: String(user.roles || '').includes('Super Administrador')
  };
}

function renderAuthCallbackPage(token: string, user: any) {
  const redirectUrl = process.env.FRONTEND_URL || '/';
  const tokenJson = JSON.stringify(token).replace(/</g, '\\u003c');
  const userJson = JSON.stringify(user).replace(/</g, '\\u003c');
  const redirectJson = JSON.stringify(redirectUrl).replace(/</g, '\\u003c');
  return `<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>PyFlow Manager</title></head>
<body>
<script>
localStorage.setItem('pyflow_token', ${tokenJson});
localStorage.setItem('pyflow_user', JSON.stringify(${userJson}));
window.location.replace(${redirectJson});
</script>
<p>Inicio de sesión correcto. Redirigiendo a PyFlow Manager...</p>
</body>
</html>`;
}

function renderAuthErrorPage(message: string) {
  const redirectUrl = process.env.FRONTEND_URL || '/';
  const safeMessage = String(message || 'No se pudo iniciar sesión con Entra ID.');
  const redirectJson = JSON.stringify(redirectUrl).replace(/</g, '\\u003c');
  return `<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>PyFlow Manager</title></head>
<body style="font-family: Arial, sans-serif; padding: 32px;">
<h2>No se pudo iniciar sesión con Microsoft Entra ID</h2>
<p>${safeMessage.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>
<button onclick="window.location.replace(${redirectJson})">Volver a PyFlow Manager</button>
</body>
</html>`;
}

router.get('/entra/start', async (_req, res, next) => {
  try {
    res.redirect(buildEntraAuthorizeUrl());
  } catch (err) {
    next(err);
  }
});

router.get('/entra/callback', async (req, res) => {
  try {
    const { code, state, error, error_description } = req.query;
    if (error) throw new Error(String(error_description || error));
    if (!code) throw new Error('Microsoft no devolvió código de autorización.');
    if (!verifyOAuthState(state)) throw new Error('La respuesta de Entra ID no pudo validarse. Intenta iniciar sesión nuevamente.');

    const tokenResponse = await exchangeEntraCode(String(code));
    const idPayload = validateEntraIdToken(tokenResponse.id_token, tokenResponse.config.tenantId, tokenResponse.config.clientId);
    const graphProfile = tokenResponse.access_token ? await fetchGraphProfile(tokenResponse.access_token) : null;

    const email = String(
      idPayload.preferred_username ||
      idPayload.email ||
      idPayload.upn ||
      graphProfile?.mail ||
      graphProfile?.userPrincipalName ||
      ''
    ).trim().toLowerCase();
    const displayName = String(idPayload.name || graphProfile?.displayName || email).trim();
    const objectId = String(idPayload.oid || graphProfile?.id || '').trim();

    if (!email) throw new Error('No se pudo identificar el correo del usuario desde Entra ID.');

    let user = await getUserWithRolesByLogin(email);
    if (!user && toBoolean(process.env.ENTRA_AUTO_CREATE_USERS)) {
      user = await createEntraUser({ email, name: displayName, objectId });
    }
    if (!user) {
      await auditLogin(null, email, 'entra_id', false, req, 'Usuario no existe en PyFlow Manager.');
      throw new Error('El usuario autenticó en Entra ID, pero no existe en PyFlow Manager. Créalo en Usuarios y Roles o habilita ENTRA_AUTO_CREATE_USERS.');
    }
    if (!isUserActive(user)) {
      await auditLogin(user.id, email, 'entra_id', false, req, 'Usuario inactivo.');
      throw new Error('Usuario inactivo en PyFlow Manager.');
    }

    await auditLogin(user.id, email, 'entra_id', true, req);
    await (await getPool()).request()
      .input('id', sql.Int, user.id)
      .input('object_id', sql.NVarChar(100), objectId || null)
      .query('UPDATE dbo.Users SET last_login = GETDATE(), azure_ad_object_id = ISNULL(azure_ad_object_id, @object_id) WHERE id = @id');

    const pyflowToken = signToken(buildPyFlowTokenUser(user));
    return res.type('html').send(renderAuthCallbackPage(pyflowToken, buildClientUser(user)));
  } catch (err: any) {
    console.error('[AUTH][ENTRA]', err);
    return res.status(401).type('html').send(renderAuthErrorPage(err?.message || 'No se pudo iniciar sesión con Entra ID.'));
  }
});

router.post('/login', async (req, res, next) => {
  try {
    const { username, password, provider = 'local' } = req.body || {};
    const authProvider = String(provider || 'local').toLowerCase();

    if (authProvider === 'entra') {
      return res.status(202).json({
        message: 'Redirigiendo a Microsoft Entra ID.',
        provider: authProvider,
        redirectUrl: process.env.ENTRA_START_URL || `${process.env.PUBLIC_API_URL || '/api'}/auth/entra/start`
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

    const isActive = isUserActive(user);

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

    const token = signToken(buildPyFlowTokenUser(user));
    const clientUser = buildClientUser(user);

    res.json({
      token,
      user: clientUser,
      mustChangePassword: clientUser.mustChangePassword
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
