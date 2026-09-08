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

The pipeline is designed to be fully idempotent:

* **Conflict Resolution:** Ingestion uses the PostgreSQL clause:
  ```sql
  INSERT INTO fact_weather_forecast (...) VALUES (...)
  ON CONFLICT (city_id, forecast_time)
  DO UPDATE SET ...;