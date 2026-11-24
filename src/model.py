from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"zone_id", "latitude", "longitude", "radiance", "distance_km"}


def validate_input(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas obligatorias: {sorted(missing)}")
    if df.empty:
        raise ValueError("El conjunto de zonas está vacío.")
    if df["zone_id"].duplicated().any():
        raise ValueError("zone_id debe ser único.")
    if (pd.to_numeric(df["distance_km"], errors="coerce") < 0).any():
        raise ValueError("distance_km no puede ser negativa.")


def contribution_index(
    radiance: pd.Series | np.ndarray,
    distance_km: pd.Series | np.ndarray,
    *,
    alpha: float = 2.0,
    spatial_scale_km: float = 5.0,
) -> np.ndarray:
    """Índice exploratorio de contribución relativa.

    NO es un modelo físico validado de skyglow. Usa una ley de potencia suavizada:
        C = L / (d^2 + s^2)^(alpha/2)

    El término s evita que la celda que contiene al observatorio se comporte como
    una fuente puntual a distancia cero. Esto es especialmente importante cuando
    las observaciones representan promedios de celdas territoriales de varios km.
    """
    r = np.maximum(np.asarray(radiance, dtype=float), 0.0)
    d = np.maximum(np.asarray(distance_km, dtype=float), 0.0)
    s = max(float(spatial_scale_km), 0.1)
    effective_distance = np.sqrt(np.square(d) + s**2)
    return r / np.power(effective_distance, float(alpha))


def rank_zones(
    df: pd.DataFrame,
    *,
    reduction_pct: float = 20.0,
    alpha: float = 2.0,
    spatial_scale_km: float = 5.0,
) -> pd.DataFrame:
    """Simula una reducción estandarizada por zona y ordena el beneficio marginal."""
    validate_input(df)
    if not 0 < reduction_pct < 100:
        raise ValueError("reduction_pct debe estar entre 0 y 100.")
    if alpha <= 0:
        raise ValueError("alpha debe ser positivo.")
    if spatial_scale_km <= 0:
        raise ValueError("spatial_scale_km debe ser positivo.")

    out = df.copy()
    out["radiance"] = pd.to_numeric(out["radiance"], errors="coerce").fillna(0.0)
    out["distance_km"] = pd.to_numeric(out["distance_km"], errors="coerce")
    out = out.dropna(subset=["distance_km"]).copy()

    base = contribution_index(
        out["radiance"], out["distance_km"], alpha=alpha, spatial_scale_km=spatial_scale_km
    )
    reduced_radiance = np.maximum(out["radiance"].to_numpy(dtype=float), 0.0) * (1.0 - reduction_pct / 100.0)
    reduced = contribution_index(
        reduced_radiance, out["distance_km"], alpha=alpha, spatial_scale_km=spatial_scale_km
    )

    out["contribution_base"] = base
    out["contribution_reduced"] = reduced
    out["marginal_benefit"] = base - reduced

    out["brightness_rank"] = out["radiance"].rank(method="min", ascending=False).astype(int)
    out["priority_rank"] = out["marginal_benefit"].rank(method="min", ascending=False).astype(int)
    out["rank_delta"] = out["brightness_rank"] - out["priority_rank"]

    # Dos escalas distintas: magnitud relativa y posición relativa del ranking.
    # El percentil se usa para el color del mapa porque evita que un único extremo
    # comprima visualmente a todas las demás zonas cerca de cero.
    max_b = float(out["marginal_benefit"].max()) if len(out) else 0.0
    out["relative_benefit"] = 0.0 if max_b <= 0 else 100.0 * out["marginal_benefit"] / max_b
    n = len(out)
    if n <= 1:
        out["priority_score"] = 100.0
    else:
        out["priority_score"] = 100.0 * (n - out["priority_rank"]) / (n - 1)

    return out.sort_values(["priority_rank", "zone_id"]).reset_index(drop=True)
