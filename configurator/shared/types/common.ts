export type UMCModuleKind = 'city-map' | 'building-map' | 'star-map'

export type UMCSectionId =
  | 'module-selector'
  | 'location'
  | 'template'
  | 'style'
  | 'objects'

export interface LocationConfig {
  query: string
  latitude: number | null
  longitude: number | null
  regionHint?: string
}

export interface TemplateConfig {
  templateId: string
  ratio: '2:3' | '3:4' | '4:5' | 'A-series' | 'custom'
  orientation: 'portrait' | 'landscape'
  sizePreset: string
}

export interface StyleConfig {
  paletteId: string
  tone: 'classic' | 'minimal' | 'night' | 'editorial'
  lineWeight: 'fine' | 'balanced' | 'bold'
  textureEnabled: boolean
}

export interface ObjectsConfig {
  roads: boolean
  labels: boolean
  buildings: boolean
  water: boolean
  stars: boolean
  constellations: boolean
  grid: boolean
}
