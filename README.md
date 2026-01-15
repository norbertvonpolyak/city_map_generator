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
