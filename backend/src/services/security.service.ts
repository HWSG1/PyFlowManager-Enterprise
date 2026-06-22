import crypto from 'crypto';
import { Request, Response, NextFunction } from 'express';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';

const SECRET = process.env.JWT_SECRET || process.env.AUTH_TOKEN_SECRET || 'pyflow-dev-secret-change-me';

function base64url(input: Buffer | string) {
  return Buffer.from(input).toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

export function hashPassword(password: string, salt = crypto.randomBytes(16).toString('hex')): string {
  const hash = crypto.pbkdf2Sync(password, salt, 120000, 64, 'sha512').toString('hex');
  return `pbkdf2$120000$${salt}$${hash}`;
}

export function verifyPassword(password: string, stored: string): boolean {
  if (!stored) return false;
  const [algo, iterations, salt, hash] = stored.split('$');
  if (algo !== 'pbkdf2' || !iterations || !salt || !hash) return false;
  const candidate = crypto.pbkdf2Sync(password, salt, Number(iterations), 64, 'sha512').toString('hex');
  return crypto.timingSafeEqual(Buffer.from(candidate, 'hex'), Buffer.from(hash, 'hex'));
}

export function signToken(payload: Record<string, any>, expiresInSeconds = 8 * 60 * 60) {
  const header = { alg: 'HS256', typ: 'JWT' };
  const body = { ...payload, exp: Math.floor(Date.now() / 1000) + expiresInSeconds };
  const unsigned = `${base64url(JSON.stringify(header))}.${base64url(JSON.stringify(body))}`;
  const signature = base64url(crypto.createHmac('sha256', SECRET).update(unsigned).digest());
  return `${unsigned}.${signature}`;
}

export function verifyToken(token: string): any | null {
  try {
    const [h, p, s] = token.split('.');
    const expected = base64url(crypto.createHmac('sha256', SECRET).update(`${h}.${p}`).digest());
    if (!crypto.timingSafeEqual(Buffer.from(s), Buffer.from(expected))) return null;
    const payload = JSON.parse(Buffer.from(p.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'));
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch { return null; }
}

export async function auditLogin(userId: number | null, username: string, method: string, success: boolean, req: Request, message?: string) {
  try {
    const pool = await getPool();
    await pool.request()
      .input('user_id', sql.Int, userId)
      .input('username', sql.NVarChar(150), username)
      .input('auth_method', sql.NVarChar(50), method)
      .input('success', sql.Bit, success ? 1 : 0)
      .input('ip_address', sql.NVarChar(80), req.ip || '')
      .input('user_agent', sql.NVarChar(500), req.headers['user-agent'] || '')
      .input('message', sql.NVarChar(500), message || null)
      .query(`INSERT INTO dbo.LoginAudit(user_id, username, auth_method, success, ip_address, user_agent, message)
              VALUES(@user_id, @username, @auth_method, @success, @ip_address, @user_agent, @message)`);
  } catch (err) { console.warn('[AUDIT] login audit skipped', err); }
}

export async function requireAuth(req: Request, res: Response, next: NextFunction) {
  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ')
    ? auth.substring(7)
    : typeof req.query.access_token === 'string' ? req.query.access_token : '';
  const payload = token ? verifyToken(token) : null;
  if (!payload) return res.status(401).json({ message: 'Sesión no válida o expirada.' });
  (req as any).user = payload;
  next();
}

export function requirePermission(permission: string) {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const user = (req as any).user;
      if (!user?.id) return res.status(401).json({ message: 'Sesión requerida.' });
      const pool = await getPool();
      const result = await pool.request()
        .input('user_id', sql.Int, user.id)
        .input('permission_key', sql.NVarChar(150), permission)
        .query(`SELECT TOP 1 1 ok
                FROM dbo.UserRoles ur
                JOIN dbo.RolePermissions rp ON rp.role_id = ur.role_id
                JOIN dbo.Permissions p ON p.id = rp.permission_id
                WHERE ur.user_id = @user_id AND p.permission_key = @permission_key`);
      if (!result.recordset.length && !user.is_super_admin) {
        return res.status(403).json({ message: 'No tienes permiso para realizar esta acción.' });
      }
      next();
    } catch (err) { next(err); }
  };
}

export type ScriptAccessAction = 'view' | 'execute' | 'edit' | 'schedule' | 'manage_access';

export function requireScriptAccess(action: ScriptAccessAction) {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const user = (req as any).user;
      if (!user?.id) return res.status(401).json({ message: 'Sesión requerida.' });
      if (user.is_super_admin) return next();

      let scriptId = Number(req.body?.scriptId || req.body?.script_id || req.params.id);
      if (req.baseUrl.endsWith('/schedules') && req.params.id && !req.body?.scriptId && !req.body?.script_id) {
        const schedule = await (await getPool()).request()
          .input('schedule_id', sql.Int, Number(req.params.id))
          .query('SELECT script_id FROM dbo.Schedules WHERE id = @schedule_id');
        scriptId = Number(schedule.recordset[0]?.script_id);
      }
      if (!scriptId) return res.status(400).json({ message: 'Script requerido.' });

      const permissionKey = action === 'manage_access' ? 'scripts.manage_access' : `scripts.${action}`;
      const accessColumn = action === 'manage_access' ? 'can_edit' : `can_${action}`;
      const pool = await getPool();
      const result = await pool.request()
        .input('user_id', sql.Int, user.id)
        .input('script_id', sql.Int, scriptId)
        .input('permission_key', sql.NVarChar(150), permissionKey)
        .query(`
          SELECT TOP 1 1 ok
          FROM dbo.UserRoles ur
          JOIN dbo.RolePermissions rp ON rp.role_id = ur.role_id
          JOIN dbo.Permissions p ON p.id = rp.permission_id
          WHERE ur.user_id = @user_id
            AND p.permission_key = @permission_key
            AND (
              NOT EXISTS (SELECT 1 FROM dbo.ScriptAccess WHERE script_id = @script_id)
              OR EXISTS (
                SELECT 1 FROM dbo.ScriptAccess
                WHERE script_id = @script_id
                  AND user_id = @user_id
                  AND ${accessColumn} = 1
              )
            )
        `);

      if (!result.recordset.length) {
        return res.status(403).json({ message: 'No tienes permiso para esta acción sobre el script.' });
      }
      next();
    } catch (error) {
      next(error);
    }
  };
}

export function requireExecutionAccess(action: 'view' | 'execute' = 'view') {
  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const user = (req as any).user;
      if (!user?.id) return res.status(401).json({ message: 'Sesion requerida.' });
      if (user.is_super_admin) return next();

      const executionId = Number(req.params.id);
      const permissionKey = `scripts.${action}`;
      const accessColumn = `can_${action}`;
      const pool = await getPool();
      const result = await pool.request()
        .input('execution_id', sql.Int, executionId)
        .input('user_id', sql.Int, user.id)
        .input('permission_key', sql.NVarChar(150), permissionKey)
        .query(`
          SELECT TOP 1 1 ok
          FROM dbo.ScriptExecutions ex
          WHERE ex.id = @execution_id
            AND EXISTS (
              SELECT 1 FROM dbo.UserRoles ur
              JOIN dbo.RolePermissions rp ON rp.role_id = ur.role_id
              JOIN dbo.Permissions p ON p.id = rp.permission_id
              WHERE ur.user_id = @user_id AND p.permission_key = @permission_key
            )
            AND (
              NOT EXISTS (SELECT 1 FROM dbo.ScriptAccess WHERE script_id = ex.script_id)
              OR EXISTS (
                SELECT 1 FROM dbo.ScriptAccess
                WHERE script_id = ex.script_id AND user_id = @user_id AND ${accessColumn} = 1
              )
            )
        `);

      if (!result.recordset.length) {
        return res.status(403).json({ message: 'No tienes permiso para esta ejecucion.' });
      }
      next();
    } catch (error) {
      next(error);
    }
  };
}

export async function validateAdminPin(pin: string) {
  const pool = await getPool();
  const result = await pool.request().query(`SELECT TOP 1 setting_value FROM dbo.SystemSettings WHERE setting_key = 'ADMIN_SECURITY_PIN'`);
  const expected = result.recordset[0]?.setting_value || process.env.ADMIN_SECURITY_PIN || '1234';
  return String(pin || '') === String(expected);
}
