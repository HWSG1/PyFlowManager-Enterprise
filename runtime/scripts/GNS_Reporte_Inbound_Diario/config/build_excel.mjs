import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [input, output] = process.argv.slice(2);
const data = JSON.parse(await fs.readFile(input, 'utf8'));
const wb = Workbook.create();
const summary = wb.worksheets.add('Resumen');
const daily = wb.worksheets.add('Diario');
const detail = wb.worksheets.add('Detalle');
const literal = value => typeof value === 'string' && value.startsWith('=') ? "'" + value : value;
function setup(sheet, title, subtitle, columns) {
  sheet.showGridLines = false;
  const area = sheet.getRange(`A1:${columns}5`);
  area.format.font = {name:'Neo Sans Std',size:11,color:'#253245'};
  sheet.getRange(`A1:${columns}2`).merge();
  sheet.getRange('A1').values = [[title]];
  sheet.getRange(`A1:${columns}2`).format.fill = '#BF001B';
  sheet.getRange(`A1:${columns}2`).format.font = {name:'Neo Sans Std',size:20,bold:true,color:'#FFFFFF'};
  sheet.getRange(`A3:${columns}3`).merge();
  sheet.getRange('A3').values = [[subtitle]];
  sheet.getRange(`A1:${columns}3`).format.rowHeight = 24;
  sheet.getRange(`A:${columns}`).format.columnWidth = 19;
  sheet.freezePanes.freezeRows(5);
}
const period = `${data.start} al ${data.end} | ${data.timezone} | Voz inbound`;
setup(summary, 'Llamadas inbound · Resumen', period, 'G');
setup(daily, 'Evolución diaria', period, 'I');
setup(detail, 'Detalle por fecha y cola', period, 'L');
const headers = ['Fecha','ID de cola','Cola','Ofrecidas','Atendidas','Abandonadas','Espera total (ms)','Gestiones','Gestión total (ms)','Abandono %','Espera media (s)','Gestión media (s)'];
detail.getRange('A5:L5').values = [headers];
const end = Math.max(6, data.detail.length + 5);
if (data.detail.length) {
  detail.getRange(`A6:I${end}`).values = data.detail.map(row => [new Date(row[0]+'T00:00:00Z'), ...row.slice(1).map(literal)]);
  detail.getRange(`J6:L${end}`).formulas = data.detail.map((_,i) => {
    const r=i+6;
    return [`=IF(D${r}=0,"",F${r}/D${r})`,`=IF(E${r}=0,"",G${r}/E${r}/1000)`,`=IF(H${r}=0,"",I${r}/H${r}/1000)`];
  });
}
detail.getRange(`A6:A${end}`).setNumberFormat('yyyy-mm-dd');
detail.getRange(`D6:I${end}`).setNumberFormat('#,##0');
detail.getRange(`J6:J${end}`).setNumberFormat('0.00%');
detail.getRange(`K6:L${end}`).setNumberFormat('0.00');
detail.getRange('B:B').format.columnWidth = 39;
detail.getRange('C:C').format.columnWidth = 46;
detail.tables.add(`A5:L${end}`,true,'DetalleInbound');

const days=[];
for(let d=new Date(data.start+'T00:00:00Z'); d<=new Date(data.end+'T00:00:00Z'); d.setUTCDate(d.getUTCDate()+1)) days.push(new Date(d));
daily.getRange('A5:I5').values = [['Fecha','Día','Ofrecidas','Atendidas','Abandonadas','Abandono %','Espera media (s)','Gestión media (s)','Gestiones']];
const weekdays=['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
daily.getRange(`A6:B${days.length+5}`).values=days.map(d=>[d,weekdays[d.getUTCDay()]]);
daily.getRange(`C6:I${days.length+5}`).formulas=days.map((_,i)=>{
  const r=i+6;
  const sum=col=>`SUMIFS(Detalle!$${col}$6:$${col}$${end},Detalle!$A$6:$A$${end},A${r})`;
  return [`=${sum('D')}`,`=${sum('E')}`,`=${sum('F')}`,`=IF(C${r}=0,"",E${r}/C${r})`,`=IF(D${r}=0,"",${sum('G')}/D${r}/1000)`,`=IF(I${r}=0,"",${sum('I')}/I${r}/1000)`,`=${sum('H')}`];
});
daily.getRange(`A6:A${days.length+5}`).setNumberFormat('yyyy-mm-dd');
daily.getRange(`C6:E${days.length+5}`).setNumberFormat('#,##0');
daily.getRange(`F6:F${days.length+5}`).setNumberFormat('0.00%');
daily.getRange(`G6:H${days.length+5}`).setNumberFormat('0.00');
daily.tables.add(`A5:I${days.length+5}`,true,'DiarioInbound');
summary.getRange('A5:B5').values=[['Indicador','Resultado']];
summary.getRange('A6:A11').values=[['Ofrecidas'],['Atendidas'],['Abandonadas'],['Abandono %'],['Espera media (s)'],['Gestión media (s)']];
summary.getRange('B6:B11').formulas=[
  [`=SUM(Detalle!D6:D${end})`],[`=SUM(Detalle!E6:E${end})`],[`=SUM(Detalle!F6:F${end})`],
  ['=IF(B6=0,"",B8/B6)'],[`=IF(B7=0,"",SUM(Detalle!G6:G${end})/B7/1000)`],
  [`=IF(SUM(Detalle!H6:H${end})=0,"",SUM(Detalle!I6:I${end})/SUM(Detalle!H6:H${end})/1000)`]
];
summary.getRange('A:A').format.columnWidth=29;
summary.getRange('B6:B8').setNumberFormat('#,##0');
summary.getRange('B9').setNumberFormat('0.00%');
summary.getRange('B10:B11').setNumberFormat('0.00');
summary.getRange('A14:G14').merge(); summary.getRange('A14').values=[['Alcance y definiciones']];
const notes=[
  'Fuente: Genesys Cloud · analytics/conversations/aggregates/query.',
  'Solo voz inbound; colas seleccionadas y accesibles al cliente OAuth.',
  'Detalle: una fila por fecha y cola con actividad. Diario incluye días sin actividad.',
  'Eventos de cola, no conversaciones únicas: las transferencias pueden contarse en varias colas.',
  'Ofrecidas no tiene que igualar atendidas más abandonadas; atribución al intervalo del evento.',
  'Abandono = abandonadas / ofrecidas. Sin denominador, la celda queda vacía.',
  'Espera = suma tAnswered / count tAnswered / 1000. Gestión = suma tHandle / count tHandle / 1000.',
  'Los promedios se ponderan por cantidad; Detalle conserva sumas en milisegundos y conteos.',
  'Definiciones: https://help.genesys.cloud/articles/view-available-columns-in-performance-views-by-category/'
];
notes.forEach((note,i)=>{const r=i+15;summary.getRange(`A${r}:G${r}`).merge(); summary.getRange(`A${r}`).values=[[note]]; summary.getRange(`A${r}:G${r}`).format.wrapText=true;summary.getRange(`A${r}:G${r}`).format.rowHeight=32;});
for(const sheet of [summary,daily,detail]) {
  const range=sheet.getUsedRange(); range.format.font.name='Neo Sans Std';
  const last=sheet===detail?'L':sheet===daily?'I':'B';
  sheet.getRange(`A5:${last}5`).format.fill='#253245';
  sheet.getRange(`A5:${last}5`).format.font={name:'Neo Sans Std',bold:true,color:'#FFFFFF',size:11};
  sheet.getRange(`A5:${last}5`).format.rowHeight=36;
  sheet.getRange(`A5:${last}5`).format.wrapText=true;
}
wb.recalculate();
const totals=summary.getRange('B6:B8').values.flat();
const expected=[3,4,5].map(index=>data.detail.reduce((sum,row)=>sum+row[index],0));
if(totals.some((value,i)=>value!==expected[i])) throw new Error('Totales Excel no coinciden con el detalle');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#N/A',options:{useRegex:true,maxResults:10},summary:'Validación de fórmulas'});
if(/"(value|text)":"#/.test(errors.ndjson||'')) throw new Error(errors.ndjson);
const file=await SpreadsheetFile.exportXlsx(wb); await file.save(output);
if(process.env.REPORT_RENDER_QA==='true') {
  for(const name of ['Resumen','Diario','Detalle']) {
    const image=await wb.render({sheetName:name,range:name==='Resumen'?'A1:G23':name==='Diario'?'A1:I12':'A1:L10',scale:1,format:'png'});
    await fs.writeFile(output+`.${name}.png`,new Uint8Array(await image.arrayBuffer()));
  }
}
console.log('Excel generado y totales verificados:',output);
