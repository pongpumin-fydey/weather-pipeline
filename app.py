import psycopg2
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Thailand Weather Dashboard",
    page_icon="⛅",
    layout="wide"
)

st.title("⛅ 7-Day Weather Forecast Dashboard")
st.caption("Data source: PostgreSQL Database (weather_db) | Ingested via Open-Meteo API")



from config import DB_CONFIG

@st.cache_data(ttl=600)
def load_forecast_data():
    conn = psycopg2.connect(**DB_CONFIG)
    query = """
        SELECT 
            c.city_name,
            f.forecast_time,
            f.temperature_celsius,
            f.rain_chance_pct,
            f.precipitation_mm
        FROM fact_weather_forecast f
        JOIN dim_cities c ON f.city_id = c.city_id
        ORDER BY f.forecast_time ASC;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    df["forecast_time"] = pd.to_datetime(df["forecast_time"])
    return df

try:
    df = load_forecast_data()

    # แถบเลือกเมือง
    cities = df["city_name"].unique()
    selected_city = st.selectbox("เลือกเมืองที่ต้องการดูข้อมูล:", cities)
    
    city_df = df[df["city_name"] == selected_city]

    # แสดง KPI Cards สรุปภาพรวม
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Max Temperature", f"{city_df['temperature_celsius'].max():.1f} °C")
    col2.metric("Min Temperature", f"{city_df['temperature_celsius'].min():.1f} °C")
    col3.metric("Avg Temperature", f"{city_df['temperature_celsius'].mean():.1f} °C")
    col4.metric("Highest Rain Chance", f"{city_df['rain_chance_pct'].max()} %")

    st.markdown("---")

    # กราฟแสดงแนวโน้มอุณหภูมิรายชั่วโมงตลอด 7 วัน
    st.subheader(f"📈 แนวโน้มอุณหภูมิ 7 วันข้างหน้า: {selected_city}")
    st.line_chart(
        data=city_df.set_index("forecast_time")["temperature_celsius"],
        use_container_width=True
    )

    # กราฟแสดงโอกาสเกิดฝน
    st.subheader(f"🌧️ โอกาสการเกิดฝนตก (%): {selected_city}")
    st.bar_chart(
        data=city_df.set_index("forecast_time")["rain_chance_pct"],
        use_container_width=True
    )

    # ตารางข้อมูลดิบใน Fact Table
    with st.expander("ดูตารางข้อมูลพยากรณ์ทั้งหมด (Data View)"):
        st.dataframe(city_df, use_container_width=True)

except Exception as e:
    st.error(f"ไม่สามารถเชื่อมต่อ Database ได้: {e}")
    