import requests
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
# UK cities with coordinates
UK_CITIES = [
    {"name": "London",     "lat": 51.5074, "lng": -0.1278},
    {"name": "Manchester", "lat": 53.4808, "lng": -2.2426},
    {"name": "Leeds",      "lat": 53.7996, "lng": -1.5491},
    {"name": "Sunderland", "lat": 54.9069, "lng": -1.3838},
    {"name": "Edinburgh",  "lat": 55.9533, "lng": -3.1883},
]

START_DATE = "2024-01-01"
END_DATE   = "2024-12-31"

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch_weather(city: dict) -> pd.DataFrame:
    params = {
        "latitude":        city["lat"],
        "longitude":       city["lng"],
        "daily":           [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "windspeed_10m_max",
            "weathercode",
        ],
        "timezone":        "Europe/London",
        "start_date":      START_DATE,
        "end_date":        END_DATE,
    }

    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data["daily"])
    df["city"]      = city["name"]
    df["latitude"]  = city["lat"]
    df["longitude"] = city["lng"]
    df = df.rename(columns={"time": "date"})
    df["date"] = pd.to_datetime(df["date"])

    print(f"  ✓ {city['name']} — {len(df)} days fetched")
    return df


# ── Load to PostgreSQL ────────────────────────────────────────────────────────
def get_engine():
    url = (
        f"postgresql+psycopg2://"
        f"{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}"
        f"/{os.getenv('POSTGRES_DB')}"
    )
    return create_engine(url)


def load_to_postgres(df: pd.DataFrame, engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))

    df.to_sql(
        name="weather_daily",
        con=engine,
        schema="raw",
        if_exists="replace",
        index=False,
    )
    print(f"\n  ✓ Loaded {len(df)} rows → raw.weather_daily")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Fetching UK weather data for 2024...\n")

    all_cities = []
    for city in UK_CITIES:
        df = fetch_weather(city)
        all_cities.append(df)

    df_all = pd.concat(all_cities, ignore_index=True)
    print(f"\nTotal rows: {len(df_all)}")
    print(f"Columns: {list(df_all.columns)}")

    print("\nLoading to PostgreSQL...")
    engine = get_engine()
    load_to_postgres(df_all, engine)
    print("\nDone!")


if __name__ == "__main__":
    main()