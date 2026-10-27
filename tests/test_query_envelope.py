"""B1 (Overpass side) and B3: query box used for retrieval, and its coverage of the renderer viewport.

Clean-HEAD compatible: the B1 call uses only parameters present at HEAD.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import osmnx as ox
import pytest
from pyproj import Transformer
from shapely.geometry import Point

from generator.core.bundle_viewport_policy import compute_osm_bundle_viewport
from generator.core.osm_bundle_cache import load_or_build_shared_osm_bundle
from generator.core.render_dispatcher import get_viewport_for_style
from generator.core.style_registry import STYLE_REGISTRY
from generator.specs import SIZES_CM, spec_from_size_key
from support.overpass_fake import FakeOverpass
from support.synthetic_osm import CENTER_LAT, CENTER_LON, build_features, build_road_network

EARTH_RADIUS_M = 6_371_009
EXTENTS_M = (1000, 2000, 5000)
EDGE_SAMPLE_STEP_M = 50.0

LOCATIONS = {
    "equator": (0.0, 19.04),
    "budapest": (CENTER_LAT, CENTER_LON),
    "south_45": (-45.0, 170.0),
    "north_60": (60.0, 25.0),
    "north_65": (65.0, 25.0),
    "utm_boundary_west": (47.5, 17.9999),
    "utm_boundary_east": (47.5, 18.0001),
}


def _expected_dist_m(bundle_half_width_m: float, bundle_half_height_m: float) -> int:
    return int(math.ceil(math.sqrt(bundle_half_width_m**2 + bundle_half_height_m**2))) + 300


def _topology_buffer(polygon):
    poly_proj, crs_utm = ox.projection.project_geometry(polygon)
    poly_buff, _ = ox.projection.project_geometry(poly_proj.buffer(500), crs=crs_utm, to_latlong=True)
    return poly_buff


def test_overpass_path_uses_osmnx_query_box_for_bundle_distance(monkeypatch):
    network = build_road_network()
    build_features(network.builder)
    fake = FakeOverpass(network.builder.elements).install(monkeypatch)

    load_or_build_shared_osm_bundle(
        center_lat=CENTER_LAT,
        center_lon=CENTER_LON,
        extent_m=560,
        half_width_m=420.0,
        half_height_m=560.0,
        use_cache=False,
        include_building_features=True,
    )

    dist_m = _expected_dist_m(420.0, 560.0)
    assert dist_m == 1000
    query_polygon = ox.utils_geo.bbox_to_poly(ox.utils_geo.bbox_from_point((CENTER_LAT, CENTER_LON), dist_m))

    assert len(fake.network_calls) == 1
    assert fake.network_calls[0][0].equals_exact(_topology_buffer(query_polygon), 0)
    assert len(fake.feature_calls) == 9
    assert all(polygon.equals_exact(query_polygon, 0) for polygon, _ in fake.feature_calls)

    rounded_polygon = ox.utils_geo.bbox_to_poly(
        ox.utils_geo.bbox_from_point((round(CENTER_LAT, 6), round(CENTER_LON, 6)), dist_m)
    )
    assert not query_polygon.equals_exact(rounded_polygon, 0)


def _rectangle_samples(cx: float, cy: float, half_width_m: float, half_height_m: float) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for x0, y0, x1, y1 in (
        (-half_width_m, -half_height_m, half_width_m, -half_height_m),
        (half_width_m, -half_height_m, half_width_m, half_height_m),
        (half_width_m, half_height_m, -half_width_m, half_height_m),
        (-half_width_m, half_height_m, -half_width_m, -half_height_m),
    ):
        steps = max(int(math.ceil(math.hypot(x1 - x0, y1 - y0) / EDGE_SAMPLE_STEP_M)), 1)
        t = np.linspace(0.0, 1.0, steps + 1)
        xs.append(cx + x0 + (x1 - x0) * t)
        ys.append(cy + y0 + (y1 - y0) * t)
    return np.concatenate(xs), np.concatenate(ys)


@pytest.mark.parametrize("location", sorted(LOCATIONS))
def test_query_box_covers_projected_renderer_viewport(location):
    lat, lon = LOCATIONS[location]
    # Same centre projection the engines use (ox.projection.project_gdf on a single point).
    center_p = ox.projection.project_gdf(gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326"))
    cx, cy = center_p.geometry.iloc[0].x, center_p.geometry.iloc[0].y
    to_lonlat = Transformer.from_crs(center_p.crs, "EPSG:4326", always_xy=True)

    worst = None
    failures = []
    for style_name in sorted(STYLE_REGISTRY):
        for size_key in SIZES_CM:
            for extent_m in EXTENTS_M:
                spec = spec_from_size_key(size_key, extent_m=extent_m)
                half_width_m, half_height_m = get_viewport_for_style(style_name, spec)
                dist_m = _expected_dist_m(*compute_osm_bundle_viewport(spec))
                west, south, east, north = ox.utils_geo.bbox_from_point((lat, lon), dist_m)

                sample_lon, sample_lat = to_lonlat.transform(*_rectangle_samples(cx, cy, half_width_m, half_height_m))
                m_per_deg_lat = math.radians(1.0) * EARTH_RADIUS_M
                m_per_deg_lon = m_per_deg_lat * np.cos(np.radians(sample_lat))
                margin_m = float(np.min(np.minimum.reduce([
                    (sample_lon - west) * m_per_deg_lon,
                    (east - sample_lon) * m_per_deg_lon,
                    (sample_lat - south) * m_per_deg_lat,
                    (north - sample_lat) * m_per_deg_lat,
                ])))

                record = (margin_m, style_name, size_key, extent_m, dist_m)
                if worst is None or margin_m < worst[0]:
                    worst = record
                if margin_m <= 0:
                    failures.append(record)

    print(
        f"\n[B3] {location} ({center_p.crs.to_string()}): minimum margin {worst[0]:.1f} m "
        f"at {worst[1]} {worst[2]} E={worst[3]} dist_m={worst[4]}"
    )
    assert not failures, f"[B3] {location}: renderer viewport not covered by query box: {failures[:10]}"
