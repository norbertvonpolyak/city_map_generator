"""B2: EXTENT_M viewport contract for every registered style, size key, and extent.

Renderer half-sizes must be (E * Wv / Hv, E) from the style's actual layout map box, and the
style-independent OSM bundle viewport must contain them. Clean-HEAD compatible.
"""

from __future__ import annotations

import pytest

from generator.core.bundle_viewport_policy import compute_osm_bundle_viewport
from generator.core.render_dispatcher import _build_layout_for_style, get_viewport_for_style
from generator.core.style_registry import STYLE_REGISTRY
from generator.specs import SIZES_CM, spec_from_size_key

EXTENTS_M = (1000, 2000, 5000)
CASES = [(style, size_key, extent) for style in sorted(STYLE_REGISTRY) for size_key in SIZES_CM for extent in EXTENTS_M]


def test_registry_and_sizes_are_the_expected_matrix():
    assert len(STYLE_REGISTRY) == 11
    assert sorted(SIZES_CM) == sorted(["40x50", "50x40", "50x70", "70x50", "50x50", "60x90", "90x60"])


@pytest.mark.parametrize("style_name,size_key,extent_m", CASES)
def test_renderer_viewport_follows_extent_contract(style_name, size_key, extent_m):
    spec = spec_from_size_key(size_key, extent_m=extent_m)
    layout = _build_layout_for_style(style_name, spec)
    half_width_m, half_height_m = get_viewport_for_style(style_name, spec)

    assert half_height_m == float(extent_m)
    assert half_width_m == pytest.approx(extent_m * layout.visible_width_cm / layout.visible_height_cm, rel=1e-12)

    width_cm, height_cm = SIZES_CM[size_key]
    if width_cm > height_cm:
        assert half_width_m > extent_m
    elif width_cm < height_cm:
        assert half_width_m < extent_m


@pytest.mark.parametrize("style_name,size_key,extent_m", CASES)
def test_bundle_viewport_contains_renderer_viewport(style_name, size_key, extent_m):
    spec = spec_from_size_key(size_key, extent_m=extent_m)
    half_width_m, half_height_m = get_viewport_for_style(style_name, spec)
    bundle_half_width_m, bundle_half_height_m = compute_osm_bundle_viewport(spec)

    gap_w = bundle_half_width_m - half_width_m
    gap_h = bundle_half_height_m - half_height_m
    assert gap_w >= 0 and gap_h >= 0, (
        f"{style_name} {size_key} E={extent_m}: bundle shortfall width={gap_w:.3f} m height={gap_h:.3f} m"
    )
