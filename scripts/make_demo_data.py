from pathlib import Path
import pandas as pd
from src.data import TOLOLO_LAT, TOLOLO_LON, haversine_km

# Datos deliberadamente sintéticos: sirven solo para probar el flujo del prototipo.
rows = [
    ("Z01", -30.03, -70.92, 10.0, 9),
    ("Z02", -29.95, -71.18, 38.0, 11),
    ("Z03", -30.08, -71.02, 18.0, 8),
    ("Z04", -30.22, -70.68, 7.0, 12),
    ("Z05", -30.32, -70.60, 15.0, 10),
    ("Z06", -30.42, -70.92, 32.0, 7),
    ("Z07", -29.84, -71.28, 65.0, 14),
    ("Z08", -30.10, -70.74, 5.0, 13),
    ("Z09", -30.52, -71.12, 55.0, 9),
    ("Z10", -29.97, -70.75, 8.0, 10),
    ("Z11", -30.18, -71.08, 24.0, 12),
    ("Z12", -30.27, -70.77, 4.5, 8),
]
records=[]
for zone_id, lat, lon, rad, cov in rows:
    records.append({
        "zone_id": zone_id,
        "latitude": lat,
        "longitude": lon,
        "radiance": rad,
        "cf_cvg": cov,
        "distance_km": haversine_km(TOLOLO_LAT, TOLOLO_LON, lat, lon),
        "data_source": "synthetic_demo",
    })
Path("data").mkdir(exist_ok=True)
pd.DataFrame(records).to_csv("data/demo_zones.csv", index=False)
print("Creado data/demo_zones.csv")
