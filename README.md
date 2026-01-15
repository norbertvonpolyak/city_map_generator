# City Map Generator

Custom, high-resolution city map generator for print-ready posters and webshop products.

This project generates stylized city maps from OpenStreetMap data with a strong focus on:
- clean, modern visual language
- print quality output (PDF)
- configurable color palettes
- scalable layouts for different poster sizes

The generator is designed as the backend rendering engine for a future webshop,
where users will be able to customize location, size, color style, and layout.

---

## Features

- 📍 Location-based rendering (latitude / longitude)
- 🗺️ Road network extraction via OSMnx
- 🧱 City block polygonization and coloring
- 🎨 Multiple curated color palettes (warm, cool, grayscale, etc.)
- 📐 Aspect-ratio aware framing based on real-world dimensions
- 🖨️ Print-ready PDF export with deterministic rendering
- 🔁 Scalable road widths based on map extent

---

## Project Structure

```text
city_map_generator/
│
├─ generator/
│  ├─ render.py        # Core rendering pipeline
│  ├─ specs.py         # Product / size specifications
│  ├─ styles.py        # Color palettes and visual styles
│
├─ scripts/
│  └─ render_example.py  # Example usage (optional)
│
├─ outputs/            # Generated PDFs (gitignored)
├─ README.md
└─ .gitignore

```

## Example Code

```code
from pathlib import Path
from generator.specs import ProductSpec
from generator.render import render_city_map

spec = ProductSpec.from_size_cm(
    width_cm=70,
    height_cm=50,
    extent_m=5000,
)

render_city_map(
    center_lat=41.3851,
    center_lon=2.1734,
    spec=spec,
    output_dir=Path("outputs"),
    palette_name="warm",
)
```

This will generate a timestamped, print-ready PDF map centered on the given location.


## Design Principles

Data-driven geometry – no manual drawing
Consistent visual hierarchy – blocks, roads, water clearly separated
Print first – color choices and line widths optimized for large formats
Deterministic output – same input yields the same result (with seed)


## Roadmap (High Level)

 Caption / typography layouts (city name, coordinates)
 Preview-optimized low-resolution renders
 Webshop integration (WooCommerce)
 User-selectable styles and palettes
 Automated SVG / DXF export for manufacturing

## Notes

This repository currently contains the rendering engine only.
Web frontend, order handling, and payment integration are intentionally not included.

## License

Private / All rights reserved (for now).


<img width="793" height="788" alt="image" src="https://github.com/user-attachments/assets/b02b94ea-f9a8-4669-a5c2-cb653f61904f" />
