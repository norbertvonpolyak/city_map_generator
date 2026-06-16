import type {
  LocationConfig,
  ObjectsConfig,
  StyleConfig,
  TemplateConfig,
  UMCModuleKind,
} from './common'

export interface BasePosterConfig {
  schemaVersion: '1.0.0'
  moduleKind: UMCModuleKind
  title: string
  createdAtIso: string
  location: LocationConfig
  template: TemplateConfig
  style: StyleConfig
  objects: ObjectsConfig
}

export interface CityPosterConfig extends BasePosterConfig {
  moduleKind: 'city-map'
  city: {
    placeId?: string
    boundaryMode: 'district' | 'city' | 'metro'
    language: string
  }
}

export interface BuildingPosterConfig extends BasePosterConfig {
  moduleKind: 'building-map'
  building: {
    buildingId?: string
    levelOfDetail: 'block' | 'facade' | 'technical'
    showAnnotations: boolean
  }
}

export interface StarPosterConfig extends BasePosterConfig {
  moduleKind: 'star-map'
  star: {
    dateIso: string
    observerCity: string
    skyStyle: 'constellation' | 'deep-sky' | 'minimal'
  }
}

export type UMCPosterConfig =
  | CityPosterConfig
  | BuildingPosterConfig
  | StarPosterConfig
