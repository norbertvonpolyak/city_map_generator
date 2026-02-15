# City Map Generator

A City Map Generator egy Python-alapú, OpenStreetMap (OSM) adatokra épülő várostérkép-renderelő rendszer, amely nyomdai minőségű, minimalista várostérképeket generál poszterekhez, faliképekhez és webshopos termékekhez.

A projekt fókusza:

letisztult vizuális stílus,
determinisztikus renderelés,
OSM-adatok intelligens feldolgozása,
skálázható termékméretek (cm → arány → vonalvastagság).

 
# ✨ Fő jellemzők

Polygonize-alapú várostömb generálás
OSM úthálózatból automatikusan képzett city block struktúra.

Hierarchikus úthálózat renderelés
Motorway → arterial → local → minor vastagsági rendszer
determinista skálázással a térképkiterjedéshez igazítva.

Minimalista vizuális stílusrendszer
Palette-alapú konfiguráció:
-blokkszínek
-útszín
-vízszín
-úthierarchia vastagság
-egységes tipográfiai strip

Egységes alsó layout strip (ReportLab composer)
-fix cm-alapú strip magasság
-jobbra zárt cím
-külön betűstílus subtitle számára
-bal oldali logó támogatás
-vékony, egységes keret minden oldalon

Termékméret-független renderelés
-cm → arány → DPI → pontos nyomdai PDF méret
-minden méret azonos layout arányokkal.

Determinista kimenet
-seed alapú blokkszínezés
-reprodukálható render.

Nyomdai minőségű PDF export
-ReportLab-alapú végső kompozíció
-timestampelt fájlnév
-méretazonosító a fájlnévben

# 🧱 Projektstruktúra

```text city_map_generator/
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
# 🎨 Stílusrendszer

MonoStyle – az egyetlen „source of truth”
A monochrome stílus teljes egészében kódban van definiálva:

```
from generator.styles import MonoStyle, DEFAULT_MONO
style = DEFAULT_MONO
```
Nincs runtime JSON betöltés, nincs preset varázslás.
A stílus verziózható, diffelhető, determinisztikus.

## Úthierarchia (vastagság)

A vastagság három tényezőből áll össze:
Globális alap
```
road_width
road_boost
```
## Úttípus-szorzók
```
lw_highway_mult
lw_arterial_mult
lw_local_mult
lw_minor_mult
```
Automatikus skálázás térképkiterjedés alapján (_scaled_linewidth)
Ez biztosítja, hogy a főutak mindig hangsúlyosabbak legyenek.

## 🛣️ Útkezelési logika (fontos)

A renderer alapértelmezésben kizárja az alábbi OSM highway típusokat:
```
footway
cycleway
path
pedestrian
steps
bridleway
```
Ez megszünteti a tipikus OSM-eredetű párhuzamos „szőrös” vonalakat.

## Kapcsolható paraméter:
```
draw_non_vehicular=False  # alapértelmezett
```
# 🧭 Használat (CLI)
## Alap futtatás
```
python main.py \
  --center-lat 47.4979 \
  --center-lon 19.0402 \
  --width-cm 50 \
  --height-cm 70 \
  --output-dir outputs/
```
## Monochrome render (ajánlott)
```
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

# 🖨️ Kimenetek

Print-ready PDF (ReportLab)

Timestampelt fájlnév:
citymap_50x70_2026-02-16_21-45-12.pdf

A PDF tartalmaz:
felső térképréteg (matplotlib render)
alsó strip
bal oldali logó
jobb oldali cím + koordináta blokk
automatikus timestampelt fájlnevek

# 🔒 Projektállapot

aktív fejlesztés webshop-integrációra előkészítve
stabil monochrome baseline a main branch-ben

# 🧠 Architektúra

A rendszer kétlépcsős:
Map Layer Render (matplotlib → PNG)
Print Composition (ReportLab → PDF)
Ez biztosítja a layout és a render teljes szétválasztását.

# 🚀 Következő tervezett lépések

🎯 1. SVG / DXF export gyártáshoz
Vektoros kimenet bevezetése lézervágás / gravírozás / CNC workflow támogatására.

🛒 2. Webshop-integráció
Frontend alapú:
térképpont kiválasztás
élő preview
méretválasztás
automatikus PDF generálás backend oldalon

🌊 3. Coastline-aware framing finomítása
Part menti városok esetén:
snap-to-land logika
intelligens center korrekció
kompozíciós optimalizálás

🧭 4. Kompozíciós preset rendszer
Strip variánsok:
minimal
logo-free edition
centered title
editorial layout

📐 5. Méretfüggő tipográfia finomhangolás
Kisebb méreteknél dinamikus font scaling, hogy 30×40 alatt se legyen túl domináns a cím.

# 👤 Szerző
<span style="color:#d73a49; font-weight:600;">Norbert von Polyák</span>

