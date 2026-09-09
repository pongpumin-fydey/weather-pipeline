-- 1. Dimension Table: ข้อมูลเมือง
CREATE TABLE IF NOT EXISTS dim_cities (
    city_id VARCHAR(10) PRIMARY KEY,
    city_name VARCHAR(50) NOT NULL,
    latitude NUMERIC(6, 4) NOT NULL,
    longitude NUMERIC(7, 4) NOT NULL
);

INSERT INTO dim_cities (city_id, city_name, latitude, longitude) VALUES
('BKK', 'Bangkok', 13.7563, 100.5018),
('CNX', 'Chiang Mai', 18.7883, 98.9853),
('HKT', 'Phuket', 7.8804, 98.3923),
('KKC', 'Khon Kaen', 16.4322, 102.8236),
('HDY', 'Hat Yai', 7.0084, 100.4747)
ON CONFLICT (city_id) DO NOTHING;

-- 2. Bronze/Raw Layer: เก็บ Payload ดิบ Audit ย้อนหลังได้
CREATE TABLE IF NOT EXISTS raw_weather_payloads (
    id SERIAL PRIMARY KEY,
    city_id VARCHAR(10) REFERENCES dim_cities(city_id),
    pulled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    raw_payload JSONB NOT NULL
);

-- 3. Gold/Fact Layer: ข้อมูลที่ Clean แล้ว พร้อมใช้ Query
CREATE TABLE IF NOT EXISTS fact_weather_forecast (
    city_id VARCHAR(10) REFERENCES dim_cities(city_id),
    forecast_time TIMESTAMP WITH TIME ZONE NOT NULL,
    temperature_celsius NUMERIC(4, 2) NOT NULL,
    rain_chance_pct INT,
    precipitation_mm NUMERIC(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (city_id, forecast_time)
);

CREATE INDEX IF NOT EXISTS idx_weather_time ON fact_weather_forecast(forecast_time);
