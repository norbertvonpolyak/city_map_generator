from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from geopy.geocoders import Nominatim
from matplotlib.patches import Circle
from pytz import timezone, utc
from skyfield.api import Star, load, load_constellation_map, wgs84
from skyfield.data import hipparcos
from skyfield.projections import build_stereographic_projection

from generator.layouts.layout_star_map import StarLayoutMode, StarStyle, build_star_layout
from generator.nebula_background import NebulaParams, make_nebula_background


@dataclass(frozen=True)
class StarsRenderResult:
    output_pdf: Path
    output_preview_png: Path


_EPHEMERIS = None
_STAR_DF = None
_TS = None


def _load_celestial_assets():
    global _EPHEMERIS, _STAR_DF, _TS
    if _EPHEMERIS is None:
        _EPHEMERIS = load("de421.bsp")
    if _TS is None:
        _TS = load.timescale()
    if _STAR_DF is None:
        with load.open(hipparcos.URL) as f:
            _STAR_DF = hipparcos.load_dataframe(f)
    return _EPHEMERIS, _STAR_DF, _TS


def _parse_local_datetime(when_local: str | None, date_text: str | None) -> datetime:
    candidates: list[str] = []
    if when_local:
        candidates.append(when_local.strip())
    if date_text:
        candidates.append(date_text.strip())

    formats = (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y",
    )

    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue

    # Fallback: current UTC converted later according to target location.
    return datetime.utcnow().replace(second=0, microsecond=0)


def _resolve_coordinates(
    *,
    location_query: str | None,
    lat: float | None,
    lon: float | None,
) -> tuple[float, float]:
    if lat is not None and lon is not None:
        return float(lat), float(lon)

    if not location_query:
        raise ValueError("Either location_query or both lat/lon must be provided.")

    geolocator = Nominatim(user_agent="mapcanvas_starmap")
    place = geolocator.geocode(location_query)
    if place is None:
        raise ValueError(f"Could not geocode location: {location_query}")
    return float(place.latitude), float(place.longitude)


def _local_to_utc(*, local_dt: datetime, lat: float, lon: float) -> datetime:
    tz_name = None
    try:
        timezonefinder_module = importlib.import_module("timezonefinder")
        tz_name = timezonefinder_module.TimezoneFinder().timezone_at(lat=lat, lng=lon)
    except Exception:
        tz_name = None

    if not tz_name:
        return utc.localize(local_dt)

    local_tz = timezone(tz_name)
    localized = local_tz.localize(local_dt, is_dst=None)
    return localized.astimezone(utc)


def _project_visible_stars(
    *,
    lat: float,
    lon: float,
    utc_dt: datetime,
    limiting_magnitude: float,
    field_of_view_degrees: float,
    clip_to_circle: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    eph, stars_df, ts = _load_celestial_assets()
    t = ts.from_datetime(utc_dt)

    earth = eph["earth"]
    observer = earth + wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon)
    observer_at_t = observer.at(t)

    zenith = observer_at_t.from_altaz(alt_degrees=90, az_degrees=0)
    ra, dec, _ = zenith.radec()
    center_object = Star(ra=ra, dec=dec)

    center = earth.at(t).observe(center_object)
    projection = build_stereographic_projection(center)

    star_positions = observer_at_t.observe(Star.from_dataframe(stars_df)).apparent()
    x_all, y_all = projection(star_positions)
    alt, _, _ = star_positions.altaz()
    alt_degrees = alt.degrees

    magnitudes = stars_df["magnitude"].to_numpy()
    valid = (
        np.isfinite(x_all)
        & np.isfinite(y_all)
        & np.isfinite(magnitudes)
        & np.isfinite(alt_degrees)
        & (magnitudes <= limiting_magnitude)
        & (alt_degrees >= 0.0)
    )

    x = x_all[valid]
    y = y_all[valid]
    mag = magnitudes[valid]

    if x.size == 0:
        return np.array([]), np.array([]), np.array([])

    # At 180 degrees full disk is shown; smaller FOV narrows the visible area.
    fov = max(1.0, min(180.0, field_of_view_degrees))
    rho_limit = float(2.0 * np.tan(np.radians(fov / 4.0)))
    rho_limit = max(rho_limit, 1e-6)

    x = x / rho_limit
    y = y / rho_limit

    if clip_to_circle:
        inside = (x * x + y * y) <= 1.0
        return x[inside], y[inside], mag[inside]

    return x, y, mag


def _project_constellation_segments(
    *,
    lat: float,
    lon: float,
    utc_dt: datetime,
    limiting_magnitude: float,
    field_of_view_degrees: float,
    clip_to_circle: bool = True,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    def build_mst_edges(points_xy: np.ndarray) -> list[tuple[int, int]]:
        count = points_xy.shape[0]
        if count < 2:
            return []

        selected = [0]
        remaining = set(range(1, count))
        edges: list[tuple[int, int]] = []

        while remaining:
            best_dist = None
            best_i = -1
            best_j = -1
            remaining_arr = np.fromiter(remaining, dtype=int)

            for i in selected:
                diffs = points_xy[remaining_arr] - points_xy[i]
                dist_sq = np.einsum("ij,ij->i", diffs, diffs)
                min_idx = int(np.argmin(dist_sq))
                candidate_dist = float(dist_sq[min_idx])
                candidate_j = int(remaining_arr[min_idx])

                if best_dist is None or candidate_dist < best_dist:
                    best_dist = candidate_dist
                    best_i = i
                    best_j = candidate_j

            edges.append((best_i, best_j))
            selected.append(best_j)
            remaining.remove(best_j)

        return edges

    eph, stars_df, ts = _load_celestial_assets()

    # Use only very bright stars so line structures remain clearly readable.
    line_mag_limit = min(float(limiting_magnitude), 3.0)
    bright_df = stars_df[stars_df["magnitude"] <= line_mag_limit]
    if bright_df.empty:
        return []

    t = ts.from_datetime(utc_dt)

    earth = eph["earth"]
    observer = earth + wgs84.latlon(latitude_degrees=lat, longitude_degrees=lon)
    observer_at_t = observer.at(t)

    zenith = observer_at_t.from_altaz(alt_degrees=90, az_degrees=0)
    ra, dec, _ = zenith.radec()
    center_object = Star(ra=ra, dec=dec)
    center = earth.at(t).observe(center_object)
    projection = build_stereographic_projection(center)

    fov = max(1.0, min(180.0, field_of_view_degrees))
    rho_limit = float(2.0 * np.tan(np.radians(fov / 4.0)))
    rho_limit = max(rho_limit, 1e-6)

    star_positions = observer_at_t.observe(Star.from_dataframe(bright_df)).apparent()
    x_all, y_all = projection(star_positions)
    alt, _, _ = star_positions.altaz()
    alt_degrees = alt.degrees
    magnitudes = bright_df["magnitude"].to_numpy()
    constellation_labels = load_constellation_map()(star_positions)

    valid = (
        np.isfinite(x_all)
        & np.isfinite(y_all)
        & np.isfinite(magnitudes)
        & np.isfinite(alt_degrees)
        & (alt_degrees >= 0.0)
    )

    if not np.any(valid):
        return []

    x = (x_all[valid] / rho_limit).astype(float)
    y = (y_all[valid] / rho_limit).astype(float)
    mag = magnitudes[valid].astype(float)
    labels = np.asarray(constellation_labels)[valid]

    if clip_to_circle:
        inside = (x * x + y * y) <= 1.0
        x = x[inside]
        y = y[inside]
        mag = mag[inside]
        labels = labels[inside]

    if x.size < 2:
        return []

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for label in np.unique(labels):
        idx = np.flatnonzero(labels == label)
        if idx.size < 2:
            continue

        order = idx[np.argsort(mag[idx])]
        keep = order[: min(6, order.size)]
        pts = np.column_stack((x[keep], y[keep]))
        if pts.shape[0] < 2:
            continue

        mst_edges = build_mst_edges(pts)
        for i, j in mst_edges:
            segments.append(((float(pts[i, 0]), float(pts[i, 1])), (float(pts[j, 0]), float(pts[j, 1]))))

    return segments


def _build_prominent_nebula_layer(
    *,
    width_cm: float,
    height_cm: float,
    dpi: int,
    seed: int,
) -> np.ndarray:
    width_px = max(900, int((width_cm / 2.54) * dpi))
    height_px = max(900, int((height_cm / 2.54) * dpi))

    nebula = make_nebula_background(
        width_px=width_px,
        height_px=height_px,
        seed=seed,
        params=NebulaParams(
            base_darkness=0.96,
            fog_strength=1.85,
            blotch_strength=1.30,
            band_strength=0.80,
            lane_strength=0.22,
            grain_strength=0.10,
            splatter_small_strength=0.24,
            splatter_mid_strength=0.20,
            splatter_big_strength=0.16,
            final_blur=0.30,
            unsharp_radius=2.8,
            unsharp_percent=145,
            unsharp_threshold=1,
        ),
    )
    return np.asarray(nebula, dtype=np.uint8)


def _build_blue_sky_base_layer(*, width_px: int, height_px: int, seed: int) -> np.ndarray:
    _ = seed
    img = np.empty((height_px, width_px, 3), dtype=np.float32)
    img[..., 0] = 5.0 / 255.0
    img[..., 1] = 23.0 / 255.0
    img[..., 2] = 44.0 / 255.0
    return img


def _build_milky_way_layer(*, width_px: int, height_px: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y = np.linspace(-1.0, 1.0, height_px, dtype=np.float32)
    x = np.linspace(-1.0, 1.0, width_px, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    # Abstract, painterly Milky Way: broad luminous blobs along a tilted spine.
    angle = np.deg2rad(-28.0)
    u = xx * np.cos(angle) + yy * np.sin(angle)
    v = -xx * np.sin(angle) + yy * np.cos(angle)

    centerline = 0.10 * np.sin((u + 0.25) * np.pi * 1.7) - 0.04
    intensity = np.exp(-((v - centerline) / 0.22) ** 2) * 0.22

    blob_count = 24
    blob_u = rng.uniform(-0.92, 0.92, blob_count)
    blob_v = 0.10 * np.sin((blob_u + 0.25) * np.pi * 1.7) - 0.04 + rng.normal(0.0, 0.06, blob_count)
    blob_wu = rng.uniform(0.08, 0.20, blob_count)
    blob_wv = rng.uniform(0.05, 0.15, blob_count)
    blob_amp = rng.uniform(0.18, 0.55, blob_count)

    for i in range(blob_count):
        intensity += blob_amp[i] * np.exp(-((u - blob_u[i]) / blob_wu[i]) ** 2 - ((v - blob_v[i]) / blob_wv[i]) ** 2)

    fine_noise = rng.random((height_px, width_px), dtype=np.float32)
    for _ in range(3):
        fine_noise = (
            fine_noise
            + np.roll(fine_noise, 1, 0)
            + np.roll(fine_noise, -1, 0)
            + np.roll(fine_noise, 1, 1)
            + np.roll(fine_noise, -1, 1)
        ) / 5.0

    texture = np.clip(0.74 + (fine_noise - 0.5) * 0.52, 0.25, 1.20)
    intensity = np.clip(intensity * texture, 0.0, 1.0)

    r = np.clip(0.62 * intensity + 0.05, 0.0, 1.0)
    g = np.clip(0.77 * intensity + 0.07, 0.0, 1.0)
    b = np.clip(1.00 * intensity + 0.12, 0.0, 1.0)
    a = np.clip(intensity * 0.80, 0.0, 0.86)
    return np.dstack((r, g, b, a))


def render_star_map_stub(
    spec,
    output_dir: Path,
    seed: int = 42,
    filename_prefix: str = "star_map",
    preview_dpi: int = 350,
    cutoff_mag: float | None = None,
    limiting_magnitude: float = 6.0,
    max_star_size: float = 100.0,
    field_of_view_degrees: float = 180.0,
    chart_size: float | None = None,
    enable_glow: bool = True,
    title: str = "Tamara & Norbert",
    motto: str = "THE NIGHT OUR LOVE WAS BORN",
    location_name: str = "KIRALYRET",
    date_text: str = "2026-06-22",
    custom_message: str = "",
    lat: float | None = 47.894722,
    lon: float | None = 18.977778,
    location_query: str | None = None,
    when_local: str | None = None,
    style: str = "sky",
    constellations: bool = True,
    nebula_strength: float = 1.0,
    sky_passepartout_alpha: float = 0.30,
    sky_edge_alpha: float = 0.30,
) -> StarsRenderResult:
    _ = seed  # API compatibility, currently deterministic without random jitter.
    _ = enable_glow  # API compatibility, glow is intentionally minimal in this renderer.

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{filename_prefix}.pdf"
    png_path = output_dir / f"{filename_prefix}_preview.png"

    lat, lon = _resolve_coordinates(location_query=location_query, lat=lat, lon=lon)
    local_dt = _parse_local_datetime(when_local=when_local, date_text=date_text)
    utc_dt = _local_to_utc(local_dt=local_dt, lat=lat, lon=lon)

    mag_limit = cutoff_mag if cutoff_mag is not None else limiting_magnitude
    is_sky = style.lower() == StarStyle.SKY.value

    x, y, magnitudes = _project_visible_stars(
        lat=lat,
        lon=lon,
        utc_dt=utc_dt,
        limiting_magnitude=mag_limit,
        field_of_view_degrees=field_of_view_degrees,
        clip_to_circle=not is_sky,
    )

    constellation_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    if constellations and is_sky:
        constellation_segments = _project_constellation_segments(
            lat=lat,
            lon=lon,
            utc_dt=utc_dt,
            limiting_magnitude=mag_limit,
            field_of_view_degrees=field_of_view_degrees,
            clip_to_circle=not is_sky,
        )

    fig_size = spec.fig_size_inches
    if chart_size is not None:
        fig_size = (chart_size, chart_size)

    width_cm = float(getattr(spec, "width_cm"))
    height_cm = float(getattr(spec, "height_cm"))
    layout = build_star_layout(width_cm, height_cm, style=StarStyle(style))

    def cm_to_fig_x(x_cm: float) -> float:
        return x_cm / width_cm

    def cm_to_fig_y(y_cm: float) -> float:
        return y_cm / height_cm

    fig = plt.figure(figsize=fig_size)
    fig.patch.set_facecolor("#f7f5ef")

    ax = fig.add_axes([
        cm_to_fig_x(layout.artwork_area.x_cm),
        cm_to_fig_y(layout.artwork_area.y_cm),
        cm_to_fig_x(layout.artwork_area.width_cm),
        cm_to_fig_y(layout.artwork_area.height_cm),
    ])
    ax.set_facecolor("none")

    radius = layout.circle.radius_cm / min(layout.artwork_area.width_cm, layout.artwork_area.height_cm)
    radius = float(max(0.08, min(0.49, radius)))
    pad = radius * 0.06

    sky_disk = Circle((0.0, 0.0), radius, color="#05112e", fill=True, zorder=0)
    ax.add_patch(sky_disk)

    if x.size > 0:
        marker_size = max_star_size * 10 ** (magnitudes / -2.5)
        marker_size = np.clip(marker_size, 1.1, max_star_size)

        # Soft halo layer to make stars pop on print and preview.
        halo = ax.scatter(
            x * radius,
            y * radius,
            s=np.clip(marker_size * 3.1, 3.0, max_star_size * 3.4),
            color="#dfe8ff",
            marker="o",
            linewidths=0,
            alpha=0.14,
            zorder=1,
        )
        halo.set_clip_path(sky_disk)

        scatter = ax.scatter(
            x * radius,
            y * radius,
            s=np.clip(marker_size * 1.2, 1.4, max_star_size * 1.25),
            color="#ffffff",
            marker="o",
            linewidths=0,
            zorder=2,
        )
        scatter.set_clip_path(sky_disk)

        # A compact bright core helps readability for smaller/fainter stars.
        core = ax.scatter(
            x * radius,
            y * radius,
            s=np.clip(marker_size * 0.32, 0.65, max_star_size * 0.34),
            color="#fffdf8",
            marker="o",
            linewidths=0,
            alpha=0.9,
            zorder=3,
        )
        core.set_clip_path(sky_disk)

    ax.add_patch(Circle((0.0, 0.0), radius, fill=False, linewidth=1.2, edgecolor="#d9dce9", zorder=4))

    date_line = local_dt.strftime("%Y-%m-%d %H:%M")
    fallback_custom = f"{lat:.4f}, {lon:.4f}"
    custom_line = custom_message.strip() if custom_message.strip() else fallback_custom

    if style == "sky":
        return _render_star_map_sky(
            spec=spec,
            output_dir=output_dir,
            x=x,
            y=y,
            magnitudes=magnitudes,
            max_star_size=max_star_size,
            layout=layout,
            width_cm=width_cm,
            height_cm=height_cm,
            fig_size=fig_size,
            title=title,
            motto=motto,
            location_name=location_name,
            date_text=date_line,
            custom_message=custom_line,
            preview_dpi=preview_dpi,
            filename_prefix=filename_prefix,
            constellation_segments=constellation_segments,
            seed=seed,
            nebula_strength=nebula_strength,
            passepartout_alpha=sky_passepartout_alpha,
            edge_alpha=sky_edge_alpha,
        )
    else:
        raise ValueError(f"Unknown style: {style}")


def _render_star_map_sky_circle(
    spec,
    output_dir: Path,
    x: np.ndarray,
    y: np.ndarray,
    magnitudes: np.ndarray,
    max_star_size: float,
    layout,
    width_cm: float,
    height_cm: float,
    fig_size: tuple[float, float],
    title: str,
    motto: str,
    location_name: str,
    date_text: str,
    custom_message: str,
    preview_dpi: int,
    filename_prefix: str,
) -> StarsRenderResult:
    """Render circular sky map with circle mask."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{filename_prefix}.pdf"
    png_path = output_dir / f"{filename_prefix}_preview.png"

    def cm_to_fig_x(x_cm: float) -> float:
        return x_cm / width_cm

    def cm_to_fig_y(y_cm: float) -> float:
        return y_cm / height_cm

    fig = plt.figure(figsize=fig_size)
    fig.patch.set_facecolor("#f7f5ef")

    ax = fig.add_axes([
        cm_to_fig_x(layout.artwork_area.x_cm),
        cm_to_fig_y(layout.artwork_area.y_cm),
        cm_to_fig_x(layout.artwork_area.width_cm),
        cm_to_fig_y(layout.artwork_area.height_cm),
    ])
    ax.set_facecolor("none")

    radius = layout.circle.radius_cm / min(layout.artwork_area.width_cm, layout.artwork_area.height_cm)
    radius = float(max(0.08, min(0.49, radius)))
    pad = radius * 0.06

    sky_disk = Circle((0.0, 0.0), radius, color="#05112e", fill=True, zorder=0)
    ax.add_patch(sky_disk)

    if x.size > 0:
        marker_size = max_star_size * 10 ** (magnitudes / -2.5)
        marker_size = np.clip(marker_size, 1.1, max_star_size)

        halo = ax.scatter(
            x * radius,
            y * radius,
            s=np.clip(marker_size * 3.1, 3.0, max_star_size * 3.4),
            color="#dfe8ff",
            marker="o",
            linewidths=0,
            alpha=0.14,
            zorder=1,
        )
        halo.set_clip_path(sky_disk)

        scatter = ax.scatter(
            x * radius,
            y * radius,
            s=np.clip(marker_size * 1.2, 1.4, max_star_size * 1.25),
            color="#ffffff",
            marker="o",
            linewidths=0,
            zorder=2,
        )
        scatter.set_clip_path(sky_disk)

        core = ax.scatter(
            x * radius,
            y * radius,
            s=np.clip(marker_size * 0.32, 0.65, max_star_size * 0.34),
            color="#fffdf8",
            marker="o",
            linewidths=0,
            alpha=0.9,
            zorder=3,
        )
        core.set_clip_path(sky_disk)

    ax.add_patch(Circle((0.0, 0.0), radius, fill=False, linewidth=1.2, edgecolor="#d9dce9", zorder=4))

    def text_pt(height_cm_value: float, scale: float) -> float:
        return max(7.5, height_cm_value * 28.3464567 * scale)

    def fit_font_size_pt(text: str, base_size_pt: float, box_width_cm: float) -> float:
        if not text:
            return base_size_pt
        width_pt = box_width_cm * 28.3464567 * 0.92
        estimate = base_size_pt * 0.53 * max(1, len(text))
        if estimate <= width_pt:
            return base_size_pt
        return max(6.2, base_size_pt * (width_pt / estimate))

    is_side_layout = layout.mode == StarLayoutMode.LAYOUT_SIDE

    def text_x(box) -> float:
        if is_side_layout:
            return cm_to_fig_x(box.x_cm + box.width_cm * 0.08)
        return cm_to_fig_x(box.center_x_cm)

    def text_align() -> str:
        return "left" if is_side_layout else "center"

    fig.text(
        text_x(layout.typography.title),
        cm_to_fig_y(layout.typography.title.center_y_cm),
        title.strip(),
        ha=text_align(),
        va="center",
        fontsize=fit_font_size_pt(
            title.strip(),
            text_pt(layout.typography.title.height_cm, 0.60),
            layout.typography.title.width_cm,
        ),
        color="#1c1b18",
    )
    fig.text(
        text_x(layout.typography.subtitle),
        cm_to_fig_y(layout.typography.subtitle.center_y_cm),
        motto.strip(),
        ha=text_align(),
        va="center",
        fontsize=fit_font_size_pt(
            motto.strip(),
            text_pt(layout.typography.subtitle.height_cm, 0.54),
            layout.typography.subtitle.width_cm,
        ),
        color="#46433d",
    )
    fig.text(
        text_x(layout.typography.location),
        cm_to_fig_y(layout.typography.location.center_y_cm),
        location_name.strip(),
        ha=text_align(),
        va="center",
        fontsize=fit_font_size_pt(
            location_name.strip(),
            text_pt(layout.typography.location.height_cm, 0.50),
            layout.typography.location.width_cm,
        ),
        color="#5a564f",
    )
    fig.text(
        text_x(layout.typography.date),
        cm_to_fig_y(layout.typography.date.center_y_cm),
        date_text,
        ha=text_align(),
        va="center",
        fontsize=fit_font_size_pt(
            date_text,
            text_pt(layout.typography.date.height_cm, 0.48),
            layout.typography.date.width_cm,
        ),
        color="#5a564f",
    )
    fig.text(
        text_x(layout.typography.custom_message),
        cm_to_fig_y(layout.typography.custom_message.center_y_cm),
        custom_message,
        ha=text_align(),
        va="center",
        fontsize=fit_font_size_pt(
            custom_message,
            text_pt(layout.typography.custom_message.height_cm, 0.48),
            layout.typography.custom_message.width_cm,
        ),
        color="#615c53",
    )

    ax.set_xlim(-(radius + pad), radius + pad)
    ax.set_ylim(-(radius + pad), radius + pad)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    fig.savefig(pdf_path, dpi=int(getattr(spec, "dpi", 300) or 300), facecolor=fig.get_facecolor())
    fig.savefig(png_path, dpi=preview_dpi, facecolor=fig.get_facecolor())
    plt.close(fig)

    return StarsRenderResult(output_pdf=pdf_path, output_preview_png=png_path)


def _render_star_map_sky(
    spec,
    output_dir: Path,
    x: np.ndarray,
    y: np.ndarray,
    magnitudes: np.ndarray,
    max_star_size: float,
    layout,
    width_cm: float,
    height_cm: float,
    fig_size: tuple[float, float],
    title: str,
    motto: str,
    location_name: str,
    date_text: str,
    custom_message: str,
    preview_dpi: int,
    filename_prefix: str,
    constellation_segments: list[tuple[tuple[float, float], tuple[float, float]]] | None = None,
    seed: int = 42,
    nebula_strength: float = 1.0,
    passepartout_alpha: float = 0.15,
    edge_alpha: float = 0.8,
) -> StarsRenderResult:
    """Render rectangular sky field with a full-bleed sky and inner passepartout edge."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle
    
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{filename_prefix}.pdf"
    png_path = output_dir / f"{filename_prefix}_preview.png"

    def cm_to_fig_x(x_cm: float) -> float:
        return x_cm / width_cm

    def cm_to_fig_y(y_cm: float) -> float:
        return y_cm / height_cm

    fig = plt.figure(figsize=fig_size)
    fig.patch.set_facecolor("#05172c")

    # Full-sheet star layer; the inner edge rectangle marks the passepartout boundary.
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_facecolor("#05172c")

    # Draw a uniform base background for the full artwork area.
    from matplotlib.patches import Rectangle as RectPatch
    black_bg = RectPatch(
        (-1, -1), 2, 2,
        fill=True,
        facecolor="#05172c",
        edgecolor="none",
        transform=ax.transData,
        zorder=0,
    )
    ax.add_patch(black_bg)

    layer_dpi = min(max(int(getattr(spec, "dpi", 300) or 300), 180), 320)
    layer_w = max(1000, int((width_cm / 2.54) * layer_dpi))
    layer_h = max(1000, int((height_cm / 2.54) * layer_dpi))
    base_sky_img = _build_blue_sky_base_layer(width_px=layer_w, height_px=layer_h, seed=seed + 11)
    ax.imshow(
        base_sky_img,
        extent=(-1, 1, -1, 1),
        origin="lower",
        interpolation="bilinear",
        alpha=1.0,
        zorder=0.7,
        aspect="auto",
    )

    # Load and render nebula PNG overlay.
    from PIL import Image
    nebula_png_path = Path(__file__).parent / "starmap" / "nebula_png" / "—Pngtree—stunning red nebula with stars_16220303 (1).png"
    if nebula_png_path.exists():
        from PIL import ImageEnhance
        nebula_pil = Image.open(nebula_png_path).convert("RGBA")
        
        # Apply image adjustments for natural look
        # Brightness: -59 → factor 0.41
        brightness_enhancer = ImageEnhance.Brightness(nebula_pil)
        nebula_pil = brightness_enhancer.enhance(0.41)
        
        # Contrast: +90 → factor 1.90
        contrast_enhancer = ImageEnhance.Contrast(nebula_pil)
        nebula_pil = contrast_enhancer.enhance(1.90)
        
        # Saturation: +68 → factor 1.68
        color_enhancer = ImageEnhance.Color(nebula_pil)
        nebula_pil = color_enhancer.enhance(1.68)
        
        nebula_array = np.asarray(nebula_pil, dtype=np.float32) / 255.0
        ax.imshow(
            nebula_array,
            extent=(-1, 1, -1, 1),
            origin="lower",
            interpolation="bilinear",
            alpha=0.5,
            zorder=0.80,
            aspect="auto",
        )
    
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.set_aspect("auto")

    transform_center_x = 0.0
    transform_center_y = 0.0
    transform_r_scale = 1.0

    if x.size > 0:
        marker_size = max_star_size * 10 ** (magnitudes / -2.5)
        marker_size = np.clip(marker_size, 1.1, max_star_size)

        # Isotropic (non-axis-stretched) normalization to keep natural star geometry.
        x_centered = x - np.median(x)
        y_centered = y - np.median(y)
        r = np.hypot(x_centered, y_centered)
        r_scale = max(float(np.percentile(r, 99)), 1e-6)
        transform_center_x = float(np.median(x))
        transform_center_y = float(np.median(y))
        transform_r_scale = float(r_scale)

        # Normalize to unit disk, then map disk -> square so corners are populated.
        r_norm = np.clip(r / r_scale, 0.0, 1.0)
        theta = np.arctan2(y_centered, x_centered)
        c = np.cos(theta)
        s = np.sin(theta)
        denom = np.maximum(np.maximum(np.abs(c), np.abs(s)), 1e-6)

        x_display = (r_norm * c / denom) * 0.98
        y_display = (r_norm * s / denom) * 0.98
        
        # Halo layer - NO clipping
        halo = ax.scatter(
            x_display,
            y_display,
            s=np.clip(marker_size * 3.1, 3.0, max_star_size * 3.4),
            color="#dfe8ff",
            marker="o",
            linewidths=0,
            alpha=0.14,
            zorder=1,
        )
        
        # Main layer - NO clipping
        scatter = ax.scatter(
            x_display,
            y_display,
            s=np.clip(marker_size * 1.2, 1.4, max_star_size * 1.25),
            color="#ffffff",
            marker="o",
            linewidths=0,
            zorder=2,
        )
        
        # Core layer - NO clipping
        core = ax.scatter(
            x_display,
            y_display,
            s=np.clip(marker_size * 0.32, 0.65, max_star_size * 0.34),
            color="#fffdf8",
            marker="o",
            linewidths=0,
            alpha=0.9,
            zorder=3,
        )

    constellation_node_points: list[tuple[float, float]] = []
    if constellation_segments:
        for (x1, y1), (x2, y2) in constellation_segments:
            x_pair = np.array([x1, x2], dtype=float)
            y_pair = np.array([y1, y2], dtype=float)

            x_centered = x_pair - transform_center_x
            y_centered = y_pair - transform_center_y
            r = np.hypot(x_centered, y_centered)
            r_norm = np.clip(r / transform_r_scale, 0.0, 1.0)
            theta = np.arctan2(y_centered, x_centered)
            c = np.cos(theta)
            s = np.sin(theta)
            denom = np.maximum(np.maximum(np.abs(c), np.abs(s)), 1e-6)

            x_line = (r_norm * c / denom) * 0.98
            y_line = (r_norm * s / denom) * 0.98

            segment_length = float(np.hypot(x_line[1] - x_line[0], y_line[1] - y_line[0]))
            if segment_length < 0.055:
                continue

            # Keep constellation lines intentionally very subtle.
            ax.plot(
                x_line,
                y_line,
                color="#b7d2ff",
                linewidth=1.25,
                alpha=0.16,
                zorder=5.2,
                solid_capstyle="round",
            )

            # Thin core stroke that remains barely visible.
            ax.plot(
                x_line,
                y_line,
                color="#f6fbff",
                linewidth=0.58,
                alpha=0.36,
                zorder=5.4,
                solid_capstyle="round",
            )

            constellation_node_points.append((float(x_line[0]), float(y_line[0])))
            constellation_node_points.append((float(x_line[1]), float(y_line[1])))

    if constellation_node_points:
        # Deduplicate near-identical points to avoid over-brightening shared vertices.
        dedup_nodes: list[tuple[float, float]] = []
        seen_nodes: set[tuple[int, int]] = set()
        for nx, ny in constellation_node_points:
            key = (int(round(nx * 20000.0)), int(round(ny * 20000.0)))
            if key in seen_nodes:
                continue
            seen_nodes.add(key)
            dedup_nodes.append((nx, ny))

        node_x = np.array([p[0] for p in dedup_nodes], dtype=float)
        node_y = np.array([p[1] for p in dedup_nodes], dtype=float)

        # Layered radial glow: strong center to transparent edge.
        ax.scatter(
            node_x,
            node_y,
            s=122.0,
            color="#d7e8ff",
            linewidths=0,
            alpha=0.08,
            zorder=5.52,
        )
        ax.scatter(
            node_x,
            node_y,
            s=66.0,
            color="#eaf3ff",
            linewidths=0,
            alpha=0.20,
            zorder=5.56,
        )
        ax.scatter(
            node_x,
            node_y,
            s=24.0,
            color="#f8fbff",
            linewidths=0,
            alpha=0.88,
            zorder=5.6,
        )

    # Triple white inner edge: body remains transparent, lines are drawn inside
    # the original artwork bounds so passepartout thickness is preserved.
    frame_x = cm_to_fig_x(layout.artwork_area.x_cm)
    frame_y = cm_to_fig_y(layout.artwork_area.y_cm)
    frame_w = cm_to_fig_x(layout.artwork_area.width_cm)
    frame_h = cm_to_fig_y(layout.artwork_area.height_cm)

    fig_w_in, fig_h_in = fig_size
    outer_lw_pt = 0.82
    inner_lw_pt = 0.34
    gap_pt = 1.8
    outer_half_x = (outer_lw_pt / 72.0) / fig_w_in / 2.0
    outer_half_y = (outer_lw_pt / 72.0) / fig_h_in / 2.0
    edge_inset = max(outer_half_x, outer_half_y)

    passepartout_alpha = 0.0
    passepartout_color = "#000000"
    edge_alpha = 1.0

    # Passepartout body remains fully transparent.
    if frame_x > 0.0:
        fig.add_artist(Rectangle(
            (0.0, 0.0),
            frame_x,
            1.0,
            fill=True,
            linewidth=0,
            facecolor=passepartout_color,
            alpha=passepartout_alpha,
            transform=fig.transFigure,
            zorder=9.1,
        ))
    right_x = frame_x + frame_w
    if right_x < 1.0:
        fig.add_artist(Rectangle(
            (right_x, 0.0),
            1.0 - right_x,
            1.0,
            fill=True,
            linewidth=0,
            facecolor=passepartout_color,
            alpha=passepartout_alpha,
            transform=fig.transFigure,
            zorder=9.1,
        ))
    if frame_y > 0.0:
        fig.add_artist(Rectangle(
            (frame_x, 0.0),
            frame_w,
            frame_y,
            fill=True,
            linewidth=0,
            facecolor=passepartout_color,
            alpha=passepartout_alpha,
            transform=fig.transFigure,
            zorder=9.1,
        ))
    top_y = frame_y + frame_h
    if top_y < 1.0:
        fig.add_artist(Rectangle(
            (frame_x, top_y),
            frame_w,
            1.0 - top_y,
            fill=True,
            linewidth=0,
            facecolor=passepartout_color,
            alpha=passepartout_alpha,
            transform=fig.transFigure,
            zorder=9.1,
        ))

    edge_color = "#C9A227"

    def draw_trimmed_edges(x0: float, y0: float, w: float, h: float, lw_pt: float, z: float) -> None:
        if w <= 0.0 or h <= 0.0:
            return
        trim_ratio = 0.03
        trim_x = w * trim_ratio
        trim_y = h * trim_ratio

        segments = (
            ((x0 + trim_x, y0), (x0 + w - trim_x, y0)),
            ((x0 + trim_x, y0 + h), (x0 + w - trim_x, y0 + h)),
            ((x0, y0 + trim_y), (x0, y0 + h - trim_y)),
            ((x0 + w, y0 + trim_y), (x0 + w, y0 + h - trim_y)),
        )
        for (x1, y1), (x2, y2) in segments:
            fig.add_artist(Line2D(
                [x1, x2],
                [y1, y2],
                linewidth=lw_pt,
                color=edge_color,
                alpha=1.0,
                transform=fig.transFigure,
                zorder=z,
                solid_capstyle="round",
            ))

    outer_x = frame_x + edge_inset
    outer_y = frame_y + edge_inset
    outer_w = frame_w - 2 * edge_inset
    outer_h = frame_h - 2 * edge_inset
    draw_trimmed_edges(outer_x, outer_y, outer_w, outer_h, outer_lw_pt, 10)

    gap_x = (gap_pt / 72.0) / fig_w_in
    gap_y = (gap_pt / 72.0) / fig_h_in
    inner_inset = edge_inset + max(gap_x, gap_y)
    if frame_w > 2 * inner_inset and frame_h > 2 * inner_inset:
        draw_trimmed_edges(
            frame_x + inner_inset,
            frame_y + inner_inset,
            frame_w - 2 * inner_inset,
            frame_h - 2 * inner_inset,
            inner_lw_pt,
            11,
        )

    third_gap_pt = 3.8
    third_lw_pt = 0.28
    third_gap_x = (third_gap_pt / 72.0) / fig_w_in
    third_gap_y = (third_gap_pt / 72.0) / fig_h_in
    third_inset = inner_inset + max(third_gap_x, third_gap_y)
    if frame_w > 2 * third_inset and frame_h > 2 * third_inset:
        draw_trimmed_edges(
            frame_x + third_inset,
            frame_y + third_inset,
            frame_w - 2 * third_inset,
            frame_h - 2 * third_inset,
            third_lw_pt,
            12,
        )

    # Gold star symbols exactly where the outer trimmed edges would meet.
    left_star_x = outer_x
    right_star_x = outer_x + outer_w
    bottom_star_y = outer_y
    top_star_y = outer_y + outer_h
    for sx, sy in (
        (left_star_x, bottom_star_y),
        (left_star_x, top_star_y),
        (right_star_x, bottom_star_y),
        (right_star_x, top_star_y),
    ):
        fig.add_artist(Line2D(
            [sx],
            [sy],
            marker="*",
            markersize=26,
            markerfacecolor=edge_color,
            markeredgecolor=edge_color,
            linestyle="None",
            alpha=1.0,
            transform=fig.transFigure,
            zorder=13,
        ))

    ax.axis("off")

    # Typography
    def text_pt(height_cm_value: float, scale: float) -> float:
        return max(7.5, height_cm_value * 28.3464567 * scale)

    def fit_font_size_pt(text: str, base_size_pt: float, box_width_cm: float) -> float:
        if not text:
            return base_size_pt
        width_pt = box_width_cm * 28.3464567 * 0.92
        estimate = base_size_pt * 0.53 * max(1, len(text))
        if estimate <= width_pt:
            return base_size_pt
        return max(6.2, base_size_pt * (width_pt / estimate))

    fig.text(
        cm_to_fig_x(layout.typography.title.center_x_cm),
        cm_to_fig_y(layout.typography.title.center_y_cm),
        title.strip(),
        ha="center",
        va="center",
        fontsize=fit_font_size_pt(
            title.strip(),
            text_pt(layout.typography.title.height_cm, 0.60),
            layout.typography.title.width_cm,
        ),
        color="#ffffff",
    )
    fig.text(
        cm_to_fig_x(layout.typography.subtitle.center_x_cm),
        cm_to_fig_y(layout.typography.subtitle.center_y_cm),
        motto.strip(),
        ha="center",
        va="center",
        fontsize=fit_font_size_pt(
            motto.strip(),
            text_pt(layout.typography.subtitle.height_cm, 0.54),
            layout.typography.subtitle.width_cm,
        ),
        color="#e0e0e0",
    )
    fig.text(
        cm_to_fig_x(layout.typography.location.center_x_cm),
        cm_to_fig_y(layout.typography.location.center_y_cm),
        location_name.strip(),
        ha="center",
        va="center",
        fontsize=fit_font_size_pt(
            location_name.strip(),
            text_pt(layout.typography.location.height_cm, 0.50),
            layout.typography.location.width_cm,
        ),
        color="#c0c0c0",
    )
    fig.text(
        cm_to_fig_x(layout.typography.date.center_x_cm),
        cm_to_fig_y(layout.typography.date.center_y_cm),
        date_text,
        ha="center",
        va="center",
        fontsize=fit_font_size_pt(
            date_text,
            text_pt(layout.typography.date.height_cm, 0.48),
            layout.typography.date.width_cm,
        ),
        color="#c0c0c0",
    )
    fig.text(
        cm_to_fig_x(layout.typography.custom_message.center_x_cm),
        cm_to_fig_y(layout.typography.custom_message.center_y_cm),
        custom_message,
        ha="center",
        va="center",
        fontsize=fit_font_size_pt(
            custom_message,
            text_pt(layout.typography.custom_message.height_cm, 0.48),
            layout.typography.custom_message.width_cm,
        ),
        color="#b0b0b0",
    )

    fig.savefig(
        pdf_path,
        dpi=int(getattr(spec, "dpi", 300) or 300),
        facecolor=fig.get_facecolor(),
        transparent=True,
    )
    fig.savefig(
        png_path,
        dpi=preview_dpi,
        facecolor=fig.get_facecolor(),
        transparent=True,
    )
    plt.close(fig)

    return StarsRenderResult(output_pdf=pdf_path, output_preview_png=png_path)
