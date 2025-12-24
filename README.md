# UDiTE Smart City Monitoring System

## Overview
UDiTE is a modular software architecture designed to simulate, analyze, and visualize urban data streams. It acts as a digital twin engine, processing data from various domains including traffic flow, critical infrastructure status, service accessibility, environmental quality, and internal system health.

## Components

### 1. Data Generator (`publisher.py`)
Acts as the source of information, simulating a network of IoT sensors distributed across the city. It generates synthetic data for five key categories:
- **Urban Viability**: Traffic congestion levels and average speeds.
- **Critical Infrastructure**: Status and metrics for bridges, tunnels, and power grids.
- **Essentials Accessibility**: Availability and access times for hospitals, schools, and markets.re-write the readme in inge
- **Environment Quality**: Weather conditions (rainfall, wind, temperature, humidity).
- **Meta Sensors**: Health status of the monitoring components themselves.

Data is published to the MQTT topic `UDiTE/city/data/get/#`.

### 2. Analyzer (`analyzer.py`)re-write the readme in inge
The core processing unit that subscribes to raw sensor data. Its responsibilities include:
- **Validation**: Ensures incoming JSON payloads contain all required fields and subfields defined in `data_structure.py`.
- **Coherence Checking**: Verifies that data values fall within logical ranges and valid enumerations.
- **Persistence**: Saves valid events into the SQLite database via `database_manager.py`.
- **Alerting**: Maintains a sliding window history of sensor data to detect anomalies (e.g., sustained critical traffic, high vibration levels) and publishes alerts to `UDiTE/city/alert`.
- **Republishing**: Publishes validated and processed data to `UDiTE/city/data/post/#`.
re-write the readme in inge
### 3. Dashboard (`dashboard.py`)
A Flask-based web application that provides a user interface for the system. It connects to the database to visualize:
- Real-time data tables.
- Statistical aggregates (averages, min/max).
- Status distribution charts.
- System health overviews.

### 4. Database Manager (`database_manager.py`)
A helper class that handles all interactions with the `city_data.db` SQLite database, including table creation and thread-safe data insertion.

### 5. Orchestrator (`run_all.py`)
A utility script designed to launch the Analyzer, Publisher, and Dashboard simultaneously as background processes. It manages their lifecycles, handles graceful shutdowns, and directs output to log files.

## Architecture & Interaction

1. **Ingestion**: The **Publisher** generates JSON events and sends them to the **MQTT Broker**.
2. **Processing**: The **Analyzer** consumes these messages.
   - If invalid: The message is logged and discarded.
   - If valid: The message is stored in the **Database** and checked against **Alert Thresholds**.
3. **Feedback**: If an anomaly is detected, the Analyzer publishes an alert back to the MQTT Broker.
4. **Visualization**: The **Dashboard** queries the **Database** to present the current state of the city to the user via a web browser.

## Requirements

- **Python 3.8+**
- **MQTT Broker**: A broker running locally on port `1883` is required. Eclipse Mosquitto is recommended.

### Python Dependencies
Install the necessary libraries using pip:

```bash
pip install paho-mqtt flask
```

## How to Run

1. **Start the MQTT Broker**:
   Ensure your MQTT broker is running on localhost:1883.
   ```bash
   # Example for Mosquitto
   mosquitto
   ```

2. **Start the System**:
   Run the orchestrator script to start all components.
   ```bash
   python run_all.py
   ```
   This will spawn the analyzer, publisher, and dashboard. Logs for each process are stored in the `logs/` directory created automatically.

3. **Access the Dashboard**:
   Open your web browser and navigate to:
   http://localhost:5000

4. **Stop the System**:
   Press `Ctrl+C` in the terminal running `run_all.py`. The script will catch the signal and terminate all child processes gracefully.