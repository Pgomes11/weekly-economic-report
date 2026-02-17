#!/usr/bin/env python3
from flask import Flask, jsonify
from datetime import datetime, timedelta
import json, os, logging, requests, feedparser, schedule, threading, time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STORAGE_FILE = 'reports.json'

class EconomicReportGenerator:
            def __init__(self):
                            self.today = datetime.now()
                            self.week_ago = self.today - timedelta(days=7)

            def fetch_news(self, feed_url):
                            articles = []
                            try:
                                                feed = feedparser.parse(feed_url)
                                                for entry in feed.entries[:3]:
                                                                        articles.append({'title': entry.get('title', ''), 'source': feed.feed.get('title', 'Unknown')})
                                                                except:
                                                pass
                            return articles

    def generate_report(self):
                    return {
                                        'metadata': {'week_start': self.week_ago.isoformat(), 'week_end': self.today.isoformat(), 'generated_at': datetime.now().isoformat()},
                                        'international': {'news': self.fetch_news('https://feeds.reuters.com/reuters/businessNews')},
                                        'spain': {'news': self.fetch_news('https://www.eleconomista.es/rss/economia.xml')},
                                        'housing': {'summary': 'Market stable'},
                                        'geopolitics': {'news': self.fetch_news('https://feeds.reuters.com/reuters/worldNews')}
                    }

class ReportManager:
            def __init__(self):
                            self.reports = self.load()

    def load(self):
                    try:
                                        with open(STORAGE_FILE, 'r') as f:
                                                                return json.load(f)
                                                        except:
                                        return {}

    def save(self):
                    with open(STORAGE_FILE, 'w') as f:
                                        json.dump(self.reports, f, default=str)

    def generate(self):
                    try:
                                        logger.info("Generando reporte...")
                                        gen = EconomicReportGenerator()
                                        report = gen.generate_report()
                                        week = datetime.now().strftime("%Y-W%W")
                                        self.reports[week] = {'timestamp': datetime.now().isoformat(), 'data': report}
                                        self.save()
                                        logger.info(f"Reporte guardado: {week}")
                                        return report
except Exception as e:
            logger.error(f"Error: {e}")
            return None

manager = ReportManager()

@app.route('/api/latest-report', methods=['GET'])
def latest():
            if manager.reports:
                            last = max(manager.reports.keys())
                            return jsonify(manager.reports[last]['data'])
                        return jsonify({'error': 'No reports'}), 404

@app.route('/api/reports/history', methods=['GET'])
def history():
                        return jsonify({'total': len(manager.reports), 'weeks': sorted(manager.reports.keys(), reverse=True)})

@app.route('/api/generate', methods=['POST'])
def generate():
            report = manager.generate()
    return jsonify({'status': 'success', 'report': report}) if report else (jsonify({'status': 'error'}), 500)

@app.route('/', methods=['GET'])
def dashboard():
            if not manager.reports:
                            return '<h1>No reports yet</h1><a href="/api/generate">Generate</a>'
                        last = max(manager.reports.keys())
    r = manager.reports[last]['data']
    return f'<h1>Informe {last}</h1><p>Generado: {r["metadata"]["generated_at"]}</p>'

@app.route('/health', methods=['GET'])
def health():
            return jsonify({'status': 'healthy'})

def scheduler():
            schedule.every().day.at("08:00").do(manager.generate)
    logger.info("Scheduler iniciado - DIARIO a las 08:00 UTC")
    while True:
                    schedule.run_pending()
        time.sleep(60)

t = threading.Thread(target=scheduler, daemon=True)
t.start()

if __name__ == '__main__':
            port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
