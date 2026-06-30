from pathlib import Path
from PIL import Image, ImageEnhance
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

nebula_dir = Path(__file__).parent / "generator" / "starmap" / "nebula_png"
nebula_files = list(nebula_dir.glob("*.png"))
assert nebula_files, f"No PNG found in {nebula_dir}"
nebula_png_path = nebula_files[0]
print(f"Using: {nebula_png_path.name}")

nebula_pil_orig = Image.open(nebula_png_path).convert("RGBA")

variants = [
    (0.41, 1.90, 1.68, 0.50),  # 1 - current
    (0.30, 2.20, 2.00, 0.55),  # 2
    (0.25, 2.50, 2.20, 0.60),  # 3
    (0.50, 1.70, 1.50, 0.45),  # 4
    (0.35, 2.00, 1.80, 0.65),  # 5
    (0.20, 3.00, 2.50, 0.55),  # 6
    (0.45, 2.10, 1.90, 0.40),  # 7
    (0.28, 2.30, 2.00, 0.70),  # 8
    (0.38, 1.80, 2.40, 0.50),  # 9
]

fig, axes = plt.subplots(3, 3, figsize=(18, 18))
fig.patch.set_facecolor("#05172c")
fig.subplots_adjust(hspace=0.08, wspace=0.04)

for i, (bright, contr, sat, alph) in enumerate(variants):
    ax = axes[i // 3][i % 3]
    ax.set_facecolor("#05172c")
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.set_aspect("auto")
    ax.axis("off")
    nebula_pil = nebula_pil_orig.copy()
    nebula_pil = ImageEnhance.Brightness(nebula_pil).enhance(bright)
    nebula_pil = ImageEnhance.Contrast(nebula_pil).enhance(contr)
    nebula_pil = ImageEnhance.Color(nebula_pil).enhance(sat)
    nebula_array = np.asarray(nebula_pil, dtype=np.float32) / 255.0
    ax.imshow(nebula_array, extent=(-1, 1, -1, 1), origin="lower", alpha=alph, aspect="auto")
    ax.set_title(f"{i+1}:  br={bright}  co={contr}  sat={sat}  a={alph}", color="white", fontsize=10, pad=6)

out_path = Path(__file__).parent / "output" / "style_test" / "sky" / "nebula_grid_9.png"
out_path.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_path, dpi=110, bbox_inches="tight", facecolor="#05172c")
plt.close(fig)
print(out_path)
