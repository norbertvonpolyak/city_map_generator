import type { UMCPosterConfig, UMCSectionId, UMCModuleKind } from '../types'

export interface UMCModuleDefinition<TConfig extends UMCPosterConfig = UMCPosterConfig> {
  kind: UMCModuleKind
  label: string
  tagline: string
  previewHint: string
  availableSections: UMCSectionId[]
  defaults: TConfig
  status: 'foundation'
}
