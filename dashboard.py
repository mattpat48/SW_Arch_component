from flask import Flask, render_template, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = "city_data.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_latest_data(table, limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_stats(table, column):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT AVG({column}) as avg, MIN({column}) as min, MAX({column}) as max, COUNT(*) as count FROM {table}")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

def get_counts_by_status(table, status_column):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {status_column}, COUNT(*) as count FROM {table} GROUP BY {status_column}")
    rows = cursor.fetchall()
    conn.close()
    return {row[status_column]: row['count'] for row in rows}

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/traffic')
def api_traffic():
    data = get_latest_data('traffic_state', 100)
    stats = get_stats('traffic_state', 'average_speed')
    congestion_counts = get_counts_by_status('traffic_state', 'congestion_level')
    return jsonify({
        'data': data,
        'stats': stats,
        'congestion_distribution': congestion_counts
    })

@app.route('/api/infrastructure')
def api_infrastructure():
    data = get_latest_data('infrastructure_status', 100)
    capacity_stats = get_stats('infrastructure_status', 'capacity_percentage')
    vibration_stats = get_stats('infrastructure_status', 'vibration_level')
    status_counts = get_counts_by_status('infrastructure_status', 'status')
    return jsonify({
        'data': data,
        'capacity_stats': capacity_stats,
        'vibration_stats': vibration_stats,
        'status_distribution': status_counts
    })

@app.route('/api/services')
def api_services():
    data = get_latest_data('service_accessibility', 100)
    access_time_stats = get_stats('service_accessibility', 'estimated_access_time')
    capacity_stats = get_stats('service_accessibility', 'capacity_percentage')
    status_counts = get_counts_by_status('service_accessibility', 'accessibility_status')
    return jsonify({
        'data': data,
        'access_time_stats': access_time_stats,
        'capacity_stats': capacity_stats,
        'status_distribution': status_counts
    })

@app.route('/api/environment')
def api_environment():
    data = get_latest_data('environmental_conditions', 100)
    return jsonify({
        'data': data,
        'temperature_stats': get_stats('environmental_conditions', 'temperature_celsius'),
        'humidity_stats': get_stats('environmental_conditions', 'humidity_percentage'),
        'wind_stats': get_stats('environmental_conditions', 'wind_speed_kmh'),
        'rainfall_stats': get_stats('environmental_conditions', 'rainfall_mm')
    })

@app.route('/api/system')
def api_system():
    data = get_latest_data('system_health', 100)
    latency_stats = get_stats('system_health', 'latency_ms')
    error_stats = get_stats('system_health', 'error_rate_percentage')
    status_counts = get_counts_by_status('system_health', 'health_status')
    return jsonify({
        'data': data,
        'latency_stats': latency_stats,
        'error_stats': error_stats,
        'status_distribution': status_counts
    })

@app.route('/api/overview')
def api_overview():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tables = ['traffic_state', 'infrastructure_status', 'service_accessibility', 
              'environmental_conditions', 'system_health']
    
    counts = {}
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
        counts[table] = cursor.fetchone()['count']
    
    conn.close()
    
    return jsonify({
        'total_records': counts,
        'last_update': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
