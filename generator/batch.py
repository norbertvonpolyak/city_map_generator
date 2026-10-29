"""Local Budapest cache-backed poster prototype."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPOSITORY_ROOT.parent
PBF_DIRECTORY_CANDIDATES = (
	WORKSPACE_ROOT / "geofabrik",
	WORKSPACE_ROOT / "GEOFABRIK",
	REPOSITORY_ROOT / "geofabrik",
	REPOSITORY_ROOT / "GEOFABRIK",
)
EUROPE_COVERAGE_BBOX = (-10.5, 34.0, 31.5, 61.5)


class PbfSelectionError(RuntimeError):
	pass


def read_pbf_header(path: Path) -> dict:
	from generator.core.pbf_store import read_pbf_header as read_header

	return read_header(path)


def discover_europe_pbf(directory_candidates=PBF_DIRECTORY_CANDIDATES) -> Path:
	candidates = sorted(
		{
			path.resolve()
			for directory in {Path(item).resolve() for item in directory_candidates}
			if directory.is_dir()
			for path in directory.iterdir()
			if path.is_file() and path.suffix.casefold() == ".pbf" and path.stat().st_size > 0
		},
		key=lambda path: str(path).casefold(),
	)
	west, south, east, north = EUROPE_COVERAGE_BBOX
	covering = []
	details = []
	for path in candidates:
		try:
			bbox = read_pbf_header(path).get("bbox")
		except (OSError, RuntimeError) as error:
			details.append(f"{path} (unreadable header: {error})")
			continue
		if bbox:
			details.append(f"{path} (bbox={bbox})")
			if bbox[0] <= west and bbox[1] <= south and bbox[2] >= east and bbox[3] >= north:
				covering.append(path)
		else:
			details.append(f"{path} (no geographic bounds)")

	if len(covering) == 1:
		return covering[0]
	candidates_text = "\n".join(f"  {item}" for item in details) or "  (none)"
	if len(covering) > 1:
		raise PbfSelectionError(f"Multiple Europe PBF files cover the configured region; specify --pbf:\n{candidates_text}")
	raise PbfSelectionError(f"No suitable Europe PBF found. Candidates:\n{candidates_text}")


def validate_pbf_input(path: Path, *, require_europe_coverage: bool = False) -> dict:
	selected = Path(path).expanduser().resolve()
	if not selected.is_file() or selected.suffix.casefold() != ".pbf" or selected.stat().st_size == 0:
		raise PbfSelectionError(f"PBF input must be an existing, non-empty .pbf file: {selected}")
	try:
		header = read_pbf_header(selected)
	except (OSError, RuntimeError) as error:
		raise PbfSelectionError(f"Cannot read PBF header from {selected}: {error}") from error
	bbox = header.get("bbox")
	if not bbox:
		raise PbfSelectionError(f"PBF has no readable geographic bounds: {selected}")
	if require_europe_coverage:
		west, south, east, north = EUROPE_COVERAGE_BBOX
		if not (bbox[0] <= west and bbox[1] <= south and bbox[2] >= east and bbox[3] >= north):
			raise PbfSelectionError(f"PBF does not cover the configured Europe region: {selected} (bbox={bbox})")
	return header


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Render Budapest size/style prototypes from the persistent city cache")
	parser.add_argument("--pbf", type=Path, help="Alternative local PBF for cache population; renders never read it directly")
	parser.add_argument("--store-dir", type=Path, help="Existing SQLite/R-tree PBF store directory")
	parser.add_argument("--cache-root", type=Path, help="Root for Budapest cache-view metadata")
	parser.add_argument("--output-dir", type=Path, help="Budapest prototype output root")
	parser.add_argument("--dpi", type=int, default=300)
	parser.add_argument("--max-webp-bytes", type=int, default=160_000)
	parser.add_argument("--dry-run", action="store_true", help="Validate cache and matrix without rendering")
	parser.add_argument("--force", action="store_true", help="Replace outputs even if already validated")
	return parser


def main(argv: list[str] | None = None) -> int:
	from generator.batch_pipeline import run_budapest_matrix

	args = build_parser().parse_args(argv)
	try:
		pbf_path = args.pbf.expanduser().resolve() if args.pbf else discover_europe_pbf()
		header = validate_pbf_input(pbf_path, require_europe_coverage=args.pbf is None)
	except PbfSelectionError as error:
		raise SystemExit(str(error)) from error

	local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
	store_dir = args.store_dir or local_app_data / "MapCanvas" / "pbf_store"
	cache_root = args.cache_root or local_app_data / "MapCanvas" / "city_cache"
	output_dir = args.output_dir or REPOSITORY_ROOT / "output" / "cities" / "budapest"
	result = run_budapest_matrix(
		selected_pbf=pbf_path,
		selected_pbf_header=header,
		store_dir=store_dir.expanduser().resolve(),
		cache_root=cache_root.expanduser().resolve(),
		output_root=output_dir.expanduser().resolve(),
		dpi=args.dpi,
		max_webp_bytes=args.max_webp_bytes,
		dry_run=args.dry_run,
		force=args.force,
	)
	print(
		f"SUMMARY expected={result['expected']} success={result['success']} "
		f"skipped={result['skipped']} failed={result['failed']}"
	)
	print(f"Manifest: {result['manifest']}")
	return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
	raise SystemExit(main())
