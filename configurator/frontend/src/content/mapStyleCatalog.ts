export type BackendCityStyleId =
  | 'bw_minimal'
  | 'nordic_teal'
  | 'blueprint'
  | 'desert_sand'
  | 'ivory_bw'
  | 'urban_modern'
  | 'midnight_ember'
  | 'midnight_blue'
  | 'architect_sage'
  | 'warm_terracotta'
  | 'mono_black'
  | 'royal_purple'
  | 'sandstone_beige'
  | 'luxury_gold'

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
    id: 'midnight_ember',
    engine: 'block',
    name: 'Midnight Ember',
    description: 'Deep urban contrast with ember accents and steel-blue block rhythm.',
    background: '#F2EEE6',
    road: '#D9D3C8',
    water: '#0F4C5C',
    buildingColors: ['#1E252B', '#25323A', '#31444D', '#45606D', '#6C8A99', '#F2A541', '#E4572E'],
    thumbnailBackground: 'linear-gradient(160deg, #F2EEE6 0%, #e9e2d6 55%, #ddd3c4 100%)',
    maxRadiusKm: 4.5,
    radiusStep: 0.2,
  },
  {
    id: 'midnight_blue',
    engine: 'building',
    name: 'Midnight Blue',
    description: 'Dark night-map building style with deep navy tones and subtle highlights.',
    background: '#081519',
    road: '#081519',
    water: '#081519',
    green: '#34513D',
    buildingColors: ['#7EA6D8', '#5E88C5', '#D8C7A8', '#476FAE', '#355B95', '#192C42'],
    thumbnailBackground: 'linear-gradient(160deg, #081519 0%, #0d2329 55%, #16363f 100%)',
    maxRadiusKm: 5,
    radiusStep: 0.2,
  },
  {
    id: 'architect_sage',
    engine: 'building',
    name: 'Architect Sage',
    description: 'Soft sage-and-stone architectural palette with calm modern tones.',
    background: '#BFD4D0',
    road: '#FFFFFF',
    water: '#9DB8B1',
    green: '#B8C3B6',
    buildingColors: ['#8EA88A', '#78966F', '#63835A', '#4D6F49', '#D6CDB6', '#1E2B22'],
    thumbnailBackground: 'linear-gradient(160deg, #BFD4D0 0%, #b1c8c3 55%, #a2bbb5 100%)',
    maxRadiusKm: 5,
    radiusStep: 0.2,
  },
  {
    id: 'warm_terracotta',
    engine: 'building',
    name: 'Warm Terracotta',
    description: 'Warm earth-toned architecture with terracotta blocks and soft neutrals.',
    background: '#F6E8D7',
    road: '#5A3E36',
    water: '#C4D9E3',
    green: '#B8CFA5',
    buildingColors: ['#D77A61', '#C76754', '#B6594A', '#9D473D', '#EBC7A8', '#3A2A24'],
    thumbnailBackground: 'linear-gradient(160deg, #F6E8D7 0%, #efddc9 55%, #e5cfb6 100%)',
    maxRadiusKm: 5,
    radiusStep: 0.2,
  },
  {
    id: 'mono_black',
    engine: 'building',
    name: 'Mono Black',
    description: 'Monochrome architecture style with crisp grayscale hierarchy.',
    background: '#F5F5F5',
    road: '#3A3A3A',
    water: '#EFEFEF',
    green: '#C8C8C8',
    buildingColors: ['#D8D8D8', '#BEBEBE', '#9F9F9F', '#7C7C7C', '#EAEAEA', '#1A1A1A'],
    thumbnailBackground: 'linear-gradient(160deg, #F5F5F5 0%, #ececec 55%, #dedede 100%)',
    maxRadiusKm: 5,
    radiusStep: 0.2,
  },
  {
    id: 'royal_purple',
    engine: 'building',
    name: 'Royal Purple',
    description: 'Luxurious dark purple architecture with rich contrast and golden accents.',
    background: '#1f1e3a',
    road: '#1f1e3a',
    water: '#1f1e3a',
    green: '#3d3657',
    buildingColors: ['#9D78D1', '#8660BC', '#724EA8', '#e4be8d', '#DCCBEF', '#241A35'],
    thumbnailBackground: 'linear-gradient(160deg, #1f1e3a 0%, #2a2750 55%, #3a3468 100%)',
    maxRadiusKm: 5,
    radiusStep: 0.2,
  },
  {
    id: 'sandstone_beige',
    engine: 'building',
    name: 'Sandstone Beige',
    description: 'Natural sandstone-inspired tones with balanced architectural contrast.',
    background: '#F7F1E8',
    road: '#6B5A48',
    water: '#D9E5EB',
    green: '#8B9B82',
    buildingColors: ['#D8C4A5', '#C8B18F', '#B69E79', '#A28A64', '#ECE2D4', '#4B4035'],
    thumbnailBackground: 'linear-gradient(160deg, #F7F1E8 0%, #eee4d6 55%, #e3d6c2 100%)',
    maxRadiusKm: 5,
    radiusStep: 0.2,
  },
  {
    id: 'luxury_gold',
    engine: 'building',
    name: 'Luxury Gold',
    description: 'Dark premium style with elegant gold architecture and cinematic mood.',
    background: '#111111',
    road: '#F0D89B',
    water: '#4E5C6A',
    green: '#8A815B',
    buildingColors: ['#D8B25A', '#C79C44', '#B58630', '#9D7122', '#F0D89B', '#F7E7B6'],
    thumbnailBackground: 'linear-gradient(160deg, #111111 0%, #242019 55%, #3d3322 100%)',
    maxRadiusKm: 5,
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
    paletteIds: ['urban_modern', 'midnight_ember'],
  },
  {
    id: 'architecture',
    name: 'Architecture',
    description: 'Building engine variants',
    thumbnailClass: 'umc-style-thumb umc-style-thumb-architecture',
    paletteIds: [
      'midnight_blue',
      'architect_sage',
      'warm_terracotta',
      'mono_black',
      'royal_purple',
      'sandstone_beige',
      'luxury_gold',
    ],
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
