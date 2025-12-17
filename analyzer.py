# analizzare i dati
# pubblicare i risultati

import mqttsub
import mqttpub

import json
from collections import deque
import statistics

from database_manager import DatabaseManager
from data_structure import REQUIRED_FIELDS, REQUIRED_SUBFIELDS, DATA_CONSTRAINTS, ALERT_THRESHOLDS

sensor_history = {} # Key: "event_type:id", Value: deque(maxlen=20)

city_string = "city/"

dataGet_string = "UDiTE/" + city_string + "data/get"
dataPost_string = "UDiTE/" + city_string + "data/post"
alert_string = "UDiTE/" + city_string + "alert"

urbanViability_string = "trafficSensor"
criticalInfrastructure_string = "criticalInfrastructure"
essentialsAccessibility_string = "essentialsAccessibility"
environmentQuality_string = "environmentQuality"
metaSensors_string = "metaSensors"

db = DatabaseManager()

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

def validate_event_message(message):
    try:
        payload = json.loads(message.payload.decode("utf-8"))
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
                    return False, f"Missing subfield '{subfield}' in field '{field}' for event_type '{event_type}'"

    is_coherent, coherence_msg = check_data_coherence(payload)
    if not is_coherent:
        return False, f"Data coherence error: {coherence_msg}"

    return True, payload

def get_unique_id(payload):
    et = payload["event_type"]
    if et == "traffic_state": return f"{et}:{payload['location']['id']}"
    if et == "infrastructure_status": return f"{et}:{payload['infrastructure']['id']}"
    if et == "service_accessibility": return f"{et}:{payload['service']['id']}"
    if et == "environmental_conditions": return f"{et}:{payload['location']['id']}"
    if et == "system_health": return f"{et}:{payload['component']['id']}"
    return "unknown"

def check_alerts(payload):
    uid = get_unique_id(payload)
    if uid not in sensor_history:
        sensor_history[uid] = deque(maxlen=20)
    
    history = sensor_history[uid]
    history.append(payload)

    # Wait for some data to accumulate to avoid false positives on startup
    if len(history) < 5:
        return []

    event_type = payload["event_type"]
    if event_type not in ALERT_THRESHOLDS:
        return []

    alerts = []
    constraints = ALERT_THRESHOLDS[event_type]

    for field, rules in constraints.items():
        if field in payload:
            for subfield, rule in rules.items():
                # Extract values from history for this specific subfield
                # We safely ignore payloads in history that might miss this field (though validation prevents that)
                values = [p[field][subfield] for p in history if field in p and subfield in p[field]]
                
                if not values: continue

                if rule["type"] == "enum":
                    # Count how many times a "bad value" appeared in the history
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

def urbanViability_callback(client, userdata, message):
    is_valid, result = validate_event_message(message)
    if not is_valid:
        print(f"Invalid message received: {result}")
        return
    
    db.save_event(result)
    
    alerts = check_alerts(result)
    if alerts:
        alert_msg = {"timestamp": result["timestamp"], "type": "ALERT", "source": "urbanViability", "details": alerts}
        mqttpub.publish(alert_string, json.dumps(alert_msg))

    mqttpub.publish(dataPost_string + urbanViability_string, json.dumps(result))
    return

def criticalInfrastructure_callback(client, userdata, message):
    is_valid, result = validate_event_message(message)
    if not is_valid:
        print(f"Invalid message received: {result}")
        return

    db.save_event(result)

    alerts = check_alerts(result)
    if alerts:
        alert_msg = {"timestamp": result["timestamp"], "type": "ALERT", "source": "criticalInfrastructure", "details": alerts}
        mqttpub.publish(alert_string, json.dumps(alert_msg))
        
    mqttpub.publish(dataPost_string + criticalInfrastructure_string, json.dumps(result))
    return

def essentialsAccessibility_callback(client, userdata, message):
    is_valid, result = validate_event_message(message)
    if not is_valid:
        print(f"Invalid message received: {result}")
        return
    
    db.save_event(result)

    alerts = check_alerts(result)
    if alerts:
        alert_msg = {"timestamp": result["timestamp"], "type": "ALERT", "source": "essentialsAccessibility", "details": alerts}
        mqttpub.publish(alert_string, json.dumps(alert_msg))
        
    mqttpub.publish(dataPost_string + essentialsAccessibility_string, json.dumps(result))
    return

def environmentQuality_callback(client, userdata, message):
    is_valid, result = validate_event_message(message)
    if not is_valid:
        print(f"Invalid message received: {result}")
        return
    
    db.save_event(result)

    alerts = check_alerts(result)
    if alerts:
        alert_msg = {"timestamp": result["timestamp"], "type": "ALERT", "source": "environmentQuality", "details": alerts}
        mqttpub.publish(alert_string, json.dumps(alert_msg))
        
    mqttpub.publish(dataPost_string + environmentQuality_string, json.dumps(result))
    return

def metaSensors_callback(client, userdata, message):
    is_valid, result = validate_event_message(message)
    if not is_valid:
        print(f"Invalid message received: {result}")
        return
    
    db.save_event(result)

    alerts = check_alerts(result)
    if alerts:
        alert_msg = {"timestamp": result["timestamp"], "type": "ALERT", "source": "metaSensors", "details": alerts}
        mqttpub.publish(alert_string, json.dumps(alert_msg))
        
    mqttpub.publish(dataPost_string + metaSensors_string, json.dumps(result))
    return

def __main__():
	mqttsub.subscribe(dataGet_string + urbanViability_string, urbanViability_callback)
	mqttsub.subscribe(dataGet_string + criticalInfrastructure_string, criticalInfrastructure_callback)
	mqttsub.subscribe(dataGet_string + essentialsAccessibility_string, essentialsAccessibility_callback)
	mqttsub.subscribe(dataGet_string + environmentQuality_string, environmentQuality_callback)
	mqttsub.subscribe(dataGet_string + metaSensors_string, metaSensors_callback)

	mqttsub.loop_forever()

	return


__main__()
