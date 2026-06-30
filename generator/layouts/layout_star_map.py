from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from generator.layouts.layout_utils import build_poster_layout


class StarLayoutMode(str, Enum):
    LAYOUT_BELOW = "layout_below"
    LAYOUT_SIDE = "layout_side"


class StarStyle(str, Enum):
    SKY = "sky"


@dataclass(frozen=True)
class StarLayoutTokens:
    # Outer margin is reused from the city minimal passepartout logic.
    outer_margin_ratio: float = 0.0
    text_band_ratio: float = 0.20
    text_band_min_ratio: float = 0.18
    text_band_max_ratio: float = 0.22
    circle_scale: float = 0.88
    typography_gap_ratio: float = 0.06
    bottom_text_floor_ratio: float = 0.05


STAR_LAYOUT = StarLayoutTokens()


@dataclass(frozen=True)
class RectCm:
    x_cm: float
    y_cm: float
    width_cm: float
    height_cm: float

    @property
    def center_x_cm(self) -> float:
        return self.x_cm + (self.width_cm / 2.0)

    @property
    def center_y_cm(self) -> float:
        return self.y_cm + (self.height_cm / 2.0)


@dataclass(frozen=True)
class CircleCm:
    center_x_cm: float
    center_y_cm: float
    diameter_cm: float

    @property
    def radius_cm(self) -> float:
        return self.diameter_cm / 2.0


@dataclass(frozen=True)
class StarTypographyLayout:
    zone: RectCm
    title: RectCm
    subtitle: RectCm
    location: RectCm
    date: RectCm
    custom_message: RectCm


@dataclass(frozen=True)
class StarPosterLayout:
    width_cm: float
    height_cm: float
    aspect_ratio: float
    mode: StarLayoutMode
    outer_margin_cm: float
    artwork_area: RectCm
    typography: StarTypographyLayout
    circle: CircleCm


def _resolve_mode(width_cm: float, height_cm: float) -> StarLayoutMode:
    ratio = width_cm / height_cm
    if ratio > 1.1:
        return StarLayoutMode.LAYOUT_SIDE
    return StarLayoutMode.LAYOUT_BELOW


def _split_typography_zone(zone: RectCm, gap_ratio: float, uniform_rows: bool = False) -> StarTypographyLayout:
    weights = (2.0, 1.2, 1.0, 1.0, 1.0)
    if uniform_rows:
        weights = (1.0, 1.0, 1.0, 1.0, 1.0)

    total_weight = sum(weights)
    gap_count = len(weights) + 1
    gap_cm = zone.height_cm * gap_ratio / gap_count
    content_h = max(zone.height_cm - (gap_cm * gap_count), 0.01)

    heights = [content_h * (w / total_weight) for w in weights]

    y = zone.y_cm + gap_cm
    custom_box = RectCm(zone.x_cm, y, zone.width_cm, heights[4])
    y += heights[4] + gap_cm

    date_box = RectCm(zone.x_cm, y, zone.width_cm, heights[3])
    y += heights[3] + gap_cm

    location_box = RectCm(zone.x_cm, y, zone.width_cm, heights[2])
    y += heights[2] + gap_cm

    subtitle_box = RectCm(zone.x_cm, y, zone.width_cm, heights[1])
    y += heights[1] + gap_cm

    title_box = RectCm(zone.x_cm, y, zone.width_cm, heights[0])

    return StarTypographyLayout(
        zone=zone,
        title=title_box,
        subtitle=subtitle_box,
        location=location_box,
        date=date_box,
        custom_message=custom_box,
    )


def build_star_layout(width_cm: float, height_cm: float, style: StarStyle = StarStyle.SKY, tokens: StarLayoutTokens | None = None) -> StarPosterLayout:
    t = tokens or STAR_LAYOUT
    
    if style == StarStyle.SKY:
        base_layout = build_poster_layout(width_cm, height_cm, uniform_margins=True)
        outer_margin_cm = base_layout.left_margin_cm
        inner_w = width_cm - 2 * outer_margin_cm
        inner_h = height_cm - 2 * outer_margin_cm
        typography_h = inner_h * 0.15

        artwork_area = RectCm(
            x_cm=outer_margin_cm,
            y_cm=outer_margin_cm,
            width_cm=inner_w,
            height_cm=inner_h,
        )
        typography_zone = RectCm(
            x_cm=outer_margin_cm,
            y_cm=outer_margin_cm,
            width_cm=inner_w,
            height_cm=typography_h,
        )
        circle = CircleCm(
            center_x_cm=artwork_area.center_x_cm,
            center_y_cm=artwork_area.center_y_cm,
            diameter_cm=min(artwork_area.width_cm, artwork_area.height_cm) * 0.95,
        )
        typography = _split_typography_zone(typography_zone, gap_ratio=t.typography_gap_ratio, uniform_rows=True)
        return StarPosterLayout(
            width_cm=width_cm,
            height_cm=height_cm,
            aspect_ratio=width_cm / height_cm,
            mode=StarLayoutMode.LAYOUT_BELOW,
            outer_margin_cm=outer_margin_cm,
            artwork_area=artwork_area,
            typography=typography,
            circle=circle,
        )
    
    mode = _resolve_mode(width_cm, height_cm)

    # Reuse exact margin logic from the minimal city map passepartout.
    base_layout = build_poster_layout(width_cm, height_cm, uniform_margins=True)
    outer_margin_cm = base_layout.left_margin_cm

    # Optional token override for experiments without hardcoded size rules.
    if t.outer_margin_ratio > 0:
        short_side_cm = min(width_cm, height_cm)
        outer_margin_cm = short_side_cm * t.outer_margin_ratio

    inner_w = width_cm - (2.0 * outer_margin_cm)
    inner_h = height_cm - (2.0 * outer_margin_cm)

    if mode == StarLayoutMode.LAYOUT_SIDE:
        text_band_ratio = min(max(t.text_band_ratio, t.text_band_min_ratio), t.text_band_max_ratio)
        typography_w = inner_w * text_band_ratio
        artwork_w = inner_w - typography_w

        artwork_area = RectCm(
            x_cm=outer_margin_cm,
            y_cm=outer_margin_cm,
            width_cm=artwork_w,
            height_cm=inner_h,
        )
        typography_zone = RectCm(
            x_cm=outer_margin_cm + artwork_w,
            y_cm=outer_margin_cm,
            width_cm=typography_w,
            height_cm=inner_h,
        )
        circle_diameter = min(artwork_area.width_cm, artwork_area.height_cm) * t.circle_scale
        circle = CircleCm(
            center_x_cm=artwork_area.center_x_cm,
            center_y_cm=artwork_area.center_y_cm,
            diameter_cm=circle_diameter,
        )
        typography = _split_typography_zone(typography_zone, gap_ratio=t.typography_gap_ratio, uniform_rows=False)
    else:
        text_band_ratio = min(max(t.text_band_ratio, t.text_band_min_ratio), t.text_band_max_ratio)
        typography_h = inner_h * text_band_ratio
        artwork_h = inner_h - typography_h
        text_floor_y_cm = height_cm * t.bottom_text_floor_ratio

        artwork_area = RectCm(
            x_cm=outer_margin_cm,
            y_cm=text_floor_y_cm + typography_h,
            width_cm=inner_w,
            height_cm=(height_cm - outer_margin_cm) - (text_floor_y_cm + typography_h),
        )
        circle_diameter = min(artwork_area.width_cm, artwork_area.height_cm) * t.circle_scale
        circle = CircleCm(
            center_x_cm=artwork_area.center_x_cm,
            center_y_cm=artwork_area.center_y_cm,
            diameter_cm=circle_diameter,
        )

        circle_bottom_cm = circle.center_y_cm - circle.radius_cm
        typography_zone = RectCm(
            x_cm=outer_margin_cm,
            y_cm=text_floor_y_cm,
            width_cm=inner_w,
            height_cm=max(circle_bottom_cm - text_floor_y_cm, 0.01),
        )
        typography = _split_typography_zone(typography_zone, gap_ratio=t.typography_gap_ratio, uniform_rows=True)

    return StarPosterLayout(
        width_cm=width_cm,
        height_cm=height_cm,
        aspect_ratio=width_cm / height_cm,
        mode=mode,
        outer_margin_cm=outer_margin_cm,
        artwork_area=artwork_area,
        typography=typography,
        circle=circle,
    )
