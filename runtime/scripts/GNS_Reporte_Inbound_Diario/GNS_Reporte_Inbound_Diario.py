"""Reporte mensual por dia de voz inbound. Solo lectura Genesys; envio optativo."""
import base64
import csv
import json
import os
import re
import time
import shutil
import subprocess
import io
import math
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Dominio Genesys", "required": True},
    "GRAPH_TENANT_ID": {"type": "global", "global_key": "GRAPH_TENANT_ID", "label": "Graph Tenant ID", "required": False},
    "GRAPH_CLIENT_ID": {"type": "global", "global_key": "GRAPH_CLIENT_ID", "label": "Graph Client ID", "required": False},
    "GRAPH_CLIENT_SECRET": {"type": "global", "global_key": "GRAPH_CLIENT_SECRET", "label": "Graph Client Secret", "required": False, "secret": True},
    "GRAPH_SENDER_EMAIL": {"type": "global", "global_key": "GRAPH_SENDER_EMAIL", "label": "Remitente Graph", "required": False},
    "REPORT_EMAIL_TO": {"type": "tags", "label": "Correos destinatarios (escribir manualmente)", "required": False},
    "REPORT_EMAIL_CC": {"type": "tags", "label": "Correos en copia", "required": False},
    "SEND_EMAIL": {"type": "select", "label": "Enviar correo", "options": ["false", "true"], "default": "false", "required": True},
    "REPORT_END_DATE": {"type": "date", "label": "Ultimo dia incluido (vacio = ayer)", "required": False},
    "REPORT_QUEUE_IDS": {"type": "genesys_queues", "label": "Colas inbound (vacio = todas las accesibles)", "required": False},
    "GENESYS_TIMEZONE": {"type": "text", "label": "Zona horaria", "default": "America/Tegucigalpa", "required": True}
}

METRICS = ["nOffered", "tAnswered", "tAbandon", "tHandle"]
FONT = "'Neo Sans Std',Arial,sans-serif"
LOGO = Path(__file__).parent / "input" / "logo-04.png"


def required(key):
    value = os.getenv(key, "").strip()
    if not value:
        raise ValueError(f"Falta configurar {key}")
    return value


def split_values(value):
    return list(dict.fromkeys(x.strip() for x in re.split(r"[;,\n]", value) if x.strip()))


def selected_queue_ids(value):
    value = value.strip()
    if not value.startswith("["):
        return split_values(value)
    try:
        items = json.loads(value)
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("id"), str)
            or not item["id"].strip() or item["id"].startswith("legacy:") for item in items
        ):
            raise ValueError()
        return list(dict.fromkeys(item["id"].strip() for item in items))
    except (ValueError, TypeError):
        raise ValueError("Seleccion de colas invalida; vuelve a elegirlas del listado.") from None


def request_json(url, payload=None, headers=None, form=False, retries=4):
    data = None if payload is None else (urlencode(payload) if form else json.dumps(payload)).encode()
    headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    for attempt in range(retries + 1):
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=90) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except HTTPError as exc:
            if exc.code not in (429, 502, 503, 504) or attempt == retries:
                # Do not print response bodies, credentials or bearer tokens.
                raise RuntimeError(f"Servicio remoto devolvio HTTP {exc.code}") from None
            delay = exc.headers.get("Retry-After", "")
            time.sleep(min(120, float(delay) if delay.isdigit() else 2 ** (attempt + 1)))


def period(today, end_text=""):
    end = date.fromisoformat(end_text) if end_text else today - timedelta(days=1)
    if end >= today:
        raise ValueError("Seleccionar un dia cerrado anterior a hoy.")
    return end.replace(day=1), end


def query_body(day, tz, queue_ids):
    start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    filters = {"type": "and", "predicates": [
        {"dimension": "mediaType", "value": "voice"},
        {"dimension": "direction", "value": "inbound"},
        {"dimension": "queueId", "operator": "exists"}
    ]}
    if queue_ids:
        filters["clauses"] = [{"type": "or", "predicates": [
            {"dimension": "queueId", "value": q} for q in queue_ids
        ]}]
    return {"interval": f"{start.isoformat()}/{end.isoformat()}", "timeZone": str(tz),
            "groupBy": ["queueId"], "granularity": "P1D", "filter": filters, "metrics": METRICS}


def empty_stats():
    return {m: {"count": 0, "sum": 0} for m in METRICS}


def add_stats(target, source):
    for metric in METRICS:
        for stat in ("count", "sum"):
            target[metric][stat] += source[metric][stat]


def parse_stats(result):
    stats = empty_stats()
    for bucket in result.get("data", []):
        for metric in bucket.get("metrics", []):
            name = metric["metric"]
            if name in stats:
                for key in ("count", "sum"):
                    stats[name][key] += metric.get("stats", {}).get(key, 0) or 0
    return stats


def row_values(label, stats):
    offered = stats["nOffered"]["count"]
    answered = stats["tAnswered"]["count"]
    abandoned = stats["tAbandon"]["count"]
    handled = stats["tHandle"]["count"]
    return [label, offered, answered, abandoned,
            round(100 * abandoned / offered, 2) if offered else "",
            round(stats["tAnswered"]["sum"] / answered / 1000, 2) if answered else "",
            round(stats["tHandle"]["sum"] / handled / 1000, 2) if handled else ""]


def html_table(rows, first_label):
    heads = [first_label, "Ofrecidas", "Atendidas", "Abandonadas", "% abandono", "Espera", "Gestión"]
    header = "".join(f'<th align="{ "left" if i == 0 else "right"}" style="padding:10px 7px;background:#edf0f4;color:#485465;font-size:11px">{escape(h)}</th>' for i,h in enumerate(heads))
    lines = []
    for index, row in enumerate(rows):
        cells = []
        for i, value in enumerate(row):
            text = "—" if value == "" else escape(str(value))
            if value != "" and i > 0:
                text = f"{value:,.0f}" if i <= 3 else f"{value:.2f}%" if i == 4 else duration(value)
            color = "#bf001b" if i in (3, 4) else "#253245"
            cells.append(f'<td align="{"left" if i == 0 else "right"}" style="padding:10px 7px;border-bottom:1px solid #e5e9ef;color:{color};font-size:12px">{text}</td>')
        bg = "#fff5f5" if str(row[0]).endswith(" *") else "#ffffff" if index % 2 == 0 else "#f8fafc"
        lines.append(f'<tr style="background:{bg}">' + "".join(cells) + '</tr>')
    return f'<table cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse;font-family:{FONT}"><tr>{header}</tr>{"".join(lines)}</table>'


def duration(seconds):
    seconds = round(seconds)
    return f"{seconds // 60:02d}m {seconds % 60:02d}s"


def daily_chart(daily):
    """PNG compatible con correo: volumen y tasa de abandono, no clientes únicos."""
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1520, 660), "white")
    draw = ImageDraw.Draw(image)
    fonts = Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts"
    def font(size):
        for name in ("NeoSansStd-Regular.otf", "NeoSansStd-Regular.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(str(fonts / name), size)
            except OSError:
                pass
        return ImageFont.load_default(size=size)
    normal, small = font(23), font(20)
    left, top, right, bottom = 110, 115, 1385, 535
    max_volume = max((row[1] for row in daily), default=0)
    step = max(1, 10 ** max(0, int(math.log10(max_volume or 1)) - 1))
    ymax = max(5, math.ceil(max_volume * 1.15 / step) * step)
    rates = [row[4] for row in daily if row[4] != ""]
    pmax = max(10, math.ceil(max(rates, default=0) / 10) * 10)
    draw.rectangle((110, 25, 141, 47), fill="#253245")
    draw.text((154, 22), "Ofrecidas · volumen", fill="#253245", font=normal)
    draw.line((510, 36, 555, 36), fill="#bf001b", width=5)
    draw.text((568, 22), "Abandono · porcentaje", fill="#bf001b", font=normal)
    draw.text((left, 75), "Llamadas", fill="#536174", font=small)
    draw.text((right, 75), "% abandono", fill="#bf001b", font=small, anchor="ra")
    for i in range(6):
        y = bottom - (bottom-top)*i/5
        draw.line((left,y,right,y), fill="#e2e7ee", width=2)
        draw.text((left-16,y), f"{ymax*i/5:,.0f}", font=small, fill="#536174", anchor="rm")
        draw.text((right+16,y), f"{pmax*i/5:.0f}%", font=small, fill="#bf001b", anchor="lm")
    slot = (right-left)/max(1,len(daily))
    previous = None
    labels = []
    for i,row in enumerate(daily):
        x = left + slot*(i+.5)
        height = (bottom-top)*row[1]/ymax
        draw.rectangle((x-slot*.32,bottom-height,x+slot*.32,bottom), fill="#253245")
        labels.append((x,bottom-height,f"{row[1]:,}","#253245",False))
        draw.text((x,bottom+18), str(row[0])[8:10], font=small, fill="#536174", anchor="mt")
        if row[4] == "":
            previous = None
            continue
        point=(x,bottom-(bottom-top)*row[4]/pmax)
        if previous:
            draw.line((*previous,*point), fill="#bf001b", width=5)
        draw.ellipse((point[0]-5,point[1]-5,point[0]+5,point[1]+5),fill="#bf001b")
        previous=point
        labels.append((point[0],point[1],f"{row[4]:.1f}%","#bf001b",True))
    # Place labels after both series; reserve each box to avoid overlapping text.
    occupied = []
    label_font = font(19)
    for x,y,text,color,is_rate in sorted(labels,key=lambda item:item[4]):
        width = draw.textbbox((0,0),text,font=label_font)[2] + 8
        height = 27
        for offset in (-25,25,-55,55,-85,85,-115,115,-145,145):
            cy = min(bottom-height/2,max(top+height/2,y+offset))
            box = (x-width/2,cy-height/2,x+width/2,cy+height/2)
            if not any(box[0]<b[2]+3 and box[2]>b[0]-3 and box[1]<b[3]+3 and box[3]>b[1]-3 for b in occupied):
                break
        occupied.append(box)
        if abs(cy-y)>35:
            draw.line((x,y,x,cy),fill=color,width=1)
        draw.rounded_rectangle(box,radius=5,fill="#fff4f5" if is_rate else "white")
        draw.text((x,cy),text,font=label_font,fill=color,anchor="mm")
    draw.text((left,610), "Día del mes · Abandono = abandonadas / ofrecidas. Sin ofrecidas, la línea se interrumpe.", font=small, fill="#657183")
    buffer=io.BytesIO()
    image.save(buffer,format="PNG")
    return buffer.getvalue()


def render_report(start, end, tz, daily, queues, total, logo_src=None, chart_src=None):
    logo_src = logo_src or "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    chart_src = chart_src or "data:image/png;base64," + base64.b64encode(daily_chart(daily)).decode()
    values = row_values("Total", total)
    cards = [("OFRECIDAS", f"{values[1]:,}", f"Promedio {values[1] / len(daily):,.0f} / día"),
             ("ATENDIDAS", f"{values[2]:,}", "Voz inbound"),
             ("ABANDONADAS", f"{values[3]:,}", f"{values[4]:.2f}% de abandono" if values[4] != "" else "Sin ofrecidas"),
             ("GESTIÓN MEDIA", duration(values[6]) if values[6] != "" else "—", "Espera: " + (duration(values[5]) if values[5] != "" else "—"))]
    cards_html = ''.join(f'<td width="25%" valign="top" style="padding:14px 10px;background:#f7f8fa;border:3px solid #fff;border-radius:8px"><div style="font-size:10px;color:#657183;font-weight:bold">{label}</div><div style="font-size:24px;font-weight:bold;color:{"#bf001b" if i == 2 else "#253245"};padding:7px 0">{value}</div><div style="font-size:11px;color:#657183">{note}</div></td>' for i,(label,value,note) in enumerate(cards))
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Reporte de llamadas inbound</title></head>
    <body style="font-family:{FONT};color:#24344b;margin:0;background:#f0f2f5">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
    <table role="presentation" width="820" cellpadding="0" cellspacing="0" style="width:100%;max-width:820px;background:#fff;border-radius:14px;overflow:hidden;font-family:{FONT}">
    <tr><td style="background:#bf001b;padding:26px 30px;color:#fff">
    <table role="presentation" width="100%"><tr><td valign="middle" style="color:#fff">
    <div style="font-size:12px;font-weight:bold;letter-spacing:1px">REPORTE DIARIO</div>
    <h1 style="margin:7px 0 10px;font-size:25px;line-height:1.2;color:#fff">Comportamiento de<br>llamadas · INBOUND</h1>
    <div style="font-size:12px;color:#fff">Corte de información: {end:%d/%m/%Y} · 11:59 p. m.</div>
    </td><td width="210" align="right" valign="middle"><img src="{escape(logo_src, quote=True)}" width="200" alt="Banco Atlántida" style="display:block;width:200px;max-width:100%;height:auto;border:0"></td></tr></table>
    </td></tr><tr><td style="padding:25px 28px">
    <p style="font-size:13px;color:#657183;margin:0 0 18px">Periodo: <strong>{start:%d/%m/%Y} al {end:%d/%m/%Y}</strong> · {escape(str(tz))} · Días completos</p>
    <h2 style="font-size:16px">Resumen acumulado del periodo</h2><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cards_html}</tr></table>
    <p style="font-size:12px;padding:12px;background:#f0f5f2;color:#345244">Excel adjunto: resumen, evolución diaria y detalle por fecha y cola para análisis.</p>
    <h2 style="font-size:16px;margin-top:28px">Acumulado por cola</h2>{html_table(queues[:20], "Cola")}
    <p style="font-size:11px;color:#657183">Se muestran las {min(20,len(queues))} colas con mayor volumen. El Excel incluye todas las colas del reporte.</p>
    <h2 style="font-size:16px;margin-top:28px">Volumen y abandono diario</h2>
    <img src="{escape(chart_src, quote=True)}" width="760" alt="Gráfico diario: barras de llamadas ofrecidas y línea de porcentaje de abandono. Valores disponibles en la tabla diaria siguiente." style="display:block;width:100%;max-width:760px;height:auto;border:0">
    <h2 style="font-size:16px;margin-top:28px">Detalle diario</h2>{html_table(sorted(daily, key=lambda row: str(row[0])[:10], reverse=True), "Fecha (*) fin de semana")}
    <p style="font-size:11px;line-height:1.6;color:#586579;background:#f7f8fa;padding:16px"><strong>Notas metodológicas</strong><br>Solo voz, direccion inbound, colas accesibles al cliente OAuth.
    Ofrecidas y atendidas son eventos de cola, no clientes ni conversaciones unicas: una transferencia puede contar en mas de una cola.
    Las metricas se atribuyen al intervalo de su evento y pueden actualizarse por procesamiento tardio.
    No se presupone que ofrecidas = atendidas + abandonadas.
    Abandono = abandonadas / ofrecidas; espera media = suma tAnswered / cantidad tAnswered;
    gestion media = suma tHandle / cantidad tHandle. Duraciones convertidas de milisegundos a segundos.
    Los promedios totales se ponderan por cantidades, no por promedios diarios. — significa sin denominador.
    No se incluyen nombres, telefonos ni grabaciones de clientes.</p>
    </td></tr><tr><td align="center" style="padding:18px;background:#edf0f4;font-size:11px;color:#657183">pyflow manager · estrategia y gestión call center</td></tr></table></td></tr></table></body></html>'''


def report_attachments(excel_path, chart_bytes):
    excel = Path(excel_path).read_bytes()
    logo = LOGO.read_bytes()
    if len(excel) >= 3_000_000:
        raise ValueError("Excel excede el límite de adjunto directo (3 MB); reducir el alcance del reporte.")
    return [
        {"@odata.type": "#microsoft.graph.fileAttachment", "name": Path(excel_path).name,
         "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "isInline": False,
         "contentBytes": base64.b64encode(excel).decode()},
        {"@odata.type": "#microsoft.graph.fileAttachment", "name": "banco-atlantida.png",
         "contentType": "image/png", "isInline": True, "contentId": "atlantida-logo",
         "contentBytes": base64.b64encode(logo).decode()},
        {"@odata.type": "#microsoft.graph.fileAttachment", "name": "volumen-abandono-diario.png",
         "contentType": "image/png", "isInline": True, "contentId": "inbound-daily-chart",
         "contentBytes": base64.b64encode(chart_bytes).decode()}
    ]


def send_report(html, to, cc, end, excel_path, chart_bytes):
    attachments = report_attachments(excel_path, chart_bytes)
    tenant = quote(required("GRAPH_TENANT_ID"), safe="")
    token = request_json(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", {
        "client_id": required("GRAPH_CLIENT_ID"), "client_secret": required("GRAPH_CLIENT_SECRET"),
        "grant_type": "client_credentials", "scope": "https://graph.microsoft.com/.default"
    }, form=True)["access_token"]
    sender = quote(required("GRAPH_SENDER_EMAIL"), safe="")
    request_json(f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail", {
        "message": {"subject": f"Llamadas inbound - acumulado al {end:%d/%m/%Y}",
                    "body": {"contentType": "HTML", "content": html},
                    "toRecipients": [{"emailAddress": {"address": a}} for a in to],
                    "ccRecipients": [{"emailAddress": {"address": a}} for a in cc],
                    "attachments": attachments},
        "saveToSentItems": True
    }, headers={"Authorization": f"Bearer {token}"}, retries=0)


def main():
    tz = ZoneInfo(os.getenv("GENESYS_TIMEZONE") or "America/Tegucigalpa")
    start, end = period(datetime.now(tz).date(), os.getenv("REPORT_END_DATE", ""))
    send = os.getenv("SEND_EMAIL", "false").lower() == "true"
    to = split_values(os.getenv("REPORT_EMAIL_TO", ""))
    cc = split_values(os.getenv("REPORT_EMAIL_CC", ""))
    if send and not to:
        raise ValueError("Escribe REPORT_EMAIL_TO antes de activar SEND_EMAIL.")
    if send:
        for address in to + cc:
            if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", address):
                raise ValueError("Formato de correo invalido.")
        for key in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET", "GRAPH_SENDER_EMAIL"):
            required(key)
    domain = required("GENESYS_REGION").removeprefix("https://").removeprefix("api.").removeprefix("login.").rstrip("/")
    if not re.fullmatch(r"[a-z0-9.-]+", domain):
        raise ValueError("GENESYS_REGION debe ser un dominio sin ruta.")
    credentials = base64.b64encode(f'{required("GENESYS_CLIENT_ID")}:{required("GENESYS_CLIENT_SECRET")}'.encode()).decode()
    token = request_json(f"https://login.{domain}/oauth/token", {"grant_type": "client_credentials"},
                         {"Authorization": f"Basic {credentials}"}, form=True)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    base = f"https://api.{domain}/api/v2"
    names = {}
    page = 1
    while True:
        response = request_json(f"{base}/routing/queues?pageSize=100&pageNumber={page}", headers=headers)
        for queue in response.get("entities", []):
            names[queue["id"]] = queue.get("name") or queue["id"]
        if page >= response.get("pageCount", page):
            break
        page += 1
    selected = selected_queue_ids(os.getenv("REPORT_QUEUE_IDS", ""))
    if set(selected) - names.keys():
        raise ValueError("Hay IDs de cola no encontrados o sin permisos en REPORT_QUEUE_IDS.")
    if not names:
        raise ValueError("No se encontraron colas accesibles; revisar permisos OAuth.")
    daily, detail, raw_detail = [], [], []
    by_queue, total = {}, empty_stats()
    day = start
    while day <= end:
        response = request_json(f"{base}/analytics/conversations/aggregates/query", query_body(day, tz, selected), headers)
        if response.get("truncated"):
            raise RuntimeError("Genesys trunco el resultado; reducir las colas del reporte.")
        day_stats = empty_stats()
        for result in response.get("results", []):
            qid = result["group"]["queueId"]
            stats = parse_stats(result)
            add_stats(day_stats, stats)
            add_stats(by_queue.setdefault(qid, empty_stats()), stats)
            detail.append([day.isoformat(), qid] + row_values(names.get(qid, qid), stats))
            raw_detail.append([day.isoformat(), qid, names.get(qid, qid), stats["nOffered"]["count"], stats["tAnswered"]["count"], stats["tAbandon"]["count"], stats["tAnswered"]["sum"], stats["tHandle"]["count"], stats["tHandle"]["sum"]])
        add_stats(total, day_stats)
        daily.append(row_values(day.isoformat() + (" *" if day.weekday() >= 5 else ""), day_stats))
        print(f"PYFLOW_PROGRESS={int(90 * ((day-start).days+1) / ((end-start).days+1))}", flush=True)
        day += timedelta(days=1)
    queues = [row_values(names.get(q, q), s) for q, s in sorted(by_queue.items(), key=lambda pair: -pair[1]["nOffered"]["count"])]
    chart_bytes = daily_chart(daily)
    html = render_report(start, end, tz, daily, queues, total, chart_src="data:image/png;base64," + base64.b64encode(chart_bytes).decode())
    output = Path(os.getenv("PYFLOW_OUTPUT_DIR") or Path(__file__).parent / "output")
    output.mkdir(parents=True, exist_ok=True)
    stem = f"inbound_{start}_{end}"
    (output / f"{stem}_diario.png").write_bytes(chart_bytes)
    data_path = output / f"{stem}.json"
    data_path.write_text(json.dumps({"start": start.isoformat(), "end": end.isoformat(), "timezone": str(tz), "detail": raw_detail}, ensure_ascii=False), encoding="utf-8")
    excel_path = output / f"{stem}.xlsx"
    node = os.getenv("PYFLOW_NODE_COMMAND") or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js es necesario para generar el Excel.")
    subprocess.run([node, str(Path(__file__).parent / "config" / "build_excel.mjs"), str(data_path), str(excel_path)], check=True, timeout=240)
    (output / f"{stem}.html").write_text(html, encoding="utf-8")
    with (output / f"{stem}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["fecha", "cola_id", "cola", "ofrecidas", "atendidas", "abandonadas", "abandono_pct", "espera_media_seg", "gestion_media_seg"])
        for row in detail:
            writer.writerow(["'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for v in row])
    print(f"Reporte generado: {output / (stem + '.html')}", flush=True)
    if send:
        mail_html = render_report(start, end, tz, daily, queues, total, "cid:atlantida-logo", "cid:inbound-daily-chart")
        send_report(mail_html, to, cc, end, excel_path, chart_bytes)
        print("Microsoft Graph acepto el envio del correo.", flush=True)
    else:
        print("Vista previa generada; envio desactivado.", flush=True)
    print("PYFLOW_PROGRESS=100", flush=True)


if __name__ == "__main__":
    main()
