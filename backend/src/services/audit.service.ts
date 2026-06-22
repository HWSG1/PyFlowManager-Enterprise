import { Request } from 'express';
import { getPool, sql } from '../db/sql';

function redact(value: unknown, key = ''): unknown {
  if (/password|secret|token|credential/i.test(key)) return '********';
  if (Array.isArray(value)) return value.map(item => redact(item));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([childKey, childValue]) => [
      childKey,
      redact(childValue, childKey)
    ]));
  }
  return value;
}

function serialize(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  const safeValue = redact(value);
  return typeof safeValue === 'string' ? safeValue : JSON.stringify(safeValue);
}

export async function auditEvent(
  req: Request | null,
  actionKey: string,
  entityType: string,
  entityId: string | number | null,
  oldValue?: unknown,
  newValue?: unknown
): Promise<void> {
  try {
    const user = req ? (req as any).user : null;
    const pool = await getPool();
    await pool.request()
      .input('user_id', sql.Int, user?.id || null)
      .input('username', sql.NVarChar(150), user?.username || 'Sistema')
      .input('action_key', sql.NVarChar(150), actionKey)
      .input('entity_type', sql.NVarChar(100), entityType)
      .input('entity_id', sql.NVarChar(150), entityId === null ? null : String(entityId))
      .input('old_value', sql.NVarChar(sql.MAX), serialize(oldValue))
      .input('new_value', sql.NVarChar(sql.MAX), serialize(newValue))
      .input('ip_address', sql.NVarChar(80), req?.ip || null)
      .input('user_agent', sql.NVarChar(500), req?.headers['user-agent'] || null)
      .query(`
        INSERT INTO dbo.AuditEvents (
          user_id, username, action_key, entity_type, entity_id,
          old_value, new_value, ip_address, user_agent
        ) VALUES (
          @user_id, @username, @action_key, @entity_type, @entity_id,
          @old_value, @new_value, @ip_address, @user_agent
        )
      `);
  } catch (error) {
    console.warn('[AUDIT] No se pudo registrar el evento:', error);
  }
}
