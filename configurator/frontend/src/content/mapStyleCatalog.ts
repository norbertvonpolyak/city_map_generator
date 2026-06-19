export type BackendCityStyleId =
  | 'bw_minimal'
  | 'nordic_teal'
  | 'blueprint'
  | 'desert_sand'
  | 'ivory_bw'
  | 'urban_modern'
  | 'minimal_sand'
  | 'vintage_atlas'
  | 'pretty_buildings'

export type CityStyleEngine = 'line' | 'block' | 'building'
export type CityStyleFamilyId = 'minimal' | 'district' | 'architecture'

export interface CityMapStyleDefinition {
  id: BackendCityStyleId
  engine: CityStyleEngine
  name: string
  description: string
  background: string
  road: string
  water: string
  green?: string
  buildingColors?: string[]
  thumbnailBackground: string
  maxRadiusKm: number
  radiusStep: number
}

export interface CityStyleFamilyDefinition {
  id: CityStyleFamilyId
  name: string
  description: string
  thumbnailClass: string
  paletteIds: BackendCityStyleId[]
}

export const cityMapStyleRegistry: CityMapStyleDefinition[] = [
  {
    id: 'nordic_teal',
    engine: 'line',
    name: 'Nordic Teal',
    description: 'Scandinavian-inspired light style with teal waterways and modern interior-design aesthetics.',
    background: '#F7F5F0',
    road: '#1F2933',
    water: '#2A9D8F',
    thumbnailBackground: 'linear-gradient(160deg, #F7F5F0 0%, #f1eee7 58%, #ece8df 100%)',
    maxRadiusKm: 50,
    radiusStep: 1,
  },
  {
    id: 'bw_minimal',
    engine: 'line',
    name: 'Minimal Night',
    description: 'Dark monochrome style with strong contrast and premium poster appearance.',
    background: '#0F0F10',
    road: '#FFFFFF',
    water: '#CFC8B8',
    thumbnailBackground: 'linear-gradient(160deg, #0F0F10 0%, #1a1a1d 55%, #2a2a30 100%)',
    maxRadiusKm: 50,
    radiusStep: 1,
  },
  {
    id: 'blueprint',
    engine: 'line',
    name: 'Blueprint',
    description: 'Technical blueprint-inspired rendering with deep navy tones and engineering character.',
    background: '#0D1B2A',
    road: '#E0E1DD',
    water: '#415A77',
    thumbnailBackground: 'linear-gradient(160deg, #0D1B2A 0%, #152942 55%, #1f3755 100%)',
    maxRadiusKm: 50,
    radiusStep: 1,
  },
  {
    id: 'desert_sand',
    engine: 'line',
    name: 'Desert Sand',
    description: 'Warm vintage travel-poster palette with sandy paper tones and muted colors.',
    background: '#F2E9DC',
    road: '#3E3A36',
    water: '#6B8FA3',
    thumbnailBackground: 'linear-gradient(160deg, #F2E9DC 0%, #ebdece 55%, #dfd0bd 100%)',
    maxRadiusKm: 50,
    radiusStep: 1,
  },
  {
    id: 'ivory_bw',
    engine: 'line',
    name: 'Ivory BW',
    description: 'Clean gallery-style black and white rendering with subtle grayscale water features.',
    background: '#FAF8F3',
    road: '#161616',
    water: '#D9D9D9',
    thumbnailBackground: 'linear-gradient(160deg, #FAF8F3 0%, #f2eee7 55%, #ece7df 100%)',
    maxRadiusKm: 50,
    radiusStep: 1,
  },
  {
    id: 'urban_modern',
    engine: 'block',
    name: 'Urban Modern',
    description: 'Warm parcel map rendering with terracotta accents and clear block hierarchy.',
    background: '#D9D5C7',
    road: '#EFEBDD',
    water: '#5F9F9B',
    buildingColors: ['#E8891C', '#D26A1E', '#C65A2A', '#E2C79F', '#F0A21A', '#7C7368', '#2F2F2F'],
    thumbnailBackground: 'linear-gradient(160deg, #D9D5C7 0%, #d3cdbd 55%, #c8bea9 100%)',
    maxRadiusKm: 4.5,
    radiusStep: 0.2,
  },
  {
    id: 'minimal_sand',
    engine: 'block',
    name: 'Minimal Sand',
    description: 'Neutral block palette with light sand paper tones and subtle contrast.',
    background: '#E9E4DA',
    road: '#FFFFFF',
    water: '#BFD1D6',
    buildingColors: ['#F2EEE6', '#E1DBCF', '#CFC6B6', '#B8AEA0', '#9C9286', '#6E6A63', '#2C2C2C'],
    thumbnailBackground: 'linear-gradient(160deg, #E9E4DA 0%, #e0d8ca 55%, #d5cab7 100%)',
    maxRadiusKm: 4.5,
    radiusStep: 0.2,
  },
  {
    id: 'vintage_atlas',
    engine: 'building',
    name: 'Vintage Atlas',
    description: 'Warm vintage atlas aesthetic with muted earth tones and historical map character.',
    background: '#E6D3B3',
    road: '#5C3D23',
    water: '#8FA6AA',
    green: '#C9D8B6',
    buildingColors: ['#C9B28F', '#BFA37C', '#D7C2A4', '#A88F6C'],
    thumbnailBackground: 'linear-gradient(160deg, #E6D3B3 0%, #dfc9a7 55%, #d5bc96 100%)',
    maxRadiusKm: 8,
    radiusStep: 0.2,
  },
  {
    id: 'pretty_buildings',
    engine: 'building',
    name: 'Pretty Buildings',
    description: 'Colorful architectural rendering with highlighted buildings and modern poster appearance.',
    background: '#F4F1EB',
    road: '#C9C9C9',
    water: '#8EC5E8',
    green: '#DADFCF',
    buildingColors: ['#F29F1F', '#E27A1F', '#C65A2A', '#D9BB8F', '#F4B942', '#2F2F2F'],
    thumbnailBackground: 'linear-gradient(160deg, #F4F1EB 0%, #ebe5da 55%, #dfd5c6 100%)',
    maxRadiusKm: 8,
    radiusStep: 0.2,
  },
]

export const defaultCityStyleId: BackendCityStyleId = 'nordic_teal'

export const cityStyleFamilies: CityStyleFamilyDefinition[] = [
  {
    id: 'minimal',
    name: 'Minimal',
    description: 'Line engine variants',
    thumbnailClass: 'umc-style-thumb umc-style-thumb-minimal',
    paletteIds: ['nordic_teal', 'bw_minimal', 'blueprint', 'desert_sand', 'ivory_bw'],
  },
  {
    id: 'district',
    name: 'District',
    description: 'Block engine variants',
    thumbnailClass: 'umc-style-thumb umc-style-thumb-district',
    paletteIds: ['urban_modern', 'minimal_sand'],
  },
  {
    id: 'architecture',
    name: 'Architecture',
    description: 'Building engine variants',
    thumbnailClass: 'umc-style-thumb umc-style-thumb-architecture',
    paletteIds: ['vintage_atlas', 'pretty_buildings'],
  },
]

export const resolveCityMapStyle = (styleId: string): CityMapStyleDefinition => {
  return cityMapStyleRegistry.find((style) => style.id === styleId) ?? cityMapStyleRegistry[0]
}

export const resolveCityStyleFamily = (familyId: string): CityStyleFamilyDefinition => {
  return cityStyleFamilies.find((family) => family.id === familyId) ?? cityStyleFamilies[0]
}

export const resolveCityStyleFamilyByStyle = (styleId: string): CityStyleFamilyDefinition => {
  return cityStyleFamilies.find((family) => family.paletteIds.includes(styleId as BackendCityStyleId)) ?? cityStyleFamilies[0]
}
