"""
Load Testing Module for UDiTE Smart City System
================================================
Genera ~100.000 eventi in 1 minuto per verificare la scalabilità del sistema.
"""

import time
import json
import random
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import paho.mqtt.client as mqtt

# ==========================
# CONFIG
# ==========================
BROKER = "localhost"
PORT = 1883
BASE_TOPIC = "UDiTE/city/data/get"

# Test parameters: 100.000 eventi in 1 minuto (60 secondi)
# = ~1667 eventi/secondo
DEFAULT_TARGET_EVENTS = 100000
DEFAULT_DURATION_SECONDS = 60  # 1 minuto
NUM_SENDER_THREADS = 8  # Thread paralleli per invio

# ==========================
# DATA CLASSES
# ==========================
@dataclass
class LoadTestResult:
    """Risultati del load test"""
    start_time: str
    end_time: str
    duration_seconds: float
    target_events: int
    events_sent: int
    events_per_second: float
    events_per_minute: float
    success_rate: float
    errors: int
    status: str  # "PASSED" or "FAILED"
    details: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": round(self.duration_seconds, 2),
            "target_events": self.target_events,
            "events_sent": self.events_sent,
            "events_per_second": round(self.events_per_second, 2),
            "events_per_minute": round(self.events_per_minute, 2),
            "success_rate": round(self.success_rate, 2),
            "errors": self.errors,
            "status": self.status,
            "details": self.details
        }


@dataclass
class LoadTestState:
    """Stato corrente del load test"""
    is_running: bool = False
    progress: float = 0.0
    events_sent: int = 0
    elapsed_seconds: float = 0.0
    errors: int = 0
    current_rate: float = 0.0
    result: Optional[LoadTestResult] = None


# Stato globale del test
_test_state = LoadTestState()
_state_lock = threading.Lock()


# ==========================
# PAYLOAD GENERATORS
# ==========================
def rand_range(min_v, max_v, decimals=2):
    return round(random.uniform(min_v, max_v), decimals)

def rand_enum(values):
    return random.choice(values)

def generate_traffic_state():
    return {
        "event_type": "traffic_state",
        "timestamp": datetime.now().isoformat(),
        "location": {
            "id": f"road-{random.randint(1, 100)}",
            "district": f"D{random.randint(1, 10)}"
        },
        "t_metrics": {
            "congestion_level": rand_enum(["LOW", "MODERATE", "HIGH", "CRITICAL"]),
            "average_speed": rand_range(0, 200)
        }
    }

def generate_infrastructure_status():
    return {
        "event_type": "infrastructure_status",
        "timestamp": datetime.now().isoformat(),
        "infrastructure": {
            "id": f"infra-{random.randint(1, 50)}",
            "type": rand_enum(["BRIDGE", "TUNNEL", "POWER_GRID"])
        },
        "status": rand_enum(["OPERATIONAL", "MAINTENANCE", "WARNING", "CRITICAL"]),
        "i_metrics": {
            "capacity_percentage": rand_range(0, 100),
            "vibration_level": rand_range(0, 100)
        }
    }

def generate_service_accessibility():
    return {
        "event_type": "service_accessibility",
        "timestamp": datetime.now().isoformat(),
        "service": {
            "id": f"service-{random.randint(1, 30)}",
            "type": rand_enum(["HOSPITAL", "SCHOOL", "SUPERMARKET"])
        },
        "accessibility": {
            "status": rand_enum(["AVAILABLE", "FULL", "CLOSED"]),
            "estimated_access_time": rand_range(0, 300),
            "capacity_percentage": rand_range(0, 100)
        }
    }

def generate_environmental_conditions():
    return {
        "event_type": "environmental_conditions",
        "timestamp": datetime.now().isoformat(),
        "location": {
            "id": f"station-{random.randint(1, 20)}",
            "district": f"D{random.randint(1, 10)}"
        },
        "e_metrics": {
            "rainfall_mm": rand_range(0, 1000),
            "wind_speed_kmh": rand_range(0, 300),
            "temperature_celsius": rand_range(-50, 60),
            "humidity_percentage": rand_range(0, 100)
        }
    }

def generate_system_health():
    return {
        "event_type": "system_health",
        "timestamp": datetime.now().isoformat(),
        "component": {
            "id": f"comp-{random.randint(1, 40)}",
            "type": rand_enum(["API", "DB", "BROKER", "EDGE_NODE"])
        },
        "health": {
            "status": rand_enum(["HEALTHY", "DEGRADED", "FAILURE"]),
            "latency_ms": rand_range(0, 10000),
            "error_rate_percentage": rand_range(0, 100)
        }
    }

# Lista dei generatori e topic
GENERATORS = [
    ("urbanViability", generate_traffic_state),
    ("criticalInfrastructure", generate_infrastructure_status),
    ("essentialsAccessibility", generate_service_accessibility),
    ("environmentQuality", generate_environmental_conditions),
    ("metaSensors", generate_system_health)
]


# ==========================
# LOAD TEST FUNCTIONS
# ==========================
def get_test_state() -> dict:
    """Ottieni lo stato corrente del test"""
    with _state_lock:
        return {
            "is_running": _test_state.is_running,
            "progress": round(_test_state.progress, 1),
            "events_sent": _test_state.events_sent,
            "elapsed_seconds": round(_test_state.elapsed_seconds, 1),
            "errors": _test_state.errors,
            "current_rate": round(_test_state.current_rate, 1),
            "result": _test_state.result.to_dict() if _test_state.result else None
        }


def is_test_running() -> bool:
    """Controlla se un test è in esecuzione"""
    with _state_lock:
        return _test_state.is_running


def _update_state(**kwargs):
    """Aggiorna lo stato del test in modo thread-safe"""
    with _state_lock:
        for key, value in kwargs.items():
            if hasattr(_test_state, key):
                setattr(_test_state, key, value)


def run_load_test(
    target_events: int = DEFAULT_TARGET_EVENTS,
    duration_seconds: int = DEFAULT_DURATION_SECONDS
) -> LoadTestResult:
    """
    Esegue il load test.
    
    Args:
        target_events: Numero di eventi da inviare (default: 100.000)
        duration_seconds: Durata del test in secondi (default: 300 = 5 minuti)
    
    Returns:
        LoadTestResult con i risultati del test
    """
    global _test_state
    
    # Check se già in esecuzione
    if is_test_running():
        raise RuntimeError("Un load test è già in esecuzione")
    
    # Reset stato
    _update_state(
        is_running=True,
        progress=0.0,
        events_sent=0,
        elapsed_seconds=0.0,
        errors=0,
        current_rate=0.0,
        result=None
    )
    
    # Calcola rate target
    events_per_second = target_events / duration_seconds
    # Batch più grandi per alto throughput, sleep minimo
    batch_size = max(10, int(events_per_second / 100) + 1)
    # Per alti volumi, niente sleep - invia il più veloce possibile
    use_throttle = events_per_second < 500
    sleep_interval = 0.01 if use_throttle else 0.001  # 1ms per alto throughput
    
    # Connessione MQTT
    client = mqtt.Client(client_id=f"udite-loadtest-{int(time.time())}")
    
    errors = 0
    events_sent = 0
    events_by_type = {gen[0]: 0 for gen in GENERATORS}
    
    start_time = datetime.now()
    start_timestamp = time.time()
    
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
    except Exception as e:
        _update_state(is_running=False, errors=1)
        return LoadTestResult(
            start_time=start_time.isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=0,
            target_events=target_events,
            events_sent=0,
            events_per_second=0,
            events_per_minute=0,
            success_rate=0,
            errors=1,
            status="FAILED",
            details={"error": f"Impossibile connettersi al broker MQTT: {str(e)}"}
        )
    
    print(f"\n{'='*60}")
    print(f"LOAD TEST AVVIATO")
    print(f"Target: {target_events:,} eventi in {duration_seconds}s")
    print(f"Rate target: {events_per_second:.1f} eventi/secondo")
    print(f"{'='*60}\n")
    
    # Pre-genera cache di payload per massimo throughput
    print("Pre-generazione cache payload...")
    payload_cache = {}
    cache_size = min(1000, target_events // 5)  # Cache di payload pre-generati
    for topic_suffix, generator in GENERATORS:
        payload_cache[topic_suffix] = [json.dumps(generator()) for _ in range(cache_size)]
    print(f"Cache generata: {cache_size} payload per tipo")
    
    try:
        generator_index = 0
        last_progress_update = 0
        cache_indices = {topic_suffix: 0 for topic_suffix, _ in GENERATORS}
        
        while True:
            current_time = time.time()
            elapsed = current_time - start_timestamp
            
            # Controllo fine test
            if elapsed >= duration_seconds or events_sent >= target_events:
                break
            
            # Invio batch di eventi
            for _ in range(batch_size):
                if events_sent >= target_events:
                    break
                
                # Seleziona generatore (round-robin)
                topic_suffix, _ = GENERATORS[generator_index % len(GENERATORS)]
                generator_index += 1
                
                topic = f"{BASE_TOPIC}/{topic_suffix}"
                
                # Usa payload dalla cache (ciclico)
                cache_idx = cache_indices[topic_suffix]
                payload_str = payload_cache[topic_suffix][cache_idx % cache_size]
                cache_indices[topic_suffix] = cache_idx + 1
                
                try:
                    result = client.publish(topic, payload_str)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        events_sent += 1
                        events_by_type[topic_suffix] += 1
                    else:
                        errors += 1
                except Exception as e:
                    errors += 1
                
            # Aggiorna stato
            elapsed = time.time() - start_timestamp
            progress = min(100.0, (elapsed / duration_seconds) * 100)
            current_rate = events_sent / max(0.1, elapsed)
            
            _update_state(
                progress=progress,
                events_sent=events_sent,
                elapsed_seconds=elapsed,
                errors=errors,
                current_rate=current_rate
            )
            
            # Log progress ogni 10%
            if int(progress / 10) > last_progress_update:
                last_progress_update = int(progress / 10)
                print(f"[{int(progress):3d}%] Eventi: {events_sent:,} | Rate: {current_rate:.1f}/s | Errori: {errors}")
            
            # Sleep per mantenere il rate
            time.sleep(sleep_interval)
            
    except Exception as e:
        errors += 1
        print(f"Errore durante il test: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
    
    # Calcola risultati finali
    end_time = datetime.now()
    total_duration = time.time() - start_timestamp
    final_rate = events_sent / max(0.1, total_duration)
    success_rate = (events_sent / target_events) * 100 if target_events > 0 else 0
    
    # Determina status
    # PASSED se abbiamo inviato almeno il 95% degli eventi target
    status = "PASSED" if success_rate >= 95 else "FAILED"
    
    result = LoadTestResult(
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        duration_seconds=total_duration,
        target_events=target_events,
        events_sent=events_sent,
        events_per_second=final_rate,
        events_per_minute=final_rate * 60,
        success_rate=success_rate,
        errors=errors,
        status=status,
        details={
            "events_by_type": events_by_type,
            "batch_size": batch_size,
            "target_rate_per_second": events_per_second,
            "achieved_rate_per_second": final_rate,
            "test_config": {
                "target_events": target_events,
                "duration_seconds": duration_seconds,
                "broker": BROKER,
                "port": PORT
            }
        }
    )
    
    _update_state(
        is_running=False,
        progress=100.0,
        events_sent=events_sent,
        elapsed_seconds=total_duration,
        errors=errors,
        current_rate=final_rate,
        result=result
    )
    
    # Stampa report finale
    print(f"\n{'='*60}")
    print(f"LOAD TEST COMPLETATO - {status}")
    print(f"{'='*60}")
    print(f"Durata totale: {total_duration:.2f} secondi")
    print(f"Eventi target: {target_events:,}")
    print(f"Eventi inviati: {events_sent:,}")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Rate medio: {final_rate:.1f} eventi/secondo")
    print(f"Rate medio: {final_rate * 60:.0f} eventi/minuto")
    print(f"Errori: {errors}")
    print(f"\nEventi per tipo:")
    for event_type, count in events_by_type.items():
        print(f"  - {event_type}: {count:,}")
    print(f"{'='*60}\n")
    
    return result


def start_load_test_async(
    target_events: int = DEFAULT_TARGET_EVENTS,
    duration_seconds: int = DEFAULT_DURATION_SECONDS
) -> bool:
    """
    Avvia il load test in un thread separato.
    
    Returns:
        True se il test è stato avviato, False se già in esecuzione
    """
    if is_test_running():
        return False
    
    thread = threading.Thread(
        target=run_load_test,
        args=(target_events, duration_seconds),
        daemon=True
    )
    thread.start()
    return True


# ==========================
# MAIN (per test standalone)
# ==========================
if __name__ == "__main__":
    print("Avvio load test standalone...")
    result = run_load_test()
    print("\nRisultato JSON:")
    print(json.dumps(result.to_dict(), indent=2))
