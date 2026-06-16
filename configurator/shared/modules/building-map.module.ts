import type { BuildingPosterConfig } from '../types'
import type { UMCModuleDefinition } from './types'

export const buildingMapDefaults: BuildingPosterConfig = {
  schemaVersion: '1.0.0',
  moduleKind: 'building-map',
  title: 'Building Map Poster',
  createdAtIso: '2026-01-01T00:00:00.000Z',
  location: {
    query: 'BMW Welt, Munich',
    latitude: 48.1767,
    longitude: 11.5562,
    regionHint: 'district-scale',
  },
  template: {
    templateId: 'building-elevation',
    ratio: '4:5',
    orientation: 'portrait',
    sizePreset: '40x50',
  },
  style: {
    paletteId: 'graphite-ivory',
    tone: 'editorial',
    lineWeight: 'fine',
    textureEnabled: false,
  },
  objects: {
    roads: true,
    labels: true,
    buildings: true,
    water: false,
    stars: false,
    constellations: false,
    grid: true,
  },
  building: {
    levelOfDetail: 'facade',
    showAnnotations: true,
  },
}

export const buildingMapModuleDefinition: UMCModuleDefinition<BuildingPosterConfig> = {
  kind: 'building-map',
  label: 'Building Map',
  tagline: 'Architectural focus with technical composition controls.',
  previewHint: 'Preview placeholder for building-map output.',
  availableSections: ['module-selector', 'location', 'template', 'style', 'objects'],
  defaults: buildingMapDefaults,
  status: 'foundation',
}
