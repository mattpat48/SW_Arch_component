# UDiTE - Analizzatore Dati Smart City

Questo progetto implementa un componente backend per l'elaborazione, la validazione e l'archiviazione di dati provenienti da sensori IoT in un contesto di Smart City. Il sistema agisce come un middleware che ascolta i dati grezzi via MQTT, li analizza e genera allarmi intelligenti.

## Struttura del Progetto

Il sistema è composto da tre file principali:

1.  **`analyzer.py`**: È il core dell'applicazione.
    *   Gestisce la connessione MQTT (sottoscrizione ai topic dei sensori e pubblicazione dei risultati).
    *   Coordina il flusso di validazione, salvataggio e analisi.
    *   Implementa la logica a finestra mobile (sliding window) per la generazione degli allarmi.

2.  **`database_manager.py`**: Gestisce la persistenza dei dati.
    *   Crea e gestisce un database SQLite locale (`city_data.db`).
    *   Dispone di tabelle separate per ogni tipologia di evento (`traffic_state`, `infrastructure_status`, ecc.).
    *   Fornisce metodi per l'inserimento sicuro dei dati.

3.  **`data_structure.py`**: Contiene la configurazione statica del sistema.
    *   Definisce lo schema dei dati attesi (`REQUIRED_FIELDS`).
    *   Imposta i vincoli di validità dei dati (`DATA_CONSTRAINTS`) come range numerici o liste di valori permessi (enum).
    *   Definisce le soglie per l'attivazione degli allarmi (`ALERT_THRESHOLDS`).

## Funzionalità Principali

### 1. Validazione e Coerenza dei Dati
Ogni messaggio ricevuto viene sottoposto a due livelli di controllo:
*   **Strutturale**: Verifica che il JSON sia valido e contenga tutti i campi e sottocampi obbligatori.
*   **Semantico (Coerenza)**: Verifica che i valori siano logici (es. la velocità non può essere negativa, lo stato di un semaforo deve essere uno di quelli predefiniti). I dati incoerenti vengono scartati prima del salvataggio.

### 2. Archiviazione (Database)
I dati validi vengono salvati automaticamente nel database SQLite locale. Il sistema smista i dati nella tabella corretta in base al campo `event_type` del messaggio.

### 3. Sistema di Allarmi Intelligente
Il sistema non genera allarmi basandosi su singole letture (che potrebbero essere falsi positivi o picchi momentanei), ma utilizza un approccio storico:
*   Mantiene in memoria una **coda degli ultimi 20 rilevamenti** per ogni singolo sensore (identificato univocamente).
*   Gli allarmi scattano solo se l'analisi di questa cronologia supera certe soglie (es. media della velocità del vento troppo alta, o troppi stati di "errore" consecutivi).

## Flusso di Esecuzione

1.  **Ricezione**: `analyzer.py` riceve un messaggio MQTT su un topic (es. `UDiTE/city/data/get/trafficSensor`).
2.  **Validazione**:
    *   Se il messaggio è malformato o incoerente, viene loggato l'errore e il flusso si interrompe.
3.  **Salvataggio**: Se valido, il dato viene salvato nel DB tramite `DatabaseManager`.
4.  **Analisi**:
    *   Il dato viene aggiunto alla cronologia specifica di quel sensore.
    *   La funzione `check_alerts` calcola statistiche (medie, conteggi) sulla cronologia.
5.  **Pubblicazione**:
    *   Se vengono rilevati problemi, viene pubblicato un messaggio di allerta sul topic `UDiTE/city/alert`.
    *   Il dato validato viene ri-pubblicato sul topic di post (es. `UDiTE/city/data/post/trafficSensor`) per essere consumato da altri servizi.

## Requisiti

*   Python 3.x
*   Librerie: `paho-mqtt` (o wrapper `mqttsub`/`mqttpub` inclusi), `sqlite3` (standard library).
