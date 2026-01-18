# City Map Generator

A City Map Generator egy Python-alapú, OpenStreetMap (OSM) adatokra épülő várostérkép-renderelő rendszer, amely nyomdai minőségű, minimalista várostérképeket generál poszterekhez, faliképekhez és webshopos termékekhez.

A projekt fókusza:

letisztult vizuális stílus,
determinisztikus renderelés,
OSM-adatok intelligens feldolgozása,
skálázható termékméretek (cm → arány → vonalvastagság).


# ✨ Fő jellemzők

Monochrome (Pretty) render mód
járműutak hierarchikus vastagsággal
gyalogos / biciklis / path rétegek alapértelmezésben kizárva
tiszta, poszter-szerű megjelenés
Polygonize-alapú várostömb színezés
Épületek, parkok, ipari területek kezelése
Vízfelületek egységes, fehér renderelése
folyók, tavak, tenger (coastline + sea mask)
Opcionális domborzati árnyalás (hillshade)
Termékméret-független vonalvastagság skálázás
Streamlit-alapú developer style tuner (nem runtime függőség)

# 🧱 Projektstruktúra

```text city_map_generator/
├── main.py                     # CLI / entry point
├── generator/
│   ├── render_monochrome.py    # Monochrome (pretty) renderer
│   ├── render_pretty.py        # Legacy / blocks render
│   ├── styles.py               # Style source of truth
│   ├── specs.py                # ProductSpec (méretek, DPI, frame)
│   ├── relief.py               # DEM + hillshade kezelés
│   ├── presets_loader.py       # (dev helper, opcionális)
│   └── style_tuner.py          # Developer-only tuner logika
├── tools/
│   └── style_tuner_app.py      # Streamlit UI stílus finomhangoláshoz
└── README.md
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

# 🧪 Style Tuner (developer-only)

A Streamlit tuner nem része a runtime pipeline-nak.

### Célja:
MonoStyle finomhangolása vizuális preview-val és az értékek kézi visszamásolása a styles.py-ba

### Indítás:
```
streamlit run tools/style_tuner_app.py
```
A tuner nem exportál, nem ír fájlt – a végleges stílus mindig hardcode-olt.

# 🖨️ Kimenetek

PDF – nyomdai minőség (CMYK-kompatibilis workflow)
PNG – preview / fejlesztés
SVG - to be implemented

automatikus timestampelt fájlnevek

# 🔒 Projektállapot

aktív fejlesztés webshop-integrációra előkészítve
stabil monochrome baseline a main branch-ben

# 🚀 Következő tervezett lépések

további MonoStyle variánsok (high contrast, ultra minimal)
SVG / DXF export gyártáshoz
webes rendelési felület (map selection + preview)
snap-to-land / coastline-aware framing finomítása

# 👤 Szerző
<span style="color:#d73a49; font-weight:600;">Norbert von Polyák</span>

