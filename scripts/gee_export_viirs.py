"""Genera data/viirs_tololo.csv desde Google Earth Engine.

Uso típico (después de crear/registrar el proyecto Cloud):
    python scripts/gee_export_viirs.py --project TU_PROJECT_ID --authenticate

El script crea una grilla regular alrededor de Cerro Tololo, calcula radiancia VIIRS
promedio y cobertura cloud-free para cada celda y guarda solo una tabla CSV.
"""
from __future__ import annotations

import argparse
from math import ceil
from pathlib import Path
import sys

# Permite ejecutar este archivo directamente desde la carpeta scripts/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, box, shape
from shapely.ops import transform as shp_transform

from src.data import TOLOLO_LAT, TOLOLO_LON, haversine_km

DATASET = "NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG"
ADMIN_DATASET = "FAO/GAUL/2025/level1"


def build_grid(radius_km: float, cell_km: float):
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True).transform
    to_wgs = Transformer.from_crs("EPSG:32719", "EPSG:4326", always_xy=True).transform
    cx, cy = to_utm(TOLOLO_LON, TOLOLO_LAT)
    radius_m, cell_m = radius_km * 1000.0, cell_km * 1000.0
    n = ceil(radius_m / cell_m)
    rows=[]
    zid=1
    for ix in range(-n, n + 1):
        for iy in range(-n, n + 1):
            minx = cx + (ix - 0.5) * cell_m
            maxx = cx + (ix + 0.5) * cell_m
            miny = cy + (iy - 0.5) * cell_m
            maxy = cy + (iy + 0.5) * cell_m
            poly_utm = box(minx, miny, maxx, maxy)
            c = poly_utm.centroid
            if ((c.x - cx) ** 2 + (c.y - cy) ** 2) ** 0.5 > radius_m:
                continue
            poly_wgs = shp_transform(to_wgs, poly_utm)
            centroid_wgs = shp_transform(to_wgs, c)
            coords = list(poly_wgs.exterior.coords)
            rows.append({
                "zone_id": f"G{zid:03d}",
                "polygon": [[float(x), float(y)] for x, y in coords],
                "latitude": float(centroid_wgs.y),
                "longitude": float(centroid_wgs.x),
            })
            zid += 1
    return rows


def load_coquimbo_boundary(ee):
    """Obtiene la región chilena de nivel 1 que contiene Cerro Tololo.

    Evita depender del nombre exacto usado por GAUL (por ejemplo, "Coquimbo",
    "Coquimbo Region", etc.). Primero restringe a Chile y luego consulta qué
    unidad administrativa contiene las coordenadas del observatorio.
    """
    tololo = ee.Geometry.Point([TOLOLO_LON, TOLOLO_LAT])
    chile = ee.FeatureCollection(ADMIN_DATASET).filter(
        ee.Filter.eq("ISO3_CODE", "CHL")
    )

    # Respaldo por si el catálogo cambiara el código ISO en una versión futura.
    if int(chile.size().getInfo()) == 0:
        chile = ee.FeatureCollection(ADMIN_DATASET).filter(
            ee.Filter.eq("GAUL0_NAME", "Chile")
        )

    region_fc = chile.filterBounds(tololo)
    count = int(region_fc.size().getInfo())
    if count == 0:
        available = chile.aggregate_array("GAUL1_NAME").distinct().sort().getInfo()
        raise RuntimeError(
            "GAUL no devolvió ninguna región chilena que contenga Cerro Tololo. "
            f"Regiones disponibles: {available}"
        )

    region = ee.Feature(region_fc.first())
    region_name = region.get("GAUL1_NAME").getInfo()
    country_name = region.get("GAUL0_NAME").getInfo()
    print(f"Límite administrativo detectado: {region_name}, {country_name}")

    # Verificación informativa: no hacemos depender el filtro del texto exacto.
    if "coquimbo" not in str(region_name).lower():
        print(
            "ADVERTENCIA: GAUL no nombró la unidad detectada como Coquimbo. "
            "Se usará de todos modos la región chilena que contiene Cerro Tololo."
        )

    # La geometría puede ser Polygon o MultiPolygon; shapely.shape maneja ambos.
    return shape(region.geometry().getInfo())


def filter_grid_to_region(grid, region_geom):
    """Conserva celdas cuyo centro cae dentro (o sobre el borde) de la región."""
    return [
        row
        for row in grid
        if region_geom.covers(Point(row["longitude"], row["latitude"]))
    ]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True, help="ID del Google Cloud Project habilitado para Earth Engine")
    p.add_argument("--start", default="2026-06-01")
    p.add_argument("--end", default="2026-09-01", help="Fecha final exclusiva")
    p.add_argument("--radius-km", type=float, default=100.0)
    p.add_argument("--cell-km", type=float, default=10.0)
    p.add_argument("--min-coverage", type=float, default=1.0)
    p.add_argument("--output", default="data/viirs_tololo.csv")
    p.add_argument("--authenticate", action="store_true")
    args = p.parse_args()

    import ee
    if args.authenticate:
        ee.Authenticate()
    ee.Initialize(project=args.project)

    grid = build_grid(args.radius_km, args.cell_km)
    initial_count = len(grid)
    coquimbo = load_coquimbo_boundary(ee)
    grid = filter_grid_to_region(grid, coquimbo)
    print(
        f"Filtro territorial: {initial_count} celdas en el radio -> "
        f"{len(grid)} con centro dentro de la Región de Coquimbo"
    )

    if not grid:
        raise RuntimeError(
            "El filtro territorial dejó la grilla vacía. Revisa radio, tamaño de celda o límite administrativo."
        )

    features=[]
    for row in grid:
        geom = ee.Geometry.Polygon([row["polygon"]], proj="EPSG:4326", geodesic=False)
        features.append(ee.Feature(geom, {
            "zone_id": row["zone_id"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
        }))
    fc = ee.FeatureCollection(features)

    def prep(img):
        valid = img.select("cf_cvg").gt(0)
        return img.select(["avg_rad", "cf_cvg"], ["radiance", "coverage"]).updateMask(valid)

    collection = ee.ImageCollection(DATASET).filterDate(args.start, args.end).map(prep)
    composite = collection.mean()
    stats = composite.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.mean(),
        scale=463.83,
        tileScale=4,
    )
    info = stats.getInfo()

    records=[]
    for feat in info.get("features", []):
        prop = feat.get("properties", {})
        rad = prop.get("radiance")
        cov = prop.get("coverage")
        if rad is None or cov is None or float(cov) < args.min_coverage:
            continue
        lat, lon = float(prop["latitude"]), float(prop["longitude"])
        records.append({
            "zone_id": prop["zone_id"],
            "latitude": lat,
            "longitude": lon,
            "radiance": max(float(rad), 0.0),
            "cf_cvg": float(cov),
            "distance_km": haversine_km(TOLOLO_LAT, TOLOLO_LON, lat, lon),
            "data_source": f"VIIRS:{DATASET}:{args.start}:{args.end}",
            "admin_region": "Coquimbo",
        })

    out = pd.DataFrame(records).sort_values("zone_id")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Guardadas {len(out)} zonas en {args.output}")


if __name__ == "__main__":
    main()
