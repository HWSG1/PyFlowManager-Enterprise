const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync('../frontend/src/app/components/script-detail/script-detail.component.ts', 'utf8');
const method = source.slice(source.indexOf('  private startIncrementalLogWatch('), source.indexOf('\n  cancelDeleteConfirm()'));
const js = ts.transpile('class Watcher {\n' + method + '\n}\nglobalThis.Watcher = Watcher;', { target: ts.ScriptTarget.ES2020 });
function setup() {
  let tick, pending, cleared = 0;
  const calls = [], scheduled = [];
  const context = { setInterval(fn, ms) { assert.equal(ms, 5000); tick = fn; return 1; }, clearInterval() { cleared++; }, setTimeout(fn) { scheduled.push(fn); } };
  vm.createContext(context); vm.runInContext(js, context);
  const watcher = new context.Watcher();
  Object.assign(watcher, { consoleSessionId: 1, currentExecutionId: 7, consoleLines: [], readProgress: () => null, scrollConsoleToBottom() {}, svc: {
    getExecutionLogs(id, cursor) { calls.push({ id, cursor }); return { subscribe(observer) { pending = observer; } }; },
    loadExecutions() {}, loadScripts() {}
  } });
  watcher.startIncrementalLogWatch(7, 1);
  return { watcher, calls, scheduled, tick: () => tick(), cleared: () => cleared,
    reply(page) { pending.next(page); pending.complete(); }, error() { pending.error(new Error('network')); } };
}
const row = id => ({ id, log_level: 'INFO', message: 'line ' + id });
let t = setup();
t.tick(); assert.equal(t.calls.length, 1, 'slow request must not overlap');
t.reply({ rows: [row('9007199254740993')], nextAfterId: '9007199254740993', hasMore: true, status: 'Exitoso' });
assert.equal(t.cleared(), 0, 'terminal history must drain all pages');
t.scheduled.shift()();
assert.equal(t.calls[1].cursor, '9007199254740993', 'bigint cursor must remain exact');
t.reply({ rows: [row('9007199254740994')], nextAfterId: '9007199254740994', hasMore: false, status: 'Exitoso' });
t.tick(); assert.equal(t.calls.length, 2, 'finished history must stop polling');
assert.equal(t.watcher.consoleLines.length, 2);
t = setup(); t.error(); t.tick(); assert.equal(t.calls.length, 2, 'network errors must allow retry');
t.watcher.consoleSessionId++;
t.reply({ rows: [row('1')], nextAfterId: '1', hasMore: true, status: 'Ejecutando' });
assert.equal(t.watcher.consoleLines.length, 0, 'obsolete response must be ignored');
assert.equal(t.scheduled.length, 0);
console.log('PASS: no overlap, incremental bigint cursor, paginated history, terminal stop, retry, stale response');
