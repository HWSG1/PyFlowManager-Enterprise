import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Public production dependency: no Codex runtime or absolute local paths.
let ExcelJS;
try { ExcelJS = (await import('exceljs')).default; }
catch (error) {
  if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
  console.error('Falta ExcelJS. Desde la raiz del proyecto ejecutar: npm ci --prefix "runtime/scripts/GNS_Reporte_Inbound_Diario/config" --omit=dev');
  process.exit(1);
}
const ratio = (sum, count, divisor = 1) => count ? sum / count / divisor : '';
const formula = (text, result) => ({ formula: text, result });
const font = { name: 'Neo Sans Std', size: 11, color: { argb: 'FF253245' } };
const fill = color => ({type:'pattern', pattern:'solid', fgColor:{argb:color}});

export async function buildExcel(data, output) {
  const start = new Date(data.start + 'T00:00:00Z'), finish = new Date(data.end + 'T00:00:00Z');
  if (!Number.isFinite(+start) || !Number.isFinite(+finish) || finish < start || (finish-start)/86400000>366 || !Array.isArray(data.detail)) throw new Error('Periodo o detalle invalido.');
  const totals = Array(6).fill(0), byDay = new Map();
  for (const row of data.detail) {
    if (!Array.isArray(row) || row.length !== 9 || !/^\d{4}-\d{2}-\d{2}$/.test(row[0]) || row[0]<data.start || row[0]>data.end || typeof row[1]!=='string' || typeof row[2]!=='string' || row.slice(3).some(v=>typeof v!=='number' || !Number.isFinite(v) || v<0)) throw new Error('Fila de detalle invalida; no se generara un reporte parcial.');
    if (!byDay.has(row[0])) byDay.set(row[0], Array(6).fill(0));
    row.slice(3).forEach((v,i)=>{totals[i]+=v;byDay.get(row[0])[i]+=v;});
  }
  const wb = new ExcelJS.Workbook();
  wb.creator = 'PyFlow Manager';
  // Cache results from raw statistics; Excel recalculates when the file opens.
  wb.calcProperties.fullCalcOnLoad = true;
  const period = `${data.start} al ${data.end} | ${data.timezone} | Voz inbound`;
  function setup(name,title,columns) {
    const s=wb.addWorksheet(name,{views:[{showGridLines:false,state:'frozen',ySplit:5}]});
    for(let i=1;i<=columns;i++)s.getColumn(i).width=20;
    s.mergeCells(1,1,2,columns);s.getCell('A1').value=title;s.getCell('A1').fill=fill('FFBF001B');
    s.getCell('A1').font={...font,size:20,bold:true,color:{argb:'FFFFFFFF'}};s.getCell('A1').alignment={vertical:'middle'};
    s.getRow(1).height=24;s.getRow(2).height=24;
    s.mergeCells(3,1,3,columns);s.getCell('A3').value=period;s.getRow(3).height=25;
    return s;
  }
  const summary=setup('Resumen','Llamadas inbound · Resumen',7);
  const daily=setup('Diario','Evolución diaria',9);
  const detail=setup('Detalle','Detalle por fecha y cola',12);
  const last=Math.max(6,data.detail.length+5);
  const detailRows=data.detail.map((row,i)=>{
    const r=i+6;
    return [new Date(row[0]+'T00:00:00Z'),...row.slice(1),
      formula(`IF(D${r}=0,"",F${r}/D${r})`,ratio(row[5],row[3])),
      formula(`IF(E${r}=0,"",G${r}/E${r}/1000)`,ratio(row[6],row[4],1000)),
      formula(`IF(H${r}=0,"",I${r}/H${r}/1000)`,ratio(row[8],row[7],1000))];
  });
  function table(s,name,headers,rows) {
    s.addTable({name,ref:'A5',headerRow:true,style:{theme:'TableStyleMedium2',showRowStripes:true},columns:headers.map(name=>({name,filterButton:true})),rows:rows.length?rows:[Array(headers.length).fill(null)]});
  }
  table(detail,'DetalleInbound',['Fecha','ID de cola','Cola','Ofrecidas','Atendidas','Abandonadas','Espera total (ms)','Gestiones','Gestión total (ms)','Abandono %','Espera media (s)','Gestión media (s)'],detailRows);
  detail.getColumn(1).numFmt='yyyy-mm-dd';detail.getColumn(2).width=39;detail.getColumn(3).width=46;
  for(let i=4;i<=9;i++)detail.getColumn(i).numFmt='#,##0';
  detail.getColumn(10).numFmt='0.00%';detail.getColumn(11).numFmt='0.00';detail.getColumn(12).numFmt='0.00';
  const dayRows=[], weekdays=['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
  for(let day=new Date(start);day<=finish;day.setUTCDate(day.getUTCDate()+1)) {
    const r=dayRows.length+6, t=byDay.get(day.toISOString().slice(0,10)) || Array(6).fill(0);
    const sum=col=>`SUMIFS(Detalle!$${col}$6:$${col}$${last},Detalle!$A$6:$A$${last},A${r})`;
    dayRows.push([new Date(day),weekdays[day.getUTCDay()],formula(sum('D'),t[0]),formula(sum('E'),t[1]),formula(sum('F'),t[2]),
      formula(`IF(C${r}=0,"",E${r}/C${r})`,ratio(t[2],t[0])),formula(`IF(D${r}=0,"",${sum('G')}/D${r}/1000)`,ratio(t[3],t[1],1000)),
      formula(`IF(I${r}=0,"",${sum('I')}/I${r}/1000)`,ratio(t[5],t[4],1000)),formula(sum('H'),t[4])]);
  }
  table(daily,'DiarioInbound',['Fecha','Día','Ofrecidas','Atendidas','Abandonadas','Abandono %','Espera media (s)','Gestión media (s)','Gestiones'],dayRows);
  daily.getColumn(1).numFmt='yyyy-mm-dd';
  for(const i of [3,4,5,9])daily.getColumn(i).numFmt='#,##0';
  daily.getColumn(6).numFmt='0.00%';daily.getColumn(7).numFmt='0.00';daily.getColumn(8).numFmt='0.00';
  summary.getRow(5).values=['Indicador','Resultado'];
  const indicators=[
    ['Ofrecidas',`SUM(Detalle!D6:D${last})`,totals[0]],['Atendidas',`SUM(Detalle!E6:E${last})`,totals[1]],
    ['Abandonadas',`SUM(Detalle!F6:F${last})`,totals[2]],['Abandono %','IF(B6=0,"",B8/B6)',ratio(totals[2],totals[0])],
    ['Espera media (s)',`IF(B7=0,"",SUM(Detalle!G6:G${last})/B7/1000)`,ratio(totals[3],totals[1],1000)],
    ['Gestión media (s)',`IF(SUM(Detalle!H6:H${last})=0,"",SUM(Detalle!I6:I${last})/SUM(Detalle!H6:H${last})/1000)`,ratio(totals[5],totals[4],1000)]
  ];
  indicators.forEach(([name,f,value],i)=>{summary.getCell(i+6,1).value=name;summary.getCell(i+6,2).value=formula(f,value);summary.getCell(i+6,2).numFmt=i<3?'#,##0':i===3?'0.00%':'0.00';});
  summary.getColumn(1).width=29;
  const notes=['Alcance y definiciones','Fuente: Genesys Cloud · analytics/conversations/aggregates/query.',
    'Solo voz inbound; colas seleccionadas y accesibles al cliente OAuth.',
    'Detalle: una fila por fecha y cola con actividad. Diario incluye días sin actividad.',
    'Eventos de cola, no conversaciones únicas: las transferencias pueden contarse en varias colas.',
    'Ofrecidas no tiene que igualar atendidas más abandonadas; atribución al intervalo del evento.',
    'Abandono = abandonadas / ofrecidas. Sin denominador, la celda queda vacía.',
    'Espera = suma tAnswered / count tAnswered / 1000. Gestión = suma tHandle / count tHandle / 1000.',
    'Los promedios se ponderan por cantidad; Detalle conserva sumas en milisegundos y conteos.',
    'Definiciones: https://help.genesys.cloud/articles/view-available-columns-in-performance-views-by-category/'];
  notes.forEach((text,i)=>{const r=i+14;summary.mergeCells(r,1,r,7);summary.getCell(r,1).value=text;summary.getCell(r,1).alignment={wrapText:true,vertical:'middle'};summary.getRow(r).height=32;});
  for(const s of [summary,daily,detail]) {
    s.eachRow((row,r)=>{row.eachCell(cell=>{if(r>2)cell.font={...font};});if(r>=6 && s!==summary)row.height=20;});
    s.getRow(5).eachCell(cell=>{cell.fill=fill('FF253245');cell.font={...font,bold:true,color:{argb:'FFFFFFFF'}};cell.alignment={wrapText:true,vertical:'middle'};});s.getRow(5).height=36;
  }
  for(let i=0;i<3;i++)if(dayRows.reduce((n,row)=>n+row[i+2].result,0)!==totals[i])throw new Error('Los totales diarios no concilian.');
  await fs.mkdir(path.dirname(output),{recursive:true});
  const temp=output+`.${process.pid}.tmp`;
  try {await wb.xlsx.writeFile(temp);await fs.rename(temp,output);}
  finally {await fs.rm(temp,{force:true});}
  console.log('Excel generado y totales verificados:',output);
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const [input,output]=process.argv.slice(2);
  try {
    if(!input||!output)throw new Error('Uso: node config/build_excel.mjs datos.json reporte.xlsx');
    await buildExcel(JSON.parse(await fs.readFile(input,'utf8')),output);
  } catch(error) {console.error('No se pudo generar el Excel:',error.message);process.exitCode=1;}
}
