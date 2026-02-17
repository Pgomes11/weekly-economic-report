from flask import Flask, jsonify
from datetime import datetime
import json
import os
import schedule
import threading
import time

app = Flask(__name__)
STORAGE_FILE = "reports.json"


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
        week = datetime.now().strftime("%Y-W%W")
        self.reports[week] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "data": {
                "message": "Informe generado",
                "week": week,
            },
        }
        self.save()


gen = ReportGenerator()


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
      --accent: #7c3aed;
      --accent2: #22c55e;
      --danger: #ef4444;
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

    .wrap{
      max-width: 980px;
      margin: 0 auto;
    }

    .top{
      display: flex;
      gap: 16px;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }

    .title{
      display:flex;
      flex-direction: column;
      gap: 6px;
    }

    .title h1{
      margin: 0;
      font-size: 28px;
      letter-spacing: -0.5px;
      line-height: 1.15;
    }

    .title p{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }

    .pill{
      display:inline-flex;
      gap: 8px;
      align-items:center;
      padding: 8px 12px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(255,255,255,0.04);
      color: var(--muted);
      font-size: 12px;
      width: fit-content;
    }

    .grid{
      display:grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 16px;
      margin-top: 18px;
    }

    @media (max-width: 860px){
      .grid{ grid-template-columns: 1fr; }
    }

    .card{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .card .hd{
      padding: 16px 18px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(255,255,255,0.06), transparent);
      display:flex;
      align-items:center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }

    .card .hd h2{
      margin:0;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
    }

    .card .bd{
      padding: 18px;
    }

    .btns{
      display:flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    button{
      appearance: none;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.06);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 12px;
      font-weight: 600;
      cursor:pointer;
      transition: transform .08s ease, background .2s ease, border-color .2s ease;
    }
    button:hover{ background: rgba(255,255,255,0.10); }
    button:active{ transform: translateY(1px); }

    .primary{
      background: linear-gradient(135deg, rgba(124,58,237,0.95), rgba(59,130,246,0.85));
      border-color: rgba(255,255,255,0.22);
    }
    .primary:hover{ background: linear-gradient(135deg, rgba(124,58,237,1), rgba(59,130,246,0.92)); }

    .success{
      background: rgba(34,197,94,0.16);
      border-color: rgba(34,197,94,0.35);
    }

    .muted{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .kv{
      display:grid;
      grid-template-columns: 140px 1fr;
      gap: 8px 12px;
      margin-top: 10px;
      font-size: 14px;
    }
    .kv div:nth-child(odd){ color: var(--muted2); }
    .kv div:nth-child(even){ font-family: var(--mono); }

    pre{
      margin: 0;
      padding: 14px;
      border-radius: 14px;
      background: var(--card2);
      border: 1px solid var(--border);
      font-family: var(--mono);
      font-size: 12.5px;
      color: rgba(255,255,255,0.86);
      overflow: auto;
      max-height: 420px;
    }

    .status{
      display:flex;
      align-items:center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      font-size: 13px;
      color: var(--muted);
    }

    .dot{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.35);
      box-shadow: 0 0 0 4px rgba(255,255,255,0.06);
    }

    .dot.ok{ background: rgba(34,197,94,0.9); box-shadow: 0 0 0 4px rgba(34,197,94,0.15); }
    .dot.bad{ background: rgba(239,68,68,0.9); box-shadow: 0 0 0 4px rgba(239,68,68,0.15); }

    a.link{
      color: rgba(255,255,255,0.9);
      text-decoration: none;
      border-bottom: 1px dashed rgba(255,255,255,0.35);
    }
    a.link:hover{ border-bottom-color: rgba(255,255,255,0.7); }

    .foot{
      margin-top: 16px;
      color: var(--muted2);
      font-size: 12px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="title">
        <div class="pill">🗓️ Report semanal · <span id="now">—</span></div>
        <h1>Weekly Economic Report</h1>
        <p>Genera y consulta el último informe desde esta misma página (sin APIs “feas”).</p>
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
            <button class="primary" id="btnGen">Generar informe</button>
            <button id="btnRefresh">Actualizar</button>
          </div>
        </div>
        <div class="bd">
          <div class="kv">
            <div>Semana</div><div id="week">—</div>
            <div>Timestamp</div><div id="ts">—</div>
          </div>
          <div style="height: 12px"></div>
          <pre id="out">Cargando...</pre>
          <div class="foot">
            Endpoints: <a class="link" href="/api/latest-report">/api/latest-report</a> ·
            <a class="link" href="/api/generate">/api/generate</a>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="hd">
          <h2>Notas</h2>
        </div>
        <div class="bd">
          <p class="muted">
            Este es un “starter” visual para tu informe semanal. Ahora mismo el contenido es un ejemplo,
            pero ya tienes el esqueleto perfecto para:
          </p>
          <ul class="muted">
            <li>Meter secciones reales (PIB, inflación, empleo, vivienda...).</li>
            <li>Mostrar tablas y gráficos en HTML.</li>
            <li>Guardar histórico por semana y navegarlo.</li>
          </ul>

          <div style="height: 10px"></div>
          <div class="status">
            <span class="dot ok"></span>
            <span>Scheduler activo: genera a las 08:00 (server time)</span>
          </div>

          <div style="height: 10px"></div>
          <p class="muted">
            Si más adelante quieres persistencia “de verdad”, en Render lo ideal es usar un Disk o una DB.
            Con <span style="font-family: var(--mono);">reports.json</span> puede funcionar, pero no es lo más robusto.
          </p>
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
        setStatus(false, 'No hay informes todavía. Genera uno.');
        return;
      }

      // data = {message, week} según tu API actual
      elWeek.textContent = data.week ?? '—';
      elTs.textContent = new Date().toISOString().slice(0,19).replace('T',' ');
      elOut.textContent = JSON.stringify(data, null, 2);
      setStatus(true, 'Listo ✅');
    }catch(e){
      elOut.textContent = 'Error cargando /api/latest-report\\n\\n' + (e?.message || e);
      setStatus(false, 'Error cargando el informe');
    }
  }

  async function generate(){
    try{
      setStatus(true, 'Generando informe...');
      const r = await fetch('/api/generate', {method: 'POST'});
      await r.json().catch(()=>{});
      await loadLatest();
      setStatus(true, 'Informe generado ✅');
    }catch(e){
      setStatus(false, 'Error generando el informe');
      elOut.textContent = 'Error llamando /api/generate\\n\\n' + (e?.message || e);
    }
  }

  document.getElementById('btnGen').addEventListener('click', generate);
  document.getElementById('btnRefresh').addEventListener('click', loadLatest);

  // fecha arriba
  document.getElementById('now').textContent =
    new Date().toLocaleString('es-ES', { dateStyle: 'full', timeStyle: 'short' });

  loadLatest();
</script>

</body>
</html>
"""


@app.route("/api/latest-report")
def latest():
    if gen.reports:
        last = max(gen.reports.keys())
        return jsonify(gen.reports[last]["data"])
    return jsonify({"error": "No reports"}), 404


@app.route("/api/generate", methods=["POST", "GET"])
def generate():
    gen.generate()
    return jsonify({"status": "ok"})


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
