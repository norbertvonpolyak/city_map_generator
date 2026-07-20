import { umcModuleDefinitions } from '../modules'
import type { PosterConfigEnvelope } from './interfaces'

export const cityPosterDocumentExample: PosterConfigEnvelope = {
  id: 'city-foundation-example',
  slug: 'city-map-foundation',
  document: {
    schema: 'umc.poster-config',
    version: '1.0.0',
    module: 'city-map',
    payload: umcModuleDefinitions['city-map'].defaults,
    metadata: {
      source: 'umc-foundation',
      notes: 'Static reference payload for architecture phase.',
    },
  },
}

export const buildingPosterDocumentExample: PosterConfigEnvelope = {
  id: 'building-foundation-example',
  slug: 'building-map-foundation',
  document: {
    schema: 'umc.poster-config',
    version: '1.0.0',
    module: 'building-map',
    payload: umcModuleDefinitions['building-map'].defaults,
    metadata: {
      source: 'umc-foundation',
      notes: 'Static reference payload for architecture phase.',
    },
  },
}
