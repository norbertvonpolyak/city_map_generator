from __future__ import annotations

from enum import Enum

from generator.specs import ProductSpec


class BundleViewportPolicy(str, Enum):
    NORMAL_MAP = "normal_map"


# Breaking-change marker for bundle sizing rules.
# If policy constants change, bump this to force intentional cache migration.
BUNDLE_VIEWPORT_POLICY_VERSION = 1


DEFAULT_BUNDLE_VIEWPORT_POLICY = BundleViewportPolicy.NORMAL_MAP


def _compute_normal_map_viewport(spec: ProductSpec) -> tuple[float, float]:
    """Compute stable bundle viewport independent from style registry content.

    NORMAL_MAP policy intentionally ignores style/margin tuning. It uses an
    explicit poster-frame model that remains stable unless policy constants are
    intentionally changed.
    """
    side_margin_ratio = 0.04
    bottom_margin_ratio = 0.10

    width_cm = float(spec.width_cm)
    height_cm = float(spec.height_cm)
    short_side_cm = min(width_cm, height_cm)

    side_margin_cm = short_side_cm * side_margin_ratio
    top_margin_cm = side_margin_cm
    bottom_margin_cm = height_cm * bottom_margin_ratio

    visible_width_cm = width_cm - (2.0 * side_margin_cm)
    visible_height_cm = height_cm - top_margin_cm - bottom_margin_cm

    if visible_width_cm <= 0 or visible_height_cm <= 0:
        raise ValueError("Invalid NORMAL_MAP bundle viewport dimensions.")

    half_height_m = float(spec.extent_m)
    half_width_m = half_height_m * (visible_width_cm / visible_height_cm)
    return half_width_m, half_height_m


def compute_osm_bundle_viewport(
    spec: ProductSpec,
    policy: BundleViewportPolicy = DEFAULT_BUNDLE_VIEWPORT_POLICY,
) -> tuple[float, float]:
    if policy == BundleViewportPolicy.NORMAL_MAP:
        return _compute_normal_map_viewport(spec)
    raise ValueError(f"Unsupported bundle viewport policy: {policy}")


def bundle_viewport_policy_cache_token(
    policy: BundleViewportPolicy = DEFAULT_BUNDLE_VIEWPORT_POLICY,
) -> str:
    return f"{policy.value}_v{BUNDLE_VIEWPORT_POLICY_VERSION}"
