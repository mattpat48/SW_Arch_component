import json
import paho.mqtt.client as mqtt
from collections import deque
import statistics

from database_manager import DatabaseManager
from data_structure import REQUIRED_FIELDS, REQUIRED_SUBFIELDS, DATA_CONSTRAINTS, ALERT_THRESHOLDS

# ==========================
# CONFIG
# ==========================
BROKER = "localhost"
PORT = 1883
CITY = "city"

BASE_TOPIC_GET = f"UDiTE/{CITY}/data/get"
BASE_TOPIC_POST = f"UDiTE/{CITY}/data/post"
ALERT_TOPIC = f"UDiTE/{CITY}/alert"

# Mapping: topic suffix -> source name for alerts
TOPICS = {
    "trafficSensor": "urbanViability",
    "criticalInfrastructure": "criticalInfrastructure",
    "essentialsAccessibility": "essentialsAccessibility",
    "environmentQuality": "environmentQuality",
    "metaSensors": "metaSensors"
}

# ==========================
# STATE
# ==========================
sensor_history = {}  # Key: "event_type:id", Value: deque(maxlen=20)
db = DatabaseManager()

# ==========================
# VALIDATION
# ==========================
def check_value(val, rule):
    if rule["type"] == "enum":
        if val not in rule["values"]:
            return False, f"Value '{val}' not in {rule['values']}"
    elif rule["type"] == "range":
        if not isinstance(val, (int, float)):
            return False, f"Value '{val}' is not a number"
        if not (rule["min"] <= val <= rule["max"]):
            return False, f"Value {val} out of range [{rule['min']}, {rule['max']}]"
    return True, ""


def check_data_coherence(payload):
    event_type = payload["event_type"]
    if event_type not in DATA_CONSTRAINTS:
        return True, "No constraints defined"

    constraints = DATA_CONSTRAINTS[event_type]
    
    for field, rules in constraints.items():
        if field in payload:
            if isinstance(payload[field], dict):
                for subfield, subrules in rules.items():
                    if subfield in payload[field]:
                        val = payload[field][subfield]
                        valid, msg = check_value(val, subrules)
                        if not valid:
                            return False, f"Field {field}.{subfield}: {msg}"
            else:
                val = payload[field]
                valid, msg = check_value(val, rules)
                if not valid:
                    return False, f"Field {field}: {msg}"
    return True, "Coherent"


def validate_event_message(raw_payload):
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return False, "Invalid JSON format"
    
    if "event_type" not in payload or "timestamp" not in payload:
        return False, "Missing mandatory fields (event_type, timestamp)"

    event_type = payload["event_type"]

    if event_type not in REQUIRED_FIELDS:
        return False, f"Unknown event_type: {event_type}"

    for field in REQUIRED_FIELDS[event_type]:
        if field not in payload:
            return False, f"Missing field '{field}' for event_type '{event_type}'"
        if field in REQUIRED_SUBFIELDS:
            for subfield in REQUIRED_SUBFIELDS[field]:
                if subfield not in payload[field]:
                    return False, f"Missing subfield '{subfield}' in field '{field}'"

    is_coherent, coherence_msg = check_data_coherence(payload)
    if not is_coherent:
        return False, f"Data coherence error: {coherence_msg}"

    return True, payload

# ==========================
# ALERTING
# ==========================
def get_unique_id(payload):
    et = payload["event_type"]
    id_map = {
        "traffic_state": lambda p: p["location"]["id"],
        "infrastructure_status": lambda p: p["infrastructure"]["id"],
        "service_accessibility": lambda p: p["service"]["id"],
        "environmental_conditions": lambda p: p["location"]["id"],
        "system_health": lambda p: p["component"]["id"]
    }
    getter = id_map.get(et)
    return f"{et}:{getter(payload)}" if getter else "unknown"


def check_alerts(payload):
    uid = get_unique_id(payload)
    if uid not in sensor_history:
        sensor_history[uid] = deque(maxlen=20)
    
    history = sensor_history[uid]
    history.append(payload)

    # Wait for some data to accumulate
    if len(history) < 5:
        return []

    event_type = payload["event_type"]
    if event_type not in ALERT_THRESHOLDS:
        return []

    alerts = []
    constraints = ALERT_THRESHOLDS[event_type]

    for field, rules in constraints.items():
        if field not in payload:
            continue
            
        for subfield, rule in rules.items():
            values = [p[field][subfield] for p in history if field in p and subfield in p[field]]
            
            if not values:
                continue

            if rule["type"] == "enum":
                count = sum(1 for v in values if v in rule["bad_values"])
                if count >= rule["min_count"]:
                    alerts.append(f"{subfield} is {values[-1]} (Critical frequency: {count}/{len(values)})")
            
            elif rule["type"] == "avg":
                avg_val = statistics.mean(values)
                limit = rule["limit"]
                if rule["op"] == "gt" and avg_val > limit:
                    alerts.append(f"{subfield} average {avg_val:.2f} > {limit}")
                elif rule["op"] == "lt" and avg_val < limit:
                    alerts.append(f"{subfield} average {avg_val:.2f} < {limit}")

    return alerts

# ==========================
# MQTT HANDLERS
# ==========================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker")
        # Subscribe to all topics
        for topic_suffix in TOPICS.keys():
            full_topic = f"{BASE_TOPIC_GET}/{topic_suffix}"
            client.subscribe(full_topic)
            print(f"Subscribed to: {full_topic}")
    else:
        print(f"Failed to connect, return code {rc}")


def on_message(client, userdata, message):
    # Extract topic suffix to identify source
    topic = message.topic
    topic_suffix = topic.split("/")[-1]
    source = TOPICS.get(topic_suffix, "unknown")
    
    # Validate
    raw_payload = message.payload.decode("utf-8")
    is_valid, result = validate_event_message(raw_payload)
    
    if not is_valid:
        print(f"[{source}] Invalid message: {result}")
        return
    
    # Save to DB
    db.save_event(result)
    
    # Check for alerts
    alerts = check_alerts(result)
    if alerts:
        alert_msg = {
            "timestamp": result["timestamp"],
            "type": "ALERT",
            "source": source,
            "details": alerts
        }
        client.publish(ALERT_TOPIC, json.dumps(alert_msg))
        print(f"[{source}] ALERT: {alerts}")
    
    # Republish validated data
    client.publish(f"{BASE_TOPIC_POST}/{topic_suffix}", json.dumps(result))
    print(f"[{source}] Processed and published")

# ==========================
# MAIN
# ==========================
def main():
    client = mqtt.Client(client_id="udite-analyzer")
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print("UDiTE Analyzer starting...")
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        db.close()
        client.disconnect()
    except Exception as e:
        print(f"Connection error: {e}")
        db.close()


if __name__ == "__main__":
    main()