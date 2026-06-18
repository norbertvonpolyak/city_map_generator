export type CityMapStyleId = 'minimal' | 'district' | 'architecture'

export interface CityMapStyleProduct {
  id: CityMapStyleId
  name: string
  description: string
  templateId: string
  thumbnailClass: string
}

export interface PaletteTheme {
  id: string
  name: string
  description: string
  colors: string[]
}

export const cityMapStyles: CityMapStyleProduct[] = [
  {
    id: 'minimal',
    name: 'Minimal',
    description: 'Letisztult vonalas térkép',
    templateId: 'city-signature',
    thumbnailClass: 'umc-style-thumb umc-style-thumb-minimal',
  },
  {
    id: 'district',
    name: 'District',
    description: 'Színezett várostömbök',
    templateId: 'urban-modern',
    thumbnailClass: 'umc-style-thumb umc-style-thumb-district',
  },
  {
    id: 'architecture',
    name: 'Architecture',
    description: 'Épületalapú városrajz',
    templateId: 'city-buildings',
    thumbnailClass: 'umc-style-thumb umc-style-thumb-architecture',
  },
]

const minimalPaletteThemes: PaletteTheme[] = [
  {
    id: 'linen',
    name: 'Linen',
    description: 'Világos bézs, nyomdai hangulat',
    colors: ['#efe3cd', '#d6c3a2', '#b39a79', '#8da8b8'],
  },
  {
    id: 'stone',
    name: 'Stone',
    description: 'Semleges szürke árnyalatok',
    colors: ['#f0efed', '#d7d5d2', '#b2b0ac', '#8a8b91'],
  },
  {
    id: 'nordic',
    name: 'Nordic',
    description: 'Hideg szürke-kék karakter',
    colors: ['#e7ebf0', '#c8d0da', '#a3b2bf', '#6d8396'],
  },
  {
    id: 'terra',
    name: 'Terra',
    description: 'Meleg földszínek',
    colors: ['#f0ddc3', '#d4b184', '#a97f57', '#75685a'],
  },
]

const districtPaletteThemes: PaletteTheme[] = [
  {
    id: 'urban_modern',
    name: 'Urban Modern',
    description: 'Meleg narancs és terrakotta árnyalatok',
    colors: ['#D9D5C7', '#E8891C', '#D26A1E', '#C65A2A', '#E2C79F', '#5F9F9B', '#2F2F2F'],
  },
  {
    id: 'minimal_sand',
    name: 'Minimal Sand',
    description: 'Letisztult homok és szürke tónusok',
    colors: ['#E9E4DA', '#F2EEE6', '#CFC6B6', '#B8AEA0', '#9C9286', '#BFD1D6', '#2C2C2C'],
  },
]

export const resolveCityStyleFromTemplate = (templateId: string): CityMapStyleProduct => {
  return cityMapStyles.find((item) => item.templateId === templateId) ?? cityMapStyles[0]
}

export const getPaletteThemesForCityStyle = (styleId: CityMapStyleId): PaletteTheme[] => {
  if (styleId === 'minimal') return minimalPaletteThemes
  if (styleId === 'district') return districtPaletteThemes
  return []
}
