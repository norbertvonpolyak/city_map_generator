import { useMemo, useState } from 'react'
import { umcModuleDefinitions } from '@umc-shared/modules'
import type { UMCPreviewObject } from '@umc-shared/types'
import type { UMCPreviewObjectType } from '@umc-shared/types'
import type { UMCPreviewPoint } from '@umc-shared/types'
import type { UMCPreviewViewportState } from '@umc-shared/types'
import type { UMCPosterConfig } from '@umc-shared/types'
import type { UMCModuleKind } from '@umc-shared/types'

export interface ConfiguratorState {
  activeModule: UMCModuleKind
  activeConfig: UMCPosterConfig
  previewViewport: UMCPreviewViewportState
  previewObjects: UMCPreviewObject[]
  selectedObjectId: string | null
  placementType: UMCPreviewObjectType
  setActiveModule: (moduleKind: UMCModuleKind) => void
  setTitle: (title: string) => void
  setLocationQuery: (query: string) => void
  setTemplateId: (templateId: string) => void
  setPaletteId: (paletteId: string) => void
  toggleObject: (key: keyof UMCPosterConfig['objects']) => void
  setPlacementType: (type: UMCPreviewObjectType) => void
  setPreviewViewport: (viewport: UMCPreviewViewportState) => void
  resetPreviewViewport: () => void
  addObjectAtPoint: (type: UMCPreviewObjectType, point: UMCPreviewPoint) => void
  moveObject: (id: string, point: UMCPreviewPoint) => void
  selectObject: (id: string | null) => void
  deleteObject: (id: string) => void
  deleteSelectedObject: () => void
}

const cloneConfig = <T,>(value: T): T => {
  return JSON.parse(JSON.stringify(value)) as T
}

const defaultViewport: UMCPreviewViewportState = {
  zoom: 1,
  pan: { x: 0, y: 0 },
}

const objectDisplayNames: Record<UMCPreviewObjectType, string> = {
  marker: 'Marker',
  heart: 'Heart',
  star: 'Star',
  pin: 'Pin',
  text: 'Text',
}

const createObject = (
  type: UMCPreviewObjectType,
  index: number,
  point: UMCPreviewPoint,
  label?: string,
): UMCPreviewObject => {
  const id = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

  return {
    id,
    type,
    label: label ?? `${objectDisplayNames[type]} ${index}`,
    position: point,
    createdAtIso: new Date().toISOString(),
  }
}

const createModuleMockObjects = (moduleKind: UMCModuleKind): UMCPreviewObject[] => {
  if (moduleKind === 'city-map') {
    return [
      createObject('heart', 1, { x: -96, y: -40 }, 'First Date'),
      createObject('pin', 2, { x: 48, y: 64 }, 'First Home'),
      createObject('star', 3, { x: 108, y: -92 }, 'Proposal'),
    ]
  }

  if (moduleKind === 'building-map') {
    return [
      createObject('marker', 1, { x: -88, y: 26 }, 'Main Entrance'),
      createObject('text', 2, { x: 66, y: -62 }, 'Skyline Focus'),
    ]
  }

  return [
    createObject('star', 1, { x: -38, y: -68 }, 'Birthday Star'),
    createObject('heart', 2, { x: 44, y: 72 }, 'Anniversary Night'),
  ]
}

export const useConfiguratorState = (): ConfiguratorState => {
  const [activeModule, setActiveModuleState] = useState<UMCModuleKind>('city-map')
  const [activeConfig, setActiveConfig] = useState<UMCPosterConfig>(() => {
    return cloneConfig(umcModuleDefinitions['city-map'].defaults)
  })
  const [previewViewport, setPreviewViewportState] = useState<UMCPreviewViewportState>(defaultViewport)
  const [previewObjects, setPreviewObjects] = useState<UMCPreviewObject[]>(() => {
    return createModuleMockObjects('city-map')
  })
  const [selectedObjectId, setSelectedObjectId] = useState<string | null>(null)
  const [placementType, setPlacementType] = useState<UMCPreviewObjectType>('pin')

  const setActiveModule = (moduleKind: UMCModuleKind) => {
    setActiveModuleState(moduleKind)
    setActiveConfig(cloneConfig(umcModuleDefinitions[moduleKind].defaults))
    setPreviewViewportState(defaultViewport)
    setPreviewObjects(createModuleMockObjects(moduleKind))
    setSelectedObjectId(null)
  }

  const setTitle = (title: string) => {
    setActiveConfig((current) => ({ ...current, title }))
  }

  const setLocationQuery = (query: string) => {
    setActiveConfig((current) => ({
      ...current,
      location: { ...current.location, query },
    }))
  }

  const setTemplateId = (templateId: string) => {
    setActiveConfig((current) => ({
      ...current,
      template: { ...current.template, templateId },
    }))
  }

  const setPaletteId = (paletteId: string) => {
    setActiveConfig((current) => ({
      ...current,
      style: { ...current.style, paletteId },
    }))
  }

  const toggleObject = (key: keyof UMCPosterConfig['objects']) => {
    setActiveConfig((current) => ({
      ...current,
      objects: {
        ...current.objects,
        [key]: !current.objects[key],
      },
    }))
  }

  const setPreviewViewport = (viewport: UMCPreviewViewportState) => {
    setPreviewViewportState(viewport)
  }

  const resetPreviewViewport = () => {
    setPreviewViewportState(defaultViewport)
  }

  const addObjectAtPoint = (type: UMCPreviewObjectType, point: UMCPreviewPoint) => {
    let nextObjectId = ''
    setPreviewObjects((current) => {
      const typedCount = current.filter((item) => item.type === type).length + 1
      const nextObject = createObject(type, typedCount, point)
      nextObjectId = nextObject.id
      return [...current, nextObject]
    })
    if (nextObjectId) {
      setSelectedObjectId(nextObjectId)
    }
  }

  const moveObject = (id: string, point: UMCPreviewPoint) => {
    setPreviewObjects((current) => {
      return current.map((item) => {
        if (item.id !== id) {
          return item
        }
        return { ...item, position: point }
      })
    })
  }

  const selectObject = (id: string | null) => {
    setSelectedObjectId(id)
  }

  const deleteObject = (id: string) => {
    setPreviewObjects((current) => current.filter((item) => item.id !== id))
    setSelectedObjectId((current) => (current === id ? null : current))
  }

  const deleteSelectedObject = () => {
    if (!selectedObjectId) {
      return
    }
    deleteObject(selectedObjectId)
  }

  return useMemo(
    () => ({
      activeModule,
      activeConfig,
      previewViewport,
      previewObjects,
      selectedObjectId,
      placementType,
      setActiveModule,
      setTitle,
      setLocationQuery,
      setTemplateId,
      setPaletteId,
      toggleObject,
      setPlacementType,
      setPreviewViewport,
      resetPreviewViewport,
      addObjectAtPoint,
      moveObject,
      selectObject,
      deleteObject,
      deleteSelectedObject,
    }),
    [activeConfig, activeModule, placementType, previewObjects, previewViewport, selectedObjectId],
  )
}
