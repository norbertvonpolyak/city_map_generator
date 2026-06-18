export interface CityPreviewRequest {
  city: string
  style: 'minimal'
  latitude?: number | null
  longitude?: number | null
  sizeKey: string
  extentM: number
}

export interface CityPreviewResponse {
  svg: string
  png_base64: string
}

export interface CityPreviewAssets {
  svg: string
  pngDataUrl: string
}

export async function generateCityPreview(request: CityPreviewRequest): Promise<CityPreviewAssets> {
  const response = await fetch('/preview/city', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorPayload?.detail ?? 'Preview Generation Failed')
  }

  const payload = (await response.json()) as CityPreviewResponse

  if (!payload.svg || !payload.png_base64) {
    throw new Error('Preview Generation Failed')
  }

  return {
    svg: payload.svg,
    pngDataUrl: `data:image/png;base64,${payload.png_base64}`,
  }
}
