import json
import logging
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import psycopg2
from psycopg2.extras import execute_batch
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry



# ตั้งค่า Logging ตาม Requirement
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# 1. พิกัด 5 เมืองตามที่โจทย์กำหนด
CITIES = [
    {"city_id": "BKK", "name": "Bangkok", "lat": 13.7563, "lon": 100.5018},
    {"city_id": "CNX", "name": "Chiang Mai", "lat": 18.7883, "lon": 98.9853},
    {"city_id": "HKT", "name": "Phuket", "lat": 7.8804, "lon": 98.3923},
    {"city_id": "KKC", "name": "Khon Kaen", "lat": 16.4322, "lon": 102.8236},
    {"city_id": "HDY", "name": "Hat Yai", "lat": 7.0084, "lon": 100.4747},
]

from config import DB_CONFIG

def get_resilient_session() -> requests.Session:
    """สร้าง Session พร้อมระบบ Exponential Backoff Retry จัดการ API หลุด/Timeout"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def fetch_weather_data(session: requests.Session, lat: float, lon: float) -> dict:
    """ดึงข้อมูลสภาพอากาศ 7 วันรายชั่วโมงจาก Open-Meteo"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability,precipitation",
        "timezone": "Asia/Bangkok",
        "forecast_days": 7
    }
    response = session.get(url, params=params, timeout=(5, 15))
    response.raise_for_status()
    return response.json()

def run_pipeline():
    start_time = time.time()
    session = get_resilient_session()
    raw_dir = "data/raw"
    os.makedirs(raw_dir, exist_ok=True)
    
    cities_processed = 0
    total_rows_upserted = 0
    failed_cities = []

    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logging.critical(f"Database connection failed: {e}")
        return

    for city in CITIES:
        city_id = city["city_id"]
        try:
            # Step A: ดึงข้อมูลจาก Open-Meteo API
            data = fetch_weather_data(session, city["lat"], city["lon"])
            
            # Step B: เก็บ Raw JSON สำรองไว้ในเครื่อง (Data Lake Landing)
            timestamp_str = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y%m%d_%H%M%S")
            raw_path = f"{raw_dir}/{city_id}_{timestamp_str}.json"
            with open(raw_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            # Step C: แปลงข้อมูล (Transform) ให้อยู่ในรูป Tabular
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            rain_chances = hourly.get("precipitation_probability", [])
            precips = hourly.get("precipitation", [])

            transformed_records = []
            for t, temp, rain, precip in zip(times, temps, rain_chances, precips):
                forecast_time = datetime.fromisoformat(t).replace(tzinfo=ZoneInfo("Asia/Bangkok"))
                transformed_records.append((
                    city_id,
                    forecast_time,
                    temp,
                    rain,
                    precip,
                    datetime.now(ZoneInfo("Asia/Bangkok"))
                ))

            # Step D: โหลดข้อมูลลง Database (Atomic Transaction + Idempotent Upsert)
            with conn.cursor() as cur:
                # 1. บันทึกก้อน JSON ลงตาราง Raw
                cur.execute(
                    "INSERT INTO raw_weather_payloads (city_id, raw_payload) VALUES (%s, %s)",
                    (city_id, json.dumps(data))
                )
                
                # 2. โหลดลงตาราง Fact (ถ้าเจอ Composite Key ซ้ำ ให้ทำ UPDATE ทับ ไม่เพิ่มแถวใหม่)
                upsert_query = """
                    INSERT INTO fact_weather_forecast 
                    (city_id, forecast_time, temperature_celsius, rain_chance_pct, precipitation_mm, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (city_id, forecast_time) 
                    DO UPDATE SET
                        temperature_celsius = EXCLUDED.temperature_celsius,
                        rain_chance_pct = EXCLUDED.rain_chance_pct,
                        precipitation_mm = EXCLUDED.precipitation_mm,
                        updated_at = EXCLUDED.updated_at;
                """
                execute_batch(cur, upsert_query, transformed_records)
                conn.commit()

            cities_processed += 1
            total_rows_upserted += len(transformed_records)
            logging.info(f"Successfully processed {city['name']} ({len(transformed_records)} records)")

        except requests.exceptions.RequestException as e:
            conn.rollback()
            failed_cities.append((city_id, f"Network Error: {str(e)}"))
            logging.error(f"API Failure for {city_id}: {e}")
        except Exception as e:
            conn.rollback()
            failed_cities.append((city_id, f"Database/Data Error: {str(e)}"))
            logging.error(f"Pipeline error for {city_id}: {e}")

    conn.close()
    elapsed_time = round(time.time() - start_time, 2)
    
    # พิมพ์สรุปผลการทำงานตามเงื่อนไข Assessment
    logging.info("=" * 45)
    logging.info(f"Execution completed in: {elapsed_time}s")
    logging.info(f"Cities Processed: {cities_processed}/{len(CITIES)}")
    logging.info(f"Total Rows Upserted: {total_rows_upserted}")
    if failed_cities:
        logging.warning(f"Failures ({len(failed_cities)}): {failed_cities}")
    logging.info("=" * 45)

if __name__ == "__main__":
    run_pipeline()