import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ExcelJS from 'exceljs';
import {buildExcel} from './build_excel.mjs';

test('portable workbook preserves numeric data, cached weighted formulas, empty days and filters',async()=>{
  const dir=await fs.mkdtemp(path.join(path.dirname(fileURLToPath(import.meta.url)),'.qa-'));
  try {
    const output=path.join(dir,'report.xlsx');
    const data={start:'2026-10-01',end:'2026-10-03',timezone:'America/Tegucigalpa',detail:[
      ['2026-10-01','q1','=literal queue',10,8,2,80000,8,800000],
      ['2026-10-02','q1','=literal queue',100,90,10,900000,90,18000000]
    ]};
    await buildExcel(data,output);
    const w=new ExcelJS.Workbook();await w.xlsx.readFile(output);
    assert.deepEqual(w.worksheets.map(s=>s.name),['Resumen','Diario','Detalle']);
    const s=w.getWorksheet('Resumen'), d=w.getWorksheet('Detalle'), daily=w.getWorksheet('Diario');
    assert.equal(s.getCell('B6').result,110);
    assert.equal(s.getCell('B7').result,98);
    assert.equal(s.getCell('B9').result,12/110);
    assert.equal(s.getCell('B10').result,10);
    assert.equal(s.getCell('B11').result,18800000/98/1000);
    assert.equal(d.getCell('C6').value,'=literal queue');
    assert.equal(d.getCell('D6').type,ExcelJS.ValueType.Number);
    assert.ok(d.getCell('A6').value instanceof Date);
    assert.equal(daily.getCell('C8').result,0);
    assert.ok(['',undefined].includes(daily.getCell('F8').result));
    assert.ok(d.getTable('DetalleInbound'));
    assert.ok(daily.getCell('C6').formula.includes('SUMIFS'));
    // Empty activity is valid; invalid raw numbers must stop generation.
    await buildExcel({...data,detail:[]},output);
    await assert.rejects(buildExcel({...data,detail:[['2026-10-01','q','q',-1,0,0,0,0,0]]},output),/invalida/);
  } finally {await fs.rm(dir,{recursive:true,force:true});}
});
