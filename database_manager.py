import sqlite3
import threading
import time

class DatabaseManager:
    def __init__(self, db_name="city_data.db", batch_size=100, flush_interval=1.0):
        # check_same_thread=False allows using the connection across different threads (e.g. MQTT callbacks)
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
        
        # Batch commit configuration
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._pending_count = 0
        self._last_commit = time.time()
        self._lock = threading.Lock()
        
        # Start background flush thread
        self._stop_flush = False
        self._flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self._flush_thread.start()
    
    def _periodic_flush(self):
        """Background thread that commits periodically"""
        while not self._stop_flush:
            time.sleep(self._flush_interval)
            self._maybe_commit(force=True)
    
    def _maybe_commit(self, force=False):
        """Commit if batch size reached or forced"""
        with self._lock:
            should_commit = force or self._pending_count >= self._batch_size
            if should_commit and self._pending_count > 0:
                try:
                    self.conn.commit()
                    self._pending_count = 0
                    self._last_commit = time.time()
                except Exception as e:
                    print(f"Commit error: {e}")

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS traffic_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                location_id TEXT,
                location_district TEXT,
                congestion_level TEXT,
                average_speed REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS infrastructure_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                infrastructure_id TEXT,
                infrastructure_type TEXT,
                status TEXT,
                capacity_percentage REAL,
                vibration_level REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_accessibility (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                service_id TEXT,
                service_type TEXT,
                accessibility_status TEXT,
                estimated_access_time REAL,
                capacity_percentage REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS environmental_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                location_id TEXT,
                location_district TEXT,
                rainfall_mm REAL,
                wind_speed_kmh REAL,
                temperature_celsius REAL,
                humidity_percentage REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                component_id TEXT,
                component_type TEXT,
                health_status TEXT,
                latency_ms REAL,
                error_rate_percentage REAL
            )
        """)
        self.conn.commit()

    def save_event(self, payload):
        event_type = payload.get("event_type")
        try:
            if event_type == "traffic_state":
                self._insert_traffic_state(payload)
            elif event_type == "infrastructure_status":
                self._insert_infrastructure_status(payload)
            elif event_type == "service_accessibility":
                self._insert_service_accessibility(payload)
            elif event_type == "environmental_conditions":
                self._insert_environmental_conditions(payload)
            elif event_type == "system_health":
                self._insert_system_health(payload)
            else:
                print(f"Unknown event type for DB: {event_type}")
        except Exception as e:
            print(f"Error inserting {event_type}: {e}")

    def _insert_traffic_state(self, data):
        self.cursor.execute("INSERT INTO traffic_state (timestamp, location_id, location_district, congestion_level, average_speed) VALUES (?, ?, ?, ?, ?)",
            (data.get("timestamp"), data["location"].get("id"), data["location"].get("district"), data["t_metrics"].get("congestion_level"), data["t_metrics"].get("average_speed")))
        self._pending_count += 1
        self._maybe_commit()

    def _insert_infrastructure_status(self, data):
        self.cursor.execute("INSERT INTO infrastructure_status (timestamp, infrastructure_id, infrastructure_type, status, capacity_percentage, vibration_level) VALUES (?, ?, ?, ?, ?, ?)",
            (data.get("timestamp"), data["infrastructure"].get("id"), data["infrastructure"].get("type"), data.get("status"), data["i_metrics"].get("capacity_percentage"), data["i_metrics"].get("vibration_level")))
        self._pending_count += 1
        self._maybe_commit()

    def _insert_service_accessibility(self, data):
        self.cursor.execute("INSERT INTO service_accessibility (timestamp, service_id, service_type, accessibility_status, estimated_access_time, capacity_percentage) VALUES (?, ?, ?, ?, ?, ?)",
            (data.get("timestamp"), data["service"].get("id"), data["service"].get("type"), data["accessibility"].get("status"), data["accessibility"].get("estimated_access_time"), data["accessibility"].get("capacity_percentage")))
        self._pending_count += 1
        self._maybe_commit()

    def _insert_environmental_conditions(self, data):
        self.cursor.execute("INSERT INTO environmental_conditions (timestamp, location_id, location_district, rainfall_mm, wind_speed_kmh, temperature_celsius, humidity_percentage) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data.get("timestamp"), data["location"].get("id"), data["location"].get("district"), data["e_metrics"].get("rainfall_mm"), data["e_metrics"].get("wind_speed_kmh"), data["e_metrics"].get("temperature_celsius"), data["e_metrics"].get("humidity_percentage")))
        self._pending_count += 1
        self._maybe_commit()

    def _insert_system_health(self, data):
        self.cursor.execute("INSERT INTO system_health (timestamp, component_id, component_type, health_status, latency_ms, error_rate_percentage) VALUES (?, ?, ?, ?, ?, ?)",
            (data.get("timestamp"), data["component"].get("id"), data["component"].get("type"), data["health"].get("status"), data["health"].get("latency_ms"), data["health"].get("error_rate_percentage")))
        self._pending_count += 1
        self._maybe_commit()

    def close(self):
        self._stop_flush = True
        self._maybe_commit(force=True)  # Final commit
        self.conn.close()