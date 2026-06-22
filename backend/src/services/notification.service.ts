import { getPool, sql } from '../db/sql';

interface ExecutionAlert {
  executionId: number;
  scriptName: string;
  status: 'Exitoso' | 'Error';
  startedAt?: Date | string | null;
  endedAt?: Date | string | null;
  durationSeconds?: number | null;
  errorMessage?: string | null;
  retryAttempt?: number;
  recipients: string;
}

function splitRecipients(value: string): string[] {
  return String(value || '')
    .replace(/[\r\n,]+/g, ';')
    .split(';')
    .map(item => item.trim())
    .filter((item, index, values) => !!item && values.indexOf(item) === index);
}

async function graphConfig(): Promise<Record<string, string>> {
  const keys = ['GRAPH_TENANT_ID', 'GRAPH_CLIENT_ID', 'GRAPH_CLIENT_SECRET', 'GRAPH_SENDER_EMAIL'];
  const pool = await getPool();
  const request = pool.request();
  keys.forEach((key, index) => request.input(`key${index}`, sql.NVarChar(150), key));
  const result = await request.query(`
    SELECT var_key, var_value FROM dbo.GlobalVariables
    WHERE var_key IN (${keys.map((_, index) => `@key${index}`).join(', ')})
  `);
  return Object.fromEntries(result.recordset.map((row: any) => [row.var_key, String(row.var_value || '')]));
}

export async function sendExecutionAlert(alert: ExecutionAlert): Promise<boolean> {
  const recipients = splitRecipients(alert.recipients);
  if (!recipients.length) return false;

  try {
    const config = await graphConfig();
    const tenantId = config.GRAPH_TENANT_ID;
    const clientId = config.GRAPH_CLIENT_ID;
    const clientSecret = config.GRAPH_CLIENT_SECRET;
    const sender = config.GRAPH_SENDER_EMAIL;
    if (!tenantId || !clientId || !clientSecret || !sender) {
      console.warn('[ALERT] Faltan variables globales de Microsoft Graph.');
      return false;
    }

    const tokenResponse = await fetch(`https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: clientId,
        client_secret: clientSecret,
        scope: 'https://graph.microsoft.com/.default',
        grant_type: 'client_credentials'
      })
    });
    if (!tokenResponse.ok) throw new Error(`Token Graph HTTP ${tokenResponse.status}`);
    const token = (await tokenResponse.json() as any).access_token;

    const color = alert.status === 'Exitoso' ? '#059669' : '#dc2626';
    const html = `
      <div style="font-family:Segoe UI,Arial,sans-serif;color:#1f2937;max-width:640px">
        <div style="background:${color};color:white;padding:24px 28px">
          <div style="font-size:12px;font-weight:700;text-transform:uppercase">PyFlow Manager</div>
          <h2 style="margin:8px 0 0">Ejecución ${alert.status}</h2>
        </div>
        <div style="padding:26px;border:1px solid #e5e7eb">
          <p><strong>Script:</strong> ${alert.scriptName}</p>
          <p><strong>Ejecución:</strong> EX-${alert.executionId}</p>
          <p><strong>Duración:</strong> ${alert.durationSeconds ?? 0} segundos</p>
          <p><strong>Intento:</strong> ${(alert.retryAttempt || 0) + 1}</p>
          ${alert.errorMessage ? `<p><strong>Error:</strong> ${String(alert.errorMessage).replace(/[<>]/g, '')}</p>` : ''}
        </div>
      </div>`;

    const response = await fetch(`https://graph.microsoft.com/v1.0/users/${encodeURIComponent(sender)}/sendMail`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: {
          subject: `[PyFlow] ${alert.status}: ${alert.scriptName} (EX-${alert.executionId})`,
          body: { contentType: 'HTML', content: html },
          toRecipients: recipients.map(address => ({ emailAddress: { address } }))
        },
        saveToSentItems: true
      })
    });
    if (!response.ok) throw new Error(`sendMail Graph HTTP ${response.status}`);
    return true;
  } catch (error) {
    console.error('[ALERT] No se pudo enviar la notificación:', error);
    return false;
  }
}
