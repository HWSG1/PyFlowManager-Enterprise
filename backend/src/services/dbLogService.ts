import { getPool, sql } from '../db/sql';

export async function addExecutionLog(
  executionId: number,
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL',
  message: string,
  source = 'runner'
) {
  const pool = await getPool();

  await pool.request()
    .input('execution_id', sql.Int, executionId)
    .input('log_level', sql.NVarChar(10), level)
    .input('message', sql.NVarChar(sql.MAX), message)
    .input('source', sql.NVarChar(100), source)
    .execute('dbo.usp_AddExecutionLog');
}
