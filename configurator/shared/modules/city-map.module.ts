import type { CityPosterConfig } from '../types'
import type { UMCModuleDefinition } from './types'

export const cityMapDefaults: CityPosterConfig = {
  schemaVersion: '1.0.0',
  moduleKind: 'city-map',
  title: 'Várostérkép poszter',
  createdAtIso: '2026-01-01T00:00:00.000Z',
  location: {
    query: 'Budapest, Magyarország',
    latitude: 47.4979,
    longitude: 19.0402,
    regionHint: 'city-center',
  },
  template: {
    templateId: 'nordic_teal',
    ratio: '3:4',
    orientation: 'portrait',
    sizePreset: '50x70',
  },
  style: {
    paletteId: 'nordic_teal',
    tone: 'classic',
    lineWeight: 'balanced',
    textureEnabled: true,
    typographyStyle: 'classic',
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
  label: 'Várostérkép',
  tagline: 'Városi identitás poszterek gondosan válogatott kartográfiai stílusban.',
  previewHint: 'A valós várostérkép előnézetet a Generálás gomb készíti el a háttérrendszerből.',
  availableSections: ['module-selector', 'location', 'template', 'style', 'objects'],
  defaults: cityMapDefaults,
  status: 'foundation',
}
