import pandas as pd

from src.model import contribution_index, rank_zones


def sample():
    return pd.DataFrame({
        "zone_id": ["A", "B", "C"],
        "latitude": [-30.0, -30.1, -30.2],
        "longitude": [-70.8, -70.9, -71.0],
        "radiance": [10.0, 20.0, 100.0],
        "distance_km": [5.0, 20.0, 100.0],
    })


def test_ranking_complete_and_unique():
    out = rank_zones(sample())
    assert len(out) == 3
    assert out["priority_rank"].nunique() == 3


def test_reduction_scales_benefit():
    a = rank_zones(sample(), reduction_pct=10)
    b = rank_zones(sample(), reduction_pct=20)
    merged = a[["zone_id", "marginal_benefit"]].merge(
        b[["zone_id", "marginal_benefit"]], on="zone_id", suffixes=("_10", "_20")
    )
    ratio = merged["marginal_benefit_20"] / merged["marginal_benefit_10"]
    assert ((ratio - 2.0).abs() < 1e-10).all()


def test_brightness_not_necessarily_priority():
    out = rank_zones(sample(), alpha=2.0, spatial_scale_km=5.0)
    brightest = out.loc[out["brightness_rank"].idxmin(), "zone_id"]
    priority = out.loc[out["priority_rank"].idxmin(), "zone_id"]
    assert brightest != priority


def test_spatial_softening_is_finite_at_zero_distance():
    val = contribution_index([10.0], [0.0], alpha=2.0, spatial_scale_km=5.0)
    assert val[0] > 0
    assert val[0] < 1.0
