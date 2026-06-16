export interface CityPreviewRequest {
  city: string
  style: 'minimal'
}

export interface CityPreviewResponse {
  svg: string
}

export async function generateCityPreview(request: CityPreviewRequest): Promise<string> {
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

  if (!payload.svg) {
    throw new Error('Preview Generation Failed')
  }

  return payload.svg
}
