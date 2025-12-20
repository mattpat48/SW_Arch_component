import time
import json
import random
from datetime import datetime
import paho.mqtt.client as mqtt

# ==========================
# CONFIG
# ==========================
BROKER = "localhost"
PORT = 1883
CITY = "city"
BASE_TOPIC = f"UDiTE/{CITY}/data/get"

PUBLISH_INTERVAL = 5  # seconds

# ==========================
# HELPERS
# ==========================
def rand_range(min_v, max_v, decimals=2):
    return round(random.uniform(min_v, max_v), decimals)

def rand_enum(values):
    return random.choice(values)

# ==========================
# PAYLOAD GENERATORS
# ==========================
def traffic_state():
    return {
        "event_type": "traffic_state",
        "timestamp": datetime.now().isoformat(),
        "location": {
            "id": f"road-{random.randint(1,100)}",
            "district": f"D{random.randint(1,10)}"
        },
        "t_metrics": {
            "congestion_level": rand_enum(["LOW", "MODERATE", "HIGH", "CRITICAL"]),
            "average_speed": rand_range(0, 200)
        }
    }

def infrastructure_status():
    return {
        "event_type": "infrastructure_status",
        "timestamp": datetime.now().isoformat(),
        "infrastructure": {
            "id": f"infra-{random.randint(1,50)}",
            "type": rand_enum(["BRIDGE", "TUNNEL", "POWER_GRID"])
        },
        "status": rand_enum(["OPERATIONAL", "MAINTENANCE", "WARNING", "CRITICAL"]),
        "i_metrics": {
            "capacity_percentage": rand_range(0, 100),
            "vibration_level": rand_range(0, 100)
        }
    }

def service_accessibility():
    return {
        "event_type": "service_accessibility",
        "timestamp": datetime.now().isoformat(),
        "service": {
            "id": f"service-{random.randint(1,30)}",
            "type": rand_enum(["HOSPITAL", "SCHOOL", "SUPERMARKET"])
        },
        "accessibility": {
            "status": rand_enum(["AVAILABLE", "FULL", "CLOSED"]),
            "estimated_access_time": rand_range(0, 300),
            "capacity_percentage": rand_range(0, 100)
        }
    }

def environmental_conditions():
    return {
        "event_type": "environmental_conditions",
        "timestamp": datetime.now().isoformat(),
        "location": {
            "id": f"station-{random.randint(1,20)}",
            "district": f"D{random.randint(1,10)}"
        },
        "e_metrics": {
            "rainfall_mm": rand_range(0, 1000),
            "wind_speed_kmh": rand_range(0, 300),
            "temperature_celsius": rand_range(-50, 60),
            "humidity_percentage": rand_range(0, 100)
        }
    }

def system_health():
    return {
        "event_type": "system_health",
        "timestamp": datetime.now().isoformat(),
        "component": {
            "id": f"comp-{random.randint(1,40)}",
            "type": rand_enum(["API", "DB", "BROKER", "EDGE_NODE"])
        },
        "health": {
            "status": rand_enum(["HEALTHY", "DEGRADED", "FAILURE"]),
            "latency_ms": rand_range(0, 10000),
            "error_rate_percentage": rand_range(0, 100)
        }
    }

# ==========================
# MQTT SETUP
# ==========================
client = mqtt.Client(client_id="udite-random-generator")
client.connect(BROKER, PORT, 60)

TOPICS = {
    "urbanViability": traffic_state,
    "criticalInfrastructure": infrastructure_status,
    "essentialsAccessibility": service_accessibility,
    "environmentQuality": environmental_conditions,
    "metaSensors": system_health
}

print("UDiTE MQTT generator started...")

# ==========================
# MAIN LOOP
# ==========================
while True:
    for topic_suffix, generator in TOPICS.items():
        topic = f"{BASE_TOPIC}/{topic_suffix}"
        print(f"Generating data for topic: {topic}")
        payload = generator()

        client.publish(topic, json.dumps(payload))
        print(f"Published to {topic}")

    time.sleep(PUBLISH_INTERVAL)

