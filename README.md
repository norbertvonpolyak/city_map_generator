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

# 🚀 Roadmap

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
