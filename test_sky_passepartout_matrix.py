#!/usr/bin/env python3
"""Generate a 3x3 opacity matrix for sky passepartout and frame edges."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from generator.specs import spec_from_size_key
from generator.render_stars import render_star_map_stub


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


output_base = Path("output/style_test/sky_matrix")
output_base.mkdir(parents=True, exist_ok=True)

spec_50x50 = spec_from_size_key(size_key="50x50", extent_m=2000, dpi=300)

body_alphas = [0.20, 0.30, 0.40]
edge_alphas = [0.20, 0.25, 0.30]

print("Generating sky opacity matrix...")

rendered_previews: list[tuple[Path, float, float]] = []
for body_alpha in body_alphas:
    for edge_alpha in edge_alphas:
        tag = f"body{int(body_alpha * 100):02d}_edge{int(edge_alpha * 100):02d}"
        case_dir = output_base / tag
        case_dir.mkdir(parents=True, exist_ok=True)

        result = render_star_map_stub(
            spec=spec_50x50,
            output_dir=case_dir,
            filename_prefix=f"star_map_sky_{tag}",
            title="Sky",
            motto="Full Sky View",
            location_name="Test Location",
            date_text="2026-06-22 22:00",
            custom_message="",
            style="sky",
            constellations=True,
            nebula_strength=1.25,
            sky_passepartout_alpha=body_alpha,
            sky_edge_alpha=edge_alpha,
        )
        rendered_previews.append((result.output_preview_png, body_alpha, edge_alpha))
        print(f"  {tag}: {result.output_preview_png}")

# Build contact sheet to compare all variants in one image.
thumb_max_w = 900
thumb_max_h = 900
label_h = 54
tile_gap = 16
padding = 22
cols = len(edge_alphas)
rows = len(body_alphas)

sample_img = Image.open(rendered_previews[0][0]).convert("RGB")
sample_img.thumbnail((thumb_max_w, thumb_max_h))
tile_w, tile_h = sample_img.size
sample_img.close()

canvas_w = (padding * 2) + (cols * tile_w) + ((cols - 1) * tile_gap)
canvas_h = (padding * 2) + (rows * (tile_h + label_h)) + ((rows - 1) * tile_gap)
sheet = Image.new("RGB", (canvas_w, canvas_h), "#0f1724")
draw = ImageDraw.Draw(sheet)
font = _load_font(24)

for row_idx, body_alpha in enumerate(body_alphas):
    for col_idx, edge_alpha in enumerate(edge_alphas):
        match = next(
            item for item in rendered_previews
            if abs(item[1] - body_alpha) < 1e-9 and abs(item[2] - edge_alpha) < 1e-9
        )
        img_path, _, _ = match
        img = Image.open(img_path).convert("RGB")
        img.thumbnail((thumb_max_w, thumb_max_h))

        x = padding + col_idx * (tile_w + tile_gap)
        y = padding + row_idx * (tile_h + label_h + tile_gap)
        sheet.paste(img, (x, y))
        img.close()

        label = f"P:{int(body_alpha * 100)}% / E:{int(edge_alpha * 100)}%"
        draw.text((x + 10, y + tile_h + 12), label, fill="#e5ecf7", font=font)

sheet_path = output_base / "sky_opacity_matrix_contact_sheet.jpg"
sheet.save(sheet_path, quality=92)

print("\nDone.")
print(f"Contact sheet: {sheet_path}")
