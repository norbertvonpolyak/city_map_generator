from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from service import generate_city_preview_svg, generate_preview, CityPreviewResult

app = FastAPI()
logger = logging.getLogger(__name__)


class CityPreviewRequest(BaseModel):
    city: str
    style: str = "minimal"
    sizeKey: str = "50x70"
    extentM: int = 1800


class LegacyPreviewRequest(BaseModel):
    lat: float
    lon: float
    size_key: str
    extent_m: int
    palette: str


@app.post("/preview/city")
def preview_city(request: CityPreviewRequest):
    try:
        result = generate_city_preview_svg(
            city=request.city,
            style=request.style,
            size_key=request.sizeKey,
            extent_m=request.extentM,
        )
    except ValueError as exc:
        message = str(exc)
        if "city name is required" in message.lower() or "geocode" in message.lower():
            raise HTTPException(status_code=404, detail="City Not Found") from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="City Not Found") from exc
    except Exception as exc:
        logger.exception("/preview/city failed")
        raise

    return JSONResponse(content={"svg": result.svg, "png_base64": result.png_base64})


@app.post(
    "/preview",
    response_class=Response,
    responses={
        200: {
            "content": {"image/svg+xml": {}},
            "description": "SVG image",
        }
    },
)
def preview(request: LegacyPreviewRequest):
    svg_bytes = generate_preview(
        lat=request.lat,
        lon=request.lon,
        size_key=request.size_key,
        palette=request.palette,
        extent_m=request.extent_m,
    )

    return Response(content=svg_bytes, media_type="image/svg+xml")
