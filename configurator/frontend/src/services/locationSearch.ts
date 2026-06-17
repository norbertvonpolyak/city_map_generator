export interface SelectedLocation {
  displayName: string
  lat: number
  lon: number
}

interface LocationSearchProvider {
  search: (query: string, signal?: AbortSignal) => Promise<SelectedLocation[]>
}

interface NominatimItem {
  display_name: string
  lat: string
  lon: string
  address?: {
    city?: string
    town?: string
    village?: string
    municipality?: string
    country?: string
  }
}

const resolveCityName = (item: NominatimItem): string | null => {
  const address = item.address
  if (!address) {
    return null
  }

  return address.city ?? address.town ?? address.village ?? address.municipality ?? null
}

const toSelectedLocation = (item: NominatimItem): SelectedLocation | null => {
  const cityName = resolveCityName(item)
  const countryName = item.address?.country ?? null
  const lat = Number.parseFloat(item.lat)
  const lon = Number.parseFloat(item.lon)

  if (!cityName || !countryName || !Number.isFinite(lat) || !Number.isFinite(lon)) {
    return null
  }

  return {
    displayName: `${cityName}, ${countryName}`,
    lat,
    lon,
  }
}

const nominatimProvider: LocationSearchProvider = {
  async search(query, signal) {
    const params = new URLSearchParams({
      q: query.trim(),
      format: 'jsonv2',
      limit: '8',
      addressdetails: '1',
      dedupe: '1',
    })

    const response = await fetch(`https://nominatim.openstreetmap.org/search?${params.toString()}`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal,
    })

    if (!response.ok) {
      throw new Error('Location Search Failed')
    }

    const items = (await response.json()) as NominatimItem[]

    const uniqueByDisplayName = new Set<string>()

    return items
      .map(toSelectedLocation)
      .filter((item): item is SelectedLocation => item !== null)
      .filter((item) => {
        const normalizedName = item.displayName.toLocaleLowerCase()
        if (uniqueByDisplayName.has(normalizedName)) {
          return false
        }
        uniqueByDisplayName.add(normalizedName)
        return true
      })
  },
}

let activeProvider: LocationSearchProvider = nominatimProvider

export const setLocationSearchProvider = (provider: LocationSearchProvider) => {
  activeProvider = provider
}

export const searchLocations = (query: string, signal?: AbortSignal): Promise<SelectedLocation[]> => {
  return activeProvider.search(query, signal)
}
