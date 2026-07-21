from PIL import Image, ImageDraw
import numpy as np
import os

# Randomizált pontozott textúra generálása
width, height = 512, 512
img = Image.new('RGB', (width, height), color=(255, 255, 255))
draw = ImageDraw.Draw(img)

# Random pontok generálása
np.random.seed(42)  # Konzisztens eredmény
dot_color = (180, 180, 180)  # szürke
num_dots = 1200  # pontok száma

# Random pontok
for _ in range(num_dots):
    # Random pozíció
    x = np.random.uniform(0, width)
    y = np.random.uniform(0, height)
    
    # Random pont méret (1-3 pixel)
    dot_radius = np.random.uniform(1, 3)
    
    # Kör rajzolása
    draw.ellipse(
        [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
        fill=dot_color
    )

# Mentés
output_path = 'assets/textures/parks_random_stipple.png'
os.makedirs('assets/textures', exist_ok=True)
img.save(output_path)
print(f"Randomizált pontozott textúra létrehozva: {output_path}")
