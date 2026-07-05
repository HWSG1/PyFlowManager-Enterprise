import sql from 'mssql';
import { env } from '../config/env';

/* SQL 2025
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
*/

let pool: sql.ConnectionPool | null = null;

export async function getPool(): Promise<sql.ConnectionPool> {
  if (pool && pool.connected) return pool;

  console.log('DB CONFIG:', {
    server: env.db.server,
    instanceName: env.db.instanceName,
    port: env.db.port,
    database: env.db.database,
    user: env.db.user
  });
  const config: sql.config = {
    server: env.db.server,
    database: env.db.database,
    user: env.db.user,
    password: env.db.password,
    connectionTimeout: Number(process.env.DB_CONNECTION_TIMEOUT_MS || 30000),
    requestTimeout: Number(process.env.DB_REQUEST_TIMEOUT_MS || 60000),
    options: {
      encrypt: env.db.encrypt,
      trustServerCertificate: env.db.trustServerCertificate
    },
    pool: {
      max: Number(process.env.DB_POOL_MAX || 10),
      min: 0,
      idleTimeoutMillis: Number(process.env.DB_POOL_IDLE_TIMEOUT_MS || 30000)
    }
  };

  if (env.db.instanceName) {
    config.options = {
      ...config.options,
      instanceName: env.db.instanceName
    };
  } else if (env.db.port) {
    config.port = env.db.port;
  }

  pool = await sql.connect(config);
  return pool;
}

export { sql };
