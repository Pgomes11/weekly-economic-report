from flask import Flask, jsonify, send_file
from datetime import datetime
import json
import os
import schedule
import threading
import time
from io import BytesIO

import requests
import feedparser

from openai import OpenAI

# PDF (ReportLab)
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors


app = Flask(__name__)
STORAGE_FILE = "reports.json"

# OpenAI client (reads OPENAI_API_KEY from env)
client = OpenAI()


# ---------------------------
# Config helpers
# ---------------------------
def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def now_week() -> str:
    return datetime.now().strftime("%Y-W%W")


def news_query() -> str:
    # Puedes cambiarlo en Render con NEWS_QUERY
    return os.getenv(
        "NEWS_QUERY",
        "mercado inmobiliario Madrid precios vivienda Idealista informe",
    ).strip()


def news_language() -> str:
    # hl: interfaz; ceid: edición, para España
    return os.getenv("NEWS_LANG", "es").strip()


def news_country() -> str:
    return os.getenv("NEWS_COUNTRY", "ES").strip()


def max_news_items() -> int:
    return env_int("NEWS_MAX_ITEMS", 10)


def openai_model() -> str:
    # Pon OPENAI_MODEL en Render si quieres cambiarlo
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


# ---------------------------
# News fetching (RSS)
# ---------------------------
def build_google_news_rss_url(query: str, lang: str = "es", country: str = "ES") -> str:
    # Ejemplo: https://news.google.com/rss/search?q=...&hl=es&gl=ES&ceid=ES:es
    ceid = f"{country}:{lang}"
    return (
        "https://news.google.com/rss/search?q="
        + requests.utils.quote(query)
        + f"&hl={lang}&gl={country}&ceid={ceid}"
    )


def fetch_news_items(query: str, max_items: int = 10, lang: str = "es", country: str = "ES") -> list[dict]:
    """
    Devuelve una lista de items:
    [{title, url, published, source, snippet}]
    """
    rss_url = build_google_news_rss_url(query, lang=lang, country=country)
    feed = feedparser.parse(rss_url)

    items = []
    for entry in feed.entries[: max_items]:
        title = getattr(entry, "title", "") or ""
        url = getattr(entry, "link", "") or ""
        published = getattr(entry, "published", "") or ""
        source = ""
        if hasattr(entry, "source") and isinstance(entry.source, dict):
            source = entry.source.get("title", "") or ""

        # snippet: Google News RSS suele meter summary/description con HTML
        snippet = ""
        if hasattr(entry, "summary"):
            snippet = entry.summary or ""
        elif hasattr(entry, "description"):
            snippet = entry.description or ""

        # Limpieza muy simple de tags HTML
        snippet = snippet.replace("<b>", "").replace("</b>", "")
        snippet = snippet.replace("<br>", " ").replace("<br/>", " ")
        snippet = " ".join(snippet.split())

        items.append(
            {
                "title": title.strip(),
                "url": url.strip(),
                "published": published.strip(),
                "source": source.strip(),
                "snippet": snippet.strip(),
            }
        )

    return items


# ---------------------------
# OpenAI report generation
# ---------------------------
def build_report_with_openai(news_items: list[dict], week: str) -> dict:
    """
    Genera un informe original en base a titulares + snippets (no copia artículos).
    Devuelve JSON estructurado.
    """
    # Compact input
    lines = []
    for i, it in enumerate(news_items, start=1):
        lines.append(
            f"{i}. TITULAR: {it.get('title','')}\n"
            f"   FECHA: {it.get('published','')}\n"
            f"   MEDIO: {it.get('source','')}\n"
            f"   LINK: {it.get('url','')}\n"
            f"   SNIPPET: {it.get('snippet','')}\n"
        )
    input_text = "\n".join(lines).strip()

    # Nota clave: debe aparecer la palabra "json" para usar text.format json_object
    instructions = (
        "IMPORTANTE: Devuelve SOLO json válido (json). No añadas texto fuera del JSON.\n\n"
        "Eres analista del mercado inmobiliario en España. "
        "Con la lista de noticias (titulares + snippets) redacta un INFORME SEMANAL original, claro y accionable.\n\n"
        "Reglas:\n"
        "- NO copies artículos ni pegues texto largo: usa solo el snippet como señal.\n"
        "- Si un dato no está en las noticias, di que no aparece.\n"
        "- Identifica temas recurrentes, señales de precio/ventas/oferta, sentimiento y riesgos.\n"
        "- Incluye una sección de 'Fuentes' con enlaces (los de las noticias).\n\n"
        "Salida EXACTA en json con esta estructura:\n"
        "{\n"
        '  "title": string,\n'
        '  "week": string,\n'
        '  "executive_summary": [string, ...],\n'
        '  "sections": [{"heading": string, "bullets": [string, ...]} ...],\n'
        '  "sources": [{"url": string, "note": string} ...],\n'
        '  "generated_at": string\n'
        "}\n"
    )

    resp = client.responses.create(
        model=openai_model(),
        instructions=instructions,
        # metemos "(json)" también aquí para cumplir el requisito sí o sí
        input=f"(json) Semana objetivo: {week}\n\nNOTICIAS:\n{input_text}",
        text={"format": {"type": "json_object"}},
    )

    data = json.loads(resp.output_text)
    data["week"] = data.get("week") or week
    data["generated_at"] = data.get("generated_at") or datetime.now().isoformat(timespec="seconds")
    data["title"] = data.get("title") or "Weekly Economic Report"
    return data


# ---------------------------
# Persistence + generator
# ---------------------------
class ReportGenerator:
    def __init__(self):
        self.reports = {}
        self.load()

    def load(self):
        try:
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                self.reports = json.load(f)
        except Exception:
            self.reports = {}

    def save(self):
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.reports, f, ensure_ascii=False, indent=2, default=str)

    def generate(self):
        """
        Pipeline:
        1) Lee noticias (RSS)
        2) Resume y estructura el informe con OpenAI
        3) Guarda en reports.json
        """
        week = now_week()

        items = fetch_news_items(
            query=news_query(),
            max_items=max_news_items(),
            lang=news_language(),
            country=news_country(),
        )

        if not items:
            # Aun así guardamos algo para no romper
            report_struct = {
                "title": "Weekly Economic Report",
                "week": week,
                "executive_summary": ["No se han podido recuperar noticias (RSS vacío o fallo de red)."],
                "sections": [
                    {"heading": "Estado del feed", "bullets": ["No hay items disponibles en este momento."]}
                ],
                "sources": [],
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }
        else:
            report_struct = build_report_with_openai(items, week=week)

        self.reports[week] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "data": report_struct,
        }
        self.save()


gen = ReportGenerator()


# ---------------------------
# UI
# ---------------------------
@app.route("/")
def home():
    return """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Weekly Economic Report</title>
  <style>
    :root{
      --bg: #0b1220;
      --card: rgba(255,255,255,0.06);
      --card2: rgba(255,255,255,0.08);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.70);
      --muted2: rgba(255,255,255,0.55);
      --border: rgba(255,255,255,0.12);
      --shadow: 0 18px 60px rgba(0,0,0,0.45);
      --radius: 18px;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Apple Color Emoji","Segoe UI Emoji";
    }
    * { box-sizing: border-box; }
    body{
      margin: 0;
      font-family: var(--sans);
      color: var(--text);
      background:
        radial-gradient(900px 600px at 10% 10%, rgba(124,58,237,0.25), transparent 55%),
        radial-gradient(900px 600px at 90% 30%, rgba(34,197,94,0.18), transparent 55%),
        radial-gradient(800px 500px at 50% 100%, rgba(59,130,246,0.12), transparent 60%),
        var(--bg);
      min-height: 100vh;
      padding: 36px 16px 64px;
    }
    .wrap{ max-width: 980px; margin: 0 auto; }
    .top{ display:flex; gap:16px; align-items:flex-start; justify-content:space-between; margin-bottom:18px; flex-wrap:wrap; }
    .title{ display:flex; flex-direction:column; gap:6px; }
    .title h1{ margin:0; font-size:28px; letter-spacing:-0.5px; line-height:1.15; }
    .title p{ margin:0; color:var(--muted); font-size:14px; }
    .pill{ display:inline-flex; gap:8px; align-items:center; padding:8px 12px; border:1px solid var(--border); border-radius:999px; background:rgba(255,255,255,0.04); color:var(--muted); font-size:12px; width:fit-content; }
    .grid{ display:grid; grid-template-columns: 1.1fr 0.9fr; gap:16px; margin-top:18px; }
    @media (max-width: 860px){ .grid{ grid-template-columns: 1fr; } }
    .card{ background:var(--card); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); overflow:hidden; }
    .card .hd{ padding:16px 18px; border-bottom:1px solid var(--border); background:linear-gradient(180deg, rgba(255,255,255,0.06), transparent); display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
    .card .hd h2{ margin:0; font-size:14px; text-transform:uppercase; letter-spacing:0.12em; color:var(--muted); }
    .card .bd{ padding:18px; }
    .btns{ display:flex; gap:10px; flex-wrap:wrap; }
    button{
      appearance:none; border:1px solid var(--border); background:rgba(255,255,255,0.06); color:var(--text);
      padding:10px 12px; border-radius:12px; font-weight:600; cursor:pointer;
      transition: transform .08s ease, background .2s ease, border-color .2s ease;
    }
    button:hover{ background:rgba(255,255,255,0.10); }
    button:active{ transform: translateY(1px); }
    .primary{ background:linear-gradient(135deg, rgba(124,58,237,0.95), rgba(59,130,246,0.85)); border-color:rgba(255,255,255,0.22); }
    .primary:hover{ background:linear-gradient(135deg, rgba(124,58,237,1), rgba(59,130,246,0.92)); }
    .success{ background:rgba(34,197,94,0.16); border-color:rgba(34,197,94,0.35); }
    .success:hover{ background:rgba(34,197,94,0.22); }
    .muted{ color:var(--muted); font-size:13px; line-height:1.45; }
    .kv{ display:grid; grid-template-columns: 140px 1fr; gap:8px 12px; margin-top:10px; font-size:14px; }
    .kv div:nth-child(odd){ color:var(--muted2); }
    .kv div:nth-child(even){ font-family:var(--mono); }
    pre{ margin:0; padding:14px; border-radius:14px; background:var(--card2); border:1px solid var(--border);
         font-family:var(--mono); font-size:12.5px; color:rgba(255,255,255,0.86); overflow:auto; max-height:420px; }
    .status{ display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:14px; border:1px solid var(--border);
             background:rgba(255,255,255,0.04); font-size:13px; color:var(--muted); }
    .dot{ width:10px; height:10px; border-radius:999px; background:rgba(255,255,255,0.35); box-shadow: 0 0 0 4px rgba(255,255,255,0.06); }
    .dot.ok{ background:rgba(34,197,94,0.9); box-shadow: 0 0 0 4px rgba(34,197,94,0.15); }
    .dot.bad{ background:rgba(239,68,68,0.9); box-shadow: 0 0 0 4px rgba(239,68,68,0.15); }
    a.link{ color:rgba(255,255,255,0.9); text-decoration:none; border-bottom:1px dashed rgba(255,255,255,0.35); }
    a.link:hover{ border-bottom-color: rgba(255,255,255,0.7); }
    .foot{ margin-top:16px; color:var(--muted2); font-size:12px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="title">
        <div class="pill">🗓️ Report semanal · <span id="now">—</span></div>
        <h1>Weekly Economic Report</h1>
        <p>Genera el informe desde noticias y descárgalo en PDF.</p>
      </div>
      <div class="status">
        <span class="dot" id="dot"></span>
        <span id="statusText">Cargando...</span>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="hd">
          <h2>Último informe</h2>
          <div class="btns">
            <button class="primary" id="btnGen">Generar informe (noticias + IA)</button>
            <button id="btnRefresh">Actualizar</button>
            <button class="success" id="btnDownload">Descargar PDF</button>
          </div>
        </div>
        <div class="bd">
          <div class="kv">
            <div>Semana</div><div id="week">—</div>
            <div>Generado</div><div id="ts">—</div>
          </div>
          <div style="height: 12px"></div>
          <pre id="out">Cargando...</pre>
          <div class="foot">
            Endpoints: <a class="link" href="/api/latest-report">/api/latest-report</a> ·
            <a class="link" href="/api/generate">/api/generate</a> ·
            <a class="link" href="/api/download-report">/api/download-report</a>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="hd"><h2>Notas</h2></div>
        <div class="bd">
          <p class="muted">
            El generador: (1) lee titulares+snippets vía RSS, (2) crea un informe original con IA, (3) lo guarda, (4) lo convierte a PDF.
          </p>
          <p class="muted">
            Configurable en Render con <span style="font-family: var(--mono);">NEWS_QUERY</span> y <span style="font-family: var(--mono);">NEWS_MAX_ITEMS</span>.
          </p>
          <div style="height: 10px"></div>
          <div class="status"><span class="dot ok"></span><span>Scheduler activo: genera a las 08:00 (server time)</span></div>
        </div>
      </div>
    </div>
  </div>

<script>
  const elOut = document.getElementById('out');
  const elWeek = document.getElementById('week');
  const elTs = document.getElementById('ts');
  const dot = document.getElementById('dot');
  const statusText = document.getElementById('statusText');

  function setStatus(ok, msg){
    dot.className = 'dot ' + (ok ? 'ok' : 'bad');
    statusText.textContent = msg;
  }

  async function loadLatest(){
    try{
      setStatus(true, 'Cargando último informe...');
      const r = await fetch('/api/latest-report', {cache: 'no-store'});
      const data = await r.json();

      if(data && data.error){
        elWeek.textContent = '—';
        elTs.textContent = '—';
        elOut.textContent = JSON.stringify(data, null, 2);
        setStatus(false, 'No hay informe todavía. Genera uno.');
        return;
      }

      elWeek.textContent = data.week ?? '—';
      elTs.textContent = data.generated_at ?? (new Date().toISOString().slice(0,19).replace('T',' '));
      elOut.textContent = JSON.stringify(data, null, 2);
      setStatus(true, 'Listo ✅');
    }catch(e){
      elOut.textContent = 'Error cargando /api/latest-report\\n\\n' + (e?.message || e);
      setStatus(false, 'Error cargando el informe');
    }
  }

  async function generate(){
    try{
      setStatus(true, 'Generando (puede tardar unos segundos)...');
      const r = await fetch('/api/generate', {method: 'POST'});
      const j = await r.json().catch(()=> ({}));
      if(!r.ok){
        elOut.textContent = JSON.stringify(j, null, 2);
        setStatus(false, 'Error generando');
        return;
      }
      await loadLatest();
      setStatus(true, 'Informe generado ✅');
    }catch(e){
      setStatus(false, 'Error generando el informe');
      elOut.textContent = 'Error llamando /api/generate\\n\\n' + (e?.message || e);
    }
  }

  function downloadPdf(){
    window.location = '/api/download-report';
  }

  document.getElementById('btnGen').addEventListener('click', generate);
  document.getElementById('btnRefresh').addEventListener('click', loadLatest);
  document.getElementById('btnDownload').addEventListener('click', downloadPdf);

  document.getElementById('now').textContent =
    new Date().toLocaleString('es-ES', { dateStyle: 'full', timeStyle: 'short' });

  loadLatest();
</script>

</body>
</html>
"""


# ---------------------------
# API
# ---------------------------
@app.route("/api/latest-report")
def latest():
    if gen.reports:
        last = max(gen.reports.keys())
        return jsonify(gen.reports[last]["data"])
    return jsonify({"error": "No reports"}), 404


@app.route("/api/generate", methods=["POST", "GET"])
def generate():
    try:
        gen.generate()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _safe_list(items):
    if not items:
        return []
    return [x for x in items if isinstance(x, str) and x.strip()]


@app.route("/api/download-report")
def download_report():
    if not gen.reports:
        return jsonify({"error": "No reports"}), 404

    last = max(gen.reports.keys())
    report = gen.reports[last]["data"]

    title = report.get("title", "Weekly Economic Report")
    week = report.get("week", last)
    generated_at = report.get("generated_at", "")
    exec_sum = _safe_list(report.get("executive_summary", []))
    sections = report.get("sections", [])
    sources = report.get("sources", [])

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=44,
        bottomMargin=44,
        title=title,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Semana: <b>{week}</b>", styles["Normal"]))
    story.append(Paragraph(f"Generado: <b>{generated_at}</b>", styles["Normal"]))
    story.append(Spacer(1, 16))

    if exec_sum:
        story.append(Paragraph("Resumen ejecutivo", styles["Heading2"]))
        story.append(Spacer(1, 6))
        bullets = ListFlowable(
            [ListItem(Paragraph(b, styles["BodyText"])) for b in exec_sum],
            bulletType="bullet",
            leftIndent=18,
        )
        story.append(bullets)
        story.append(Spacer(1, 14))

    if isinstance(sections, list) and sections:
        for s in sections:
            heading = (s.get("heading") if isinstance(s, dict) else "") or "Sección"
            bullets = s.get("bullets") if isinstance(s, dict) else []
            bullets = _safe_list(bullets)

            story.append(Paragraph(heading, styles["Heading2"]))
            story.append(Spacer(1, 6))
            if bullets:
                lf = ListFlowable(
                    [ListItem(Paragraph(b, styles["BodyText"])) for b in bullets],
                    bulletType="bullet",
                    leftIndent=18,
                )
                story.append(lf)
            else:
                story.append(Paragraph("—", styles["BodyText"]))
            story.append(Spacer(1, 12))

    if isinstance(sources, list) and sources:
        story.append(Paragraph("Fuentes", styles["Heading2"]))
        story.append(Spacer(1, 6))

        rows = [["URL", "Nota"]]
        for src in sources[:20]:
            if not isinstance(src, dict):
                continue
            url = src.get("url", "")
            note = src.get("note", "")
            rows.append([url, note])

        table = Table(rows, colWidths=[290, 230])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BOX", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    buffer.seek(0)

    filename = f"weekly_report_{week}.pdf".replace(":", "-")
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# ---------------------------
# Scheduler
# ---------------------------
def run_scheduler():
    schedule.every().day.at("08:00").do(gen.generate)
    while True:
        schedule.run_pending()
        time.sleep(60)


t = threading.Thread(target=run_scheduler, daemon=True)
t.start()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
