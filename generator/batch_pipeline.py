"""Cache validation and sequential Budapest poster rendering."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import fitz
from PIL import Image, ImageStat

from generator.core.bundle_viewport_policy import compute_osm_bundle_viewport
from generator.core.render_dispatcher import get_viewport_for_style, render_product
from generator.core.style_registry import STYLE_REGISTRY
from generator.specs import ProductLine, SIZES_CM, spec_from_size_key, validate_size_key_for_product_line


CITY_DATA_PATH = Path(__file__).resolve().parents[2] / "woocommerce_helpers" / "data" / "cities_with_coords.json"
CITY_ID = "budapest"
CITY_NAME = "Budapest"
RADIUS_M = 3500
SIZE_KEY_FORMATS = tuple(SIZES_CM)
EXCLUDED_STYLES = frozenset({"mp_noir_gold", "minimal_sand"})
SUPPORTED_FEATURE_LAYERS = ("buildings", "trees", "waterway", "railway", "paths", "water", "green", "coast", "islands")
REQUIRED_FEATURE_LAYERS = frozenset(SUPPORTED_FEATURE_LAYERS) - {"coast"}
OUTPUT_MANIFEST_NAME = "prototype_manifest.json"
CITY_CACHE_MANIFEST_NAME = "cache_manifest.json"
PREVIEW_LONG_SIDE_PRESETS = (2240, 1680, 1400, 1120)
PREVIEW_QUALITY_SETTINGS = (90, 80, 70, 60, 40, 30)
WEBP_METHOD = 6


class CacheValidationError(RuntimeError):
	pass


class OutputValidationError(RuntimeError):
	pass


def eligible_styles() -> list[str]:
	return [style for style in STYLE_REGISTRY if style not in EXCLUDED_STYLES]


def load_budapest_config(path: Path = CITY_DATA_PATH) -> dict:
	data = json.loads(path.read_text(encoding="utf-8"))
	matches = [
		city for city in data
		if str(city.get("city") or city.get("name") or "").strip().casefold() == CITY_NAME.casefold()
	]
	if len(matches) != 1:
		raise ValueError(f"Expected one Budapest city record in {path}, found {len(matches)}")
	city = matches[0]
	if str(city.get("country", "")).casefold() != "hungary":
		raise ValueError(f"Budapest config has unexpected country: {city.get('country')!r}")
	return {
		"id": CITY_ID,
		"display_name": CITY_NAME,
		"country": str(city["country"]),
		"center_lat": float(city.get("lat") or city.get("latitude")),
		"center_lon": float(city.get("lon") or city.get("longitude")),
	}


def _canonical_hash(value: object) -> str:
	payload = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=str)
	return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_only_json(path: Path) -> dict | None:
	if not path.is_file():
		return None
	try:
		value = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as error:
		raise RuntimeError(f"Cannot read existing manifest without overwriting it: {path}: {error}") from error
	if not isinstance(value, dict):
		raise RuntimeError(f"Existing manifest is not a JSON object; preserving it: {path}")
	return value


def _atomic_json(path: Path, payload: dict) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
	temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
	os.replace(temp, path)


def _matrix_and_viewports(dpi: int) -> tuple[list[dict], dict]:
	styles = eligible_styles()
	if not styles:
		raise RuntimeError("No eligible registered styles remain after exclusions.")
	matrix = []
	size_viewports = {}
	for size_key in SIZE_KEY_FORMATS:
		validate_size_key_for_product_line(size_key, ProductLine.CITYMAP)
		spec = spec_from_size_key(size_key, extent_m=RADIUS_M, dpi=dpi)
		bundle_hw, bundle_hh = compute_osm_bundle_viewport(spec)
		style_viewports = {}
		max_style_hw = 0.0
		max_style_hh = 0.0
		for style in styles:
			half_width, half_height = get_viewport_for_style(style, spec)
			if bundle_hw < half_width or bundle_hh < half_height:
				raise RuntimeError(
					f"Bundle viewport does not cover renderer for {style}/{size_key}: "
					f"bundle=({bundle_hw},{bundle_hh}) renderer=({half_width},{half_height})"
				)
			style_viewports[style] = [half_width, half_height]
			max_style_hw = max(max_style_hw, half_width)
			max_style_hh = max(max_style_hh, half_height)
			matrix.append({
				"city_id": CITY_ID,
				"style_id": style,
				"size_key": size_key,
				"width_cm": spec.width_cm,
				"height_cm": spec.height_cm,
				"extent_radius_m": RADIUS_M,
				"renderer_half_width_m": half_width,
				"renderer_half_height_m": half_height,
			})
		size_viewports[size_key] = {
			"bundle_half_width_m": bundle_hw,
			"bundle_half_height_m": bundle_hh,
			"max_style_half_width_m": max_style_hw,
			"max_style_half_height_m": max_style_hh,
			"style_viewports": style_viewports,
		}
	return matrix, size_viewports


def _preflight_store(
	store_dir: Path,
	city: dict,
	selected_pbf: Path,
	selected_pbf_header: dict,
	size_viewports: dict,
) -> dict:
	from generator.core.pbf_source import PbfBundleSource
	from generator.core.pbf_store import PbfStoreReader

	store_file = store_dir / "osm_store.sqlite"
	if not store_file.is_file():
		raise CacheValidationError(f"No existing geographic store at {store_file}; refusing an implicit build.")

	max_half_width = max(item["bundle_half_width_m"] for item in size_viewports.values())
	max_half_height = max(item["bundle_half_height_m"] for item in size_viewports.values())
	with PbfStoreReader(store_dir) as reader:
		source_path = Path(reader.meta.get("pbf_path", ""))
		if not source_path.is_file():
			raise CacheValidationError(f"Store source is unavailable; cannot verify provenance: {source_path}")
		with PbfStoreReader(store_dir, pbf_path=source_path, verify_sha256=True) as verified:
			if verified.meta.get("status") != "complete":
				raise CacheValidationError("Geographic store is not marked complete.")
			if verified.counts.get("road_ways", 0) <= 0:
				raise CacheValidationError("Geographic store contains no roads.")
			missing_schema_layers = set(SUPPORTED_FEATURE_LAYERS) - set(verified.layer_bits)
			if missing_schema_layers:
				raise CacheValidationError(f"Store lacks required layer indexes: {sorted(missing_schema_layers)}")
			cache_source = {
				"path": str(source_path.resolve()),
				"sha256": verified.meta["pbf_sha256"],
				"size_bytes": int(verified.meta["pbf_size"]),
				"replication_timestamp": verified.meta.get("pbf_replication_timestamp"),
				"schema_version": verified.meta["schema_version"],
				"preprocess_version": verified.meta["preprocess_version"],
				"tag_rules_hash": verified.meta["tag_rules_hash"],
				"store_path": str(verified.store_path.resolve()),
				"store_size_bytes": verified.store_path.stat().st_size,
				"store_counts": verified.counts,
				"store_header_bbox": list(verified.header_bbox or ()),
			}
			query_source = PbfBundleSource(verified)
			bundle = query_source.load_bundle(
				center_lat=city["center_lat"],
				center_lon=city["center_lon"],
				extent_m=RADIUS_M,
				half_width_m=max_half_width,
				half_height_m=max_half_height,
				include_building_features=True,
			)
			stats = query_source.last_stats
			query_bbox = tuple(stats["query_bbox"])
			road_query_bbox = tuple(stats["road_query_bbox"])
			if not verified.covers(road_query_bbox):
				raise CacheValidationError(f"Largest buffered render query is outside cache coverage: {road_query_bbox}")
			if stats["roads"].get("edges", 0) <= 0 or stats["roads"].get("incomplete_ways_dropped", 0) > 0:
				raise CacheValidationError(f"Road cache validation failed: {stats['roads']}")
			layers = stats.get("layers", {})
			missing_features = {
				name: layers.get(name, {}).get("features", 0)
				for name in REQUIRED_FEATURE_LAYERS
				if not layers.get(name, {}).get("features", 0)
			}
			if missing_features:
				raise CacheValidationError(f"Required feature layers are empty: {missing_features}")
			relation_issues = {
				name: {
					"missing_members": layer.get("relations_with_missing_members", 0),
					"nested_members": layer.get("relations_with_nested_members", 0),
					"incomplete_ways": layer.get("incomplete_ways_dropped", 0),
				}
				for name, layer in layers.items()
				if layer.get("relations_with_missing_members", 0)
				or layer.get("relations_with_nested_members", 0)
				or layer.get("incomplete_ways_dropped", 0)
			}
			if relation_issues:
				raise CacheValidationError(f"Budapest feature query has incomplete OSM dependencies: {relation_issues}")
			runtime_layers = {key: None if value is None else len(value) for key, value in bundle.items()}
			if not runtime_layers.get("edges_raw") or not runtime_layers.get("gdf_all_raw"):
				raise CacheValidationError(f"Renderer bundle lacks roads or buildings: {runtime_layers}")

			city_coverage = {
				"radius_m": RADIUS_M,
				"max_half_width_m": max_half_width,
				"max_half_height_m": max_half_height,
				"query_bbox_wgs84": list(query_bbox),
				"road_query_bbox_wgs84": list(road_query_bbox),
				"source_cache_header_bbox_wgs84": list(verified.header_bbox or ()),
			}
			cache_id = _canonical_hash({
				"city": city,
				"coverage": city_coverage,
				"store_source_sha256": verified.meta["pbf_sha256"],
				"store_schema_version": verified.meta["schema_version"],
				"tag_rules_hash": verified.meta["tag_rules_hash"],
			})[:24]
			return {
				"cache_id": cache_id,
				"store_path": str(verified.store_path.resolve()),
				"store_size_bytes": verified.store_path.stat().st_size,
				"cache_source": cache_source,
				"selected_input_pbf": str(selected_pbf),
				"selected_input_pbf_size": selected_pbf.stat().st_size,
				"selected_input_pbf_header": selected_pbf_header,
				"coverage": city_coverage,
				"bundle_stats": stats,
				"runtime_layers": runtime_layers,
				"verified_relation_issues": relation_issues,
			}


@contextmanager
def _cache_only_environment(store_dir: Path):
	names = ("MAPCANVAS_OSM_SOURCE", "MAPCANVAS_PBF_STORE_DIR", "MAPCANVAS_PBF_PATH")
	previous = {name: os.environ.get(name) for name in names}
	os.environ["MAPCANVAS_OSM_SOURCE"] = "pbf"
	os.environ["MAPCANVAS_PBF_STORE_DIR"] = str(store_dir)
	os.environ.pop("MAPCANVAS_PBF_PATH", None)
	try:
		yield
	finally:
		for name, value in previous.items():
			if value is None:
				os.environ.pop(name, None)
			else:
				os.environ[name] = value


def _sha256_file(path: Path) -> str:
	digest = hashlib.sha256()
	with path.open("rb") as handle:
		for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
			digest.update(chunk)
	return digest.hexdigest()


def _validate_pdf(path: Path, width_cm: int, height_cm: int) -> dict:
	if not path.is_file() or path.stat().st_size == 0:
		raise OutputValidationError(f"PDF is missing or empty: {path}")
	with fitz.open(path) as document:
		if len(document) != 1:
			raise OutputValidationError(f"Expected one PDF page, got {len(document)}")
		page = document[0]
		width_mm = page.rect.width * 25.4 / 72
		height_mm = page.rect.height * 25.4 / 72
		if abs(width_mm - width_cm * 10) > 0.05 or abs(height_mm - height_cm * 10) > 0.05:
			raise OutputValidationError(
				f"PDF page dimensions {width_mm:.4f}x{height_mm:.4f} mm do not match {width_cm * 10}x{height_cm * 10} mm"
			)
		drawings = len(page.get_drawings())
		images = len(page.get_images(full=True))
		if drawings == 0 and images == 0 and not page.get_text().strip():
			raise OutputValidationError("PDF has no detectable poster content")
		return {"width_mm": width_mm, "height_mm": height_mm, "vector_drawings": drawings, "embedded_images": images}


def _expected_pixel_size(width_cm: int, height_cm: int, dpi: int) -> tuple[int, int]:
	return round(width_cm / 2.54 * dpi), round(height_cm / 2.54 * dpi)


def _preview_dimensions(
	width_cm: float, height_cm: float, long_sides: tuple[int, ...] = PREVIEW_LONG_SIDE_PRESETS,
) -> tuple[tuple[int, int], ...]:
	dimensions = []
	for long_side in long_sides:
		if width_cm <= height_cm:
			size = (round(long_side * width_cm / height_cm), long_side)
		else:
			size = (long_side, round(long_side * height_cm / width_cm))
		if size not in dimensions:
			dimensions.append(size)
	return tuple(dimensions)


def _rasterize_pdf_preview(pdf_path: Path, size: tuple[int, int]) -> Image.Image:
	with fitz.open(pdf_path) as document:
		page = document[0]
		scale_x = size[0] / page.rect.width
		scale_y = size[1] / page.rect.height
		pixmap = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y), alpha=False)
		image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
	if image.size != size:
		image = image.resize(size, Image.Resampling.LANCZOS)
	return image


def probe_pdf_preview_candidates(
	pdf_path: Path,
	output_dir: Path,
	width_cm: int,
	height_cm: int,
	max_bytes: int = 160_000,
) -> list[dict]:
	"""Write a deterministic, bounded comparison set for manual preview inspection."""
	output_dir.mkdir(parents=True, exist_ok=True)
	candidates = []
	for width_px, height_px in _preview_dimensions(width_cm, height_cm):
		image = _rasterize_pdf_preview(pdf_path, (width_px, height_px))
		for quality in PREVIEW_QUALITY_SETTINGS:
			path = output_dir / f"preview_{width_px}x{height_px}_q{quality}.webp"
			image.save(path, format="WEBP", quality=quality, method=WEBP_METHOD)
			candidates.append({
				"path": str(path),
				"width_px": width_px,
				"height_px": height_px,
				"quality": quality,
				"method": WEBP_METHOD,
				"encoding": "lossy-webp-rgb",
				"bytes": path.stat().st_size,
				"within_limit": path.stat().st_size <= max_bytes,
			})
	return candidates


def _render_pdf_to_webp(
	pdf_path: Path,
	webp_path: Path,
	width_cm: int,
	height_cm: int,
	max_bytes: int,
	max_long_side: int | None = None,
	long_sides: tuple[int, ...] = PREVIEW_LONG_SIDE_PRESETS,
) -> dict:
	attempts = []
	dimensions = _preview_dimensions(width_cm, height_cm, long_sides)
	if max_long_side is not None:
		dimensions = tuple(size for size in dimensions if max(size) <= max_long_side)
	if not dimensions:
		raise OutputValidationError(f"No supported preview dimensions fit within {max_long_side} pixels")
	for width_px, height_px in dimensions:
		image = _rasterize_pdf_preview(pdf_path, (width_px, height_px))
		for quality in PREVIEW_QUALITY_SETTINGS:
			image.save(webp_path, format="WEBP", quality=quality, method=WEBP_METHOD)
			size_bytes = webp_path.stat().st_size
			attempts.append({
				"width_px": width_px,
				"height_px": height_px,
				"quality": quality,
				"method": WEBP_METHOD,
				"bytes": size_bytes,
			})
			if size_bytes <= max_bytes:
				return {
					"bytes": size_bytes,
					"width_px": width_px,
					"height_px": height_px,
					"dimensions_px": [width_px, height_px],
					"quality": quality,
					"method": WEBP_METHOD,
					"encoding": "lossy-webp-rgb",
					"max_bytes": max_bytes,
					"attempts": attempts,
				}
	webp_path.unlink(missing_ok=True)
	raise OutputValidationError(
		f"Preview fallback ladder could not meet {max_bytes} bytes; "
		f"last candidate was {attempts[-1]['width_px']}x{attempts[-1]['height_px']} "
		f"quality={attempts[-1]['quality']} at {attempts[-1]['bytes']} bytes"
	)


def _validate_webp(path: Path, expected_size: tuple[int, int], max_bytes: int) -> dict:
	if not path.is_file() or path.stat().st_size == 0:
		raise OutputValidationError(f"WebP is missing or empty: {path}")
	if path.stat().st_size > max_bytes:
		raise OutputValidationError(f"WebP size {path.stat().st_size} exceeds {max_bytes} bytes")
	with Image.open(path) as image:
		if image.format != "WEBP" or image.size != expected_size:
			raise OutputValidationError(f"Unexpected WebP format/dimensions: {image.format} {image.size}; expected {expected_size}")
		image.load()
		if max(ImageStat.Stat(image.convert("RGB")).var) < 0.01:
			raise OutputValidationError("WebP appears blank")
		return {
			"bytes": path.stat().st_size,
			"width_px": image.width,
			"height_px": image.height,
			"dimensions_px": [image.width, image.height],
		}


def _validate_pair(
	pdf_path: Path,
	webp_path: Path,
	spec,
	max_bytes: int,
	expected_preview_size: tuple[int, int] | None = None,
) -> tuple[dict, dict]:
	pdf_info = _validate_pdf(pdf_path, spec.width_cm, spec.height_cm)
	if expected_preview_size is None:
		with Image.open(webp_path) as image:
			expected_preview_size = image.size
	if expected_preview_size not in _preview_dimensions(spec.width_cm, spec.height_cm):
		raise OutputValidationError(f"Preview dimensions {expected_preview_size} are not in the supported size fallbacks")
	webp_info = _validate_webp(webp_path, expected_preview_size, max_bytes)
	return pdf_info, webp_info


def _publish_pair(
	staged_dir: Path,
	output_dir: Path,
	expected_names: frozenset[str] | None = None,
	retired_names: frozenset[str] = frozenset(),
) -> None:
	"""Atomically replace ``output_dir``; ``retired_names`` are former deliverables an older product may still hold."""
	expected = set(expected_names or {"map.pdf", "map.webp"})
	if {path.name for path in staged_dir.iterdir()} != expected:
		raise OutputValidationError(f"Staging directory must contain exactly {sorted(expected)}")
	if output_dir.exists():
		existing = {path.name for path in output_dir.iterdir()}
		if existing - expected - set(retired_names):
			raise OutputValidationError(f"Preserving output directory with unknown files: {sorted(existing - expected - set(retired_names))}")
	backup = output_dir.with_name(f".{output_dir.name}.backup-{uuid.uuid4().hex}")
	moved_old = False
	try:
		if output_dir.exists():
			os.replace(output_dir, backup)
			moved_old = True
		os.replace(staged_dir, output_dir)
	except Exception:
		if moved_old and backup.exists() and not output_dir.exists():
			os.replace(backup, output_dir)
		raise
	if moved_old:
		shutil.rmtree(backup)


def _manifest_for_output(path: Path, cache: dict, matrix: list[dict]) -> dict:
	current = _read_only_json(path)
	identity = {"city_id": CITY_ID, "cache_id": cache["cache_id"], "radius_m": RADIUS_M}
	if current is None:
		return {"schema_version": 1, "identity": identity, "cache": cache, "jobs_expected": len(matrix), "jobs": {}}
	if current.get("identity") != identity:
		raise RuntimeError(f"Existing Budapest prototype manifest has a different identity; preserving it: {path}")
	current["cache"] = cache
	current["jobs_expected"] = len(matrix)
	current.setdefault("jobs", {})
	return current


def _job_key(job: dict) -> str:
	return f"{job['style_id']}/{job['size_key']}"


def _job_identity(job: dict, cache: dict, dpi: int, max_webp_bytes: int) -> dict:
	return {
		"city_id": job["city_id"],
		"style_id": job["style_id"],
		"size_key": job["size_key"],
		"width_cm": job["width_cm"],
		"height_cm": job["height_cm"],
		"radius_m": RADIUS_M,
		"cache_id": cache["cache_id"],
		"dpi": dpi,
		"max_webp_bytes": max_webp_bytes,
		"preview_dimensions_px": [list(size) for size in _preview_dimensions(job["width_cm"], job["height_cm"])],
		"preview_quality_settings": list(PREVIEW_QUALITY_SETTINGS),
		"preview_method": WEBP_METHOD,
	}


def _job_is_current(record: dict | None, identity: dict, output_dir: Path) -> bool:
	if not record or record.get("status") != "success" or record.get("identity") != identity:
		return False
	pdf, webp = output_dir / "map.pdf", output_dir / "map.webp"
	if not pdf.is_file() or not webp.is_file():
		return False
	if record.get("pdf_sha256") != _sha256_file(pdf) or record.get("webp_sha256") != _sha256_file(webp):
		return False
	return True


def _write_cache_manifest(cache_root: Path, cache: dict) -> Path:
	cache_dir = cache_root / CITY_ID / cache["cache_id"]
	path = cache_dir / CITY_CACHE_MANIFEST_NAME
	current = _read_only_json(path)
	if current is not None and current.get("cache_id") != cache["cache_id"]:
		raise RuntimeError(f"Existing city cache manifest conflicts; preserving it: {path}")
	if current is None:
		_atomic_json(path, {"schema_version": 1, **cache})
	return path


def record_preview_experiment(
	manifest_path: Path,
	candidates: list[dict],
	selected: dict,
	visual_assessment: str,
) -> None:
	manifest = _read_only_json(manifest_path)
	if manifest is None:
		raise RuntimeError(f"Prototype manifest does not exist; refusing to create a detached preview record: {manifest_path}")
	identity = manifest.get("identity", {})
	if identity.get("city_id") != CITY_ID or identity.get("radius_m") != RADIUS_M:
		raise RuntimeError(f"Prototype manifest identity does not match Budapest/{RADIUS_M} m: {manifest_path}")
	if identity.get("cache_id") != selected.get("cache_id", identity.get("cache_id")):
		raise RuntimeError("Selected preview cache identity does not match the prototype manifest")

	def candidate_record(candidate: dict) -> dict:
		return {
			"width_px": candidate["width_px"],
			"height_px": candidate["height_px"],
			"quality": candidate["quality"],
			"method": candidate["method"],
			"encoding": "lossy-webp-rgb",
			"bytes": candidate["bytes"],
			"within_limit": candidate["within_limit"],
		}

	manifest["preview_strategy"] = {
		"maximum_bytes": 160_000,
		"long_side_presets_px": list(PREVIEW_LONG_SIDE_PRESETS),
		"quality_settings": list(PREVIEW_QUALITY_SETTINGS),
		"method": WEBP_METHOD,
		"aspect_ratio_policy": "match-selected-spec",
		"source": "validated final PDF",
	}
	manifest["preview_experiment"] = {
		"status": "validated-preview-only; no deliverable published",
		"city_id": CITY_ID,
		"style_id": "urban_modern",
		"size_key": "50x70",
		"cache_id": identity["cache_id"],
		"candidate_results": [candidate_record(candidate) for candidate in candidates],
		"selected": candidate_record(selected),
		"visual_assessment": visual_assessment,
	}
	_atomic_json(manifest_path, manifest)


def run_budapest_matrix(
	*,
	selected_pbf: Path,
	selected_pbf_header: dict,
	store_dir: Path,
	cache_root: Path,
	output_root: Path,
	dpi: int = 300,
	max_webp_bytes: int = 160_000,
	dry_run: bool = False,
	force: bool = False,
) -> dict:
	if dpi <= 0 or max_webp_bytes <= 0:
		raise ValueError("dpi and max_webp_bytes must be positive")
	city = load_budapest_config()
	matrix, size_viewports = _matrix_and_viewports(dpi)
	print(f"City: {CITY_NAME} center=({city['center_lat']},{city['center_lon']}) radius={RADIUS_M} m")
	print(f"Sizes ({len(SIZE_KEY_FORMATS)}): {', '.join(SIZE_KEY_FORMATS)}")
	print(f"Eligible styles ({len(eligible_styles())}): {', '.join(eligible_styles())}")
	print(f"Excluded styles: {', '.join(sorted(EXCLUDED_STYLES))}")
	print(f"Expected combinations: {len(matrix)}")

	preflight_started = time.perf_counter()
	cache = _preflight_store(store_dir, city, selected_pbf, selected_pbf_header, size_viewports)
	cache["validation_duration_s"] = round(time.perf_counter() - preflight_started, 3)
	cache_manifest = _write_cache_manifest(cache_root, cache)
	cache["cache_manifest"] = str(cache_manifest)
	print(
		f"CACHE REUSE id={cache['cache_id']} path={cache['store_path']} bytes={cache['store_size_bytes']} "
		f"source={cache['cache_source']['path']} sha256={cache['cache_source']['sha256']}"
	)
	print(f"CACHE COVERAGE query={cache['coverage']['query_bbox_wgs84']} road={cache['coverage']['road_query_bbox_wgs84']}")
	print(f"CACHE LAYERS {cache['runtime_layers']}")
	print(f"CACHE VALIDATED in {cache['validation_duration_s']}s; extraction/build not required")

	manifest_path = output_root / OUTPUT_MANIFEST_NAME
	manifest = _manifest_for_output(manifest_path, cache, matrix)
	manifest["selected_europe_pbf"] = {
		"path": str(selected_pbf),
		"size_bytes": selected_pbf.stat().st_size,
		"header": selected_pbf_header,
		"used_for_rendering": False,
	}
	manifest["sizes"] = {key: list(value) for key, value in SIZES_CM.items()}
	manifest["eligible_styles"] = eligible_styles()
	manifest["excluded_styles"] = sorted(EXCLUDED_STYLES)
	manifest["preview_strategy"] = {
		"maximum_bytes": max_webp_bytes,
		"long_side_presets_px": list(PREVIEW_LONG_SIDE_PRESETS),
		"quality_settings": list(PREVIEW_QUALITY_SETTINGS),
		"method": WEBP_METHOD,
		"aspect_ratio_policy": "match-selected-spec",
		"source": "validated final PDF",
	}
	manifest["jobs_expected"] = len(matrix)
	_atomic_json(manifest_path, manifest)
	if dry_run:
		return {"expected": len(matrix), "success": 0, "skipped": 0, "failed": 0, "manifest": str(manifest_path)}

	success = skipped = failed = 0
	for job in matrix:
		key = _job_key(job)
		spec = spec_from_size_key(job["size_key"], extent_m=RADIUS_M, dpi=dpi)
		output_dir = output_root / job["style_id"] / job["size_key"]
		identity = _job_identity(job, cache, dpi, max_webp_bytes)
		current_record = manifest["jobs"].get(key)
		if not force and _job_is_current(current_record, identity, output_dir):
			webp_record = current_record.get("webp", {})
			expected_preview = tuple(webp_record.get("dimensions_px", ()))
			_validate_pair(output_dir / "map.pdf", output_dir / "map.webp", spec, max_webp_bytes, expected_preview)
			skipped += 1
			print(f"[{key}] SKIP validated cache_id={cache['cache_id']}")
			continue
		if output_dir.exists() and not force and not current_record:
			print(f"[{key}] FAIL existing output has no matching manifest; preserving files")
			manifest["jobs"][key] = {"status": "failed", "error": "Untracked existing output directory preserved"}
			failed += 1
			_atomic_json(manifest_path, manifest)
			continue

		job_started = time.perf_counter()
		print(f"[{key}] START cache_id={cache['cache_id']} cache_path={cache['store_path']} radius_m={RADIUS_M}")
		try:
			output_dir.parent.mkdir(parents=True, exist_ok=True)
			with tempfile.TemporaryDirectory(prefix=f"budapest-{job['style_id']}-{job['size_key']}-", dir=output_dir.parent) as temp:
				temp_dir = Path(temp)
				render_dir = temp_dir / "render"
				stage_dir = temp_dir / "stage"
				render_dir.mkdir()
				stage_dir.mkdir()
				with _cache_only_environment(store_dir):
					rendered = render_product(
						style_name=job["style_id"],
						center_lat=city["center_lat"],
						center_lon=city["center_lon"],
						spec=spec,
						output_dir=render_dir,
						title=CITY_NAME,
						subtitle=city["country"],
						preview_mode=False,
						order_id=f"BUDAPEST_{job['style_id']}_{job['size_key']}_{time.time_ns()}",
						use_cache=True,
					)
				if rendered.output_pdf is None or not rendered.output_pdf.is_file():
					raise OutputValidationError("Renderer did not produce a PDF")
				staged_pdf = stage_dir / "map.pdf"
				staged_webp = stage_dir / "map.webp"
				shutil.copy2(rendered.output_pdf, staged_pdf)
				pdf_info = _validate_pdf(staged_pdf, spec.width_cm, spec.height_cm)
				webp_info = _render_pdf_to_webp(staged_pdf, staged_webp, spec.width_cm, spec.height_cm, max_webp_bytes)
				_validate_pair(staged_pdf, staged_webp, spec, max_webp_bytes, tuple(webp_info["dimensions_px"]))
				_publish_pair(stage_dir, output_dir)

			record = {
				"status": "success",
				"identity": identity,
				"cache_id": cache["cache_id"],
				"cache_path": cache["store_path"],
				"cache_read_via_pbf_bundle_adapter": True,
				"raw_pbf_read_during_render": False,
				"geographic_store_rebuilds": 0,
				"pdf_path": str(output_dir / "map.pdf"),
				"pdf_sha256": _sha256_file(output_dir / "map.pdf"),
				"pdf_bytes": (output_dir / "map.pdf").stat().st_size,
				"pdf": pdf_info,
				"webp_path": str(output_dir / "map.webp"),
				"webp_sha256": _sha256_file(output_dir / "map.webp"),
				"webp": webp_info,
				"render_duration_s": round(time.perf_counter() - job_started, 3),
				"temporary_cleanup": "completed",
			}
			manifest["jobs"][key] = record
			success += 1
			print(f"[{key}] OK cache_id={cache['cache_id']} webp={webp_info['bytes']} bytes quality={webp_info['quality']} mode={webp_info['mode']} duration={record['render_duration_s']}s")
		except Exception as error:
			manifest["jobs"][key] = {
				"status": "failed",
				"identity": identity,
				"cache_id": cache["cache_id"],
				"cache_read_via_pbf_bundle_adapter": True,
				"raw_pbf_read_during_render": False,
				"error": f"{type(error).__name__}: {error}",
				"render_duration_s": round(time.perf_counter() - job_started, 3),
			}
			failed += 1
			print(f"[{key}] FAIL {type(error).__name__}: {error}")
		_atomic_json(manifest_path, manifest)

	return {"expected": len(matrix), "success": success, "skipped": skipped, "failed": failed, "manifest": str(manifest_path)}
