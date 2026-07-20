import type { UMCModuleKind } from '../types'
import { buildingMapModuleDefinition } from './building-map.module'
import { cityMapModuleDefinition } from './city-map.module'
import type { UMCModuleDefinition } from './types'

export const umcModuleDefinitions: Record<UMCModuleKind, UMCModuleDefinition> = {
  'city-map': cityMapModuleDefinition,
  'building-map': buildingMapModuleDefinition,
}

export const umcModuleList: UMCModuleDefinition[] = Object.values(umcModuleDefinitions)
