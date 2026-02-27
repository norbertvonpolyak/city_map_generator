# 🗺️ City Map Generator

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![React](https://img.shields.io/badge/React-Frontend-61DAFB)
![OSMnx](https://img.shields.io/badge/OSMnx-2.x-green)
![Matplotlib](https://img.shields.io/badge/Matplotlib-Render-orange)
![ReportLab](https://img.shields.io/badge/ReportLab-PDF-red)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

A **City Map Generator** egy Python-alapú, OpenStreetMap (OSM) adatokra épülő, nyomdai minőségű várostérkép-renderelő rendszer.

A projekt célja egy determinisztikus, minimalista és termékorientált térképgenerátor, amely:

- 🖨️ Print-ready PDF fájlokat generál
- 🌐 Élő webes preview-t biztosít
- 🧠 Determinisztikus seed-alapú renderelést használ
- 🏗️ Teljesen szétválasztja a render és layout réteget
- 🛒 Webshop-integrációra optimalizált architektúrát követ

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

A projekt két külön repository-ban működik:

- `city_map_generator` – Python backend
- `city-map-frontend` – React konfigurátor

---

# 🎯 Core Philosophy

```
cm → arány → render → layout → gyártás
```

- Centiméter-alapú méretlogika
- Determinisztikus vizuális output
- Layout és térkép teljes függetlensége
- Print-grade PDF export
- Skálázható webshop pipeline

---

# ✨ Fő jellemzők

## 🧱 Polygonize-alapú várostömb generálás

- OSMnx 2.x kompatibilis pipeline
- `graph_from_point`
- `polygonize` alapú tömbképzés
- Bounding box alapú clipping
- Seed-alapú determinisztikus blokkszínezés

---

## 🛣️ Hierarchikus úthálózat renderelés

Úthierarchia:

- Highway
- Arterial
- Local
- Minor

Vastagság képlete:

1. `base_width`
2. `multipliers[class]`
3. Extent-alapú skálázás

Ez biztosítja a vizuális konzisztenciát minden méretben.

---

## 🌊 Vízkezelés

- `natural=water` OSM lekérés
- Projektált CRS-ben clipping
- Blokkokból kivonás (`difference`)
- Palette-specifikus vízszín

---

## 🚫 Nem kívánt OSM elemek kizárása

Alapértelmezetten nem kerülnek renderelésre:

- `footway`
- `cycleway`
- `path`
- `pedestrian`
- `steps`
- `bridleway`

Ez megszünteti az OSM zajt és párhuzamos vonalakat.

---

# 🎨 Stílusrendszer

Központi konfiguráció:

```python
from generator.styles import get_palette_config

palette = get_palette_config("urban_modern")
```

Elérhető paletták például:

- `urban_modern`
- `vintage_atlas`
- `black_minimal`

Konfigurálható:

- háttérszín
- blokkszínek
- vízszín
- útszín
- road_style (base_width + multipliers)

Teljesen verziózható és determinisztikus.

---

# 🌐 FastAPI Preview API

## Endpoint

```
POST /preview
```

## Payload példa

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

Lehetővé teszi:

- Élő React preview
- Méretváltás
- Palettaváltás
- Dinamikus térképkiterjedés

---

# 🖨️ Two-Step Rendering Architecture

## 1️⃣ Map Layer (Matplotlib → PNG)

- Determinisztikus seed
- DPI-aware render
- Full-bleed axes
- Optional SVG export

## 2️⃣ Print Composition (ReportLab → PDF)

- Fix cm-alapú keret
- 1cm oldalsó + felső margin
- 4cm alsó strip
- Jobbra zárt cím
- Subtitle tracking
- Logó támogatás
- Timestampelt fájlnév
- Méretazonosító a fájlnévben

---

# 📐 Méretlogika

Minden méret az alábbi logika szerint:

```
cm → arány → extent_m → DPI → pontos nyomdai PDF
```

Példa kimenet:

```
citymap_50x70_2026-02-16_21-45-12.pdf
```

---

# 🧭 CLI Használat

## Alap futtatás

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

# 📦 Projektstruktúra (Backend)

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

# 📦 Projektstruktúra (Frontend)

```
city-map-frontend/
│
├── src/
│   ├── components/
│   ├── pages/
│   ├── layout/
│   ├── config/
│   ├── App.jsx
│   └── main.jsx
│
├── tailwind.config.js
├── postcss.config.js
└── vite.config.js
```

---

# 🚀 Roadmap

## 1. SVG / DXF Export

- Lézervágás
- Gravírozás
- CNC támogatás

## 2. Webshop Integráció

Frontend:

- Térképpont kiválasztás
- Élő preview
- Méret- és palettaválasztás

Backend:

- Automatikus PDF generálás
- Gyártási fájl export
- Privát gyártói endpoint

## 3. Coastline-aware Framing

- Snap-to-land logika
- Intelligens center korrekció
- Kompozíciós optimalizálás

## 4. Méretfüggő tipográfia

- Dinamikus font scaling
- Kis méret optimalizálás
- Nyomdai balansz finomítás

---

# 🔒 Projektállapot

- Stabil render pipeline
- Preview API működik
- React konfigurátor integrálva
- Layout és render teljesen szétválasztva
- Determinisztikus output biztosított

---

# 👤 Author

**Norbert von Polyák**

---

# 🧠 Vision

A cél nem pusztán egy térképgenerátor, hanem egy:

- Determinisztikus
- Skálázható
- Nyomdai minőségű
- Webshop-integrálható
- Architekturálisan tiszta

térképprodukciós rendszer.
