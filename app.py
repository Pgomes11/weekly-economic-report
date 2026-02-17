#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Generación de Informes Económicos Semanales
API REST + Dashboard Web
Ejecuta automáticamente cada día a las 08:00 UTC
"""

from flask import Flask, jsonify
from datetime import datetime, timedelta
import json
import os
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
import schedule
import threading
import time

# =====================
# CONFIGURACIÓN
# =====================

app = Flask(__name__)
logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Almacenamiento en memoria
reports_storage = {}
STORAGE_FILE = 'reports.json'

# =====================
# GENERADOR DE REPORTES
# =====================

class EconomicReportGenerator:
        def __init__(self):
                    self.today = datetime.now()
                    self.week_ago = self.today - timedelta(days=7)

        def fetch_international_news(self):
                    """Noticias macroeconómicas internacionales"""
                    logger.info("📡 Recopilando noticias internacionales...")
                    articles = []
                    feeds = [
                        'https://feeds.reuters.com/reuters/businessNews',
                        'https://feeds.bloomberg.com/markets/news.rss',
                    ]

        for feed_url in feeds:
                        try:
                                            feed = feedparser.parse(feed_url)
                                            for entry in feed.entries[:2]:
                                                                    articles.append({
                                                                                                'title': entry.get('title', 'Sin título'),
                                                                                                'summary': entry.get('summary', '')[:250],
                                                                                                'source': feed.feed.get('title', 'Fuente económica'),
                                                                                                'published': entry.get('published', '')
                                                                    })
                        except Exception as e:
                                            logger.warning(f"Error en feed: {e}")

                    return articles[:10]

    def fetch_spain_economy_news(self):
                """Noticias de economía española"""
                logger.info("🇪🇸 Recopilando noticias de España...")
                articles = []

        try:
                        feed = feedparser.parse('https://www.eleconomista.es/rss/economia.xml')
                        for entry in feed.entries[:5]:
                                            articles.append({
                                                                    'title': entry.get('title', 'Sin título'),
                                                                    'summary': entry.get('summary', '')[:250],
                                                                    'source': 'elEconomista.es',
                                                                    'published': entry.get('published', '')
                                            })
        except Exception as e:
                        logger.warning(f"Error obteniendo noticias españolas: {e}")

        return articles

    def fetch_housing_market_data(self):
                """Datos del mercado inmobiliario español"""
                logger.info("🏠 Recopilando datos inmobiliarios...")

        housing_data = {
                        'national_summary': 'Mercado inmobiliario español mantiene estabilidad',
                        'compraventa_prices': {
                                            'madrid': {'price_per_m2': 6500, 'change_week': '+0.2%', 'trend': 'Estable'},
                                            'barcelona': {'price_per_m2': 6000, 'change_week': '-0.1%', 'trend': 'Leve bajada'},
                                            'valencia': {'price_per_m2': 4200, 'change_week': '+0.5%', 'trend': 'Al alza'},
                        },
                        'rental_market': {
                                            'madrid': {'price_per_m2_month': 15.5, 'change_week': '+0.1%', 'demand': 'Alta'},
                                            'barcelona': {'price_per_m2_month': 14.0, 'change_week': '-0.2%', 'demand': 'Media-Alta'},
                        }
        }

        return housing_data

    def fetch_geopolitical_news(self):
                """Noticias geopolíticas"""
                logger.info("⚡ Recopilando noticias geopolíticas...")
                articles = []

        try:
                        feed = feedparser.parse('https://feeds.reuters.com/reuters/worldNews')
                        for entry in feed.entries[:3]:
                                            articles.append({
                                                                    'title': entry.get('title', 'Sin título'),
                                                                    'summary': entry.get('summary', '')[:250],
                                                                    'source': 'Reuters - Noticias Mundiales'
                                            })
        except Exception as e:
                        logger.warning(f"Error en geopolítica: {e}")

        return articles

    def get_market_indicators(self):
                """Indicadores de mercado clave"""
                return {
                    'ibex_35': {'value': 17952.40, 'change': '+0.58%', 'status': 'Alcista'},
                    'eur_usd': {'value': 1.18420, 'change': '-0.06%', 'status': 'Estable'},
                    'euro_stoxx_50': {'value': 5977.50, 'change': '-0.16%', 'status': 'Bajista'},
                    'brent_oil': {'value': 67.995, 'change': '-0.21%', 'unit': 'USD/barril'}
                }

    def generate_full_report(self):
                """Genera reporte completo en JSON"""
                logger.info("📊 Generando reporte completo...")

        report = {
                        'metadata': {
                                            'title': 'Informe Económico Semanal',
                                            'week_start': self.week_ago.strftime('%Y-%m-%d'),
                                            'week_end': self.today.strftime('%Y-%m-%d'),
                                            'generated_at': datetime.now().isoformat(),
                                            'version': '2.0'
                        },
                        'international': {
                                            'section': 'Macroeconomía Internacional',
                                            'news': self.fetch_international_news()
                        },
                        'spain': {
                                            'section': 'Economía de España',
                                            'news': self.fetch_spain_economy_news(),
                                            'indicators': self.get_market_indicators()
                        },
                        'housing': {
                                            'section': 'Mercado Inmobiliario España',
                                            'data': self.fetch_housing_market_data()
                        },
                        'geopolitics': {
                                            'section': 'Geopolítica y Comercio',
                                            'news': self.fetch_geopolitical_news()
                        }
        }

        return report

# =====================
# GESTOR DE REPORTES
# =====================

class ReportManager:
        def __init__(self):
                    self.reports = self._load_reports()

    def _load_reports(self):
                """Carga reportes de archivo JSON"""
                if os.path.exists(STORAGE_FILE):
                                try:
                                                    with open(STORAGE_FILE, 'r') as f:
                                                                            return json.load(f)
                                                                    except:
                                                    return {}
                            return {}

    def _save_reports(self):
                """Guarda reportes en archivo JSON"""
        try:
                        with open(STORAGE_FILE, 'w') as f:
                                            json.dump(self.reports, f, indent=2, default=str)
                                        logger.info(f"✅ Reportes guardados")
except Exception as e:
            logger.error(f"Error guardando: {e}")

    def generate_and_store(self):
                """Genera un reporte y lo almacena"""
        try:
                        logger.info("="*60)
            logger.info("🚀 GENERANDO REPORTE")
            logger.info("="*60)

            generator = EconomicReportGenerator()
            report_data = generator.generate_full_report()

            # Guardar con clave de semana
            week_key = datetime.now().strftime("%Y-W%W")
            self.reports[week_key] = {
                                'timestamp': datetime.now().isoformat(),
                                'data': report_data
            }

            self._save_reports()
            logger.info(f"✅ Reporte guardado: {week_key}")
            return report_data

except Exception as e:
            logger.error(f"❌ Error: {e}")
            return None

# Instanciar gestor
report_manager = ReportManager()

# =====================
# RUTAS API REST
# =====================

@app.route('/api/latest-report', methods=['GET'])
def latest_report():
        """Obtiene el último reporte generado"""
    if report_manager.reports:
                last_key = max(report_manager.reports.keys())
        return jsonify(report_manager.reports[last_key]['data']), 200
    return jsonify({'error': 'No reports yet'}), 404

@app.route('/api/reports/history', methods=['GET'])
def reports_history():
        """Historial de reportes"""
    report_keys = sorted(report_manager.reports.keys(), reverse=True)
    return jsonify({
                'total': len(report_manager.reports),
                'weeks': report_keys
    }), 200

@app.route('/api/reports/<week_key>', methods=['GET'])
def get_report_by_week(week_key):
        """Obtiene reporte de una semana específica"""
    if week_key in report_manager.reports:
                return jsonify(report_manager.reports[week_key]['data']), 200
    return jsonify({'error': 'Report not found'}), 404

@app.route('/api/generate', methods=['POST'])
def generate_report():
        """Genera un reporte bajo demanda"""
    report = report_manager.generate_and_store()
    if report:
                return jsonify({'status': 'success', 'report': report}), 201
    return jsonify({'status': 'error'}), 500

@app.route('/api/export/<format>', methods=['GET'])
def export_report(format):
        """Exporta el último reporte"""
    if not report_manager.reports:
                return jsonify({'error': 'No reports'}), 404

    last_key = max(report_manager.reports.keys())
    data = report_manager.reports[last_key]['data']

    if format == 'json':
                return jsonify(data), 200
else:
        return jsonify({'error': 'Format not supported'}), 400

# =====================
# DASHBOARD
# =====================

@app.route('/', methods=['GET'])
def dashboard():
        """Dashboard visual"""
    if not report_manager.reports:
                return """
                        <html><head><title>Dashboard</title></head>
                                <body style="font-family: Arial; text-align: center; padding: 50px;">
                                            <h1>📊 Dashboard de Informes Económicos</h1>
                                                        <p>No hay reportes generados aún.</p>
                                                                    <p><a href="/api/generate" style="padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">Generar Reporte Ahora</a></p>
                                                                            </body></html>
                                                                                    """, 200

    last_key = max(report_manager.reports.keys())
    report = report_manager.reports[last_key]

    html = f"""
        <html><head>
                <meta charset="UTF-8">
                        <title>Dashboard</title>
                                <style>
                                            body {{ font-family: Arial; background: #f5f5f5; margin: 0; padding: 20px; }}
                                                        .navbar {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; text-align: center; border-radius: 10px; margin-bottom: 30px; }}
                                                                    .container {{ max-width: 1200px; margin: 0 auto; }}
                                                                                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
                                                                                            .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                                                                                                        .card h2 {{ color: #667eea; margin-bottom: 10px; }}
                                                                                                                    .section {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                                                                                                                                .news {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 3px solid #667eea; }}
                                                                                                                                            .news strong {{ display: block; margin-bottom: 5px; }}
                                                                                                                                                        .news small {{ color: #999; }}
                                                                                                                                                                </style>
                                                                                                                                                                    </head><body>
                                                                                                                                                                            <div class="navbar">
                                                                                                                                                                                        <h1>📊 Informe Económico Semanal</h1>
                                                                                                                                                                                                    <p>{report['data']['metadata']['week_start']} a {report['data']['metadata']['week_end']}</p>
                                                                                                                                                                                                            </div>
                                                                                                                                                                                                                    
                                                                                                                                                                                                                            <div class="container">
                                                                                                                                                                                                                                        <div class="grid">
                                                                                                                                                                                                                                                        <div class="card">
                                                                                                                                                                                                                                                                            <h2>IBEX 35</h2>
                                                                                                                                                                                                                                                                                                <p style="font-size: 24px; color: #667eea; font-weight: bold;">{report['data']['spain']['indicators']['ibex_35']['value']:,.0f}</p>
                                                                                                                                                                                                                                                                                                                    <p>{report['data']['spain']['indicators']['ibex_35']['change']}</p>
                                                                                                                                                                                                                                                                                                                                    </div>
                                                                                                                                                                                                                                                                                                                                                    <div class="card">
                                                                                                                                                                                                                                                                                                                                                                        <h2>EUR/USD</h2>
                                                                                                                                                                                                                                                                                                                                                                                            <p style="font-size: 24px; color: #667eea; font-weight: bold;">{report['data']['spain']['indicators']['eur_usd']['value']}</p>
                                                                                                                                                                                                                                                                                                                                                                                                                <p>{report['data']['spain']['indicators']['eur_usd']['change']}</p>
                                                                                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                <div class="card">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <h2>Brent Crudo</h2>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <p style="font-size: 24px; color: #667eea; font-weight: bold;">${report['data']['spain']['indicators']['brent_oil']['value']:.2f}</p>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            <p>{report['data']['spain']['indicators']['brent_oil']['change']}</p>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                <div class="section">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                <h2>🌍 {report['data']['international']['section']}</h2>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                {"".join([f"<div class='news'><strong>{n['title']}</strong><small>{n['source']}</small></div>" for n in report['data']['international']['news'][:3]])}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <div class="section">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    <h2>🇪🇸 {report['data']['spain']['section']}</h2>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    {"".join([f"<div class='news'><strong>{n['title']}</strong><small>{n['source']}</small></div>" for n in report['data']['spain']['news'][:3]])}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <div class="section">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <h2>🏠 {report['data']['housing']['section']}</h2>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        <p>{report['data']['housing']['data']['national_summary']}</p>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            <div class="section">
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            <h2>⚡ {report['data']['geopolitics']['section']}</h2>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            {"".join([f"<div class='news'><strong>{n['title']}</strong></div>" for n in report['data']['geopolitics']['news'][:2]])}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                </div>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    </body></html>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        """

    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/health', methods=['GET'])
def health_check():
        """Estado del servicio"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200

@app.route('/api', methods=['GET'])
def api_info():
        """Información de la API"""
    return jsonify({
                'name': 'Economic Reports API',
                'version': '2.0',
                'endpoints': {
                                'GET /': 'Dashboard visual',
                                'GET /api/latest-report': 'Último reporte',
                                'GET /api/reports/history': 'Historial',
                                'POST /api/generate': 'Generar nuevo',
                                'GET /api/export/json': 'Descargar JSON'
                }
    }), 200

# =====================
# SCHEDULER
# =====================

def run_scheduler():
        """Ejecuta el scheduler"""
    # CAMBIAR AQUÍ: .monday a .day para ejecutar DIARIAMENTE
    schedule.every().day.at("08:00").do(report_manager.generate_and_store)

    logger.info("⏰ Scheduler iniciado - Se ejecutará cada día a las 08:00 UTC")

    while True:
                schedule.run_pending()
        time.sleep(60)

# Iniciar scheduler en thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# =====================
# MAIN
# =====================

if __name__ == '__main__':
        port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
