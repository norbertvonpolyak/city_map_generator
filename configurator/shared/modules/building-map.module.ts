import type { BuildingPosterConfig } from '../types'
import type { UMCModuleDefinition } from './types'

export const buildingMapDefaults: BuildingPosterConfig = {
  schemaVersion: '1.0.0',
  moduleKind: 'building-map',
  title: 'Épülettérkép poszter',
  createdAtIso: '2026-01-01T00:00:00.000Z',
  location: {
    query: 'BMW Welt, Munchen',
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
    paletteId: 'stone',
    tone: 'editorial',
    lineWeight: 'fine',
    textureEnabled: false,
    typographyStyle: 'classic',
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
  label: 'Épülettérkép',
  tagline: 'Építészeti fókusz precíz kompozíciós beállításokkal.',
  previewHint: 'Helyőrző előnézet az épülettérkép kimenetéhez.',
  availableSections: ['module-selector', 'location', 'template', 'style', 'objects'],
  defaults: buildingMapDefaults,
  status: 'foundation',
}
