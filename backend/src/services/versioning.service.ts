import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { getPool, sql } from '../db/sql';
import { env } from '../config/env';

function safeVersion(version: string): string {
  const clean = String(version || '').trim();
  if (!/^[0-9A-Za-z._-]{1,30}$/.test(clean)) {
    throw new Error('La versión solo puede contener letras, números, punto, guion y guion bajo.');
  }
  return clean;
}

export function resolveManagedScriptPath(filePath: string): string {
  const scriptsRoot = path.resolve(env.runtime.scriptsDir);
  const resolved = path.isAbsolute(filePath)
    ? path.resolve(filePath)
    : path.resolve(scriptsRoot, path.basename(filePath.replace(/\\/g, '/')));
  if (!resolved.toLowerCase().startsWith(scriptsRoot.toLowerCase())) {
    throw new Error('Ruta de script fuera del directorio administrado.');
  }
  return resolved;
}

export async function createVersionSnapshot(
  scriptId: number,
  versionValue: string,
  sourcePath: string,
  userId: number | null,
  notes: string | null
): Promise<any> {
  const version = safeVersion(versionValue);
  const content = fs.readFileSync(sourcePath);
  const checksum = crypto.createHash('sha256').update(content).digest('hex');
  const pool = await getPool();
  const duplicate = await pool.request()
    .input('script_id', sql.Int, scriptId)
    .input('version', sql.NVarChar(30), version)
    .query('SELECT TOP 1 id FROM dbo.ScriptVersions WHERE script_id=@script_id AND version=@version');
  if (duplicate.recordset.length) throw new Error(`La version ${version} ya existe para este script.`);

  const versionDirectory = path.resolve(env.runtime.scriptsDir, '.versions', String(scriptId));
  fs.mkdirSync(versionDirectory, { recursive: true });
  const versionPath = path.join(versionDirectory, `${version}.py`);
  if (fs.existsSync(versionPath)) throw new Error(`El archivo de la version ${version} ya existe.`);
  fs.writeFileSync(versionPath, content, { flag: 'wx' });

  const tx = new sql.Transaction(pool);
  await tx.begin();
  try {
    await new sql.Request(tx)
      .input('script_id', sql.Int, scriptId)
      .query('UPDATE dbo.ScriptVersions SET is_current = 0 WHERE script_id = @script_id');
    const result = await new sql.Request(tx)
      .input('script_id', sql.Int, scriptId)
      .input('version', sql.NVarChar(30), version)
      .input('file_path', sql.NVarChar(1000), versionPath)
      .input('checksum', sql.NVarChar(128), checksum)
      .input('notes', sql.NVarChar(sql.MAX), notes)
      .input('user_id', sql.Int, userId)
      .query(`
        INSERT INTO dbo.ScriptVersions (
          script_id, version, file_path, checksum_sha256, change_notes,
          created_by_user_id, created_at, is_current
        )
        OUTPUT INSERTED.*
        VALUES (@script_id, @version, @file_path, @checksum, @notes, @user_id, SYSUTCDATETIME(), 1)
      `);
    await new sql.Request(tx)
      .input('script_id', sql.Int, scriptId)
      .input('version', sql.NVarChar(30), version)
      .query('UPDATE dbo.Scripts SET current_version = @version, updated_at = SYSUTCDATETIME() WHERE id = @script_id');
    await tx.commit();
    return result.recordset[0];
  } catch (error) {
    await tx.rollback();
    if (fs.existsSync(versionPath)) fs.unlinkSync(versionPath);
    throw error;
  }
}

export async function restoreVersion(scriptId: number, versionId: number): Promise<any> {
  const pool = await getPool();
  const result = await pool.request()
    .input('script_id', sql.Int, scriptId)
    .input('version_id', sql.Int, versionId)
    .query(`
      SELECT v.*, s.file_path AS current_file_path
      FROM dbo.ScriptVersions v
      JOIN dbo.Scripts s ON s.id = v.script_id
      WHERE v.id = @version_id AND v.script_id = @script_id
    `);
  if (!result.recordset.length) throw new Error('Versión no encontrada.');
  const version = result.recordset[0];
  if (!fs.existsSync(version.file_path)) throw new Error('El archivo físico de la versión no existe.');
  const versionContent = fs.readFileSync(version.file_path);
  const checksum = crypto.createHash('sha256').update(versionContent).digest('hex');
  if (version.checksum_sha256 && checksum !== version.checksum_sha256) {
    throw new Error('El archivo de la version fue modificado y no coincide con su checksum.');
  }
  const currentPath = resolveManagedScriptPath(version.current_file_path);
  const currentContent = fs.existsSync(currentPath) ? fs.readFileSync(currentPath) : null;
  fs.writeFileSync(currentPath, versionContent);

  const tx = new sql.Transaction(pool);
  await tx.begin();
  try {
    await new sql.Request(tx).input('script_id', sql.Int, scriptId)
      .query('UPDATE dbo.ScriptVersions SET is_current = 0 WHERE script_id = @script_id');
    await new sql.Request(tx).input('version_id', sql.Int, versionId)
      .query('UPDATE dbo.ScriptVersions SET is_current = 1 WHERE id = @version_id');
    await new sql.Request(tx)
      .input('script_id', sql.Int, scriptId)
      .input('version', sql.NVarChar(30), version.version)
      .query('UPDATE dbo.Scripts SET current_version = @version, updated_at = SYSUTCDATETIME() WHERE id = @script_id');
    await tx.commit();
    return version;
  } catch (error) {
    await tx.rollback();
    if (currentContent) fs.writeFileSync(currentPath, currentContent);
    throw error;
  }
}
