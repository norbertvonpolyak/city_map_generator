export type UMCPreviewObjectType = 'marker' | 'heart' | 'star' | 'pin' | 'text'

export interface UMCPreviewPoint {
  x: number
  y: number
}

export interface UMCPreviewObject {
  id: string
  type: UMCPreviewObjectType
  label: string
  position: UMCPreviewPoint
  createdAtIso: string
}

export interface UMCPreviewViewportState {
  zoom: number
  pan: UMCPreviewPoint
}

export interface UMCPreviewDocument {
  viewport: UMCPreviewViewportState
  objects: UMCPreviewObject[]
}
