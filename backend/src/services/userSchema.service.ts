import { sql } from '../db/sql';

export async function ensureUserPasswordPolicyColumns(pool: any) {
  await pool.request().query(`
    IF COL_LENGTH('dbo.Users', 'must_change_password') IS NULL
    BEGIN
      ALTER TABLE dbo.Users
        ADD must_change_password bit NOT NULL
        CONSTRAINT DF_Users_must_change_password DEFAULT (0);
    END
  `);
}

export function normalizeRoleIds(value: any): number[] {
  const raw = Array.isArray(value)
    ? value
    : String(value || '')
        .split(',')
        .map(item => item.trim())
        .filter(Boolean);

  return Array.from(
    new Set(
      raw
        .map(item => Number(item))
        .filter(item => Number.isInteger(item) && item > 0)
    )
  );
}

export async function replaceUserRoles(transaction: sql.Transaction, userId: number, roleIds: number[]) {
  await new sql.Request(transaction)
    .input('user_id', sql.Int, userId)
    .query('DELETE FROM dbo.UserRoles WHERE user_id = @user_id');

  for (const roleId of roleIds) {
    await new sql.Request(transaction)
      .input('user_id', sql.Int, userId)
      .input('role_id', sql.Int, roleId)
      .query(`
        IF EXISTS (SELECT 1 FROM dbo.Roles WHERE id = @role_id)
        BEGIN
          INSERT INTO dbo.UserRoles(user_id, role_id)
          VALUES(@user_id, @role_id);
        END
      `);
  }
}
