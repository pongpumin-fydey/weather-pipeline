-- อุณหภูมิเฉลี่ย, สูงสุด และต่ำสุดต่อเมืองต่อวัน
SELECT 
    c.city_name,
    DATE(f.forecast_time) AS forecast_date,
    ROUND(AVG(f.temperature_celsius), 2) AS avg_temp,
    MAX(f.temperature_celsius) AS max_temp,
    MIN(f.temperature_celsius) AS min_temp
FROM fact_weather_forecast f
JOIN dim_cities c ON f.city_id = c.city_id
GROUP BY c.city_name, DATE(f.forecast_time)
ORDER BY c.city_name, forecast_date;

-- เมืองที่มีช่วงอุณหภูมิแกว่งกว้างที่สุด (Max − Min) ในรอบ 7 วัน
SELECT 
    c.city_name,
    MIN(f.temperature_celsius) AS min_temp,
    MAX(f.temperature_celsius) AS max_temp,
    ROUND(MAX(f.temperature_celsius) - MIN(f.temperature_celsius), 2) AS temp_range
FROM fact_weather_forecast f
JOIN dim_cities c ON f.city_id = c.city_id
GROUP BY c.city_name
ORDER BY temp_range DESC
LIMIT 1;

-- ชั่วโมงที่มีโอกาสเกิดฝนตกสูงที่สุดในแต่ละวัน แยกตามเมือง
WITH ranked_hourly_rain AS (
    SELECT 
        c.city_name,
        DATE(f.forecast_time) AS forecast_date,
        f.forecast_time,
        f.rain_chance_pct,
        ROW_NUMBER() OVER (
            PARTITION BY c.city_id, DATE(f.forecast_time) 
            ORDER BY f.rain_chance_pct DESC, f.forecast_time ASC
        ) AS rank_order
    FROM fact_weather_forecast f
    JOIN dim_cities c ON f.city_id = c.city_id
)
SELECT 
    city_name,
    forecast_date,
    forecast_time AS peak_rain_hour,
    rain_chance_pct AS max_rain_chance
FROM ranked_hourly_rain
WHERE rank_order = 1
ORDER BY city_name, forecast_date;

-- ผลต่างของอุณหภูมิเฉลี่ยเมื่อเทียบกับวันก่อนหน้า (Day-over-Day Difference)
WITH daily_city_avg AS (
    SELECT 
        c.city_name,
        DATE(f.forecast_time) AS forecast_date,
        ROUND(AVG(f.temperature_celsius), 2) AS avg_temp
    FROM fact_weather_forecast f
    JOIN dim_cities c ON f.city_id = c.city_id
    GROUP BY c.city_name, DATE(f.forecast_time)
)
SELECT 
    city_name,
    forecast_date,
    avg_temp AS current_day_avg,
    LAG(avg_temp) OVER (
        PARTITION BY city_name 
        ORDER BY forecast_date
    ) AS prev_day_avg,
    ROUND(
        avg_temp - LAG(avg_temp) OVER (
            PARTITION BY city_name 
            ORDER BY forecast_date
        ), 2
    ) AS temp_difference
FROM daily_city_avg
ORDER BY city_name, forecast_date;
