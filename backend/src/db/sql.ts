import sql from 'mssql';
import { env } from '../config/env';

let pool: sql.ConnectionPool | null = null;

export async function getPool(): Promise<sql.ConnectionPool> {
  if (pool && pool.connected) return pool;

  pool = await sql.connect({
    server: env.db.server,
    port: env.db.port,
    database: env.db.database,
    user: env.db.user,
    password: env.db.password,
    options: {
      encrypt: env.db.encrypt,
      trustServerCertificate: env.db.trustServerCertificate
    },
    pool: {
      max: 10,
      min: 0,
      idleTimeoutMillis: 30000
    }
  });

  return pool;
}

export { sql };
