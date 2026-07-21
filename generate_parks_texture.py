from PIL import Image, ImageDraw
import os

# Pontozott textúra generálása
width, height = 512, 512
img = Image.new('RGB', (width, height), color=(255, 255, 255))
draw = ImageDraw.Draw(img)

# Sűrűn pontozott szürke minta
dot_color = (180, 180, 180)  # szürke
dot_spacing = 8  # pontok közötti távolság pixelben
dot_radius = 2   # pont nagysága

for y in range(0, height, dot_spacing):
    for x in range(0, width, dot_spacing):
        # Kör rajzolása (pont)
        draw.ellipse(
            [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
            fill=dot_color
        )

# Mentés
output_path = 'assets/textures/parks_stipple_grey.png'
os.makedirs('assets/textures', exist_ok=True)
img.save(output_path)
print(f"Pontozott textúra létrehozva: {output_path}")
