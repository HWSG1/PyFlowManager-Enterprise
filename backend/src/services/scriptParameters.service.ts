import { getPool, sql } from '../db/sql';

export function extractPyflowParams(content: string): Record<string, any> {
  const startIndex = content.indexOf('PYFLOW_PARAMS');
  if (startIndex === -1) return {};

  const equalIndex = content.indexOf('=', startIndex);
  const braceStart = content.indexOf('{', equalIndex);
  if (equalIndex === -1 || braceStart === -1) return {};

  let depth = 0;
  let braceEnd = -1;
  let quote = '';
  let escaped = false;

  for (let i = braceStart; i < content.length; i++) {
    const character = content[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === '\\' && quote) {
      escaped = true;
      continue;
    }
    if ((character === '"' || character === "'") && (!quote || quote === character)) {
      quote = quote ? '' : character;
      continue;
    }
    if (quote) continue;
    if (character === '{') depth++;
    if (character === '}') depth--;
    if (depth === 0) {
      braceEnd = i;
      break;
    }
  }

  if (braceEnd === -1) return {};

  try {
    const jsonLike = content.substring(braceStart, braceEnd + 1)
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
      .replace(/\bNone\b/g, 'null')
      .replace(/'/g, '"')
      .replace(/,\s*([}\]])/g, '$1');
    return JSON.parse(jsonLike);
  } catch (error) {
    console.error('Error parseando PYFLOW_PARAMS:', error);
    throw new Error('PYFLOW_PARAMS no contiene una estructura valida. Revisa comillas, comas y llaves.');
  }
}

export async function syncScriptParameters(scriptId: number, content: string) {
  const parameters = extractPyflowParams(content);
  const pool = await getPool();
  const transaction = new sql.Transaction(pool);
  await transaction.begin();

  try {
    await new sql.Request(transaction)
      .input('script_id', sql.Int, scriptId)
      .query('DELETE FROM dbo.ScriptParameters WHERE script_id = @script_id');

    for (const [key, config] of Object.entries<any>(parameters)) {
      await new sql.Request(transaction)
        .input('script_id', sql.Int, scriptId)
        .input('param_key', sql.NVarChar(150), key)
        .input('param_value', sql.NVarChar(1000), String(config.default ?? ''))
        .input('param_type', sql.NVarChar(30), 'env')
        .input('control_type', sql.NVarChar(30), config.type ?? 'text')
        .input('is_secret', sql.Bit, !!config.secret)
        .input('description', sql.NVarChar(500), config.description || config.label || null)
        .input('label', sql.NVarChar(255), config.label || key)
        .input('options_json', sql.NVarChar(sql.MAX), config.options ? JSON.stringify(config.options) : null)
        .input('is_required', sql.Bit, !!config.required)
        .input('global_key', sql.NVarChar(150), config.global_key || null)
        .query(`
          INSERT INTO dbo.ScriptParameters (
            script_id, param_key, param_value, param_type, control_type,
            is_secret, description, label, options_json, is_required, global_key
          ) VALUES (
            @script_id, @param_key, @param_value, @param_type, @control_type,
            @is_secret, @description, @label, @options_json, @is_required, @global_key
          )
        `);
    }

    await transaction.commit();
    return parameters;
  } catch (error) {
    await transaction.rollback();
    throw error;
  }
}
