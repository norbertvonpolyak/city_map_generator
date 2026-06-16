import type { UMCModuleKind, UMCPosterConfig } from '../types'

export interface PosterConfigDocument<TPayload extends UMCPosterConfig = UMCPosterConfig> {
  schema: 'umc.poster-config'
  version: '1.0.0'
  module: UMCModuleKind
  payload: TPayload
  metadata: {
    source: 'umc-foundation'
    notes?: string
  }
}

export interface PosterConfigEnvelope {
  id: string
  slug: string
  document: PosterConfigDocument
}
