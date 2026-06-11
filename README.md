# 🗺️ City Map Generator

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![React](https://img.shields.io/badge/React-Frontend-61DAFB)
![OSMnx](https://img.shields.io/badge/OSMnx-2.x-green)
![Matplotlib](https://img.shields.io/badge/Matplotlib-Render-orange)
![ReportLab](https://img.shields.io/badge/ReportLab-PDF-red)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

The **City Map Generator** is a deterministic, print-grade city map rendering system built on top of OpenStreetMap (OSM) data.

The goal of the project is to create a scalable, webshop-ready map production pipeline that:

- 🖨️ Generates print-ready PDF files  
- 🌐 Provides live web preview via API  
- 🧠 Uses deterministic seed-based rendering  
- 🏗️ Strictly separates rendering and layout layers  
- 🛒 Is optimized for e-commerce integration  

---

# 🏗️ Architecture

```
React Frontend
        ↓
   FastAPI Backend
        ↓
     OSMnx
        ↓
 Matplotlib Render
        ↓
 ReportLab Layout
        ↓
   Print-ready PDF
```

The system operates in two separate repositories:

- `city_map_generator` – Python backend
- `city-map-frontend` – React configurator UI

---

# 🎯 Core Philosophy

```
cm → aspect ratio → render → layout → production
```

- Centimeter-based size logic  
- Deterministic visual output  
- Full separation of map and layout  
- Print-grade PDF export  
- Scalable webshop production pipeline  

---

# ✨ Key Features

## 🧱 Polygonize-Based City Block Generation

- OSMnx 2.x compatible pipeline  
- `graph_from_point` retrieval  
- `polygonize`-based block generation  
- Bounding-box clipping  
- Seed-based deterministic block coloring  

---

## 🛣️ Hierarchical Road Rendering

Road classes:

- Highway  
- Arterial  
- Local  
- Minor  

Line width calculation:

1. `base_width`  
2. `multipliers[class]`  
3. Extent-based scaling  

This ensures visual consistency across all product sizes.

---

## 🌊 Water Handling

- `natural=water` retrieval from OSM  
- Clipping in projected CRS  
- Subtraction from city blocks (`difference`)  
- Palette-specific water color  

---

## 🚫 Exclusion of Non-Vehicular OSM Elements

By default, the following are not rendered:

- `footway`  
- `cycleway`  
- `path`  
- `pedestrian`  
- `steps`  
- `bridleway`  

This eliminates OSM noise and unwanted parallel “hairline” artifacts.

---

# 🎨 Style System

Central configuration:

```python
from generator.styles import get_palette_config

palette = get_palette_config("urban_modern")
```

Available palettes (examples):

- `urban_modern`
- `vintage_atlas`
- `black_minimal`

Configurable parameters:

- background color  
- block colors  
- water color  
- road color  
- road style (base width + multipliers)  

Fully version-controlled and deterministic.

---

# 🌐 FastAPI Preview API

## Endpoint

```
POST /preview
```

## Example Payload

```json
{
  "lat": 48.1351,
  "lon": 11.5820,
  "size_key": "30x40",
  "extent_m": 2000,
  "palette": "urban_modern"
}
```

## Response

```
image/png
```

Enables:

- Live React preview  
- Size switching  
- Palette switching  
- Dynamic map extent adjustment  

---

# 🖨️ Two-Step Rendering Architecture

## 1️⃣ Map Layer (Matplotlib → PNG/SVG)

- Deterministic seed  
- DPI-aware rendering  
- Full-bleed axes  
- Optional SVG export  

## 2️⃣ Print Composition (ReportLab → PDF)

- Fixed centimeter-based margins  
- 1 cm side + top margin  
- 4 cm bottom strip  
- Right-aligned title  
- Subtitle tracking  
- Logo support  
- Timestamped filename  
- Size identifier in filename  

---

# 📐 Size Logic

All product sizes follow:

```
cm → aspect ratio → extent_m → DPI → exact print PDF
```

Example output:

```
citymap_50x70_2026-02-16_21-45-12.pdf
```

---

# 🧭 CLI Usage

## Basic Run

```bash
python main.py \
  --center-lat 47.4979 \
  --center-lon 19.0402 \
  --size-key 50x70 \
  --extent-m 3000 \
  --palette urban_modern \
  --output-dir output/
```

---

# 📦 Project Structure (Backend)

```
city_map_generator/
│
├── api.py
├── service.py
├── main.py
├── requirements.txt
│
├── generator/
│   ├── render.py
│   ├── layout_composer.py
│   ├── specs.py
│   ├── styles.py
│   ├── relief.py
│   └── presets_loader.py
│
├── Fonts/
├── Logo/
└── output/
```

---

# � Known Issues & Resolutions

## Issue: Islands Inside Harbors Not Parcelized (v6 Water Fix)

### Problem Description

In map rendering with large extent (e.g., 2000m) near coastlines with harbors/archipelagos (e.g., Stockholm), island land masses were incorrectly classified as water, resulting in teal-colored (water) filling instead of parcel-colored (land) blocks.

**Root Cause Chain:**
1. OSM water polygons (natural=water, water=*, bay, etc.) often cover large harbor areas as single polygons without explicit island holes.
2. When water polygons are clipped to the render extent, islands may be fully contained inside the water geometry.
3. Water-to-cell classification used a buffered overlap heuristic that would mark cells as water even when they had zero real overlap with unbuffered water (false positives).
4. Explicit island OSM features (`place=island`, `place=islet`, `natural=island`) existed but were not used to override water classification.

### Solution Implemented

**File:** `generator/engines/render_block.py`

#### Step 1: Explicit Island Polygon Subtraction (Lines ~210–240)

```python
# ISLAND OVERRIDE
# Remove explicit island polygons from water surfaces so they are
# always rendered as land parcels.
try:
    islands = ox.features_from_polygon(
        clip_wgs,
        tags={
            "place": ["island", "islet"],
            "natural": "island",
        },
    )
except Exception:
    islands = None

if islands is not None and len(islands) > 0 and len(water_p) > 0:
    islands = islands[islands.geometry.notnull()]
    islands_p = islands.to_crs(edges_p.crs)
    islands_p = islands_p[
        islands_p.geom_type.isin(["Polygon", "MultiPolygon"])
    ]

    if len(islands_p) > 0:
        islands_p = gpd.clip(
            islands_p,
            gpd.GeoSeries([clip_rect], crs=edges_p.crs)
        )

    if len(islands_p) > 0:
        island_union = unary_union(islands_p.geometry)
        water_p = water_p.copy()
        water_p["geometry"] = water_p.geometry.apply(
            lambda geom: geom.difference(island_union)
        )
        water_p = water_p[
            water_p.geometry.notnull() & (~water_p.geometry.is_empty)
        ]
        water_p = water_p[
            water_p.geom_type.isin(["Polygon", "MultiPolygon"])
        ]
```

**What it does:**
- Queries OSM for explicit island/islet features within the render extent.
- Converts them to the same projection as the render bounds.
- Uses Shapely's `difference()` operation to subtract island geometry from all water polygons.
- Removes resulting empty/null geometries to keep water data clean.

#### Step 2: Gated Water-Cell Classification (Lines ~265–285)

```python
if len(large_water) > 0:
    water_union = unary_union(large_water.geometry)
    # Small expansion helps fragmented shore segments, but only when
    # there is already true (unbuffered) water overlap.
    water_mask = water_union.buffer(5)

    def is_water_cell(poly):
        raw_inter = poly.intersection(water_union)
        if raw_inter.is_empty:
            # Never classify as water from buffered overlap only.
            return False

        poly_area = poly.area
        if poly_area <= 0:
            return False

        raw_ratio = raw_inter.area / poly_area
        if raw_ratio > 0.5:
            return True

        buffered_inter = poly.intersection(water_mask)
        if buffered_inter.is_empty:
            return False

        buffered_ratio = buffered_inter.area / poly_area
        return raw_ratio > 0.03 and buffered_ratio > 0.2

    cells["is_water"] = cells.geometry.apply(is_water_cell)
```

**Classification Logic:**
- **Gate 1:** Cell must have **non-zero overlap with unbuffered water**. If `raw_inter` is empty, return False (land).
- **Gate 2:** If raw overlap > 50%, cell is definitely water.
- **Gate 3:** If raw overlap is low (0.03–0.5), allow buffered overlap **only if** both `raw_ratio > 0.03` AND `buffered_ratio > 0.2`.
- **Result:** Prevents false-positive water classification; islands with zero raw overlap stay land.

#### Step 3: Island-Specific Post-Classification Override (Lines ~287–299)

```python
if island_union is not None:
    def is_island_cell(poly):
        inter = poly.intersection(island_union)
        if inter.is_empty or poly.area <= 0:
            return False
        return (inter.area / poly.area) > 0.15

    island_cells = cells.geometry.apply(is_island_cell)
    cells.loc[island_cells, "is_water"] = False
```

**What it does:**
- After all water classification, explicitly re-mark any cell with >15% island polygon overlap as **land**.
- Guarantees islands stay parcel-colored, even if coastal cells were previously marked water.
- Acts as a final deterministic override layer.

#### Step 4: Cache Invalidation

- Updated cache prefix from `block_v5_water` → `block_v6_water` to force fresh geometry rebuild.
- Old cached (incorrect) geometries are not reused.

### Narrowed OSM Water Source (Lines ~123–138)

To avoid over-aggressive water detection:

**Before:**
```python
tags={
    "natural": ["water", "bay", "strait"],
    "water": True,
    "waterway": ["riverbank", "dock", "canal"],
    "landuse": ["basin", "reservoir"],
    "seamark:type": ["harbour", "anchorage"],
}
```

**After:**
```python
tags={
    "natural": ["water", "bay", "strait"],
    "water": True,
    "waterway": ["riverbank", "canal"],
    "landuse": ["basin", "reservoir"],
}
```

**Removed:**
- `waterway=dock` (can span islands)
- `seamark:type=harbour/anchorage` (harbor area polygons often cover islands)

### New CLI Flag: `--no-cache`

**Files:** `main.py`, `generator/core/render_dispatcher.py`, `generator/engines/render_block.py`

Added explicit cache bypass:

```bash
python main.py \
  --size-key 50x50 \
  --extent-m 2000 \
  --center-lat 59.3293 \
  --center-lon 18.0686 \
  --palette urban_modern \
  --title "STOCKHOLM" \
  --output-dir output \
  --no-cache
```

- `--no-cache` forces fresh OSM data fetch and geometry rebuild.
- Useful for testing changes or avoiding stale cached data.
- Falls back to caching by default (no flag = use cache).

### Verification Checklist

**Test City:** Stockholm (59.3293° N, 18.0686° E), 50×50 cm, urban_modern palette, 2000m extent.

**Expected Behavior:**
1. ✅ Major islands (Södermalm, Kungsholmen, Djurgården, etc.) appear with parcel colors (orange, yellow, gray, black).
2. ✅ Water (harbors, Mälaren lake, bays) remains teal/water color.
3. ✅ No large land area is rendered as solid water.
4. ✅ Road network visible on all islands.

**How to Verify:**

```bash
# With fresh geometry (no cache):
python main.py --size-key 50x50 --extent-m 2000 \
  --center-lat 59.3293 --center-lon 18.0686 \
  --palette urban_modern --title "STOCKHOLM" \
  --output-dir output --no-cache

# Check output PDF:
# Islands should be parcel-colored (orange/yellow/gray/black blocks).
# Surrounding harbor should be teal.
# Visual comparison: [output/urban_modern_50x50_YYYY-MM-DD_HH-MM-SS.pdf]
```

**Numerical Verification (Python):**

```python
import pickle
from pathlib import Path

cache = Path("cache/block_v6_water_59.329300_18.068600_2000.pkl")
with open(cache, 'rb') as f:
    data = pickle.load(f)

cells = data['cells']
print(f"Total cells: {len(cells)}")
print(f"Water cells: {int(cells['is_water'].sum())}")
print(f"Land cells: {int((~cells['is_water']).sum())}")

# For each named island, check water ratio:
# Södermalm should have water_ratio < 0.05 (>95% land)
# Kungsholmen should have water_ratio < 0.05
# etc.
```

### Regression Testing

**Cities to re-render:**
- Amsterdam (52.3676° N, 4.9041° E) – No islands; water must stay correct.
- Bergen (60.3913° N, 5.3221° E) – Many small islands; all must be parcel-colored.
- Munich (default: 48.1365° N, 11.5768° E) – Inland; should be unchanged.

**Acceptance Criteria:**
- All three render without errors.
- Water/land color separation is visually correct.
- No regressions in road rendering or layout.

---

# �🚀 Roadmap

## 1. SVG / DXF Export

- Laser cutting  
- Engraving  
- CNC workflow support  

## 2. Full Webshop Integration

Frontend:

- Location selection  
- Live preview  
- Size and palette selection  

Backend:

- Automated PDF generation  
- Manufacturing file export  
- Private production endpoint  

## 3. Coastline-Aware Framing

- Snap-to-land logic  
- Intelligent center correction  
- Composition optimization  

## 4. Size-Dependent Typography

- Dynamic font scaling  
- Small-format optimization  
- Print visual balance refinement  

---

# 🔒 Project Status

- Stable render pipeline  
- Working preview API  
- Frontend integration completed  
- Full separation of render and layout  
- Deterministic output ensured  

---

# 👤 Author

**Norbert von Polyák**

---

# 🧠 Vision

This project is not just a map renderer.

It is a deterministic, scalable, print-grade, webshop-integrated map production system designed with architectural clarity and real-world manufacturing in mind.
