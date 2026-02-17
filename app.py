from flask import Flask
from datetime import datetime, timedelta
import json, os, schedule, threading, time

app = Flask(__name__)
STORAGE_FILE = 'reports.json'

class ReportGenerator:
                def __init__(self):
                                    self.reports = {}
                                    self.load()
                                def load(self):
                                                    try:
                                                                            with open(STORAGE_FILE) as f:
                                                                                                        self.reports = json.load(f)
                                                                                                except:
                                                                            self.reports = {}
                                                def save(self):
                                                                    with open(STORAGE_FILE, 'w') as f:
                                                                                            json.dump(self.reports, f, default=str)
                                                                                    def generate(self):
                                                                                                        week = datetime.now().strftime("%Y-W%W")
                                                                                                        self.reports[week] = {
                                                                                                            'timestamp': datetime.now().isoformat(),
                                                                                                            'data': {'message': 'Informe generado', 'week': week}
                                                                                                                    }
                                                                                                        self.save()

gen = ReportGenerator()

@app.route('/')
def home():
                return '<h1>Informe Economico</h1><p><a href="/api/generate">Generar</a></p>'

@app.route('/api/latest-report')
def latest():
                if gen.reports:
                                    last = max(gen.reports.keys())
        return gen.reports[last]['data']
    return {'error': 'No reports'}

@app.route('/api/generate', methods=['POST', 'GET'])
def generate():
                gen.generate()
    return {'status': 'ok'}

def run_scheduler():
                schedule.every().day.at("08:00").do(gen.generate)
    while True:
                        schedule.run_pending()
        time.sleep(60)

t = threading.Thread(target=run_scheduler, daemon=True)
t.start()

if __name__ == '__main__':
                port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
