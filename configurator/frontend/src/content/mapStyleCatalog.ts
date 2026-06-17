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

const fullPaletteThemes: PaletteTheme[] = [
  {
    id: 'linen',
    name: 'Linen',
    description: 'Lágy, világos városblokkok',
    colors: ['#f3e6ce', '#e8d5b4', '#d7be91', '#c8a97a', '#b69164', '#9f7d55', '#7f6f63'],
  },
  {
    id: 'stone',
    name: 'Stone',
    description: 'Semleges városi árnyalatok',
    colors: ['#f1f0ee', '#e2dfdc', '#d1cdca', '#bdb9b6', '#a8a4a2', '#8f8d8f', '#6f7176'],
  },
  {
    id: 'nordic',
    name: 'Nordic',
    description: 'Hűvös skandináv karakter',
    colors: ['#e9edf2', '#dbe3ec', '#c8d3df', '#adbccd', '#8fa4bb', '#738ea8', '#58758f'],
  },
  {
    id: 'terra',
    name: 'Terra',
    description: 'Meleg földszín kompozíció',
    colors: ['#f2dfc8', '#e6ccad', '#d8b589', '#c89d69', '#b18253', '#966b45', '#715542'],
  },
  {
    id: 'slate',
    name: 'Slate',
    description: 'Grafit és kő tónusok',
    colors: ['#e7e8ea', '#cfd3d8', '#b5bcc4', '#99a5b2', '#7c8998', '#5f6b79', '#424d5a'],
  },
  {
    id: 'mist',
    name: 'Mist',
    description: 'Párás, lágy átmenetek',
    colors: ['#f1f2f0', '#e2e6e1', '#d3dad4', '#c2cec7', '#a9bdb4', '#8ea59a', '#70867a'],
  },
  {
    id: 'copper',
    name: 'Copper',
    description: 'Réz és bronz hangulat',
    colors: ['#f2dec8', '#e2c49f', '#d0a67b', '#bb885c', '#a9714e', '#8d5a3f', '#6b4535'],
  },
]

export const resolveCityStyleFromTemplate = (templateId: string): CityMapStyleProduct => {
  return cityMapStyles.find((item) => item.templateId === templateId) ?? cityMapStyles[0]
}

export const getPaletteThemesForCityStyle = (styleId: CityMapStyleId): PaletteTheme[] => {
  return styleId === 'minimal' ? minimalPaletteThemes : fullPaletteThemes
}
