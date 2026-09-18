const { test } = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
require('ts-node/register');

let domain = 'mypurecloud.com';
const originalLoad = Module._load;
Module._load = function (name, ...args) {
  if (name === '../db/sql') return {
    sql: { Int: 'int' },
    getPool: async () => ({ request: () => ({
      input() { return this; },
      async query() { return { recordset: [
        { param_key: 'GENESYS_CLIENT_ID', var_value: 'test-client' },
        { param_key: 'GENESYS_CLIENT_SECRET', var_value: 'test-secret' },
        { param_key: 'GENESYS_REGION', var_value: domain }
      ] }; }
    }) })
  };
  return originalLoad.call(this, name, ...args);
};
const { listGenesysFlows, listGenesysCatalog } = require('../src/services/genesysFlows.service');
Module._load = originalLoad;

test('catalog pagination retains duplicate names with distinct IDs and returns no credentials', async () => {
  const urls = [];
  const originalFetch = global.fetch;
  global.fetch = async url => {
    urls.push(url);
    const data = urls.length === 1 ? { access_token: 'test-token' }
      : { pageCount: 2, entities: [{ id: `flow-${urls.length}`, name: 'Mismo nombre', type: 'inboundcall', secret: 'must-not-return' }] };
    return { ok: true, json: async () => data };
  };
  try {
    const flows = await listGenesysFlows(1);
    assert.equal(flows.length, 2);
    assert.notEqual(flows[0].id, flows[1].id);
    assert.match(urls[2], /pageNumber=2/);
    assert.deepEqual(Object.keys(flows[0]), ['id', 'name', 'type']);
  } finally { global.fetch = originalFetch; }
});

test('permission failure is actionable and does not leak the remote response', async () => {
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => ++calls === 1
    ? { ok: true, json: async () => ({ access_token: 'test-token' }) }
    : { ok: false, status: 403 };
  try { await assert.rejects(listGenesysFlows(1), /architect:flow:view/); }
  finally { global.fetch = originalFetch; }
});

test('rejects foreign domains before sending credentials', async () => {
  domain = 'example.com';
  try { await assert.rejects(listGenesysFlows(1), /Dominio de Genesys no válido/); }
  finally { domain = 'mypurecloud.com'; }
});

 test('all selectable catalogs use their fixed endpoint and preserve IDs', async () => {
  const originalFetch = global.fetch;
  try {
    for (const [catalog, endpoint] of Object.entries({ users: '/users', queues: '/routing/queues', campaigns: '/outbound/campaigns', contactlists: '/outbound/contactlists', wrapupcodes: '/routing/wrapupcodes' })) {
      const urls = [];
      global.fetch = async url => {
        urls.push(url);
        return { ok: true, json: async () => urls.length === 1 ? { access_token: 'test' } : { pageCount: 1, entities: [{ id: 'id', name: 'Name', email: 'user@example.com' }] } };
      };
      const options = await listGenesysCatalog(1, catalog);
      assert.ok(urls[1].includes('/api/v2' + endpoint + '?'));
      assert.equal(options[0].id, 'id');
      assert.equal(options[0].type, 'user@example.com');
    }
    await assert.rejects(listGenesysCatalog(1, 'constructor'), /Catálogo no válido/);
  } finally { global.fetch = originalFetch; }
});
