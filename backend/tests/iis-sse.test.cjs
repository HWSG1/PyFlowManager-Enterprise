const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');
const express = require('express');
const ts = require('typescript');

function loadRoute(file, mocks, timers = {}) {
  const filename = path.join(__dirname, '../src/routes', file);
  const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true }
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => mocks[name] || require(name), ...timers }, { filename });
  return exports.default;
}

test('health through HTTP retains the database connectivity check', async () => {
  let statement;
  const router = loadRoute('health.routes.ts', {
    '../db/sql': { getPool: async () => ({ request: () => ({ query: async sql => { statement = sql; } }) }) }
  });
  const app = express(); app.use('/api/health', router);
  const server = app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  try {
    assert.equal(server.address().address, '127.0.0.1');
    const response = await fetch(`http://127.0.0.1:${server.address().port}/api/health`);
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.ok, true); assert.equal(body.database, 'connected');
    assert.equal(statement, 'SELECT 1 AS ok');
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
});

test('SSE flushes immediately, sends heartbeat comments and live logs, and cleans up on disconnect', { timeout: 10000 }, async () => {
  const bus = new EventEmitter();
  let heartbeat, cleared = false, unreferenced = false;
  let resolveCleanup;
  const cleanup = new Promise(resolve => { resolveCleanup = resolve; });
  const timer = { unref() { unreferenced = true; } };
  const pass = (_req, _res, next) => next();
  const router = loadRoute('executions.routes.ts', {
    '../db/sql': {}, '../services/logBus': { logBus: bus },
    '../services/security.service': { requireAuth: pass, requireExecutionAccess: () => pass }
  }, {
    setInterval(fn, delay) { assert.equal(delay, 15000); heartbeat = fn; return timer; },
    clearInterval(value) { assert.equal(value, timer); cleared = true; resolveCleanup(); }
  });
  const app = express(); app.use('/api/executions', router);
  const server = app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  const controller = new AbortController();
  try {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/api/executions/7/stream`, { signal: controller.signal });
    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /text\/event-stream/);
    const reader = response.body.getReader();
    const read = async () => new TextDecoder().decode((await reader.read()).value);
    assert.equal(await read(), ': connected\n\n');
    assert.equal(unreferenced, true);
    heartbeat();
    assert.equal(await read(), ': heartbeat\n\n');
    const payload = { level: 'INFO', message: 'Log en vivo', source: 'stdout' };
    bus.emit('execution:7', payload);
    assert.equal(await read(), `data: ${JSON.stringify(payload)}\n\n`);
    bus.emit('execution:7', { done: true, status: 'Exitoso' });
    assert.match(await read(), /"done":true/);
    controller.abort();
    await new Promise(resolve => setImmediate(resolve));
  } finally {
    controller.abort(); server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    await new Promise(resolve => setImmediate(resolve));
  }
  await cleanup;
  assert.equal(cleared, true);
  assert.equal(bus.listenerCount('execution:7'), 0);
});

test('production entry point explicitly binds to loopback', () => {
  const source = fs.readFileSync(path.join(__dirname, '../src/server.ts'), 'utf8');
  assert.match(source, /app\.listen\(env\.port, '127\.0\.0\.1',/);
});
