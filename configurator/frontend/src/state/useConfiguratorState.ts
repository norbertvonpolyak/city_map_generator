import { useMemo, useState } from 'react'
import { umcModuleDefinitions } from '@umc-shared/modules'
import type { UMCPreviewObject } from '@umc-shared/types'
import type { UMCPreviewObjectType } from '@umc-shared/types'
import type { UMCPreviewPoint } from '@umc-shared/types'
import type { UMCPreviewViewportState } from '@umc-shared/types'
import type { UMCPosterConfig } from '@umc-shared/types'
import type { UMCModuleKind } from '@umc-shared/types'
import type { UMCPosterTypographyStyle } from '@umc-shared/types'
import { huObjectTypeLabels, huUiText } from '../content/hu'
import { generateCityPreview as fetchCityPreview } from '../services/cityPreviewApi'
import type { SelectedLocation } from '../services/locationSearch'

export interface ConfiguratorState {
  activeModule: UMCModuleKind
  activeConfig: UMCPosterConfig
  previewViewport: UMCPreviewViewportState
  previewObjects: UMCPreviewObject[]
  selectedObjectId: string | null
  placementType: UMCPreviewObjectType
  cityPreviewSvg: string | null
  cityPreviewStatus: 'idle' | 'loading' | 'ready' | 'city-not-found' | 'failed'
  cityPreviewError: string | null
  printSizeId: string
  setActiveModule: (moduleKind: UMCModuleKind) => void
  setTitle: (title: string) => void
  setLocationQuery: (query: string) => void
  setSelectedLocation: (location: SelectedLocation) => void
  setLocationCoordinates: (latitude: number, longitude: number) => void
  setTemplateId: (templateId: string) => void
  setPaletteId: (paletteId: string) => void
  setTypographyStyle: (typographyStyle: UMCPosterTypographyStyle) => void
  setStarDateIso: (dateIso: string) => void
  setStarSkyStyle: (skyStyle: 'constellation' | 'minimal') => void
  toggleObject: (key: keyof UMCPosterConfig['objects']) => void
  setPlacementType: (type: UMCPreviewObjectType) => void
  setPreviewViewport: (viewport: UMCPreviewViewportState) => void
  resetPreviewViewport: () => void
  generateCityPreview: () => Promise<void>
  addObjectAtPoint: (type: UMCPreviewObjectType, point: UMCPreviewPoint) => void
  moveObject: (id: string, point: UMCPreviewPoint) => void
  selectObject: (id: string | null) => void
  deleteObject: (id: string) => void
  deleteSelectedObject: () => void
  setPrintSizeId: (sizeId: string) => void
}

const cloneConfig = <T,>(value: T): T => {
  return JSON.parse(JSON.stringify(value)) as T
}

const defaultViewport: UMCPreviewViewportState = {
  zoom: 1,
  pan: { x: 0, y: 0 },
}

const roundCoordinate = (value: number): number => {
  return Math.round(value * 1_000_000) / 1_000_000
}

const objectDisplayNames: Record<UMCPreviewObjectType, string> = huObjectTypeLabels

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
      createObject('heart', 1, { x: -96, y: -40 }, huUiText.mockLabels.firstDate),
      createObject('pin', 2, { x: 48, y: 64 }, huUiText.mockLabels.firstHome),
      createObject('star', 3, { x: 108, y: -92 }, huUiText.mockLabels.proposal),
    ]
  }

  if (moduleKind === 'building-map') {
    return [
      createObject('marker', 1, { x: -88, y: 26 }, huUiText.mockLabels.mainEntrance),
      createObject('text', 2, { x: 66, y: -62 }, huUiText.mockLabels.skylineFocus),
    ]
  }

  return [
    createObject('text', 1, { x: 0, y: 0 }, huUiText.mockLabels.anniversaryNight),
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
  const [cityPreviewSvg, setCityPreviewSvg] = useState<string | null>(null)
  const [cityPreviewStatus, setCityPreviewStatus] = useState<'idle' | 'loading' | 'ready' | 'city-not-found' | 'failed'>('idle')
  const [cityPreviewError, setCityPreviewError] = useState<string | null>(null)
  const [printSizeId, setPrintSizeIdState] = useState<string>('50x70')

  const setPrintSizeId = (sizeId: string) => setPrintSizeIdState(sizeId)

  const setActiveModule = (moduleKind: UMCModuleKind) => {
    setActiveModuleState(moduleKind)
    setActiveConfig(cloneConfig(umcModuleDefinitions[moduleKind].defaults))
    setPreviewViewportState(defaultViewport)
    setPreviewObjects(createModuleMockObjects(moduleKind))
    setSelectedObjectId(null)
    setCityPreviewSvg(null)
    setCityPreviewStatus('idle')
    setCityPreviewError(null)
  }

  const setTitle = (title: string) => {
    setActiveConfig((current) => ({ ...current, title }))
  }

  const setLocationQuery = (query: string) => {
    setActiveConfig((current) => ({
      ...current,
      location: { ...current.location, query },
    }))
    if (activeModule === 'city-map') {
      setCityPreviewSvg(null)
      setCityPreviewStatus('idle')
      setCityPreviewError(null)
    }
  }

  const setSelectedLocation = (location: SelectedLocation) => {
    setActiveConfig((current) => ({
      ...current,
      location: {
        ...current.location,
        query: location.displayName,
        latitude: location.lat,
        longitude: location.lon,
      },
    }))
    if (activeModule === 'city-map') {
      setCityPreviewSvg(null)
      setCityPreviewStatus('idle')
      setCityPreviewError(null)
    }
  }

  const setLocationCoordinates = (latitude: number, longitude: number) => {
    const roundedLat = roundCoordinate(latitude)
    const roundedLon = roundCoordinate(longitude)

    let changed = false
    setActiveConfig((current) => {
      if (current.location.latitude === roundedLat && current.location.longitude === roundedLon) {
        return current
      }

      changed = true
      return {
        ...current,
        location: {
          ...current.location,
          latitude: roundedLat,
          longitude: roundedLon,
        },
      }
    })

    if (changed && activeModule === 'city-map') {
      setCityPreviewSvg(null)
      setCityPreviewStatus('idle')
      setCityPreviewError(null)
    }
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

  const setTypographyStyle = (typographyStyle: UMCPosterTypographyStyle) => {
    setActiveConfig((current) => ({
      ...current,
      style: { ...current.style, typographyStyle },
    }))
  }

  const setStarDateIso = (dateIso: string) => {
    setActiveConfig((current) => {
      if (current.moduleKind !== 'star-map') {
        return current
      }
      return {
        ...current,
        star: {
          ...current.star,
          dateIso,
        },
      }
    })
  }

  const setStarSkyStyle = (skyStyle: 'constellation' | 'minimal') => {
    setActiveConfig((current) => {
      if (current.moduleKind !== 'star-map') {
        return current
      }
      return {
        ...current,
        star: {
          ...current.star,
          skyStyle,
        },
      }
    })
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

  const generateCityPreview = async () => {
    if (activeModule !== 'city-map') {
      return
    }

    const city = activeConfig.location.query.trim()
    if (!city) {
      setCityPreviewSvg(null)
      setCityPreviewStatus('failed')
      setCityPreviewError(huUiText.enterCityFirst)
      return
    }

    setCityPreviewStatus('loading')
    setCityPreviewError(null)

    try {
      const assets = await fetchCityPreview({
        city,
        style: 'minimal',
        latitude: activeConfig.location.latitude,
        longitude: activeConfig.location.longitude,
        sizeKey: printSizeId,
        extentM: Math.round(radiusKm * 1000),
      })
      setCityPreviewSvg(assets.svg)
      setCityPreviewStatus('ready')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Preview Generation Failed'
      setCityPreviewSvg(null)
      setCityPreviewError(message)
      setCityPreviewStatus(message === 'City Not Found' ? 'city-not-found' : 'failed')
    }
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
      cityPreviewSvg,
      cityPreviewStatus,
      cityPreviewError,
      printSizeId,
      setActiveModule,
      setTitle,
      setLocationQuery,
      setSelectedLocation,
      setLocationCoordinates,
      setTemplateId,
      setPaletteId,
      setTypographyStyle,
      setStarDateIso,
      setStarSkyStyle,
      toggleObject,
      setPlacementType,
      setPreviewViewport,
      resetPreviewViewport,
      generateCityPreview,
      addObjectAtPoint,
      moveObject,
      selectObject,
      deleteObject,
      deleteSelectedObject,
      setPrintSizeId,
    }),
    [
      activeConfig,
      activeModule,
      cityPreviewError,
      cityPreviewSvg,
      cityPreviewStatus,
      printSizeId,
      placementType,
      previewObjects,
      previewViewport,
      selectedObjectId,
      setStarDateIso,
      setStarSkyStyle,
    ],
  )
}
