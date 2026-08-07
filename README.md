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

## 1️⃣ Map Layer (Engine Render → Temporary SVG)

- Deterministic seed  
- DPI-aware rendering  
- Full-bleed axes  
- Engine-specific map layer generation  
- Temporary SVG layer used as composition input  

## 2️⃣ Poster Composition (SVG Layout Stage)

- Size-driven poster layout  
- Engine-specific passepartout and typography rules  
- Final composed poster SVG for inspection and frontend consistency  
- Fade / bottom band / decorative subtitle lines handled at layout level  

## 3️⃣ Final Poster Outputs

- The engine first renders a temporary map-only SVG layer.  
- That temporary SVG is then composed into the final poster SVG.  
- Final PNG and PDF are generated from the composed poster stage, never from the raw map layer directly.  
- The temporary map SVG is written to a transient directory and is no longer saved into `output/`.  

### Line Engine Export Note

For Line Engine posters, the browser-rendered final SVG remains the visual source of truth for layout and styling, but PNG/PDF export uses a dedicated stable print path.

Reason:

- In this workspace environment, Cairo runtime libraries may be unavailable.  
- Under those conditions, generic SVG→PDF/PNG conversion backends can shift typography, fade overlays, or nested SVG placement.  

Current solution:

- Final poster SVG is still produced for inspection and frontend consistency.  
- Line Engine PNG/PDF exports are composed through a dedicated ReportLab-based print path that reproduces the same poster layout directly for stable output.  
- PNG is rasterized from that dedicated PDF composition path, so PDF and PNG stay in sync with each other.  
- This avoids intermediate converter regressions while keeping the final SVG available as the canonical visual reference.  

### Line Engine Fade Behavior (Current)

- Fade is applied to the map area only, not to the passepartout.  
- Passepartout remains visually untouched (top, sides, and bottom strip stay solid).  
- Fade geometry and opacity profile are identical across SVG/PDF/PNG outputs.  
- For dark Line Engine minimal palettes (Minimal Night, Blueprint), fade color is black while preserving the same fade geometry and opacity progression.  

### Building Engine Water and Bridge Behavior (Current)

- Building Engine now draws water as a dissolved, seam-free surface to avoid mid-river artifacts caused by overlapping inner geometries.  
- `waterway` overlays are treated as fallback only when no polygonal water surface is available.  
- Non-water polygon layers are masked against the final water geometry to prevent accidental overlays inside river surfaces.  
- Bridge segments are rendered as a dedicated top layer so crossings stay distinguishable from water and building fills.  

Current bridge color rules in Building Engine:

- `architect_sage`: `#bfd4cf`  
- `warm_terracotta`: `#f5e8d6`  
- `sandstone_beige`: road color  
- `luxury_gold`: `#111111`  
- `midnight_blue`: `#183940`  
- `mono_black`: `#e0e0e0`  
- `royal_purple`: `#4b4779`  

### Configurator Placeholder Behavior (Current)

- For Line Engine minimal styles, static placeholder PNG assets are used before the customer selects a custom location.  
- Placeholder selection is palette+size specific (`{palette}_{size}.png`) and sourced from `configurator/frontend/public/city-placeholders/`.  
- Placeholder PNG is rendered as a full poster asset (no additional frontend passepartout/fade/text overlay is applied on top).  
- After the customer selects a custom location, configurator preview switches from placeholder mode to the live map module and no longer renders placeholder PNG.  

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

# Star Map (Rebuilt)

The star map backend is rebuilt around Skyfield and supports parameterized rendering by:

- place (name or latitude/longitude)
- local date and time
- limiting magnitude and field of view

Batch render entrypoint:

```bash
python batch_render_stars.py
```

The script currently demonstrates these parameters:

- location_query: place-name geocoding
- when_local: local datetime input
- lat/lon: explicit coordinate override
- limiting_magnitude
- field_of_view_degrees
- max_star_size

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

## Issue: Location Selection Updates Text, but Map Does Not Recenter (2026-06-19)

### Problem Description

In the frontend configurator, selecting a new place from autocomplete updated
the location label and coordinates, but the live Leaflet preview sometimes only
zoomed out/in and did not reliably move to the new city center.

### Root Cause

The map sync bridge created a feedback loop between:

1. Programmatic map movement (`flyToBounds` + explicit `setZoom`).
2. Continuous `move`/`zoomend` center writes back into app state.
3. A new state-driven move command arriving while the previous animation was
    still in-flight.

This made center updates nondeterministic and occasionally kept the viewport
 near the old location.

### Solution Implemented

**File:** `configurator/frontend/src/components/preview/CityLiveMapPreview.tsx`

1. Switched controlled camera updates to explicit center+zoom operations:
    - initial sync: `map.setView(center, zoom, { animate: false })`
    - subsequent sync: `map.flyTo(center, zoom, ...)`
2. Removed high-frequency center propagation during animation:
    - dropped `move` throttled emitter
    - dropped `zoomend` emitter
    - kept only `moveend` center propagation
3. Kept sync lock (`syncLockUntilRef`) so programmatic camera changes are not
    immediately mirrored back into state.

### Why This Works

- One source of truth for camera target (`center`, `zoom`) avoids bounds/zoom
  drift combinations.
- State is updated only after movement settles (`moveend`), preventing
  mid-animation rewrites.
- The two-way sync becomes deterministic instead of oscillating.

### Verification Checklist

1. Open the configurator and expand **Helyszín**.
2. Select three far-apart cities in sequence (example: Budapest → London → New York).
3. Confirm after each selection:
    - location text updates,
    - latitude/longitude fields update,
    - the live map center visibly moves to the selected city (not only zoom changes).

### Frontend Guardrails (Do Not Regress)

- Prefer `setView`/`flyTo` for controlled center transitions.
- Avoid emitting state updates on every `move` event for controlled maps.
- Do not combine `flyToBounds` with a separate `setZoom` in the same sync step.
- Keep anti-feedback lock windows around programmatic camera transitions.

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

## Issue: Opposite Bank / Open Sea Rendered as Land Blocks (v10 Multi-Landmass Fix)

### Problem Description

In coastal cities whose frame contains **more than one landmass** — a strait or
river splitting the city (Istanbul / Bosphorus, New York / Hudson) or an
archipelago (Helsinki, Stockholm) — large water areas were rendered as
parcel-colored **land blocks** with roads drawn on top, instead of solid water.

Visual symptom: the opposite bank of a strait, or a big open bay/gulf, appears
as one giant orange/yellow block instead of teal water.

### Root Cause

The coastline step polygonizes the OSM `natural=coastline` lines together with
the frame boundary, producing several closed regions. The original logic kept
**only the region containing the map center** as land and flooded everything
else as sea:

```python
if p.contains(center_p):
    land_poly = p
    sea_poly = clip_rect.difference(land_poly)   # everything else = sea
    break
```

This is wrong in **both** directions when there are multiple landmasses:
- a genuine second landmass (Istanbul's Asian side) is **not** connected to the
  center, so it got flooded as sea — water with streets on top;
- conversely, when later tweaked, an entire open gulf could be kept as land.

### Solution Implemented

**File:** `generator/engines/render_block.py` (COASTLINE block)

Each coastline-bounded region is now classified **individually** as land or sea
by **road-length density** (metres of road per m² of region):

```python
roads_union = unary_union(list(edges_p.geometry.values)) if len(edges_p) > 0 else None

sea_regions = []
for p in polys:
    if p.contains(center_p):
        continue  # region with the map center is always land

    density = 0.0
    if roads_union is not None and p.area > 0:
        road_inside = p.intersection(roads_union)
        if not road_inside.is_empty:
            density = road_inside.length / p.area

    if density < 1e-2:          # below threshold -> open water
        sea_regions.append(p)

if sea_regions:
    sea_poly = unary_union(sea_regions)
```

**Why it works (measured densities, 3000 m extent):**
- Dense built-up land: ~3e-2 … 9e-2 m/m²
- Map-center mainland: ~6e-2 m/m²
- Open sea / gulf (only piers, breakwaters, shore footpaths): ~2.5e-3 m/m² or lower

The `1e-2` threshold sits in the wide gap between sea and land. Islands occupy
their **own** coastline regions (the sea face has a hole where each island sits),
so flagging a sea region never turns an island into water. The existing
island-override still runs afterwards as a final safety net.

### Critical "Do NOT" Notes (avoid re-introducing past bugs)

- **Do NOT** revert to `sea_poly = clip_rect.difference(land_poly)` — that is the
  original multi-landmass bug.
- **Do NOT** buffer the whole road network (e.g. `roads_union.buffer(120)`) and
  intersect it per region — it is far too slow and **froze the render for >20 min**.
- **Do NOT** lower the threshold to `2e-3` — Helsinki's open gulf measures
  ~2.46e-3 and leaks through as land.
- Ferries / vessel routes are **not** a factor: `network_type="all"` only pulls
  `highway=*` ways (0 ferry edges). Don't chase ferry routes.

### Cache Invalidation

Cache prefix bumped to `block_v10_density`. Older cached geometry
(`block_v6_water`, etc.) holds the **old misclassification** — re-render affected
cities with `--no-cache`, or clear `cache/`, or run the batch **without**
`--skip-existing` to rebuild.

### How to Verify

```bash
# Strait-split city (Asian side must be land, Bosphorus + Marmara must be water):
python main.py --size-key 50x50 --extent-m 3000 \
  --center-lat 41.0082 --center-lon 28.9784 \
  --palette urban_modern --title "ISTANBUL" --output-dir output --no-cache

# Archipelago (gulf must be water, every island must stay parcel-colored):
python main.py --size-key 50x50 --extent-m 3000 \
  --center-lat 60.1699 --center-lon 24.9384 \
  --palette urban_modern --title "HELSINKI" --output-dir output --no-cache
```

### 🔁 If This Problem Recurs — What to Prompt

If a coastal city again shows water rendered as land blocks (or land rendered as
water), paste this to the assistant:

> In `generator/engines/render_block.py`, the per-region land/sea classification
> in the COASTLINE block is misclassifying regions for `<CITY>` (lat `<LAT>`,
> lon `<LON>`, extent `<EXTENT_m>`). Water is showing as land blocks (or land as
> water). Add a temporary diagnostic that prints, for each polygonized coastline
> region, its `area`, road-length `density` (`region ∩ roads_union`.length /
> region.area), and whether it contains the center — then adjust the `1e-2`
> density threshold so the offending region lands on the correct side of the gap,
> **without** buffering the whole road network and **without** reverting to
> `clip_rect.difference(land_poly)`. Bump the `block_v##_density` cache prefix and
> re-render with `--no-cache`.

This reproduces the exact debugging path used for the v10 fix.

---

## Issue: River Rendered as Oversized Blob in Local Exact-Water Mode (v11 Porto Fix)

### Problem Description

In Porto (and potentially other river cities), local XML + exact-water enrichment
produced a blue river, but its geometry could still look too wide or "inflated"
when `waterway` line fallback polygons were merged on top of already-available
water surface polygons.

Visual symptom: the river appears as a large, coarse, uniform-width polygon
instead of following the real riverbanks.

### Root Cause

The block engine had two water sources:

1. polygonal water surfaces (`water_raw`)
2. buffered `waterway` lines (`waterway_raw`)

Even in local exact-water mode (where real water polygons are already enriched),
the line-buffer fallback could still be added. This re-introduced synthetic
width artifacts.

### Solution Implemented

**File:** `generator/engines/render_block.py`

`waterway` buffering is now strict fallback logic:

- if `OSM_LOCAL_EXACT_WATER` is enabled **and** polygonal water exists,
  do **not** add buffered `waterway` geometry;
- use buffered `waterway` only when polygonal water is missing.

Implemented decision:

```python
exact_water_mode = os.getenv("OSM_LOCAL_EXACT_WATER", "").strip().lower() in {"1", "true", "yes", "on"}
use_waterway_fallback = (not exact_water_mode) or len(water_p) == 0
```

This preserves full blue water coverage while avoiding over-inflated river shapes.

### Reusable Rule (Use This Next Time)

When debugging water geometry regressions:

1. If exact polygonal water is present, treat line-based `waterway` buffers as
    fallback only.
2. Never merge constant-width river buffers onto already-correct polygonal water.
3. Keep fallback enabled only for data-gaps (no polygon water available).

### Quick Verification

1. Render with local source + exact water enabled.
2. Confirm river stays blue across full surface.
3. Confirm riverbanks are not replaced by uniform-width, coarse polygons.

---
## Issue: Building Engine — Islands Missing, Water Not Uniform Near Coastlines (2026-08-07)

### Problem Description

When rendering Stockholm (or any coastal city near an OSM UTM zone boundary) with the **Building engine**, the following defects appeared:

1. **Islands in water bodies were not rendered** — Skeppsholmen, Långholmen, Riddarholmen and others appeared as solid blue water instead of distinct land areas.
2. **Large open water (fjords, straits) stayed beige** — the Saltsjön east of Gamla Stan had no blue fill despite being clearly open water.
3. These issues did not affect the **Line engine**, which rendered Stockholm correctly.

### Root Cause — Three Separate Bugs

#### Bug 1: `_fill_polygon_holes` erased island holes

The function used to fill small interior rings (data noise) was implemented as:

```python
def _fill_polygon_holes(geom):
    if isinstance(geom, Polygon):
        return Polygon(geom.exterior)   # strips ALL interior rings
```

In OSM, large water bodies (e.g. Riddarfjärden, Mälaren) encode islands as interior rings (holes) in the water polygon. Stripping all interiors made islands invisible — the water polygon became a solid fill that covered the island positions.

**Fix:** Threshold-based hole filling — keep rings larger than 10,000 m² (real islands), discard only tiny rings (data artefacts):

```python
def _fill_polygon_holes(geom, min_hole_area_m2: float = 10_000):
    if isinstance(geom, Polygon):
        kept = [r for r in geom.interiors if Polygon(r).area >= min_hole_area_m2]
        return Polygon(geom.exterior, kept)
```

#### Bug 2: Saltsjön / open-sea fjords missing from `water_raw`

The `water_raw` OSM bundle uses `natural=water|bay|strait` and `water=*` tags. Many Stockholm fjords (Saltsjön, Lilla Värtan) are tagged as `natural=coastline` lines in OSM, not as closed water polygons, so they never appear in `water_raw`.

The Building engine previously called `polygonize(coast_lines)` on the raw coastline geometry. This only produced polygons where coastline segments were already closed — generating 1 tiny polygon (60,000 m²) instead of the full fjord.

**Fix:** Add the clip-rectangle boundary to the merge before `polygonize`, then use road-density filtering to distinguish sea from land (same technique as `render_line.py` vintage_atlas mode):

```python
merged = unary_union(list(coast_lines.geometry.values) + [clip_rect_local.boundary])
water_polygons = [p for p in polygonize(merged) if not p.is_empty]

for poly in water_polygons:
    if poly.contains(center_in_ref):
        continue   # centre point is on land, skip
    density = road_length_inside / poly.area
    if density < 1e-2:               # open water has no roads
        sea_regions.append(poly)
```

#### Bug 3: UTM zone mismatch silently clipped all buildings to zero

`ox.projection.project_gdf()` selects UTM zone independently per dataset based on centroid. At the 18 °E boundary between Zone 33 and Zone 34 (exactly where Stockholm sits), `edges_raw` was projected to EPSG:32634 (Zone 34) and `gdf_all_raw` (buildings) to EPSG:32633 (Zone 33). `gpd.clip()` found zero overlapping features — all buildings vanished silently.

**Fix:** Project all layers to the same reference CRS derived from `edges_p`:

```python
ref_crs = edges_p.crs          # single authoritative zone
gdf_all_p = gdf_all_raw.to_crs(ref_crs)   # not project_gdf()
```

#### Bug 4: Buildings/greens on islands erased by the water mask (2026-08-07 follow-up)

After fixing Bug 2, the sea/fjord outline drew correctly and `islands_p` was overlaid on top with the background color — visually the island looked fine. But buildings and green areas **on the island itself** still failed to render, in styles where they had rendered fine before (e.g. Line engine, `urban_modern`, `midnight_ember`).

**Root cause:** every land layer (`buildings_p`, `greens_p`, `parking_p`, `industrial_p`, etc.) is passed through `_mask_out_water(gdf, water_mask_geom)`, which calls `geom.difference(water_mask_geom)`. `water_mask_geom` includes `coast_union = unary_union(coast_water.geometry)` — the synthetic sea polygon from Bug 2's fix. That polygon is classified purely by **road density** (`density < 1e-2` ⇒ "sea"). A low-traffic island with only footpaths/pedestrian ways (e.g. a park island) can fall under the threshold and get folded entirely into the "sea" polygon as if it had no land at all. `islands_p` was only ever drawn as a *visual* patch on top (zorder), it was never subtracted from the actual mask geometry — so every building on that island was differenced away before it ever reached the plot call.

**Fix:** explicitly punch the known OSM islands (`islands_raw`, i.e. `place=island|islet` / `natural=island`) out of `coast_water` as real holes, the same way `render_line.py` already does for `water_p`. This does not depend on road density and therefore also protects islands with sparse or no road network:

```python
if coast_water is not None and len(coast_water) > 0 and len(islands_p) > 0:
    island_union = unary_union(islands_p.geometry)
    coast_water["geometry"] = coast_water.geometry.apply(
        lambda g: g.difference(island_union) if g is not None else g
    )
```

Because `water_mask_geom` is derived from `coast_water` after this fix, every downstream `_mask_out_water(...)` call automatically stops erasing content on tagged islands — no per-layer changes needed.

### Files Changed

| File | Change |
|------|--------|
| `generator/engines/render_building.py` | `_fill_polygon_holes` threshold; coastline sea polygon via `clip_rect.boundary`; islands punched out of `coast_water` as real holes; all `.to_crs(ref_crs)` projections |
| `generator/core/render_dispatcher.py` | `EngineType.BLOCK` branch called `render_map_line` instead of `render_map_block` |

### Reusable Rules

- **Never strip all interior rings** from water polygons — each ring is a potential island.  
- **Coastline polygonize without the clip boundary produces incomplete results** for any viewport that cuts through a coastline (i.e. coastal cities). Always merge `clip_rect_local.boundary` into the line set before `polygonize`.  
- **Road density alone is not a reliable land/sea classifier.** Low-traffic islands (parks, pedestrian-only islets, military/historic islands) can score below the "sea" threshold. Any synthetic water polygon derived from heuristics (not from explicit OSM water tags) must have known islands (`islands_raw`) subtracted as real geometric holes — not just painted over visually — before it is used as a mask for other layers.  
- **A visual overlay is not a mask fix.** Drawing `islands_p` on top with `zorder` makes an island *look* right while the underlying `water_mask_geom` can still erase buildings/greens on it via `_mask_out_water`. Always fix the geometry that masks are derived from, not just what gets painted last.  
- **Road-density threshold ~0.01** reliably separates open sea from built-up islands.  
- **UTM zone mismatch** is silent — `gpd.clip()` returns an empty GeoDataFrame rather than raising. Always force `to_crs(ref_crs)` when combining datasets from independent `project_gdf()` calls.

### Verification

1. Run `batch_render_manual.py` for a coastal city (Stockholm).
2. Confirm open fjords (Saltsjön, Riddarfjärden, Mälaren) are rendered blue.
3. Confirm Skeppsholmen, Långholmen, Riddarholmen appear as distinct land areas inside the water.
4. Confirm buildings are present on the main islands (Stadsholmen / Gamla Stan).

---

## Issue: `OSM_SOURCE=local` Was Never Actually Read — All Data Still Came From Overpass (2026-08-07)

### Problem Description

`manual_render_common.py` sets `OSM_SOURCE=local` and `OSM_LOCAL_FILE=<path>` when a local `.osm` file is configured, and the CLI even prints `OSM src : local`. Despite this, styles that needed a brand-new cache variant (e.g. `vintage_atlas` — its layout margins produce a different `hw/hh` viewport than the other styles) failed with Overpass proxy errors:

```
[OSM] features_from_point:feature_tags failed via https://overpass-api.de/api: ...
ProxyError: ('Unable to connect to proxy', OSError('Tunnel connection failed: 503 Service Unavailable'))
```

### Root Cause

`generator/core/osm_bundle_cache.py` never read `OSM_SOURCE` / `OSM_LOCAL_FILE` at all. `_build_shared_osm_bundle()` unconditionally called `ox.graph_from_point(...)` and `ox.features_from_point(...)` (live Overpass queries) for every layer. The local `.osm` file was only ever used by `manual_render_common.py` to compute the **auto-fit center/extent** (via `_read_osm_bounds`) — the actual road/building/water geometry was always fetched live from Overpass, regardless of "local" mode. This worked as long as a cache pickle already existed for the exact viewport size, masking the bug — it only surfaced as a hard failure when a new viewport size needed a fresh fetch and Overpass/the proxy was unavailable.

### Solution Implemented

**File:** `generator/core/osm_bundle_cache.py`

1. Added `_local_osm_file_path()` — returns the configured path when `OSM_SOURCE=local` and `OSM_LOCAL_FILE` point to an existing file, else `None`.
2. Added `_fetch_features(tags, label, *, local_file, ...)` — calls `ox.features_from_xml(local_file, tags=tags)` when in local mode, otherwise falls back to the existing `_run_with_overpass_fallback(ox.features_from_point, ...)` path. Every feature layer (`gdf_all_raw`, `trees_raw`, `waterway_raw`, `railway_raw`, `paths_raw`, `water_raw`, `green_raw`, `coast_raw`, `islands_raw`) now goes through this single helper.
3. Road graph: `ox.graph_from_xml(local_file, simplify=True)` replaces `ox.graph_from_point(...)` in local mode. `graph_from_xml` has no `custom_filter` argument, so edges are post-filtered by the same allowed `highway` set as `_ROAD_CUSTOM_FILTER` (`_highway_tag_matches`).
4. Cache key now includes a `_local` suffix when local mode is active, so local-file and Overpass-derived bundles for the same coordinates never collide in `cache/`.
5. Logs `[OSM] Local mode: reading <file> (no Overpass calls)` so it's obvious at runtime which path was taken.

```python
def _fetch_features(tags, query_label, *, local_file, center_lat, center_lon, dist_m):
    if local_file is not None:
        return ox.features_from_xml(local_file, tags=tags)
    return _run_with_overpass_fallback(
        lambda: ox.features_from_point((center_lat, center_lon), tags=tags, dist=dist_m),
        query_label,
    )
```

### Reusable Rules

- **Setting an env var is not the same as reading it.** Grep the actual consumer (`os.getenv(...)`) before assuming a "local/offline mode" flag has any effect — it may only be read by an unrelated helper (here: auto-fit bounds calculation).
- When adding a genuine local-file code path, mirror **every** query call site (graph + every feature tag set), not just one — partial coverage silently falls back to network calls for the rest.
- `graph_from_xml`/`features_from_xml` skip the Overpass network entirely but also skip the `dist`/`custom_filter` server-side filtering — replicate any `custom_filter` as a client-side post-filter, and rely on downstream `clip_rect_local` clipping to bound the area.
- Give local-mode and network-mode cache entries **different cache keys** — their feature sets can differ slightly (server-side filter vs whole-file parse), so they must never be reused interchangeably.

### Verification

1. Set `OSM_SOURCE=local` + `OSM_LOCAL_FILE=<path to .osm>` and delete any cache for a fresh viewport size (e.g. `vintage_atlas`).
2. Run `batch_render_manual.py` (or call `render_style` directly) — confirm the log prints `[OSM] Local mode: reading <file> (no Overpass calls)` and no `ProxyError`/`overpass-api.de` lines appear.
3. Confirm all styles complete with `OK`, even with no network/proxy access.

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
