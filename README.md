# ⛅ Thailand Weather Data Pipeline & Dashboard

An end-to-end data pipeline built for the OOCA Data Engineer Internship assessment. The pipeline ingests 7-day hourly weather forecasts for 5 major cities in Thailand from Open-Meteo API, stores raw and processed data into PostgreSQL, provides analytical SQL queries, and visualizes insights via a Streamlit dashboard.

---

## 📸 Dashboard Preview

![Dashboard Overview](<Weather Data Pipeline Dashboard 1.png>)
![Dashboard Details](<Weather Data Pipeline Dashboard 2.png>)

---

## 🏗️ Architecture & Schema Design

The database schema follows an **ELT / Medallion pattern** using PostgreSQL:

1. **`dim_cities` (Dimension Table):** Stores normalized static city metadata (`city_id`, `city_name`, `latitude`, `longitude`) to eliminate string redundancy across time-series records (3NF).
2. **`raw_weather_payloads` (Bronze Layer):** Stores unprocessed API JSON responses (`JSONB`) along with ingestion timestamps. This preserves an immutable audit trail, allowing backfilling and reprocessing without re-calling the external API.
3. **`fact_weather_forecast` (Gold/Fact Layer):** Stores cleaned hourly forecast data with numeric types.
   * **Composite Primary Key:** `(city_id, forecast_time)` uniquely identifies an hourly observation per city and enables performant lookups.
   * **Index:** B-Tree index on `forecast_time` for fast time-range filtering.

---

## 🔁 Idempotency Strategy

The pipeline is designed to ensure data consistency across multiple runs:

* **Conflict Resolution (Gold Layer):** Ingestion into `fact_weather_forecast` uses PostgreSQL upsert:
  ```sql
  INSERT INTO fact_weather_forecast (...) VALUES (...)
  ON CONFLICT (city_id, forecast_time)
  DO UPDATE SET
      temperature_celsius = EXCLUDED.temperature_celsius,
      rain_chance_pct = EXCLUDED.rain_chance_pct,
      precipitation_mm = EXCLUDED.precipitation_mm,
      updated_at = EXCLUDED.updated_at;
  ```
  Running the pipeline repeatedly will refresh existing hourly records rather than inflating the row count.

* **Immutable Audit Trail (Bronze Layer):** 
The `raw_weather_payloads` table intentionally operates as append-only to preserve a historical audit log of every ingestion run.

* **Atomic Transactions:** 
Ingestion steps are wrapped in transactional blocks (`commit`/`rollback`). If a failure occurs mid-batch, changes are rolled back cleanly to prevent partial loads.
---

## 🛠️ Data Quality & Handling Edge Cases

* **Timezone Consistency:** Requested data with explicit `timezone=Asia/Bangkok` (+07:00) and stored timestamps as `TIMESTAMP WITH TIME ZONE` (`TIMESTAMPTZ`), preventing UTC-shift errors during day-level aggregations.
* **Transient API Failures:** Implemented Exponential Backoff Retry via `requests.adapters.HTTPAdapter` (3 retries on HTTP 429, 500, 502, 503, 504).
* **Null Handling:** Initial boundary days in Window functions (e.g., `LAG()`) produce expected `NULL` values for previous-day comparisons, handled naturally without breaking the schema.
* **Units:** Open-Meteo returns temperature in Celsius and precipitation in millimeters by default, matching target regional standards; explicit column naming (`temperature_celsius`, `precipitation_mm`) prevents any ambiguity downstream.
* **Data Gaps:** Handled potential missing fields or truncated payloads gracefully using safe dictionary lookups (`.get()`) and Python's `zip()` truncation behavior, preventing runtime `IndexError` crashes if hourly arrays return misaligned lengths.

---

## 🚀 Scaling to Hourly, Year-Round Execution

If this pipeline runs hourly in production, the following architectural upgrades would be implemented:

1. **Table Partitioning:** Implement declarative range partitioning on `fact_weather_forecast` by month (`PARTITION BY RANGE (forecast_time)`) to maintain index performance and prune cold partitions.
2. **Orchestration:** Transition from standalone Python scripts to an orchestrator like **Apache Airflow** or **Prefect** for DAG scheduling, retry policies, and alerting.
3. **Object Storage Data Lake:** Offload raw JSON files to cloud object storage (AWS S3 / GCS) with lifecycle policies to keep database storage costs minimal.
4. **Connection Pooling:** Use **PgBouncer** to manage concurrent client connections between ingestion workers and dashboard readers.
5. **Data Retention Policy:** Implement a daily cleanup routine to remove stale historical forecasts (e.g., `DELETE FROM fact_weather_forecast WHERE forecast_time < CURRENT_DATE - INTERVAL '1 day';`) to prevent indefinite table growth and maintain query performance.

---

## 💡 Interesting Insights from Data

1. **Diurnal Temperature Variation:** Inland and northern cities (e.g., Chiang Mai, Khon Kaen) exhibit a significantly wider day-night temperature range compared to coastal cities (e.g., Phuket), where maritime air keeps temperatures stable.
2. **Precipitation Patterns:** Rain probability peaks during late afternoon and early evening (around 2:00 PM – 7:00 PM), consistent with typical tropical afternoon showers driven by daytime surface heating.

---

## 🤖 AI Tools Disclosure

AI assistance (Gemini / Claude) was utilized for:
* Reviewing ANSI SQL Window Function syntax (`ROW_NUMBER`, `LAG`).
* Designing standard Python retry configurations with `urllib3`.
* I personally verified, tested, and understand all business logic, SQL transformations, and pipeline operations.

---

## ⚡ How to Run Locally

### 1. Prerequisites
* Python 3.10+
* PostgreSQL 15+

### 2. Setup Database
Create database `weather_db` in PostgreSQL and run `schema.sql`:
```bash
psql -U postgres -d weather_db -f schema.sql
```

### 3. Setup Environment Variables
Create a `.env` file in the root directory based on the provided `.env.example` and fill in your PostgreSQL credentials:
```bash
cp .env.example .env
```


### 4. Install Dependencies & Run Ingestion
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1   # On Windows
pip install -r requirements.txt
python pipeline.py
```


### 5. Run Dashboard
```bash
streamlit run app.py
```