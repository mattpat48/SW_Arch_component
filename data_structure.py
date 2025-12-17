REQUIRED_FIELDS = {
    "traffic_state": ["location", "t_metrics"],
    "infrastructure_status": ["infrastructure", "status", "i_metrics"],
    "service_accessibility": ["service", "accessibility"],
    "environmental_conditions": ["location", "e_metrics"],
    "system_health": ["component", "health"]
}

REQUIRED_SUBFIELDS = {
	"location": ["id", "district"],
	"t_metrics": ["congestion_level", "average_speed"],

	"infrastructure": ["id", "type"],
	"i_metrics": ["capacity_percentage", "vibration_level"],

	"service": ["id", "type"],
	"accessibility": ["status", "estimated_access_time", "capacity_percentage"],

	"e_metrics": ["rainfall_mm", "wind_speed_kmh", "temperature_celsius", "humidity_percentage"],

	"component": ["id", "type"],
	"health": ["status", "latency_ms", "error_rate_percentage"]
}

DATA_CONSTRAINTS = {
    "traffic_state": {
        "t_metrics": {
            "congestion_level": {"type": "enum", "values": ["LOW", "MODERATE", "HIGH", "CRITICAL"]},
            "average_speed": {"type": "range", "min": 0.0, "max": 200.0}
        }
    },
    "infrastructure_status": {
        "status": {"type": "enum", "values": ["OPERATIONAL", "MAINTENANCE", "WARNING", "CRITICAL"]},
        "i_metrics": {
            "capacity_percentage": {"type": "range", "min": 0.0, "max": 100.0},
            "vibration_level": {"type": "range", "min": 0.0, "max": 100.0}
        }
    },
    "service_accessibility": {
        "accessibility": {
            "status": {"type": "enum", "values": ["AVAILABLE", "FULL", "CLOSED"]},
            "estimated_access_time": {"type": "range", "min": 0.0, "max": 300.0},
            "capacity_percentage": {"type": "range", "min": 0.0, "max": 100.0}
        }
    },
    "environmental_conditions": {
        "e_metrics": {
            "rainfall_mm": {"type": "range", "min": 0.0, "max": 1000.0},
            "wind_speed_kmh": {"type": "range", "min": 0.0, "max": 300.0},
            "temperature_celsius": {"type": "range", "min": -50.0, "max": 60.0},
            "humidity_percentage": {"type": "range", "min": 0.0, "max": 100.0}
        }
    },
    "system_health": {
        "health": {
            "status": {"type": "enum", "values": ["HEALTHY", "DEGRADED", "FAILURE"]},
            "latency_ms": {"type": "range", "min": 0.0, "max": 10000.0},
            "error_rate_percentage": {"type": "range", "min": 0.0, "max": 100.0}
        }
    }
}

ALERT_THRESHOLDS = {
    "traffic_state": {
        "t_metrics": {
            "congestion_level": {"type": "enum", "bad_values": ["HIGH", "CRITICAL"], "min_count": 10},
            "average_speed": {"type": "avg", "op": "lt", "limit": 5.0}
        }
    },
    "infrastructure_status": {
        "status": {"type": "enum", "bad_values": ["WARNING", "CRITICAL"], "min_count": 5},
        "i_metrics": {
            "vibration_level": {"type": "avg", "op": "gt", "limit": 50.0}
        }
    },
    "service_accessibility": {
        "accessibility": {
            "status": {"type": "enum", "bad_values": ["CLOSED"], "min_count": 15},
            "capacity_percentage": {"type": "avg", "op": "gt", "limit": 95.0}
        }
    },
    "environmental_conditions": {
        "e_metrics": {
            "wind_speed_kmh": {"type": "avg", "op": "gt", "limit": 80.0},
            "rainfall_mm": {"type": "avg", "op": "gt", "limit": 50.0},
            "temperature_celsius": {"type": "avg", "op": "gt", "limit": 45.0}
        }
    },
    "system_health": {
        "health": {
            "status": {"type": "enum", "bad_values": ["DEGRADED", "FAILURE"], "min_count": 5},
            "latency_ms": {"type": "avg", "op": "gt", "limit": 500.0},
            "error_rate_percentage": {"type": "avg", "op": "gt", "limit": 10.0}
        }
    }
}