import dotenv from 'dotenv';
import path from 'path';

dotenv.config();

export const env = {
  port: Number(process.env.PORT || 3000),
  nodeEnv: process.env.NODE_ENV || 'development',

  db: {
    server: process.env.DB_SERVER || 'localhost',
    port: Number(process.env.DB_PORT || 1433),
    database: process.env.DB_DATABASE || 'PyFlowManager',
    user: process.env.DB_USER || 'sa',
    password: process.env.DB_PASSWORD || '',
    encrypt: String(process.env.DB_ENCRYPT || 'false').toLowerCase() === 'true',
    trustServerCertificate: String(process.env.DB_TRUST_SERVER_CERTIFICATE || 'true').toLowerCase() === 'true'
  },

  defaultUserId: Number(process.env.DEFAULT_USER_ID || 1),
  defaultEnvironmentId: Number(process.env.DEFAULT_ENVIRONMENT_ID || 3),
  pythonCommand: process.env.PYTHON_COMMAND || 'py',

  runtime: {
    scriptsDir: path.resolve(process.cwd(), process.env.RUNTIME_SCRIPTS_DIR || '../runtime/scripts'),
    logsDir: path.resolve(process.cwd(), process.env.RUNTIME_LOGS_DIR || '../runtime/logs'),
    exportsDir: path.resolve(process.cwd(), process.env.RUNTIME_EXPORTS_DIR || '../runtime/exports')
  }
};
