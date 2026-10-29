"""Order-driven rendering from a raw OSM XML file (``MAPCANVAS_OSM_SOURCE=xml``).

Each order streams the XML into a temporary selected-feature store, renders through the existing
dispatcher/style/layout/export path, publishes validated products atomically and removes all
intermediate data. A persistent store is opt-in only (``persistent_store_dir``).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import geopandas as gpd
import osmium
import osmnx as ox
from shapely.geometry import Point, box

from generator.batch_pipeline import _atomic_json, _publish_pair, _render_pdf_to_webp, _validate_webp
from generator.core.bundle_viewport_policy import compute_osm_bundle_viewport
from generator.core.render_dispatcher import get_viewport_for_style, render_product
from generator.core.style_registry import STYLE_REGISTRY
from generator.order_renderer import OrderRenderError, _slug, _validate_pdf
from generator.specs import DEFAULT_EXTENT_M, resolve_size_request, spec_from_dimensions

WEB_PREVIEW_MAX_BYTES = 150_000
WEB_PREVIEW_MAX_LONG_SIDE = 1400
WEB_PREVIEW_LONG_SIDES = (1400, 1120, 960, 800)
PRODUCT_MANIFEST = "manifest.json"
_ENV_NAMES = (
    "MAPCANVAS_OSM_SOURCE", "MAPCANVAS_XML_STORE_DIR", "MAPCANVAS_XML_PATH", "MAPCANVAS_PBF_STORE_DIR", "MAPCANVAS_PBF_PATH",
)


# ---------------------------------------------------------------------------
# Measurement helpers
# ---------------------------------------------------------------------------

def _memory_counters() -> tuple[int | None, int | None]:
    """(peak, current) resident memory of this process; None where the platform does not expose it."""
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        class _Counters(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
                )
            ]

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = wt.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(_Counters), wt.DWORD]
        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None, None
        return int(counters.PeakWorkingSetSize), int(counters.WorkingSetSize)
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = int(peak if sys.platform == "darwin" else peak * 1024)
    except (ImportError, OSError):
        peak = None
    try:
        with open("/proc/self/statm", encoding="ascii") as handle:
            current = int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, AttributeError):
        current = None
    return peak, current


def peak_rss_bytes() -> int | None:
    return _memory_counters()[0]


class _MemorySampler:
    """Samples current resident memory in a background thread and attributes peaks to named phases."""

    def __init__(self, interval_s: float = 0.05) -> None:
        self.interval_s = interval_s
        self.phase = "setup"
        self.peaks: dict[str, int] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "_MemorySampler":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
        self._sample()

    def mark(self, phase: str) -> None:
        self._sample()
        self.phase = phase

    def _sample(self) -> None:
        current = _memory_counters()[1]
        if current is not None:
            self.peaks[self.phase] = max(self.peaks.get(self.phase, 0), current)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._sample()


def _dir_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) if path.exists() else 0


class _DiskMeter:
    def __init__(self) -> None:
        self.roots: list[Path] = []
        self.peak_bytes = 0

    def sample(self) -> None:
        self.peak_bytes = max(self.peak_bytes, sum(_dir_bytes(root) for root in self.roots))


def _remove_tree(path: Path, attempts: int = 5) -> bool:
    for attempt in range(attempts):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return True
        # Windows can hold memory-mapped/SQLite handles briefly after close.
        time.sleep(0.2 * (attempt + 1))
    return not path.exists()


@contextmanager
def _temporary_dir(parent: Path | None, prefix: str, meter: _DiskMeter, cleanup: dict):
    """Create, track and always remove a directory created here; never touches anything else."""
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    meter.roots.append(path)
    try:
        yield path
    finally:
        meter.sample()
        meter.roots.remove(path)
        cleanup[prefix.rstrip("-")] = {"path": str(path), "removed": _remove_tree(path)}


@contextmanager
def _xml_source_environment(store_dir: Path, xml_path: Path):
    previous = {name: os.environ.get(name) for name in _ENV_NAMES}
    os.environ["MAPCANVAS_OSM_SOURCE"] = "xml"
    os.environ["MAPCANVAS_XML_STORE_DIR"] = str(store_dir)
    os.environ["MAPCANVAS_XML_PATH"] = str(xml_path)
    os.environ.pop("MAPCANVAS_PBF_STORE_DIR", None)
    os.environ.pop("MAPCANVAS_PBF_PATH", None)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# ---------------------------------------------------------------------------
# Source preflight
# ---------------------------------------------------------------------------

def _inside(bbox, lon: float, lat: float) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def inspect_osm_xml(path: Path | str) -> dict:
    """Stream the XML once: object counts, declared vs observed bounds and the map-center decision.

    The declared ``<bounds>`` are accepted only when every object outside them is merely a reference
    of an object inside them (Overpass recursion tails). Otherwise the observed node bounds are used.
    """
    from generator.core.pbf_store import read_pbf_header, source_format

    path = Path(path)
    header = read_pbf_header(path)
    declared = tuple(header["bbox"]) if header.get("bbox") else None
    counts = {"nodes": 0, "ways": 0, "relations": 0, "invalid_node_locations": 0}
    west = south = float("inf")
    east = north = float("-inf")
    outside_nodes: set[int] = set()
    referenced_outside_nodes: set[int] = set()
    outside_ways: set[int] = set()
    referenced_outside_ways: set[int] = set()
    started = time.perf_counter()
    for obj in osmium.FileProcessor(str(path)):
        if obj.is_node():
            counts["nodes"] += 1
            location = obj.location
            if not location.valid():
                counts["invalid_node_locations"] += 1
                continue
            lon, lat = location.lon, location.lat
            west, south, east, north = min(west, lon), min(south, lat), max(east, lon), max(north, lat)
            if declared and not _inside(declared, lon, lat):
                outside_nodes.add(obj.id)
        elif obj.is_way():
            counts["ways"] += 1
            refs = [n.ref for n in obj.nodes]
            hits = [ref for ref in refs if ref in outside_nodes]
            referenced_outside_nodes.update(hits)
            if refs and len(hits) == len(refs):
                outside_ways.add(obj.id)
        elif obj.is_relation():
            counts["relations"] += 1
            for member in obj.members:
                if member.type == "n" and member.ref in outside_nodes:
                    referenced_outside_nodes.add(member.ref)
                elif member.type == "w" and member.ref in outside_ways:
                    referenced_outside_ways.add(member.ref)
    if counts["nodes"] == counts["invalid_node_locations"]:
        raise OrderRenderError(f"OSM XML contains no valid node locations: {path}")
    observed = (west, south, east, north)

    unreferenced_nodes = len(outside_nodes - referenced_outside_nodes)
    unreferenced_ways = len(outside_ways - referenced_outside_ways)
    declared_verified = bool(
        declared
        and declared[0] < declared[2]
        and declared[1] < declared[3]
        and len(outside_nodes) < counts["nodes"]
        and unreferenced_nodes == 0
        and unreferenced_ways == 0
    )
    bounds = declared if declared_verified else observed
    if declared is None:
        reason = "XML has no <bounds>; observed node bounds used"
    elif declared_verified:
        reason = (
            "<bounds> verified: every node/way outside it is only a reference of data inside it "
            "(recursion tails); observed extremes are not the data extent"
        )
    else:
        reason = "<bounds> unreliable: data exists outside it independently; observed node bounds used"
    return {
        "path": str(path.resolve()),
        "format": source_format(path),
        "generator": header.get("generator"),
        "declared_bounds": list(declared) if declared else None,
        "observed_node_bounds": list(observed),
        "declared_bounds_verified": declared_verified,
        "center_bounds": list(bounds),
        "center_bounds_source": "declared" if declared_verified else "observed",
        "center_reason": reason,
        "center_lat": (bounds[1] + bounds[3]) / 2,
        "center_lon": (bounds[0] + bounds[2]) / 2,
        "counts": counts,
        "outside_declared_bounds": {
            "nodes": len(outside_nodes),
            "nodes_not_referenced_by_inside_data": unreferenced_nodes,
            "ways_wholly_outside": len(outside_ways),
            "ways_wholly_outside_not_relation_members": unreferenced_ways,
        },
        "scan_s": round(time.perf_counter() - started, 3),
    }


def _source_identity(path: Path) -> dict:
    from generator.core.pbf_store import file_sha256

    before = path.stat()
    digest = file_sha256(path)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OrderRenderError(f"OSM XML changed while computing its identity: {path}")
    return {"path": str(path.resolve()), "size_bytes": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": digest}


# ---------------------------------------------------------------------------
# Geometry diagnostics
# ---------------------------------------------------------------------------

def effective_coverage(center_lat: float, center_lon: float, half_width_m: float, half_height_m: float) -> dict:
    """The renderer's clip rectangle, in the same OSMnx UTM projection the engines use."""
    center = ox.projection.project_gdf(gpd.GeoDataFrame(geometry=[Point(center_lon, center_lat)], crs="EPSG:4326"))
    point = center.geometry.iloc[0]
    rect = box(point.x - half_width_m, point.y - half_height_m, point.x + half_width_m, point.y + half_height_m)
    wgs84 = gpd.GeoSeries([rect], crs=center.crs).to_crs("EPSG:4326").iloc[0]
    return {
        "projected_crs": center.crs.to_string(),
        "projected_bounds_m": [round(v, 3) for v in rect.bounds],
        "width_m": round(2 * half_width_m, 3),
        "height_m": round(2 * half_height_m, 3),
        "wgs84_bounds": [round(v, 7) for v in wgs84.bounds],
    }


def _bundle_diagnostics(stats: dict) -> dict:
    layers = stats.get("layers", {})
    warnings = []
    roads = stats.get("roads", {})
    if roads.get("incomplete_ways_dropped"):
        warnings.append(f"roads: {roads['incomplete_ways_dropped']} incomplete ways dropped")
    for name, layer in layers.items():
        for key in ("incomplete_ways_dropped", "relations_with_missing_members", "relations_with_nested_members"):
            if layer.get(key):
                warnings.append(f"{name}: {layer[key]} {key.replace('_', ' ')}")
    return {
        "query_bbox_wgs84": stats.get("query_bbox"),
        "road_query_bbox_wgs84": stats.get("road_query_bbox"),
        "roads": {key: roads.get(key) for key in ("candidate_ways", "selected_ways", "incomplete_ways_dropped", "edges")},
        "layers": {name: {"features": layer.get("features", 0), "relations": layer.get("relations", 0)} for name, layer in layers.items()},
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def _validate_preview(info: dict, width_cm: float, height_cm: float) -> None:
    size = (info["width_px"], info["height_px"])
    if max(size) > WEB_PREVIEW_MAX_LONG_SIDE or info["bytes"] > WEB_PREVIEW_MAX_BYTES:
        raise OrderRenderError(f"Web preview {size} {info['bytes']} bytes exceeds the web limits")
    if abs(size[0] / size[1] - width_cm / height_cm) > 1 / min(size):
        raise OrderRenderError(f"Web preview aspect {size} does not match {width_cm}x{height_cm} cm")


def _render_product(
    *, base: str, stage_dir: Path, store_dir: Path, xml_path: Path, city_name: str, style: str,
    spec, center_lat: float, center_lon: float, meter: _DiskMeter, memory: _MemorySampler,
) -> dict:
    from generator.core import pbf_source

    render_dir = stage_dir.parent / f"{stage_dir.name}-render"
    render_dir.mkdir()
    try:
        memory.mark("render")
        started = time.perf_counter()
        with _xml_source_environment(store_dir, xml_path):
            pbf_source.LAST_XML_BUNDLE_STATS.clear()
            rendered = render_product(
                style_name=style,
                center_lat=center_lat,
                center_lon=center_lon,
                spec=spec,
                output_dir=render_dir,
                title=city_name,
                subtitle=f"{center_lat:.4f} N  {center_lon:.4f} E",
                preview_mode=False,
                order_id=f"ORDER_{base}",
                use_cache=True,
            )
            bundle_stats = dict(pbf_source.LAST_XML_BUNDLE_STATS)
        render_s = time.perf_counter() - started
        if rendered.output_pdf is None or not rendered.output_pdf.is_file():
            raise OrderRenderError("Renderer did not produce a PDF")
        if not bundle_stats:
            raise OrderRenderError("Renderer did not read the OSM XML store")
        meter.sample()
        # Release renderer geometry/figures before rasterizing the preview.
        import gc

        import matplotlib.pyplot as plt

        plt.close("all")
        gc.collect()

        memory.mark("export")
        started = time.perf_counter()
        pdf_path = stage_dir / f"{base}.pdf"
        preview_path = stage_dir / f"{base}_preview.webp"
        shutil.copy2(rendered.output_pdf, pdf_path)
    finally:
        _remove_tree(render_dir)

    pdf_info = _validate_pdf(pdf_path, spec.width_cm, spec.height_cm)
    preview_info = _render_pdf_to_webp(
        pdf_path, preview_path, spec.width_cm, spec.height_cm, WEB_PREVIEW_MAX_BYTES,
        max_long_side=WEB_PREVIEW_MAX_LONG_SIDE, long_sides=WEB_PREVIEW_LONG_SIDES,
    )
    _validate_webp(preview_path, tuple(preview_info["dimensions_px"]), WEB_PREVIEW_MAX_BYTES)
    _validate_preview(preview_info, spec.width_cm, spec.height_cm)
    meter.sample()
    if len(bundle_stats.get("roads", {})) == 0 or not bundle_stats["roads"].get("edges"):
        raise OrderRenderError("No road edges were rendered from the OSM XML store")
    return {
        "render_s": round(render_s, 3),
        "export_s": round(time.perf_counter() - started, 3),
        "bundle": _bundle_diagnostics(bundle_stats),
        "files": {
            "pdf": {"name": pdf_path.name, "bytes": pdf_path.stat().st_size, **pdf_info},
            "preview_webp": {
                "name": preview_path.name,
                **{key: preview_info[key] for key in ("width_px", "height_px", "bytes", "quality", "method", "encoding")},
                "max_long_side_px": WEB_PREVIEW_MAX_LONG_SIDE,
                "max_bytes": WEB_PREVIEW_MAX_BYTES,
            },
        },
    }


def _validate_store_reuse(store_dir: Path, xml_path: Path, identity: dict) -> bool:
    from generator.core.pbf_store import PbfStoreReader

    try:
        with PbfStoreReader(store_dir, pbf_path=xml_path) as reader:
            return reader.meta.get("source_format") == "xml" and reader.meta.get("pbf_sha256") == identity["sha256"]
    except Exception:
        return False


def render_xml_order(**kwargs) -> dict:
    """Render one order from a raw OSM XML; ``sizes`` holds catalog keys and/or (width_cm, height_cm) pairs.

    Keyword arguments: xml_path, city_name, style, sizes, extent_m, output_dir, center, dpi, temp_root,
    persistent_store_dir, location_storage, reference_tracking (see ``_run_xml_order``).
    """
    with _MemorySampler() as memory:
        return _run_xml_order(memory=memory, **kwargs)


def _run_xml_order(
    *,
    memory: _MemorySampler,
    xml_path: Path | str,
    city_name: str,
    style: str,
    sizes,
    extent_m: float = DEFAULT_EXTENT_M,
    output_dir: Path | str,
    center: tuple[float, float] | None = None,
    dpi: int = 300,
    temp_root: Path | str | None = None,
    persistent_store_dir: Path | str | None = None,
    location_storage: str = "flex_mem",
    reference_tracking: str = "sparse",
) -> dict:
    from generator.core.pbf_store import PbfStoreReader, build_store, source_format

    order_started = time.perf_counter()
    xml_path = Path(xml_path).expanduser().resolve()
    if not xml_path.is_file() or source_format(xml_path) != "xml":
        raise ValueError(f"xml_path must be an existing OSM XML (.osm/.xml) file: {xml_path}")
    if style not in STYLE_REGISTRY:
        raise ValueError(f"Style {style!r} is not registered")
    if "file" in location_storage.split(",", 1)[0]:
        raise ValueError(
            f"location_storage={location_storage!r} is file-backed; PyOsmium keeps such index files open until "
            "process exit, so per-order cleanup cannot remove them. Use flex_mem or sparse_mem_array."
        )
    if not city_name.strip():
        raise ValueError("city_name must not be empty")
    if isinstance(sizes, str) or not sizes:
        raise ValueError("sizes must be a non-empty sequence of catalog keys and/or (width_cm, height_cm) pairs")
    requests = [(size, *resolve_size_request(size)) for size in sizes]
    catalog_labels = {label for size, label, _, _ in requests if isinstance(size, str)}
    specs = {label: spec_from_dimensions(width, height, extent_m=extent_m, dpi=dpi) for _, label, width, height in requests}
    output_dir = Path(output_dir).expanduser().resolve()
    city_slug = _slug(city_name)
    order_root = output_dir / city_slug
    temp_root = Path(temp_root).expanduser().resolve() if temp_root else None

    memory.mark("source_scan")
    source = inspect_osm_xml(xml_path)
    identity = _source_identity(xml_path)
    center_lat, center_lon = center if center else (source["center_lat"], source["center_lon"])
    print(f"SOURCE: {xml_path} ({identity['size_bytes']} bytes, generator {source['generator']})")
    print(f"BOUNDS declared={source['declared_bounds']} observed={source['observed_node_bounds']}")
    print(f"CENTER: {center_lat:.7f}, {center_lon:.7f} ({source['center_reason']})")

    meter = _DiskMeter()
    cleanup: dict = {}
    timings = {"source_scan_s": source["scan_s"]}
    results: dict[str, dict] = {}
    staged: dict[str, Path] = {}
    order_root.mkdir(parents=True, exist_ok=True)
    with _temporary_dir(order_root, ".staging-", meter, cleanup) as staging_root:
        with _temporary_dir(temp_root, "xml-order-store-", meter, cleanup) as store_workspace:
            memory.mark("store_build")
            started = time.perf_counter()
            if persistent_store_dir is not None:
                store_dir = Path(persistent_store_dir).expanduser().resolve()
                store_reused = _validate_store_reuse(store_dir, xml_path, identity)
                if not store_reused:
                    build = build_store(xml_path, store_dir, location_storage=location_storage, reference_tracking=reference_tracking)
            else:
                store_dir = store_workspace / "store"
                store_reused = False
                build = build_store(xml_path, store_dir, location_storage=location_storage, reference_tracking=reference_tracking)
            timings["store_build_s"] = 0.0 if store_reused else round(time.perf_counter() - started, 3)
            meter.sample()
            store_bytes = (store_dir / "osm_store.sqlite").stat().st_size
            if store_reused:
                with PbfStoreReader(store_dir) as reader:
                    store_counts = reader.counts
            else:
                store_counts = build.counts
            print(f"STORE: {'reused' if store_reused else 'built'} {store_bytes} bytes in {timings['store_build_s']} s")

            for label, spec in specs.items():
                base = f"{city_slug}_{style}_{label}_extent{spec.extent_m:g}"
                stage_dir = staging_root / base
                stage_dir.mkdir()
                job_started = time.perf_counter()
                try:
                    product = _render_product(
                        base=base, stage_dir=stage_dir, store_dir=store_dir, xml_path=xml_path, city_name=city_name,
                        style=style, spec=spec, center_lat=center_lat, center_lon=center_lon, meter=meter,
                        memory=memory,
                    )
                    half_width_m, half_height_m = get_viewport_for_style(style, spec)
                    bundle_hw, bundle_hh = compute_osm_bundle_viewport(spec)
                    results[label] = {
                        "status": "staged",
                        "base": base,
                        "spec": spec,
                        "viewport": {
                            "extent_m": spec.extent_m,
                            "extent_semantics": "projected viewport half-height in metres",
                            "renderer_half_width_m": half_width_m,
                            "renderer_half_height_m": half_height_m,
                            "half_width_formula": "extent_m * visible_map_width_cm / visible_map_height_cm",
                            "bundle_half_width_m": bundle_hw,
                            "bundle_half_height_m": bundle_hh,
                            "effective_coverage": effective_coverage(center_lat, center_lon, half_width_m, half_height_m),
                        },
                        **product,
                        "job_s": round(time.perf_counter() - job_started, 3),
                    }
                    staged[label] = stage_dir
                    print(f"[{label}] staged pdf={product['files']['pdf']['width_mm']:.2f}x{product['files']['pdf']['height_mm']:.2f}mm "
                          f"preview={product['files']['preview_webp']['width_px']}x{product['files']['preview_webp']['height_px']} "
                          f"{product['files']['preview_webp']['bytes']} bytes")
                except Exception as error:
                    results[label] = {"status": "failed", "base": base, "error": f"{type(error).__name__}: {error}"}
                    print(f"[{label}] FAIL {type(error).__name__}: {error}")
        store_workspace_cleanup = cleanup.get("xml-order-store", {})

        memory.mark("publish")
        peak_rss = peak_rss_bytes()
        for label, stage_dir in staged.items():
            record = results[label]
            spec = record.pop("spec")
            manifest = {
                "schema_version": 1,
                "product": record["base"],
                "city_name": city_name,
                "style": style,
                "print_size": {
                    "label": label,
                    "catalog_key": label if label in catalog_labels else None,
                    "width_cm": spec.width_cm,
                    "height_cm": spec.height_cm,
                    "width_mm": spec.width_cm * 10,
                    "height_mm": spec.height_cm * 10,
                    "orientation": spec.orientation,
                },
                "center": {"lat": center_lat, "lon": center_lon, "source": "explicit" if center else source["center_bounds_source"]},
                "source": {"type": "osm_xml", "identity": identity, **{k: v for k, v in source.items() if k != "path"}},
                "viewport": record["viewport"],
                "bundle": record["bundle"],
                "files": record["files"],
                "timings_s": {**timings, "render_s": record["render_s"], "export_s": record["export_s"], "job_s": record["job_s"]},
                "resources": {
                    "process_peak_rss_bytes": peak_rss,
                    "phase_peak_rss_bytes": dict(memory.peaks),
                    "temporary_disk_peak_bytes": meter.peak_bytes,
                    "store_bytes": store_bytes,
                    "store_counts": store_counts,
                    "reference_tracking": reference_tracking,
                    "location_storage": location_storage,
                },
                "cache_policy": {
                    "persistent_store": str(persistent_store_dir) if persistent_store_dir else None,
                    "store_reused": store_reused,
                    "temporary_store_removed": store_workspace_cleanup.get("removed"),
                },
                "remote_osm_api_used": False,
            }
            _atomic_json(stage_dir / PRODUCT_MANIFEST, manifest)
            expected = frozenset({f["name"] for f in record["files"].values()} | {PRODUCT_MANIFEST})
            _publish_pair(
                stage_dir, order_root / record["base"], expected_names=expected,
                retired_names=frozenset({f"{record['base']}.webp"}),
            )
            record.update({"status": "success", "output_dir": str(order_root / record["base"]), "manifest": manifest})

    total_s = round(time.perf_counter() - order_started, 3)
    success = sum(1 for r in results.values() if r["status"] == "success")
    return {
        "expected": len(specs),
        "success": success,
        "failed": len(specs) - success,
        "source": source,
        "center": (center_lat, center_lon),
        "results": results,
        "cleanup": cleanup,
        "temporary_disk_peak_bytes": meter.peak_bytes,
        "process_peak_rss_bytes": peak_rss_bytes(),
        "phase_peak_rss_bytes": dict(memory.peaks),
        "total_s": total_s,
    }
