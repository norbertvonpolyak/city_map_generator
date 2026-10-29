"""Dynamic print sizes: catalog and internal sizes share one renderer, layout, viewport and export path."""

from __future__ import annotations

import math

import fitz
import pytest
from PIL import Image

from generator import xml_order
from generator.batch_pipeline import _render_pdf_to_webp, _validate_webp
from generator.core.bundle_viewport_policy import compute_osm_bundle_viewport
from generator.core.render_dispatcher import _build_layout_for_style, get_viewport_for_style
from generator.core.style_registry import STYLE_REGISTRY
from generator.order_renderer import _validate_pdf
from generator.specs import (
    SIZES_CM,
    ProductSpec,
    resolve_size_request,
    spec_from_dimensions,
    spec_from_size_key,
)

CATALOG = [SIZES_CM[key] for key in SIZES_CM]
INTERNAL = [(45, 65), (45.5, 65), (65, 45), (33.3, 33.3)]
ALL_SIZES = CATALOG + INTERNAL
INVALID = [0, -1, -0.5, "50", None, True, float("nan"), float("inf"), float("-inf"), [50]]


def test_webshop_catalog_is_unchanged():
    assert SIZES_CM == {
        "40x50": (40, 50), "50x40": (50, 40), "50x70": (50, 70), "70x50": (70, 50),
        "50x50": (50, 50), "60x90": (60, 90), "90x60": (90, 60),
    }
    for key, (width_cm, height_cm) in SIZES_CM.items():
        assert resolve_size_request(key) == (key, width_cm, height_cm)
        spec = spec_from_size_key(key)
        assert (spec.width_cm, spec.height_cm, spec.size_label) == (width_cm, height_cm, key)


def test_internal_sizes_resolve_outside_the_catalog():
    assert resolve_size_request((45, 65)) == ("45x65", 45, 65)
    assert resolve_size_request([45.5, 65.0]) == ("45.5x65", 45.5, 65)
    with pytest.raises(ValueError, match="catalog"):
        resolve_size_request("45x65")


@pytest.mark.parametrize("size,orientation", [((45, 65), "portrait"), ((65, 45), "landscape"), ((50, 50), "square")])
def test_orientation_is_derived(size, orientation):
    assert spec_from_dimensions(*size).orientation == orientation


@pytest.mark.parametrize("value", INVALID)
def test_invalid_dimensions_are_rejected(value):
    with pytest.raises(ValueError):
        spec_from_dimensions(value, 70)
    with pytest.raises(ValueError):
        spec_from_dimensions(50, value)
    with pytest.raises(ValueError):
        resolve_size_request((value, 70))


@pytest.mark.parametrize("value", [0, -4000, float("nan"), float("inf"), "4000"])
def test_invalid_extent_is_rejected(value):
    with pytest.raises(ValueError):
        ProductSpec(width_cm=50, height_cm=70, extent_m=value)


@pytest.mark.parametrize("size", ALL_SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("style", sorted(STYLE_REGISTRY))
def test_viewport_follows_map_box_and_is_undistorted(style, size):
    width_cm, height_cm = size
    spec = spec_from_dimensions(width_cm, height_cm, extent_m=4000)
    layout = _build_layout_for_style(style, spec)
    half_width_m, half_height_m = get_viewport_for_style(style, spec)

    assert half_height_m == 4000
    assert half_width_m == pytest.approx(4000 * layout.visible_width_cm / layout.visible_height_cm, rel=1e-12)
    # Metres-per-cm are equal on both axes (no stretch).
    assert (2 * half_width_m) / layout.visible_width_cm == pytest.approx((2 * half_height_m) / layout.visible_height_cm, rel=1e-12)
    assert layout.map_box.x_cm >= 0 and layout.map_box.x_cm + layout.visible_width_cm <= width_cm + 1e-9
    assert layout.map_box.y_cm + layout.visible_height_cm <= height_cm + 1e-9
    bundle_hw, bundle_hh = compute_osm_bundle_viewport(spec)
    assert bundle_hw >= half_width_m - 1e-9 and bundle_hh >= half_height_m - 1e-9


@pytest.mark.parametrize("size", ALL_SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_side_and_top_margins_are_equal(size):
    layout = _build_layout_for_style("urban_modern", spec_from_dimensions(*size))
    assert layout.left_margin_cm == pytest.approx(layout.right_margin_cm)
    assert layout.left_margin_cm == pytest.approx(layout.top_margin_cm)
    assert layout.left_margin_cm == pytest.approx(0.04 * min(size))


def test_extent_is_independent_of_physical_size():
    small = spec_from_dimensions(25, 35, extent_m=4000)
    large = spec_from_dimensions(50, 70, extent_m=4000)
    assert get_viewport_for_style("urban_modern", small) == pytest.approx(get_viewport_for_style("urban_modern", large))
    assert small.frame_half_sizes_m == pytest.approx(large.frame_half_sizes_m)


def _write_pdf(path, width_cm, height_cm):
    document = fitz.open()
    page = document.new_page(width=width_cm / 2.54 * 72, height=height_cm / 2.54 * 72)
    for index in range(60):
        y = 20 + index * (page.rect.height - 40) / 60
        page.draw_line((20, y), (page.rect.width - 20, y), color=(0.1, 0.2, 0.3), width=0.4 + index % 3 * 0.2)
    document.save(path)
    document.close()
    return path


@pytest.mark.parametrize("size", ALL_SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_pdf_and_preview_follow_requested_size(tmp_path, size):
    width_cm, height_cm = size
    pdf = _write_pdf(tmp_path / "map.pdf", width_cm, height_cm)

    pdf_info = _validate_pdf(pdf, width_cm, height_cm)
    assert pdf_info["width_mm"] == pytest.approx(width_cm * 10, abs=0.05)
    assert pdf_info["height_mm"] == pytest.approx(height_cm * 10, abs=0.05)

    preview = _render_pdf_to_webp(pdf, tmp_path / "preview.webp", width_cm, height_cm, 150_000, max_long_side=1400)
    _validate_webp(tmp_path / "preview.webp", tuple(preview["dimensions_px"]), 150_000)
    xml_order._validate_preview(preview, width_cm, height_cm)
    with Image.open(tmp_path / "preview.webp") as image:
        assert max(image.size) <= 1400
        assert math.isclose(image.width / image.height, width_cm / height_cm, abs_tol=1 / min(image.size))


def test_preview_over_limits_is_rejected():
    with pytest.raises(Exception, match="Web preview"):
        xml_order._validate_preview({"width_px": 1500, "height_px": 2100, "bytes": 100}, 50, 70)
