import { getPool, sql } from '../db/sql';

const catalogs: Record<string, string> = {
  flows: '/api/v2/flows', users: '/api/v2/users', queues: '/api/v2/routing/queues',
  campaigns: '/api/v2/outbound/campaigns', contactlists: '/api/v2/outbound/contactlists',
  wrapupcodes: '/api/v2/routing/wrapupcodes'
};
export const isGenesysCatalog = (name: string) => Object.prototype.hasOwnProperty.call(catalogs, name);
export const listGenesysFlows = (scriptId: number) => listGenesysCatalog(scriptId, 'flows');
export async function listGenesysCatalog(scriptId: number, catalog: string) {
  if (!isGenesysCatalog(catalog)) throw new Error('Catálogo no válido.');
  const pool = await getPool();
  const result = await pool.request().input('script_id', sql.Int, scriptId).query(`
    SELECT sp.param_key, gv.var_value
    FROM dbo.ScriptParameters sp
    LEFT JOIN dbo.GlobalVariables gv ON gv.var_key = COALESCE(NULLIF(sp.global_key, ''), sp.param_key)
    WHERE sp.script_id = @script_id
      AND sp.param_key IN ('GENESYS_CLIENT_ID', 'GENESYS_CLIENT_SECRET', 'GENESYS_REGION')
  `);
  const values = Object.fromEntries(result.recordset.map(row => [row.param_key, String(row.var_value || '').trim()]));
  if (!values.GENESYS_CLIENT_ID || !values.GENESYS_CLIENT_SECRET || !values.GENESYS_REGION) {
    throw new Error('Configure las variables globales de Genesys para consultar los flujos.');
  }
  const domain = values.GENESYS_REGION.toLowerCase().replace(/^https?:\/\//, '').replace(/^(api|login|apps)\./, '').replace(/\/+$/, '');
  if (!/^(?:mypurecloud\.(?:com|ie|de|jp|com\.au)|(?:[a-z0-9-]+\.)?pure\.cloud|(?:[a-z0-9-]+\.)?genesyscloud\.com)$/.test(domain)) {
    throw new Error('Dominio de Genesys no válido.');
  }
  const tokenResponse = await fetch(`https://login.${domain}/oauth/token`, {
    method: 'POST', redirect: 'error', signal: AbortSignal.timeout(20000),
    headers: { Authorization: `Basic ${Buffer.from(`${values.GENESYS_CLIENT_ID}:${values.GENESYS_CLIENT_SECRET}`).toString('base64')}`, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=client_credentials'
  });
  if (!tokenResponse.ok) throw new Error(`No se pudo autenticar en Genesys (HTTP ${tokenResponse.status}).`);
  const token: any = await tokenResponse.json();
  if (!token.access_token) throw new Error('Genesys no devolvió un token de acceso.');
  const flows = new Map<string, { id: string; name: string; type: string }>();
  for (let page = 1; ; page++) {
    const response = await fetch(`https://api.${domain}${catalogs[catalog]}?pageSize=100&pageNumber=${page}`, {
      redirect: 'error', signal: AbortSignal.timeout(20000), headers: { Authorization: `Bearer ${token.access_token}` }
    });
    if (!response.ok) {
      throw new Error(response.status === 403
        ? (catalog === 'flows' ? 'Genesys denegó la consulta de flujos. Revise el permiso architect:flow:view y las divisiones del cliente OAuth.' : `Genesys denegó la consulta de ${catalog}. Revise los permisos y divisiones del cliente OAuth.`)
        : `No se pudieron consultar los flujos de Genesys (HTTP ${response.status}).`);
    }
    const data: any = await response.json();
    const entities = data.entities || [];
    for (const flow of entities) {
      if (flow.id && flow.name) flows.set(flow.id, { id: flow.id, name: flow.name, type: flow.email || flow.type || '' });
    }
    if (!entities.length || (data.pageCount ? page >= data.pageCount : entities.length < 100)) break;
    if (page >= 1000) throw new Error('El catálogo de flujos excede el límite de consulta.');
  }
  return [...flows.values()];
}
