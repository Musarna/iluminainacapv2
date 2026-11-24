from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd

TOLOLO_LAT = -30.1777778
TOLOLO_LON = -70.8034972


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(a))


def load_zones(path_or_buffer) -> pd.DataFrame:
    df = pd.read_csv(path_or_buffer)
    rename = {
        "avg_rad": "radiance",
        "centroid_lat": "latitude",
        "centroid_lon": "longitude",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "distance_km" not in df.columns and {"latitude", "longitude"}.issubset(df.columns):
        df["distance_km"] = [
            haversine_km(TOLOLO_LAT, TOLOLO_LON, float(lat), float(lon))
            for lat, lon in zip(df["latitude"], df["longitude"])
        ]
    if "data_source" not in df.columns:
        df["data_source"] = "archivo_usuario"
    return df


def default_data_path() -> Path:
    real = Path("data/viirs_tololo.csv")
    return real if real.exists() else Path("data/demo_zones.csv")
