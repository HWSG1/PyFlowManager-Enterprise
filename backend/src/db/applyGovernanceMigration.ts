import fs from 'fs';
import path from 'path';
import { getPool } from './sql';
import { createVersionSnapshot, resolveManagedScriptPath } from '../services/versioning.service';

async function main() {
  const migrationPath = path.resolve(process.cwd(), '..', 'Generar DBA SQL Server', '03_First_Phase_Governance.sql');
  const sqlText = fs.readFileSync(migrationPath, 'utf8');
  const batches = sqlText
    .split(/^\s*GO\s*$/gim)
    .map(batch => batch.trim())
    .filter(Boolean);

  const pool = await getPool();
  for (const batch of batches) {
    await pool.request().batch(batch);
  }

  const missingVersions = await pool.request().query(`
    SELECT s.id, s.current_version, s.file_path
    FROM dbo.Scripts s
    WHERE NOT EXISTS (SELECT 1 FROM dbo.ScriptVersions v WHERE v.script_id = s.id)
  `);
  let snapshots = 0;
  for (const script of missingVersions.recordset) {
    const scriptPath = resolveManagedScriptPath(script.file_path);
    if (!fs.existsSync(scriptPath)) {
      console.warn(`No se creó snapshot para script ${script.id}: archivo no encontrado.`);
      continue;
    }
    await createVersionSnapshot(
      script.id,
      script.current_version || '1.0.0',
      scriptPath,
      null,
      'Snapshot inicial al habilitar versionado'
    );
    snapshots++;
  }

  console.log(`Migración aplicada: ${path.basename(migrationPath)} (${batches.length} lotes, ${snapshots} snapshots)`);
  await pool.close();
}

main().catch(error => {
  console.error('Error aplicando migración:', error);
  process.exitCode = 1;
});
