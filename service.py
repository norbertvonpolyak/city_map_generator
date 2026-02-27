from io import BytesIO
import matplotlib.pyplot as plt

from generator.specs import spec_from_size_key
from generator.render import render_city_map


def generate_preview(
    *,
    lat: float,
    lon: float,
    size_key: str,
    palette: str,
    extent_m: int | None = None,
) -> bytes:

    spec = spec_from_size_key(
        size_key=size_key,
        extent_m=extent_m if extent_m is not None else 5000,
    )

    fig = render_city_map(
        center_lat=lat,
        center_lon=lon,
        spec=spec,
        output_dir=None,
        palette_name=palette,
        seed=42,
        filename_prefix="preview",
    )

    buffer = BytesIO()

    fig.savefig(
        buffer,
        format="png",
        dpi=spec.dpi,
        bbox_inches="tight",
        pad_inches=0,
    )

    buffer.seek(0)
    plt.close(fig)

    return buffer.read()