from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import warnings

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import random
from matplotlib import colors as mcolors
from PIL import Image

from shapely.geometry import Point, box

from generator.specs import ProductSpec
from generator.styles import get_style_config, MaptoposterLineStyleConfig, BlockStyleConfig
from generator.core.osm_bundle_cache import load_or_build_shared_osm_bundle


# ---------------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MapLayerResult:
    output_svg: Path


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _normalize_highway_value(v):
    return v[0] if isinstance(v, (list, tuple)) and v else v


def _normalize_maptoposter_road_type(highway_value) -> str:
    hw = str(_normalize_highway_value(highway_value) or "").strip().lower()
    if hw.endswith("_link"):
        hw = hw[:-5]

    if hw in {"motorway", "trunk", "primary", "secondary", "tertiary"}:
        return hw

    if hw in {"residential", "living_street", "unclassified", "service"}:
        return "residential"

    return "default"


def _resolve_maptoposter_edge_style(highway_value, road_colors: dict[str, str], road_widths: dict[str, float]) -> tuple[str, float]:
    road_type = _normalize_maptoposter_road_type(highway_value)
    color = road_colors.get(road_type, road_colors.get("default", "#777777"))
    width = road_widths.get(road_type, road_widths.get("default", 0.4))
    return color, float(width)


def _road_width_scale_for_extent_line(extent_m: float) -> float:
    """Linear width scaling for line engine.

    - 2000m extent -> 100% width
    - 10000m extent -> 70% width
    """
    min_extent = 2000.0
    max_extent = 10000.0
    max_reduction = 0.30

    clamped = max(min_extent, min(max_extent, float(extent_m)))
    t = (clamped - min_extent) / (max_extent - min_extent)
    return 1.0 - (max_reduction * t)


def _block_inherited_default_widths() -> dict[str, float]:
    """Derive default line widths from block road style hierarchy."""
    block_cfg = get_style_config("urban_modern")
    if not isinstance(block_cfg, BlockStyleConfig):
        # Safe fallback if style wiring changes.
        return {
            "motorway": 2.6,
            "trunk": 2.0,
            "primary": 2.0,
            "secondary": 1.5,
            "tertiary": 1.2,
            "residential": 0.9,
            "default": 0.9,
        }

    rs = block_cfg.road_style
    base = rs.base_width * 0.42
    mult_highway = rs.multipliers.get("highway", 2.4)
    mult_arterial = rs.multipliers.get("arterial", 1.8)
    mult_local = rs.multipliers.get("local", 1.0)
    mult_minor = rs.multipliers.get("minor", 0.6)
    mult_secondary = (mult_arterial + mult_local) / 2.0

    return {
        "motorway": base * mult_highway,
        "trunk": base * mult_arterial,
        "primary": base * mult_arterial,
        "secondary": base * mult_secondary,
        "tertiary": base * mult_local,
        "residential": base * mult_minor,
        "default": base * mult_minor,
    }


def _resolve_effective_line_widths(style_widths: dict[str, float], extent_m: float) -> dict[str, float]:
    """Combine style widths with block-inherited defaults and extent scaling."""
    inherited = _block_inherited_default_widths()
    extent_scale = _road_width_scale_for_extent_line(extent_m)

    widths: dict[str, float] = {}
    default_style_width = float(style_widths.get("default", inherited["default"]))

    for road_type, inherited_width in inherited.items():
        style_width = float(style_widths.get(road_type, default_style_width))
        # Keep style character but ensure stronger baseline hierarchy from block defaults.
        blended = max(style_width * 1.30, inherited_width * 0.85)
        widths[road_type] = blended * extent_scale

    return widths


def _prepare_polygon_layer(raw_layer: gpd.GeoDataFrame | None, target_crs, clip_rect) -> gpd.GeoDataFrame:
    if raw_layer is None or len(raw_layer) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    layer = raw_layer[(~raw_layer.geometry.isna()) & (~raw_layer.geometry.is_empty)]
    if len(layer) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    layer_p = layer.to_crs(target_crs)
    layer_p = layer_p[layer_p.geom_type.isin(["Polygon", "MultiPolygon"])]
    if len(layer_p) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    return gpd.clip(layer_p, gpd.GeoSeries([clip_rect], crs=target_crs))


def _prepare_line_layer(raw_layer: gpd.GeoDataFrame | None, target_crs, clip_rect) -> gpd.GeoDataFrame:
    if raw_layer is None or len(raw_layer) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    layer = raw_layer[(~raw_layer.geometry.isna()) & (~raw_layer.geometry.is_empty)]
    if len(layer) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    layer_p = layer.to_crs(target_crs)
    layer_p = layer_p[layer_p.geom_type.isin(["LineString", "MultiLineString"])]
    if len(layer_p) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=target_crs)

    return gpd.clip(layer_p, gpd.GeoSeries([clip_rect], crs=target_crs))


def _series_or_none(gdf: gpd.GeoDataFrame, column: str):
    return gdf[column] if column in gdf.columns else None


def _is_bridge_value(v) -> bool:
    if isinstance(v, (list, tuple, set)):
        return any(_is_bridge_value(item) for item in v)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s not in {"", "0", "false", "no", "none", "nan"}


def _relative_luminance(color: str) -> float:
    r, g, b = mcolors.to_rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _blend_towards(color: str, target: str, amount: float) -> str:
    r, g, b = mcolors.to_rgb(color)
    tr, tg, tb = mcolors.to_rgb(target)
    a = max(0.0, min(1.0, amount))
    return mcolors.to_hex((r + (tr - r) * a, g + (tg - g) * a, b + (tb - b) * a))


def _build_fallback_paper_texture(height: int = 1200, width: int = 900) -> np.ndarray:
    """Create a subtle warm paper-like texture when no texture image file is available."""
    rng = np.random.default_rng(42)
    base = np.array([246, 239, 228], dtype=np.float32)

    # Fine grain and broad cloud-like variation for a vintage paper feel.
    fine = rng.normal(loc=0.0, scale=8.0, size=(height, width, 1)).astype(np.float32)
    cloud_small = rng.normal(loc=0.0, scale=1.0, size=(height // 10 + 2, width // 10 + 2, 1)).astype(np.float32)
    cloud = np.kron(cloud_small, np.ones((10, 10, 1), dtype=np.float32))[:height, :width, :]

    texture = base + fine + (cloud * 6.0)
    return np.clip(texture, 0, 255).astype(np.uint8)


def _cover_crop_to_aspect(image: Image.Image, target_aspect: float) -> Image.Image:
    """Center-crop image to target aspect ratio (cover behavior, no distortion)."""
    if target_aspect <= 0:
        return image

    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    current_aspect = width / height
    if abs(current_aspect - target_aspect) < 1e-6:
        return image

    if current_aspect > target_aspect:
        new_width = int(round(height * target_aspect))
        left = max((width - new_width) // 2, 0)
        return image.crop((left, 0, left + new_width, height))

    new_height = int(round(width / target_aspect))
    top = max((height - new_height) // 2, 0)
    return image.crop((0, top, width, top + new_height))


# ---------------------------------------------------------------------------
# MAIN LINE ENGINE
# ---------------------------------------------------------------------------

def render_map_line(
    *,
    center_lat: float,
    center_lon: float,
    spec: ProductSpec,
    map_width_cm: float,
    map_height_cm: float,
    viewport_half_width_m: float,
    viewport_half_height_m: float,
    bundle_half_width_m: Optional[float] = None,
    bundle_half_height_m: Optional[float] = None,
    output_dir: Path,
    palette_name: str,
    seed: Optional[int] = 42,
    filename_prefix: str = "map_layer_line",
    preview_mode: bool = False,
    use_cache: bool = True,
    draw_background_texture: bool = True,
    transparent_map_background: bool = False,
) -> MapLayerResult:

    style_cfg = get_style_config(palette_name)

    if not isinstance(style_cfg, MaptoposterLineStyleConfig):
        raise TypeError(f"Style '{palette_name}' is not line-based.")

    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig_w_in = map_width_cm / 2.54
    fig_h_in = map_height_cm / 2.54
    half_width_m, half_height_m = viewport_half_width_m, viewport_half_height_m
    bundle_hw = half_width_m if bundle_half_width_m is None else float(bundle_half_width_m)
    bundle_hh = half_height_m if bundle_half_height_m is None else float(bundle_half_height_m)
    extent_m = int(spec.extent_m)
    # -----------------------------------------------------------------------
    # CENTER + CLIP
    # -----------------------------------------------------------------------

    center = gpd.GeoDataFrame(
        geometry=[Point(center_lon, center_lat)],
        crs="EPSG:4326",
    )

    center_p = ox.projection.project_gdf(center).geometry.iloc[0]

    minx = center_p.x - half_width_m
    maxx = center_p.x + half_width_m
    miny = center_p.y - half_height_m
    maxy = center_p.y + half_height_m
    clip_rect = box(minx, miny, maxx, maxy)

    def _build_geometry():
        edges = shared_bundle["edges_raw"]
        edges_p = ox.projection.project_gdf(edges)
        edges_p = gpd.clip(edges_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))
        edges_p = edges_p[~edges_p.is_empty]

        gdf_all_raw = shared_bundle["gdf_all_raw"]
        coast_raw = shared_bundle["coast_raw"]
        water_raw = shared_bundle["water_raw"]
        green_raw = shared_bundle["green_raw"]

        water_p = _prepare_polygon_layer(water_raw, edges_p.crs, clip_rect)
        green_p = _prepare_polygon_layer(green_raw, edges_p.crs, clip_rect)
        gdf_all_p = _prepare_polygon_layer(gdf_all_raw, edges_p.crs, clip_rect)
        gdf_all_any_p = gpd.GeoDataFrame(geometry=[], crs=edges_p.crs)
        coast_lines_p = _prepare_line_layer(coast_raw, edges_p.crs, clip_rect)

        if gdf_all_raw is not None and len(gdf_all_raw) > 0:
            gdf_all_raw = gdf_all_raw[(~gdf_all_raw.geometry.isna()) & (~gdf_all_raw.geometry.is_empty)]
            if len(gdf_all_raw) > 0:
                gdf_all_any_p = gdf_all_raw.to_crs(edges_p.crs)
                gdf_all_any_p = gpd.clip(gdf_all_any_p, gpd.GeoSeries([clip_rect], crs=edges_p.crs))

        landuse = _series_or_none(gdf_all_p, "landuse")
        amenity = _series_or_none(gdf_all_p, "amenity")
        natural = _series_or_none(gdf_all_p, "natural")
        man_made = _series_or_none(gdf_all_any_p, "man_made")

        harbour_p = gdf_all_p[(landuse == "harbour") if landuse is not None else False]
        marina_p = gdf_all_p[(amenity == "marina") if amenity is not None else False]
        shingle_p = gdf_all_p[(natural == "shingle") if natural is not None else False]
        beach_p = gdf_all_p[(natural.isin(["beach", "sand"])) if natural is not None else False]
        pier_p = gdf_all_any_p[
            ((man_made == "pier") if man_made is not None else False)
            & gdf_all_any_p.geom_type.isin(["LineString", "MultiLineString"])
        ]
        breakwater_p = gdf_all_any_p[
            ((man_made == "breakwater") if man_made is not None else False)
            & gdf_all_any_p.geom_type.isin(["LineString", "MultiLineString"])
        ]

        if "highway" in edges_p.columns:
            edges_p = edges_p.copy()
            edges_p["highway"] = edges_p["highway"].apply(_normalize_highway_value)

        return {
            "edges_p": edges_p,
            "water_p": water_p,
            "green_p": green_p,
            "harbour_p": harbour_p,
            "marina_p": marina_p,
            "shingle_p": shingle_p,
            "beach_p": beach_p,
            "coast_lines_p": coast_lines_p,
            "pier_p": pier_p,
            "breakwater_p": breakwater_p,
        }

    shared_bundle = load_or_build_shared_osm_bundle(
        center_lat=center_lat,
        center_lon=center_lon,
        extent_m=extent_m,
        half_width_m=bundle_hw,
        half_height_m=bundle_hh,
        use_cache=use_cache,
        include_building_features=True,
    )

    geometry_data = _build_geometry()

    edges_p = geometry_data["edges_p"]
    water_p = geometry_data["water_p"]
    green_p = geometry_data["green_p"]
    harbour_p = geometry_data["harbour_p"]
    marina_p = geometry_data["marina_p"]
    shingle_p = geometry_data["shingle_p"]
    beach_p = geometry_data["beach_p"]
    coast_lines_p = geometry_data["coast_lines_p"]
    pier_p = geometry_data["pier_p"]
    breakwater_p = geometry_data["breakwater_p"]

    # -----------------------------------------------------------------------
    # PLOT
    # -----------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in))
    target_aspect = (maxx - minx) / (maxy - miny)

    render_cfg = style_cfg.render
    effective_road_widths = _resolve_effective_line_widths(render_cfg.road_widths, extent_m)
    if transparent_map_background:
        fig.patch.set_alpha(0.0)
        ax.set_facecolor("none")
    else:
        fig.patch.set_facecolor(render_cfg.background)
        ax.set_facecolor(render_cfg.background)

    # Optional texture overlay for paper-like backgrounds.
    if draw_background_texture and render_cfg.background_texture_path:
        texture_path = Path(render_cfg.background_texture_path)
        if not texture_path.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            texture_path = project_root / texture_path

        texture_opacity = max(0.0, min(1.0, float(render_cfg.background_texture_opacity)))
        if texture_path.exists():
            if texture_opacity > 0.0:
                with Image.open(texture_path) as texture_img:
                    texture_rgb = _cover_crop_to_aspect(texture_img.convert("RGB"), target_aspect)
                    ax.imshow(
                        texture_rgb,
                        extent=(minx, maxx, miny, maxy),
                        interpolation="bilinear",
                        alpha=texture_opacity,
                        zorder=0,
                    )
        elif texture_opacity > 0.0:
            warnings.warn(
                f"Texture file not found for style '{palette_name}': {texture_path}. Using procedural paper texture.",
                RuntimeWarning,
            )
            fallback_texture = _build_fallback_paper_texture()
            ax.imshow(
                fallback_texture,
                extent=(minx, maxx, miny, maxy),
                interpolation="bilinear",
                alpha=texture_opacity,
                zorder=0,
            )

    water_lum = _relative_luminance(render_cfg.water)
    water_edge_target = "#F6F4EF" if water_lum < 0.55 else "#3A3A3A"
    water_edge = _blend_towards(render_cfg.water, water_edge_target, 0.18)
    water_alpha = 0.4 if palette_name == "vintage_atlas" else 0.78
    bridge_color = _blend_towards(
        render_cfg.road_colors.get("primary", render_cfg.road_colors.get("default", "#666666")),
        "#FFFFFF" if water_lum < 0.55 else "#111111",
        0.22,
    )

    if len(water_p) > 0:
        water_p.plot(
            ax=ax,
            color=render_cfg.water,
            edgecolor=water_edge,
            linewidth=0.35,
            alpha=water_alpha,
            antialiased=True,
            zorder=1,
        )

    if len(green_p) > 0:
        green_p.plot(
            ax=ax,
            color=render_cfg.parks,
            edgecolor="none",
            alpha=0.48,
            antialiased=True,
            zorder=2,
        )

    if palette_name == "vintage_atlas":
        harbour_color = _blend_towards(render_cfg.parks, render_cfg.water, 0.38)
        marina_color = _blend_towards(render_cfg.parks, render_cfg.water, 0.28)
        shingle_color = _blend_towards("#CFC6B8", render_cfg.water, 0.36)
        beach_color = _blend_towards("#E4D9C8", render_cfg.water, 0.28)
        coastline_color = _blend_towards("#6E665D", render_cfg.water, 0.14)
        pier_color = _blend_towards("#4E4A46", render_cfg.water, 0.08)
        breakwater_color = _blend_towards("#3F3B38", render_cfg.water, 0.06)
        harbour_edge = _blend_towards(harbour_color, "#2B2A2A", 0.18)
        marina_edge = _blend_towards(marina_color, "#2B2A2A", 0.18)
        shingle_edge = _blend_towards(shingle_color, "#2B2A2A", 0.14)
    else:
        harbour_color = _blend_towards(render_cfg.parks, render_cfg.water, 0.26)
        marina_color = _blend_towards(render_cfg.parks, render_cfg.water, 0.18)
        shingle_color = _blend_towards("#C9C2B4", render_cfg.water, 0.20)
        beach_color = _blend_towards("#D5CCBA", render_cfg.water, 0.18)
        coastline_color = _blend_towards(render_cfg.water, render_cfg.road_colors.get("default", "#777777"), 0.28)
        pier_color = _blend_towards(render_cfg.road_colors.get("default", "#777777"), render_cfg.water, 0.16)
        breakwater_color = _blend_towards(render_cfg.road_colors.get("primary", "#666666"), render_cfg.water, 0.10)
        harbour_edge = _blend_towards(harbour_color, render_cfg.background, 0.25)
        marina_edge = _blend_towards(marina_color, render_cfg.background, 0.25)
        shingle_edge = _blend_towards(shingle_color, render_cfg.background, 0.18)

    if len(beach_p) > 0:
        beach_p.plot(
            ax=ax,
            color=beach_color,
            edgecolor="none",
            alpha=0.26 if palette_name == "vintage_atlas" else 0.20,
            antialiased=True,
            zorder=1.10,
        )

    if len(harbour_p) > 0:
        harbour_p.plot(
            ax=ax,
            color=harbour_color,
            edgecolor=harbour_edge,
            linewidth=0.10,
            alpha=0.42 if palette_name == "vintage_atlas" else 0.32,
            antialiased=True,
            zorder=1.15,
        )

    if len(marina_p) > 0:
        marina_p.plot(
            ax=ax,
            color=marina_color,
            edgecolor=marina_edge,
            linewidth=0.12,
            alpha=0.38 if palette_name == "vintage_atlas" else 0.28,
            antialiased=True,
            zorder=1.18,
        )

    if len(shingle_p) > 0:
        shingle_p.plot(
            ax=ax,
            color=shingle_color,
            edgecolor=shingle_edge,
            linewidth=0.04,
            alpha=0.28 if palette_name == "vintage_atlas" else 0.24,
            antialiased=True,
            zorder=1.12,
        )

    if len(coast_lines_p) > 0:
        coast_lines_p.plot(
            ax=ax,
            color=coastline_color,
            linewidth=0.46 if palette_name == "vintage_atlas" else 0.40,
            alpha=0.84 if palette_name == "vintage_atlas" else 0.72,
            antialiased=True,
            zorder=1.30,
        )

    if len(pier_p) > 0:
        pier_p.plot(
            ax=ax,
            color=pier_color,
            linewidth=0.62 if palette_name == "vintage_atlas" else 0.52,
            alpha=0.84 if palette_name == "vintage_atlas" else 0.76,
            antialiased=True,
            zorder=1.34,
        )

    if len(breakwater_p) > 0:
        breakwater_p.plot(
            ax=ax,
            color=breakwater_color,
            linewidth=0.70 if palette_name == "vintage_atlas" else 0.60,
            alpha=0.86 if palette_name == "vintage_atlas" else 0.78,
            antialiased=True,
            zorder=1.35,
        )

    edges_p = edges_p.copy()
    if "highway" in edges_p.columns:
        resolved_styles = edges_p["highway"].apply(
            lambda hw: _resolve_maptoposter_edge_style(hw, render_cfg.road_colors, effective_road_widths)
        )
    else:
        resolved_styles = edges_p.geometry.apply(
            lambda _: _resolve_maptoposter_edge_style("default", render_cfg.road_colors, effective_road_widths)
        )

    edges_p["_mp_color"] = resolved_styles.apply(lambda item: item[0])
    edges_p["_mp_width"] = resolved_styles.apply(lambda item: item[1])

    if len(edges_p) > 0:
        width_order = sorted(edges_p["_mp_width"].unique(), reverse=True)
        for draw_index, width in enumerate(width_order):
            subset = edges_p[edges_p["_mp_width"] == width]
            if len(subset) == 0:
                continue
            subset.plot(
                ax=ax,
                color=subset["_mp_color"].tolist(),
                linewidth=width,
                alpha=0.97,
                capstyle="round",
                joinstyle="round",
                antialiased=True,
                snap=False,
                zorder=12 + draw_index,
            )

    if "bridge" in edges_p.columns:
        bridges = edges_p[edges_p["bridge"].apply(_is_bridge_value)]
    else:
        bridges = edges_p.iloc[0:0]

    if len(bridges) > 0:
        bridge_width_order = sorted(bridges["_mp_width"].unique(), reverse=True)
        for draw_index, width in enumerate(bridge_width_order):
            bridge_subset = bridges[bridges["_mp_width"] == width]
            if len(bridge_subset) == 0:
                continue
            bridge_subset.plot(
                ax=ax,
                color=bridge_color,
                linewidth=width * 1.10,
                alpha=1.0,
                capstyle="round",
                joinstyle="round",
                antialiased=True,
                snap=False,
                zorder=30 + draw_index,
            )

    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_axis_off()
    ax.set_position([0, 0, 1, 1])

    # -----------------------------------------------------------------------
    # SAVE
    # -----------------------------------------------------------------------

    if preview_mode:
        output_path = output_dir / f"{filename_prefix}.png"
        fig.savefig(
            output_path,
            format="png",
            dpi=140,
            pad_inches=0,
        )
    else:
        output_path = output_dir / f"{filename_prefix}.svg"
        fig.savefig(
            output_path,
            format="svg",
            pad_inches=0,
            transparent=transparent_map_background,
        )

    plt.close(fig)

    return MapLayerResult(output_svg=output_path)