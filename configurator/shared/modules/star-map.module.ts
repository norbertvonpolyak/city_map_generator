import type { StarPosterConfig } from '../types'
import type { UMCModuleDefinition } from './types'

export const starMapDefaults: StarPosterConfig = {
  schemaVersion: '1.0.0',
  moduleKind: 'star-map',
  title: 'Star Map Poster',
  createdAtIso: '2026-01-01T00:00:00.000Z',
  location: {
    query: 'Reykjavik, Iceland',
    latitude: 64.1466,
    longitude: -21.9426,
    regionHint: 'northern-latitude',
  },
  template: {
    templateId: 'stellar-classic',
    ratio: '2:3',
    orientation: 'portrait',
    sizePreset: '30x45',
  },
  style: {
    paletteId: 'night-gilded',
    tone: 'night',
    lineWeight: 'fine',
    textureEnabled: true,
  },
  objects: {
    roads: false,
    labels: true,
    buildings: false,
    water: false,
    stars: true,
    constellations: true,
    grid: true,
  },
  star: {
    dateIso: '2026-06-16T20:00:00.000Z',
    observerCity: 'Reykjavik',
    skyStyle: 'constellation',
  },
}

export const starMapModuleDefinition: UMCModuleDefinition<StarPosterConfig> = {
  kind: 'star-map',
  label: 'Star Map',
  tagline: 'Celestial compositions for meaningful moments in time.',
  previewHint: 'Preview placeholder for star-map output.',
  availableSections: ['module-selector', 'location', 'template', 'style', 'objects'],
  defaults: starMapDefaults,
  status: 'foundation',
}
