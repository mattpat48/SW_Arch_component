"""
Impact Simulation Test Module for UDiTE Smart City System
==========================================================
Simula emergenze stradali (congestione/chiusura) e misura il tempo di risposta
del sistema per calcolare percorsi alternativi.

Requisito: max 5-10 secondi di delay per gli aggiornamenti della simulazione.
"""

import time
import json
import random
import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import paho.mqtt.client as mqtt

# ==========================
# CONFIG
# ==========================
BROKER = "localhost"
PORT = 1883
BASE_TOPIC = "UDiTE/city/data/get/urbanViability"
ALERT_TOPIC = "UDiTE/city/alert"

# Requisito temporale massimo (secondi)
MAX_ACCEPTABLE_DELAY = 10.0
TARGET_DELAY = 5.0

# ==========================
# CITY ROAD NETWORK MODEL
# ==========================
# Simuliamo una rete stradale con 10 distretti, ognuno con 10 strade
# Le strade vicine sono quelle nello stesso distretto o in distretti adiacenti

DISTRICTS = [f"D{i}" for i in range(1, 11)]
ROADS_PER_DISTRICT = 10

# Mappa di adiacenza tra distretti (griglia 2x5)
# D1-D2-D3-D4-D5
# D6-D7-D8-D9-D10
DISTRICT_ADJACENCY = {
    "D1": ["D2", "D6"],
    "D2": ["D1", "D3", "D7"],
    "D3": ["D2", "D4", "D8"],
    "D4": ["D3", "D5", "D9"],
    "D5": ["D4", "D10"],
    "D6": ["D1", "D7"],
    "D7": ["D6", "D8", "D2"],
    "D8": ["D7", "D9", "D3"],
    "D9": ["D8", "D10", "D4"],
    "D10": ["D9", "D5"]
}


def get_all_roads() -> List[Dict]:
    """Genera tutte le strade della città"""
    roads = []
    for district in DISTRICTS:
        for i in range(1, ROADS_PER_DISTRICT + 1):
            roads.append({
                "id": f"road-{district}-{i}",
                "district": district,
                "name": f"Via {district}-{i}"
            })
    return roads


def get_adjacent_roads(road_id: str, district: str) -> List[str]:
    """Trova le strade adiacenti (stesso distretto + distretti vicini)"""
    adjacent = []
    
    # Strade nello stesso distretto
    for i in range(1, ROADS_PER_DISTRICT + 1):
        adj_id = f"road-{district}-{i}"
        if adj_id != road_id:
            adjacent.append(adj_id)
    
    # Strade nei distretti adiacenti
    for adj_district in DISTRICT_ADJACENCY.get(district, []):
        for i in range(1, ROADS_PER_DISTRICT + 1):
            adjacent.append(f"road-{adj_district}-{i}")
    
    return adjacent


# ==========================
# DATA CLASSES
# ==========================
@dataclass
class RoadStatus:
    """Stato di una strada"""
    road_id: str
    district: str
    congestion_level: str  # LOW, MODERATE, HIGH, CRITICAL
    average_speed: float
    is_emergency: bool = False


@dataclass
class AlternativeRoute:
    """Percorso alternativo suggerito"""
    road_id: str
    district: str
    congestion_level: str
    average_speed: float
    distance_score: int  # 0 = stesso distretto, 1 = distretto adiacente


@dataclass
class EmergencyEvent:
    """Evento di emergenza (strada bloccata/congestionata)"""
    road_id: str
    district: str
    timestamp: str
    previous_status: str
    new_status: str = "CRITICAL"


@dataclass
class SimulationResult:
    """Risultati della simulazione"""
    start_time: str
    end_time: str
    
    # Timing breakdown (in millisecondi)
    total_time_ms: float
    event_generation_ms: float
    mqtt_publish_ms: float
    route_calculation_ms: float
    response_generation_ms: float
    
    # Dati emergenza
    roads_affected: int
    emergency_events: List[Dict]
    
    # Percorsi alternativi
    alternatives_found: int
    alternative_routes: List[Dict]
    
    # Verifica requisito
    requirement_met: bool
    max_delay_seconds: float
    
    def to_dict(self):
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "timing": {
                "total_ms": round(self.total_time_ms, 2),
                "total_seconds": round(self.total_time_ms / 1000, 3),
                "breakdown": {
                    "event_generation_ms": round(self.event_generation_ms, 2),
                    "mqtt_publish_ms": round(self.mqtt_publish_ms, 2),
                    "route_calculation_ms": round(self.route_calculation_ms, 2),
                    "response_generation_ms": round(self.response_generation_ms, 2)
                }
            },
            "emergency": {
                "roads_affected": self.roads_affected,
                "events": self.emergency_events
            },
            "alternatives": {
                "routes_found": self.alternatives_found,
                "routes": self.alternative_routes
            },
            "verification": {
                "requirement_met": self.requirement_met,
                "max_allowed_delay_s": self.max_delay_seconds,
                "actual_delay_s": round(self.total_time_ms / 1000, 3),
                "status": "PASSED ✓" if self.requirement_met else "FAILED ✗",
                "margin_ms": round((self.max_delay_seconds * 1000) - self.total_time_ms, 2)
            }
        }


@dataclass
class SimulationState:
    """Stato corrente della simulazione"""
    is_running: bool = False
    result: Optional[SimulationResult] = None


# Stato globale
_simulation_state = SimulationState()
_state_lock = threading.Lock()

# Stato corrente delle strade (simulato)
_road_states: Dict[str, RoadStatus] = {}
_road_states_lock = threading.Lock()


def _init_road_states():
    """Inizializza lo stato delle strade con valori casuali normali"""
    global _road_states
    with _road_states_lock:
        _road_states.clear()
        for road in get_all_roads():
            # La maggior parte delle strade è in condizioni normali
            congestion = random.choices(
                ["LOW", "MODERATE", "HIGH", "CRITICAL"],
                weights=[50, 30, 15, 5]
            )[0]
            speed = {
                "LOW": random.uniform(60, 90),
                "MODERATE": random.uniform(40, 60),
                "HIGH": random.uniform(20, 40),
                "CRITICAL": random.uniform(0, 20)
            }[congestion]
            
            _road_states[road["id"]] = RoadStatus(
                road_id=road["id"],
                district=road["district"],
                congestion_level=congestion,
                average_speed=round(speed, 1),
                is_emergency=False
            )


def get_simulation_state() -> dict:
    """Ottieni lo stato corrente della simulazione"""
    with _state_lock:
        return {
            "is_running": _simulation_state.is_running,
            "result": _simulation_state.result.to_dict() if _simulation_state.result else None
        }


def is_simulation_running() -> bool:
    """Controlla se una simulazione è in esecuzione"""
    with _state_lock:
        return _simulation_state.is_running


def _update_state(**kwargs):
    """Aggiorna lo stato in modo thread-safe"""
    with _state_lock:
        for key, value in kwargs.items():
            if hasattr(_simulation_state, key):
                setattr(_simulation_state, key, value)


def run_impact_simulation(num_roads_to_block: int = None) -> SimulationResult:
    """
    Esegue la simulazione di impatto:
    1. Seleziona casualmente alcune strade da mettere in emergenza
    2. Pubblica gli eventi MQTT
    3. Calcola i percorsi alternativi
    4. Misura tutti i tempi
    
    Args:
        num_roads_to_block: Numero di strade da bloccare (default: random 2-5)
    
    Returns:
        SimulationResult con tutti i dettagli e tempi
    """
    global _simulation_state
    
    if is_simulation_running():
        raise RuntimeError("Una simulazione è già in esecuzione")
    
    _update_state(is_running=True, result=None)
    
    # Inizializza/resetta lo stato delle strade
    _init_road_states()
    
    # Numero casuale di strade da bloccare (2-5)
    if num_roads_to_block is None:
        num_roads_to_block = random.randint(2, 5)
    
    num_roads_to_block = max(1, min(10, num_roads_to_block))
    
    start_time = datetime.now()
    start_timestamp = time.perf_counter()
    
    timing = {
        "event_generation": 0,
        "mqtt_publish": 0,
        "route_calculation": 0,
        "response_generation": 0
    }
    
    emergency_events = []
    alternative_routes = []
    
    try:
        # ==========================
        # FASE 1: Generazione Eventi Emergenza
        # ==========================
        t1 = time.perf_counter()
        
        # Seleziona strade casuali da bloccare
        all_road_ids = list(_road_states.keys())
        roads_to_block = random.sample(all_road_ids, num_roads_to_block)
        
        for road_id in roads_to_block:
            with _road_states_lock:
                road = _road_states[road_id]
                previous_status = road.congestion_level
                
                # Crea evento emergenza
                event = EmergencyEvent(
                    road_id=road_id,
                    district=road.district,
                    timestamp=datetime.now().isoformat(),
                    previous_status=previous_status,
                    new_status="CRITICAL"
                )
                emergency_events.append({
                    "road_id": event.road_id,
                    "district": event.district,
                    "timestamp": event.timestamp,
                    "previous_status": event.previous_status,
                    "new_status": event.new_status
                })
                
                # Aggiorna stato strada
                road.congestion_level = "CRITICAL"
                road.average_speed = random.uniform(0, 5)
                road.is_emergency = True
        
        timing["event_generation"] = (time.perf_counter() - t1) * 1000
        
        # ==========================
        # FASE 2: Pubblicazione MQTT
        # ==========================
        t2 = time.perf_counter()
        
        try:
            client = mqtt.Client(client_id=f"udite-simulation-{int(time.time())}")
            client.connect(BROKER, PORT, 60)
            
            for event in emergency_events:
                # Pubblica evento traffico critico
                payload = {
                    "event_type": "traffic_state",
                    "timestamp": event["timestamp"],
                    "location": {
                        "id": event["road_id"],
                        "district": event["district"]
                    },
                    "t_metrics": {
                        "congestion_level": "CRITICAL",
                        "average_speed": random.uniform(0, 5)
                    },
                    "emergency": True,
                    "simulation_test": True
                }
                client.publish(BASE_TOPIC, json.dumps(payload))
                
                # Pubblica alert
                alert_payload = {
                    "type": "ROAD_CLOSURE",
                    "severity": "CRITICAL",
                    "timestamp": event["timestamp"],
                    "source": "simulation_test",
                    "affected_road": event["road_id"],
                    "district": event["district"],
                    "message": f"EMERGENZA: Strada {event['road_id']} in {event['district']} - Congestione critica"
                }
                client.publish(ALERT_TOPIC, json.dumps(alert_payload))
            
            client.disconnect()
        except Exception as e:
            print(f"Errore MQTT (non critico per il test): {e}")
        
        timing["mqtt_publish"] = (time.perf_counter() - t2) * 1000
        
        # ==========================
        # FASE 3: Calcolo Percorsi Alternativi
        # ==========================
        t3 = time.perf_counter()
        
        blocked_roads = set(roads_to_block)
        blocked_districts = set(e["district"] for e in emergency_events)
        
        for event in emergency_events:
            road_id = event["road_id"]
            district = event["district"]
            
            # Trova strade alternative
            adjacent_roads = get_adjacent_roads(road_id, district)
            
            candidates = []
            with _road_states_lock:
                for adj_road_id in adjacent_roads:
                    if adj_road_id in blocked_roads:
                        continue
                    
                    adj_road = _road_states.get(adj_road_id)
                    if adj_road and adj_road.congestion_level in ["LOW", "MODERATE"]:
                        # Calcola punteggio distanza
                        distance_score = 0 if adj_road.district == district else 1
                        
                        candidates.append(AlternativeRoute(
                            road_id=adj_road_id,
                            district=adj_road.district,
                            congestion_level=adj_road.congestion_level,
                            average_speed=adj_road.average_speed,
                            distance_score=distance_score
                        ))
            
            # Ordina per: distanza, poi congestione, poi velocità
            candidates.sort(key=lambda x: (
                x.distance_score,
                0 if x.congestion_level == "LOW" else 1,
                -x.average_speed
            ))
            
            # Prendi le migliori 3 alternative
            best_alternatives = candidates[:3]
            
            for alt in best_alternatives:
                alternative_routes.append({
                    "for_blocked_road": road_id,
                    "blocked_district": district,
                    "alternative_road": alt.road_id,
                    "alternative_district": alt.district,
                    "congestion_level": alt.congestion_level,
                    "average_speed": round(alt.average_speed, 1),
                    "distance": "same_district" if alt.distance_score == 0 else "adjacent_district"
                })
        
        timing["route_calculation"] = (time.perf_counter() - t3) * 1000
        
        # ==========================
        # FASE 4: Generazione Risposta
        # ==========================
        t4 = time.perf_counter()
        
        end_time = datetime.now()
        total_time_ms = (time.perf_counter() - start_timestamp) * 1000
        
        timing["response_generation"] = (time.perf_counter() - t4) * 1000
        
        # Verifica requisito temporale
        requirement_met = (total_time_ms / 1000) <= MAX_ACCEPTABLE_DELAY
        
        result = SimulationResult(
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            total_time_ms=total_time_ms,
            event_generation_ms=timing["event_generation"],
            mqtt_publish_ms=timing["mqtt_publish"],
            route_calculation_ms=timing["route_calculation"],
            response_generation_ms=timing["response_generation"],
            roads_affected=len(emergency_events),
            emergency_events=emergency_events,
            alternatives_found=len(alternative_routes),
            alternative_routes=alternative_routes,
            requirement_met=requirement_met,
            max_delay_seconds=MAX_ACCEPTABLE_DELAY
        )
        
        _update_state(is_running=False, result=result)
        
        # Log risultati
        print(f"\n{'='*60}")
        print(f"SIMULATION TEST COMPLETATO - {'PASSED ✓' if requirement_met else 'FAILED ✗'}")
        print(f"{'='*60}")
        print(f"Strade bloccate: {len(emergency_events)}")
        print(f"Alternative trovate: {len(alternative_routes)}")
        print(f"Tempo totale: {total_time_ms:.2f} ms ({total_time_ms/1000:.3f} s)")
        print(f"Requisito (max {MAX_ACCEPTABLE_DELAY}s): {'SODDISFATTO' if requirement_met else 'NON SODDISFATTO'}")
        print(f"\nBreakdown tempi:")
        print(f"  - Generazione eventi: {timing['event_generation']:.2f} ms")
        print(f"  - Pubblicazione MQTT: {timing['mqtt_publish']:.2f} ms")
        print(f"  - Calcolo percorsi: {timing['route_calculation']:.2f} ms")
        print(f"  - Generazione risposta: {timing['response_generation']:.2f} ms")
        print(f"{'='*60}\n")
        
        return result
        
    except Exception as e:
        _update_state(is_running=False)
        raise e


def start_simulation_async(num_roads: int = None) -> bool:
    """
    Avvia la simulazione in un thread separato.
    
    Returns:
        True se avviata, False se già in esecuzione
    """
    if is_simulation_running():
        return False
    
    thread = threading.Thread(
        target=run_impact_simulation,
        args=(num_roads,),
        daemon=True
    )
    thread.start()
    return True


# ==========================
# MAIN (per test standalone)
# ==========================
if __name__ == "__main__":
    print("Avvio simulation test standalone...")
    result = run_impact_simulation(3)
    print("\nRisultato JSON:")
    print(json.dumps(result.to_dict(), indent=2))
