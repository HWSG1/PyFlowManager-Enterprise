// Prueba del selector sin navegador, red ni servicios reales.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../frontend/node_modules/typescript');
const source = fs.readFileSync(require('node:path').join(__dirname,
  '../frontend/src/app/components/genesys-flow-select/genesys-flow-select.component.ts'), 'utf8');
const decorator = () => () => {};
class EventEmitter { emit(value) { this.last = value; } }
const exportsObject = {};
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, experimentalDecorators: true
}}).outputText, { exports: exportsObject, require: name => name === '@angular/core'
  ? { Component: decorator, Input: decorator, Output: decorator, EventEmitter } : {} });
const c = new exportsObject.GenesysFlowSelectComponent({});
c.flows = [{ id: 'a', name: 'Bot A', type: 'bot' }, { id: 'b', name: 'Bot B', type: 'bot' }];
c.value = 'a'; // Un flujo guardado con la versión anterior.
const select = { value: 'b' };
c.choose('b', select);
assert.equal(c.valueChange.last, 'a;b');
assert.equal(select.value, '');
c.value = c.valueChange.last;
c.choose('b', select);
assert.equal(c.valueChange.last, 'a;b');
c.remove('a');
assert.equal(c.valueChange.last, 'b');
c.value = 'b'; c.remove('b');
assert.equal(c.valueChange.last, '');
c.value = 'unknown';
assert.equal(c.selections()[0].name, 'unknown');
c.search = 'Bot B';
assert.equal(c.filteredFlows().length, 1);
for (const catalog of ['queues', 'users', 'campaigns', 'contactlists', 'wrapupcodes']) {
  c.catalog = catalog; c.value = '';
  c.choose('a', select); c.value = c.valueChange.last; c.choose('b', select);
  assert.deepEqual(JSON.parse(c.valueChange.last).map(x => x.id), ['a', 'b']);
  c.value = c.valueChange.last; c.remove('a');
  assert.deepEqual(JSON.parse(c.valueChange.last).map(x => x.id), ['b']);
}
c.catalog = 'options'; c.options = ['todos', 'voice', 'message']; c.value = 'todos'; c.load();
assert.equal(c.selections().length, 0);
c.choose('voice', select); c.value = c.valueChange.last; c.choose('message', select);
assert.equal(c.valueChange.last, 'voice;message');
console.log('Selección múltiple: flujos, cinco catálogos y opciones verificados.');
