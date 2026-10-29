import os
from pathlib import Path

import fitz
import pytest
from PIL import Image

from generator.batch_pipeline import (
    EXCLUDED_STYLES,
    PREVIEW_LONG_SIDE_PRESETS,
    PREVIEW_QUALITY_SETTINGS,
    _cache_only_environment,
    _expected_pixel_size,
    _matrix_and_viewports,
    _publish_pair,
    _preview_dimensions,
    record_preview_experiment,
    _render_pdf_to_webp,
    _validate_pair,
    probe_pdf_preview_candidates,
    eligible_styles,
)
from generator.core.style_registry import STYLE_REGISTRY
from generator.specs import SIZES_CM, spec_from_size_key


def _write_sample_pdf(path):
    document = fitz.open()
    page = document.new_page(width=50 / 2.54 * 72, height=70 / 2.54 * 72)
    for index in range(120):
        y = 40 + index * 6
        page.draw_line((30, y), (page.rect.width - 30, y), color=(0.1, 0.1, 0.1), width=0.3 + index % 4 * 0.1)
    document.save(path)
    document.close()
    return path


def test_matrix_dimensions_and_style_exclusions_are_registry_driven():
    styles = eligible_styles()
    assert styles == [style for style in STYLE_REGISTRY if style not in EXCLUDED_STYLES]
    assert "mp_noir_gold" not in styles
    assert "minimal_sand" not in styles
    assert len(SIZES_CM) == 7
    assert len(styles) * len(SIZES_CM) == 70
    matrix, viewports = _matrix_and_viewports(300)
    assert len(matrix) == 70
    assert set(viewports) == set(SIZES_CM)
    assert {job["extent_radius_m"] for job in matrix} == {3500}


@pytest.mark.parametrize("size_key,expected", [
    ("40x50", (4724, 5906)),
    ("50x40", (5906, 4724)),
    ("50x70", (5906, 8268)),
    ("70x50", (8268, 5906)),
    ("50x50", (5906, 5906)),
    ("60x90", (7087, 10630)),
    ("90x60", (10630, 7087)),
])
def test_size_pixel_dimensions_follow_physical_spec(size_key, expected):
    width_cm, height_cm = SIZES_CM[size_key]
    assert _expected_pixel_size(width_cm, height_cm, 300) == expected


def test_preview_presets_match_50x70_and_preserve_other_size_aspects():
    assert _preview_dimensions(50, 70) == ((1600, 2240), (1200, 1680), (1000, 1400), (800, 1120))
    for width_cm, height_cm in SIZES_CM.values():
        for width_px, height_px in _preview_dimensions(width_cm, height_cm):
            assert abs(width_px / height_px - width_cm / height_cm) <= 1 / min(width_px, height_px)


def test_candidate_probe_records_exact_sizes_quality_and_method(tmp_path):
    pdf = _write_sample_pdf(tmp_path / "sample.pdf")
    candidates = probe_pdf_preview_candidates(pdf, tmp_path / "candidates", 50, 70)

    assert len(candidates) == len(PREVIEW_LONG_SIDE_PRESETS) * len(PREVIEW_QUALITY_SETTINGS)
    assert all(candidate["method"] == 6 for candidate in candidates)
    assert all(candidate["encoding"] == "lossy-webp-rgb" for candidate in candidates)
    assert all(candidate["bytes"] == (tmp_path / "candidates" / Path(candidate["path"]).name).stat().st_size for candidate in candidates)
    assert [(candidate["width_px"], candidate["height_px"]) for candidate in candidates[:4]] == [(1600, 2240)] * 4


def test_pdf_preview_fallback_meets_limit_without_changing_print_pdf(tmp_path):
    pdf = _write_sample_pdf(tmp_path / "sample.pdf")
    spec = spec_from_size_key("50x70", extent_m=3500)
    webp = tmp_path / "preview.webp"

    result = _render_pdf_to_webp(pdf, webp, spec.width_cm, spec.height_cm, 160_000)
    pdf_info, webp_info = _validate_pair(pdf, webp, spec, 160_000, tuple(result["dimensions_px"]))

    assert (pdf_info["width_mm"], pdf_info["height_mm"]) == pytest.approx((500, 700), abs=0.05)
    assert webp_info["bytes"] <= 160_000
    assert tuple(webp_info["dimensions_px"]) in _preview_dimensions(50, 70)
    assert result["attempts"]


def test_web_preview_respects_long_side_and_byte_limits(tmp_path):
    pdf = _write_sample_pdf(tmp_path / "sample.pdf")
    webp = tmp_path / "preview.webp"

    result = _render_pdf_to_webp(pdf, webp, 50, 70, 150_000, max_long_side=1400)

    assert max(result["dimensions_px"]) <= 1400
    assert result["bytes"] <= 150_000
    assert result["encoding"] == "lossy-webp-rgb"
    assert webp.is_file()


def test_preview_fallback_rejects_when_limit_is_impossible(tmp_path):
    pdf = _write_sample_pdf(tmp_path / "sample.pdf")
    target = tmp_path / "preview.webp"

    with pytest.raises(Exception, match="could not meet 1 bytes"):
        _render_pdf_to_webp(pdf, target, 50, 70, 1)

    assert not target.exists()


def test_render_environment_cannot_read_the_raw_pbf(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPCANVAS_PBF_PATH", "must-not-be-used.pbf")
    with _cache_only_environment(tmp_path / "store"):
        assert os.environ["MAPCANVAS_OSM_SOURCE"] == "pbf"
        assert os.environ["MAPCANVAS_PBF_STORE_DIR"] == str(tmp_path / "store")
        assert "MAPCANVAS_PBF_PATH" not in os.environ
    assert os.environ["MAPCANVAS_PBF_PATH"] == "must-not-be-used.pbf"


def test_publish_pair_replaces_only_known_deliverables(tmp_path):
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "map.pdf").write_bytes(b"pdf")
    (staged / "map.webp").write_bytes(b"webp")
    output = tmp_path / "output"
    output.mkdir()
    (output / "map.pdf").write_bytes(b"old-pdf")
    (output / "map.webp").write_bytes(b"old-webp")

    _publish_pair(staged, output)

    assert {path.name for path in output.iterdir()} == {"map.pdf", "map.webp"}
    assert (output / "map.pdf").read_bytes() == b"pdf"
    assert (output / "map.webp").read_bytes() == b"webp"


def test_publish_preserves_unknown_files(tmp_path):
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "map.pdf").write_bytes(b"pdf")
    (staged / "map.webp").write_bytes(b"webp")
    output = tmp_path / "output"
    output.mkdir()
    (output / "user-note.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(Exception, match="unknown files"):
        _publish_pair(staged, output)

    assert (output / "user-note.txt").read_text(encoding="utf-8") == "keep"


def test_preview_experiment_is_recorded_without_marking_a_job_success(tmp_path):
    manifest = tmp_path / "prototype_manifest.json"
    manifest.write_text(
        '{"identity":{"city_id":"budapest","cache_id":"cache-1","radius_m":3500},"jobs":{}}',
        encoding="utf-8",
    )
    candidates = [{
        "path": "temporary-candidate.webp", "width_px": 1000, "height_px": 1400,
        "quality": 30, "method": 6, "bytes": 151274, "within_limit": True,
    }]

    record_preview_experiment(manifest, candidates, candidates[0], "Roads remain legible; mild compression softness.")

    import json

    result = json.loads(manifest.read_text(encoding="utf-8"))
    assert result["preview_experiment"]["selected"]["bytes"] == 151274
    assert "path" not in result["preview_experiment"]["selected"]
    assert result["jobs"] == {}