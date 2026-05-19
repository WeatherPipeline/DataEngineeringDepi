import os
import requests
import pandas as pd
from sqlalchemy import create_engine, text
import urllib
from sklearn.linear_model import LinearRegression

# =====================================================
# Egypt Governorates
# =====================================================

governorates = [
    {"city": "Cairo", "country": "Egypt", "lat": 30.0444, "lon": 31.2357},
    {"city": "Giza", "country": "Egypt", "lat": 30.0131, "lon": 31.2089},
    {"city": "Alexandria", "country": "Egypt", "lat": 31.2001, "lon": 29.9187},
    {"city": "Dakahlia", "country": "Egypt", "lat": 31.0409, "lon": 31.3785},
    {"city": "Red Sea", "country": "Egypt", "lat": 24.6826, "lon": 34.1532},
    {"city": "Beheira", "country": "Egypt", "lat": 30.8481, "lon": 30.3436},
    {"city": "Fayoum", "country": "Egypt", "lat": 29.3084, "lon": 30.8428},
    {"city": "Gharbia", "country": "Egypt", "lat": 30.8754, "lon": 31.0335},
    {"city": "Ismailia", "country": "Egypt", "lat": 30.5965, "lon": 32.2715},
    {"city": "Menofia", "country": "Egypt", "lat": 30.5972, "lon": 30.9876},
    {"city": "Minya", "country": "Egypt", "lat": 28.1099, "lon": 30.7503},
    {"city": "Qalyubia", "country": "Egypt", "lat": 30.3292, "lon": 31.2165},
    {"city": "New Valley", "country": "Egypt", "lat": 25.4514, "lon": 30.5466},
    {"city": "Suez", "country": "Egypt", "lat": 29.9668, "lon": 32.5498},
    {"city": "Aswan", "country": "Egypt", "lat": 24.0889, "lon": 32.8998},
    {"city": "Assiut", "country": "Egypt", "lat": 27.1783, "lon": 31.1859},
    {"city": "Beni Suef", "country": "Egypt", "lat": 29.0661, "lon": 31.0994},
    {"city": "Port Said", "country": "Egypt", "lat": 31.2653, "lon": 32.3019},
    {"city": "Damietta", "country": "Egypt", "lat": 31.4165, "lon": 31.8133},
    {"city": "Sharkia", "country": "Egypt", "lat": 30.7326, "lon": 31.7195},
    {"city": "South Sinai", "country": "Egypt", "lat": 28.7670, "lon": 33.6405},
    {"city": "Kafr El Sheikh", "country": "Egypt", "lat": 31.1107, "lon": 30.9388},
    {"city": "Matrouh", "country": "Egypt", "lat": 31.3543, "lon": 27.2373},
    {"city": "Luxor", "country": "Egypt", "lat": 25.6872, "lon": 32.6396},
    {"city": "Qena", "country": "Egypt", "lat": 26.1551, "lon": 32.7160},
    {"city": "North Sinai", "country": "Egypt", "lat": 31.1313, "lon": 33.7984},
    {"city": "Sohag", "country": "Egypt", "lat": 26.5591, "lon": 31.6957}
]

# =====================================================
# Weather Conditions
# =====================================================

weather_conditions = {
    0: "Clear Sky",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Dense Drizzle",
    61: "Slight Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    71: "Slight Snow",
    73: "Moderate Snow",
    75: "Heavy Snow",
    95: "Thunderstorm"
}

# =====================================================
# SQL Connection
# =====================================================

SERVER = os.getenv("WEATHER_DB_SERVER", ".")
DATABASE = os.getenv("WEATHER_DB_NAME", "Weather_DataBase")
USERNAME = os.getenv("WEATHER_DB_USER", "sa")
PASSWORD = os.getenv("WEATHER_DB_PASSWORD", "YourStrongPassword123")
DRIVER = os.getenv("WEATHER_DB_DRIVER", "ODBC Driver 17 for SQL Server")

params = urllib.parse.quote_plus(
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    f"TrustServerCertificate=yes;"
)

conn_str = f"mssql+pyodbc:///?odbc_connect={params}"

engine = create_engine(conn_str)

# =====================================================
# Create Table If Not Exists
# =====================================================

def create_table():

    create_table_query = """

    IF NOT EXISTS (
        SELECT *
        FROM sysobjects
        WHERE name='WeatherForecast'
        AND xtype='U'
        )

    CREATE TABLE WeatherForecast (
        id INT IDENTITY(1,1) PRIMARY KEY,

        city NVARCHAR(100),
        country NVARCHAR(100),

        timestamp DATETIME,

        temperature FLOAT,
        humidity FLOAT,
        wind_speed FLOAT,

        predicted_temperature FLOAT,

        weather_condition NVARCHAR(100),

        alert NVARCHAR(100),

        CONSTRAINT uq_city_timestamp UNIQUE(city, timestamp)
    )

    IF OBJECT_ID('weather_day', 'V') IS NULL
        EXEC('CREATE VIEW weather_day AS
        SELECT
            id AS ID,
            city AS City,
            country AS Country,
            [timestamp] AS [Timestamp],
            temperature AS Temperature,
            humidity AS Humidity,
            wind_speed AS [Wind Speed],
            predicted_temperature AS [Predicted Temperature],
            weather_condition AS [Weather Condition],
            alert AS Alert,
            DATENAME(WEEKDAY, [timestamp]) AS Day
        FROM WeatherForecast')

    """

    with engine.begin() as conn:
        conn.execute(text(create_table_query))

    print("[SUCCESS] Table checked/created successfully")

# =====================================================
# Extract + Transform
# =====================================================

def get_weather_data():

    url = "https://api.open-meteo.com/v1/forecast"

    all_data = []

    for gov in governorates:

        params = {
            "latitude": gov["lat"],
            "longitude": gov["lon"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "Africa/Cairo"
        }

        try:

            response = requests.get(
                url,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            current = response.json()["current"]

            all_data.append({
                "city": gov["city"],
                "country": gov["country"],
                "timestamp": current["time"],

                "temperature": round(current["temperature_2m"], 1),

                "humidity": round(current["relative_humidity_2m"], 1),

                "wind_speed": round(current["wind_speed_10m"], 1),

                "weather_condition": weather_conditions.get(
                    current["weather_code"],
                    "Unknown"
                )
            })

            print(f"[SUCCESS] {gov['city']} collected")

        except Exception as e:

            print(f"[ERROR] {gov['city']} -> {e}")

    df = pd.DataFrame(all_data)

    if df.empty:
        raise ValueError("No data extracted")

    # Convert datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Alert System
    df["alert"] = df["temperature"].apply(
        lambda x:
        "High Temperature"
        if x > 36
        else ("Low Temperature" if x < 15 else "Normal")
    )

    # AI Prediction
    X = df[["humidity", "wind_speed"]]

    y = df["temperature"]

    model = LinearRegression()

    model.fit(X, y)

    df["predicted_temperature"] = model.predict(X).round(1)

    return df

# =====================================================
# Check Duplicate
# =====================================================

def record_exists(city, timestamp):

    query = text("""

        SELECT COUNT(*)

        FROM WeatherForecast

        WHERE city = :city
        AND timestamp = :timestamp

    """)

    with engine.connect() as conn:

        result = conn.execute(
            query,
            {
                "city": city,
                "timestamp": timestamp
            }
        ).scalar()

    return result > 0

# =====================================================
# Load Data
# =====================================================

def load_data(df):

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():

        try:

            exists = record_exists(
                row["city"],
                row["timestamp"]
            )

            if exists:

                print(
                    f"[SKIPPED] "
                    f"{row['city']} already exists"
                )

                skipped += 1

                continue

            single_row = pd.DataFrame([row])

            single_row.to_sql(
                "WeatherForecast",
                con=engine,
                if_exists="append",
                index=False
            )

            print(
                f"[INSERTED] "
                f"{row['city']}"
            )

            inserted += 1

        except Exception as e:

            print(
                f"[ERROR] "
                f"{row['city']} -> {e}"
            )

    print("\n=========== SUMMARY ===========")

    print(f"Inserted : {inserted}")

    print(f"Skipped  : {skipped}")

    print("================================")

# =====================================================
# Main
# =====================================================

if __name__ == "__main__":

    try:

        print("\n========== WEATHER ETL STARTED ==========\n")

        create_table()

        df = get_weather_data()

        print("\n[SUCCESS] DataFrame created\n")

        print(df.head())

        load_data(df)

        print("\n========== ETL FINISHED ==========\n")

    except Exception as e:

        print(f"\n[FATAL ERROR] {e}\n")
