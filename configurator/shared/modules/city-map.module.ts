import type { CityPosterConfig } from '../types'
import type { UMCModuleDefinition } from './types'

export const cityMapDefaults: CityPosterConfig = {
  schemaVersion: '1.0.0',
  moduleKind: 'city-map',
  title: 'City Map Poster',
  createdAtIso: '2026-01-01T00:00:00.000Z',
  location: {
    query: 'Budapest, Hungary',
    latitude: 47.4979,
    longitude: 19.0402,
    regionHint: 'city-center',
  },
  template: {
    templateId: 'city-signature',
    ratio: '3:4',
    orientation: 'portrait',
    sizePreset: '50x70',
  },
  style: {
    paletteId: 'heritage-sand',
    tone: 'classic',
    lineWeight: 'balanced',
    textureEnabled: true,
  },
  objects: {
    roads: true,
    labels: true,
    buildings: true,
    water: true,
    stars: false,
    constellations: false,
    grid: false,
  },
  city: {
    boundaryMode: 'city',
    language: 'en',
  },
}

export const cityMapModuleDefinition: UMCModuleDefinition<CityPosterConfig> = {
  kind: 'city-map',
  label: 'City Map',
  tagline: 'Urban identity posters with curated cartographic style.',
  previewHint: 'Generate a real city SVG preview from the backend.',
  availableSections: ['module-selector', 'location', 'template', 'style', 'objects'],
  defaults: cityMapDefaults,
  status: 'foundation',
}
