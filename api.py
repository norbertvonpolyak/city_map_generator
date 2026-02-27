from fastapi import FastAPI, Response
from pydantic import BaseModel
from service import generate_preview

app = FastAPI()


class PreviewRequest(BaseModel):
    lat: float
    lon: float
    size_key: str
    extent_m: int
    palette: str


@app.post(
    "/preview",
    response_class=Response,
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "PNG image"
        }
    },
)
def preview(request: PreviewRequest):
    png_bytes = generate_preview(
        lat=request.lat,
        lon=request.lon,
        size_key=request.size_key,
        palette=request.palette,
        extent_m=request.extent_m,
    )

    return Response(content=png_bytes, media_type="image/png")