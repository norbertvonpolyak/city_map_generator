#!/usr/bin/env python3
"""Test the sky star map style."""

from pathlib import Path
from generator.specs import spec_from_size_key
from generator.render_stars import render_star_map_stub

output_base = Path("output/style_test")
output_base.mkdir(parents=True, exist_ok=True)

spec_50x50 = spec_from_size_key(size_key="50x50", extent_m=2000, dpi=300)

print("Testing Sky style...")
result_sky = render_star_map_stub(
    spec=spec_50x50,
    output_dir=output_base / "sky",
    filename_prefix="star_map_sky",
    title="Sky",
    motto="Full Sky View",
    location_name="Test Location",
    date_text="2026-06-22 22:00",
    custom_message="",
    style="sky",
    constellations=True,
    nebula_strength=1.25,
)
print(f"  PDF: {result_sky.output_pdf}")
print(f"  PNG: {result_sky.output_preview_png}")

print("\nDone!")
