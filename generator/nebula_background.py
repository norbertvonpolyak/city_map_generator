# generator/nebula_background.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np
from PIL import Image, ImageFilter, ImageChops


# Referenciához közelebb: sötét alapszín + kékes köd (nincs fehér)
DEFAULT_RAMP = (
    (1, 3, 8),        # near-black blue
    (7, 12, 26),      # deep navy
    (14, 28, 52),     # dark blue
    (36, 72, 108),    # nebula blue
    (78, 120, 152),   # light fog (still blue)
)

@dataclass(frozen=True)
class NebulaParams:
    # Alap fátyol
    large_scale: int = 520
    mid_scale: int = 220
    fine_scale: int = 90

    fog_gamma: float = 1.10
    fog_strength: float = 1.30
    base_darkness: float = 0.62   # lejjebb -> sötétebb dominancia

    # "Watercolor blotches" – belső ködfoltok (nem threshold!)
    blotch_scale: int = 260
    blotch_detail_scale: int = 95
    blotch_strength: float = 0.75
    blotch_blur: float = 22.0

    # Dark lanes – sötét porcsíkok (nagylépték, erős blur, ezért nem pöttyös)
    lane_scale: int = 380
    lane_strength: float = 0.35
    lane_blur: float = 52.0

    # Granulation / papír-textúra (multiplicative)
    grain_scale: int = 38
    grain_strength: float = 0.22

    # Splatter / csillagpor több méretben
    splatter_small_density: float = 0.020
    splatter_small_strength: float = 0.65
    splatter_mid_density: float = 0.0045
    splatter_mid_strength: float = 0.55
    splatter_big_density: float = 0.0009
    splatter_big_strength: float = 0.45

    # Tejút sáv
    band_strength: float = 0.40
    band_blur: float = 60.0

    # Vignetta + végső fátyolos blur
    vignette: float = 0.45
    final_blur: float = 0.55

    # Lokális kontraszt (akvarell “élek” érzet)
    unsharp_radius: float = 2.2
    unsharp_percent: int = 80
    unsharp_threshold: int = 2


# ------------------------- noise utils -------------------------

def _value_noise(w: int, h: int, grid: int, rng: np.random.Generator) -> np.ndarray:
    gw = max(2, int(np.ceil(w / grid)) + 1)
    gh = max(2, int(np.ceil(h / grid)) + 1)
    base = rng.random((gh, gw), dtype=np.float32)

    y = np.linspace(0, gh - 1, h, dtype=np.float32)
    x = np.linspace(0, gw - 1, w, dtype=np.float32)
    yi = np.floor(y).astype(int)
    xi = np.floor(x).astype(int)
    yf = y - yi
    xf = x - xi

    yi1 = np.clip(yi + 1, 0, gh - 1)
    xi1 = np.clip(xi + 1, 0, gw - 1)

    n00 = base[yi[:, None], xi[None, :]]
    n10 = base[yi1[:, None], xi[None, :]]
    n01 = base[yi[:, None], xi1[None, :]]
    n11 = base[yi1[:, None], xi1[None, :]]

    nx0 = n00 * (1 - xf[None, :]) + n01 * xf[None, :]
    nx1 = n10 * (1 - xf[None, :]) + n11 * xf[None, :]
    nxy = nx0 * (1 - yf[:, None]) + nx1 * yf[:, None]

    img = Image.fromarray(np.uint8(np.clip(nxy * 255, 0, 255)), mode="L")
    img = img.filter(ImageFilter.GaussianBlur(radius=max(0.0, grid * 0.08)))
    return np.asarray(img, dtype=np.float32) / 255.0


def _fbm(w: int, h: int, rng: np.random.Generator, scales: Tuple[int, ...], weights: Tuple[float, ...]) -> np.ndarray:
    acc = np.zeros((h, w), dtype=np.float32)
    wsum = 0.0
    for s, a in zip(scales, weights):
        acc += a * _value_noise(w, h, s, rng)
        wsum += a
    return acc / max(1e-6, wsum)


def _smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


# ------------------------- color / texture -------------------------

def _apply_ramp(gray: np.ndarray) -> Image.Image:
    g = np.clip(gray, 0.0, 1.0)
    stops = np.linspace(0.0, 1.0, len(DEFAULT_RAMP), dtype=np.float32)

    r = np.zeros_like(g)
    gg = np.zeros_like(g)
    b = np.zeros_like(g)

    for i in range(len(DEFAULT_RAMP) - 1):
        lo, hi = stops[i], stops[i + 1]
        mask = (g >= lo) & (g <= hi)
        if not np.any(mask):
            continue
        t = (g[mask] - lo) / (hi - lo + 1e-6)
        c0 = np.array(DEFAULT_RAMP[i], dtype=np.float32) / 255.0
        c1 = np.array(DEFAULT_RAMP[i + 1], dtype=np.float32) / 255.0
        c = c0[None, :] * (1 - t[:, None]) + c1[None, :] * t[:, None]
        r[mask], gg[mask], b[mask] = c[:, 0], c[:, 1], c[:, 2]

    rgb = np.stack([r, gg, b], axis=-1)
    return Image.fromarray(np.uint8(np.clip(rgb * 255.0, 0, 255)), mode="RGB")


def _add_splatter(img: Image.Image, rng: np.random.Generator, density: float, strength: float, blur: float) -> Image.Image:
    w, h = img.size
    m = rng.random((h, w), dtype=np.float32)
    dots = (m < density).astype(np.float32)
    amp = rng.random((h, w), dtype=np.float32) * dots
    amp = np.clip(amp * 255.0 * strength, 0, 255).astype(np.uint8)
    layer = Image.fromarray(amp, mode="L").filter(ImageFilter.GaussianBlur(radius=blur))
    layer_rgb = Image.merge("RGB", (layer, layer, layer))
    return ImageChops.screen(img, layer_rgb)


def _multiply_grain(img: Image.Image, rng: np.random.Generator, scale: int, strength: float) -> Image.Image:
    w, h = img.size
    g = _value_noise(w, h, scale, rng)
    # 0.5 körül ingadozzon, és finoman hasson
    g = (g - 0.5) * 2.0  # -1..1
    g = 1.0 + g * strength  # 1 +/- strength
    g = np.clip(g, 0.0, 2.0)

    grain = Image.fromarray(np.uint8(np.clip(g * 255.0, 0, 255)), mode="L")
    grain_rgb = Image.merge("RGB", (grain, grain, grain))
    return ImageChops.multiply(img, grain_rgb)


def _vignette(img: Image.Image, amount: float) -> Image.Image:
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    dx = (xx - cx) / max(1.0, w)
    dy = (yy - cy) / max(1.0, h)
    rr = np.sqrt(dx * dx + dy * dy)
    v = 1.0 - np.clip((rr / np.sqrt(0.5)) * amount, 0.0, 1.0)
    mask = Image.fromarray(np.uint8(np.clip(v, 0.0, 1.0) * 255.0), mode="L")
    return ImageChops.multiply(img, Image.merge("RGB", (mask, mask, mask)))


# ------------------------- public API -------------------------

def make_nebula_background(width_px: int, height_px: int, seed: int, params: NebulaParams = NebulaParams()) -> Image.Image:
    rng = np.random.default_rng(seed)

    # 1) Folytonos fátyol (3 lépték) – ez adja a "ködfátylak" gerincét
    veil = _fbm(
        width_px, height_px, rng,
        scales=(params.large_scale, params.mid_scale, params.fine_scale),
        weights=(1.0, 0.78, 0.55),
    )
    veil = np.clip(veil, 0.0, 1.0)

    # 2) Watercolor blotches – belső ködfoltok, NINCS kemény threshold
    b0 = _value_noise(width_px, height_px, params.blotch_scale, rng)
    b1 = _value_noise(width_px, height_px, params.blotch_detail_scale, rng)
    blotch = 0.75 * b0 + 0.25 * b1
    # középtartományt emeljük, hogy "foltok" legyenek, de ne szigetek
    blotch = _smoothstep(np.clip((blotch - 0.35) / 0.65, 0.0, 1.0))
    blotch_img = Image.fromarray(np.uint8(blotch * 255.0), mode="L").filter(
        ImageFilter.GaussianBlur(radius=params.blotch_blur)
    )
    blotch = np.asarray(blotch_img, dtype=np.float32) / 255.0

    # 3) Tejút-sáv – finoman
    yy, xx = np.mgrid[0:height_px, 0:width_px].astype(np.float32)
    ang = rng.uniform(-0.72, -0.25)
    cx = rng.uniform(0.30, 0.70) * width_px
    cy = rng.uniform(0.30, 0.70) * height_px
    d = (xx - cx) * np.cos(ang) + (yy - cy) * np.sin(ang)
    band = np.exp(-(d * d) / (2.0 * (0.24 * max(width_px, height_px)) ** 2))
    band_img = Image.fromarray(np.uint8(np.clip(band * 255.0, 0, 255)), mode="L").filter(
        ImageFilter.GaussianBlur(radius=params.band_blur)
    )
    band = np.asarray(band_img, dtype=np.float32) / 255.0

    # 4) Dark lanes – NAGYLÉPTÉKŰ sötétítés, erős blur, hogy ne legyen leopárd
    lanes = _value_noise(width_px, height_px, params.lane_scale, rng)
    lanes = _smoothstep(np.clip((lanes - 0.20) / 0.80, 0.0, 1.0))
    lanes_img = Image.fromarray(np.uint8(lanes * 255.0), mode="L").filter(
        ImageFilter.GaussianBlur(radius=params.lane_blur)
    )
    lanes = np.asarray(lanes_img, dtype=np.float32) / 255.0

    # 5) Kompozit (fátyol domináns + belső foltok + sáv - lane sötétítés)
    g = (
        veil * 0.92 +
        blotch * params.blotch_strength +
        band * params.band_strength
    )
    g = np.clip(g, 0.0, 1.0)

    # sötét csíkok: finoman kivonjuk (nagyon lágy, nincs pötty)
    g = np.clip(g - lanes * params.lane_strength, 0.0, 1.0)

    # tónus
    g = np.clip((g ** params.fog_gamma) * params.fog_strength, 0.0, 1.0)
    g = np.clip(g * params.base_darkness, 0.0, 1.0)

    # 6) Színezés
    img = _apply_ramp(g)

    # 7) Papír/granuláció (multiplicative) + splatter több méretben (reference feeling!)
    img = _multiply_grain(img, rng, params.grain_scale, params.grain_strength)

    img = _add_splatter(img, rng, params.splatter_small_density, params.splatter_small_strength, blur=0.55)
    img = _add_splatter(img, rng, params.splatter_mid_density,   params.splatter_mid_strength,   blur=1.25)
    img = _add_splatter(img, rng, params.splatter_big_density,   params.splatter_big_strength,   blur=2.4)

    # 8) Vignetta
    img = _vignette(img, params.vignette)

    # 9) Lokális kontraszt (akvarell "élek") + végső blur
    img = img.filter(ImageFilter.UnsharpMask(
        radius=params.unsharp_radius,
        percent=params.unsharp_percent,
        threshold=params.unsharp_threshold,
    ))

    if params.final_blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=params.final_blur))

    return img
