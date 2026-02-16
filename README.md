# City Map Generator

A **City Map Generator** egy Python-alapú, OpenStreetMap (OSM) adatokra épülő, nyomdai minőségű várostérkép-renderelő rendszer.  

A projekt célja egy determinisztikus, minimalista és termékorientált térképgenerátor, amely poszterekhez, faliképekhez és webshopos termékekhez készít print-ready PDF kimenetet.

A rendszer logikai lánca:

**cm → arány → render → layout → gyártás**

---

# 🎯 Projekt fókusz

- Letisztult vizuális stílus
- Determinisztikus renderelés
- OSM adatok intelligens feldolgozása
- Skálázható termékméretek (cm → arány → vonalvastagság)
- Layout és render teljes szétválasztása
- Nyomdai minőségű PDF export

---

# ✨ Fő jellemzők

## 🧱 Polygonize-alapú várostömb generálás

Az OSM úthálózatból automatikusan képzett city block struktúra.

- OSMnx 2.x kompatibilis pipeline
- Polygonize-alapú tömbképzés
- Determinisztikus blokkszínezés seed alapján

---

## 🛣️ Hierarchikus úthálózat renderelés

Úthierarchia:

- Motorway
- Arterial
- Local
- Minor

A vastagság három komponensből áll:

### 1. Globális alap
- `road_width`
- `road_boost`

### 2. Úttípus-szorzók
- `lw_highway_mult`
- `lw_arterial_mult`
- `lw_local_mult`
- `lw_minor_mult`

### 3. Automatikus skálázás térképkiterjedés alapján
`_scaled_linewidth()` biztosítja az arányos vizuális hierarchiát minden méretben.

---

## 🚫 Nem kívánt OSM útvonalak kizárása

Alapértelmezetten nem kerülnek renderelésre:

- `footway`
- `cycleway`
- `path`
- `pedestrian`
- `steps`
- `bridleway`

Ez megszünteti az OSM-eredetű párhuzamos „szőrös” vonalakat.

```python
draw_non_vehicular = False  # default

```

---

# 🎨 Stílusrendszer

A projekt egyetlen „source of truth”-ja a **MonoStyle**.

```python
from generator.styles import MonoStyle, DEFAULT_MONO

style = DEFAULT_MONO
```

- Nincs runtime JSON betöltés
- Nincs preset varázslás
- Teljesen verziózható
- Diffelhető
- Determinisztikus

Konfigurálható:

- blokkszínek
- útszín
- vízszín
- úthierarchia vastagság
- alsó strip tipográfia

---

# 🖨️ Kétlépcsős architektúra

A rendszer szigorúan szétválasztja a renderelést és a kompozíciót.

## 1️⃣ Map Layer Render  
**matplotlib → PNG**

- Térkép réteg generálása  
- Determinisztikus seed  
- DPI-alapú skálázás  

## 2️⃣ Print Composition  
**ReportLab → PDF**

- Fix cm-alapú alsó strip  
- Jobbra zárt cím  
- Subtitle külön betűstílussal  
- Bal oldali logó támogatás  
- Egységes vékony keret minden oldalon  
- Timestampelt fájlnév  
- Méretazonosító a fájlnévben  

Ez biztosítja a layout és a térkép teljes függetlenségét.

---

# 📐 Termékméret-független renderelés

Minden méret egységes logika mentén készül:

**cm → arány → DPI → pontos nyomdai PDF méret**

Példa kimenet:

```
citymap_50x70_2026-02-16_21-45-12.pdf
```

---

# 🧭 Használat (CLI)

## Alap futtatás

```bash
python main.py \
  --center-lat 47.4979 \
  --center-lon 19.0402 \
  --width-cm 50 \
  --height-cm 70 \
  --output-dir output/
```

## Monochrome render (baseline)

```python
result = render_city_map_monochrome(
    center_lat=...,
    center_lon=...,
    spec=spec,
    output_dir=output_dir,
    zoom=1.0,
    preset_name="snazzy_bw_blackwater",
    draw_non_vehicular=False,
)
```

---

# 🧱 Projektstruktúra

```
city_map_generator/
│
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

# 🔒 Projektállapot

- Stabil monochrome baseline a `main` branch-ben  
- Aktív fejlesztés webshop-integráció irányába  
- Determinisztikus render biztosított  
- Layout és render réteg teljesen szétválasztva  

---

# 🚀 Roadmap

## 🎯 1. SVG / DXF export

Vektoros kimenet gyártáshoz:

- Lézervágás  
- Gravírozás  
- CNC workflow támogatás  

## 🛒 2. Webshop-integráció

Frontend:

- Térképpont kiválasztás  
- Élő preview  
- Méretválasztás  

Backend:

- Automatikus PDF generálás  
- Gyártási fájl generálás  
- Privát gyártói hozzáférés  

## 🌊 3. Coastline-aware framing

- Snap-to-land logika  
- Intelligens center korrekció  
- Kompozíciós optimalizálás  

## 🧭 4. Kompozíciós preset rendszer

- Minimal logo-free edition  
- Centered title  
- Editorial layout  
- Premium edition  

## 📐 5. Méretfüggő tipográfia

- Dinamikus font scaling  
- 30×40 cm alatti optimalizálás  
- Nyomdai vizuális balansz finomítása  

---

# 👤 Author

**Norbert von Polyák**
