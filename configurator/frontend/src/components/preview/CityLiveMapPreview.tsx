import { useEffect, useRef } from 'react'
import type { MutableRefObject } from 'react'
import { MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

interface PreviewPoint {
  x: number
  y: number
}

interface CityLiveMapPreviewProps {
  latitude: number | null
  longitude: number | null
  radiusKm: number
  posterAspectRatio: number
  onCenterChange?: (latitude: number, longitude: number) => void
  onPlacementClick?: (point: PreviewPoint) => void
}

const BUDAPEST_CENTER: [number, number] = [47.4979, 19.0402]

const clamp = (value: number, min: number, max: number): number => {
  return Math.min(max, Math.max(min, value))
}

const radiusToZoom = (radiusKm: number): number => {
  const safeRadius = Math.max(radiusKm, 1)
  const computedZoom = 14.5 - Math.log2(safeRadius)
  return clamp(computedZoom, 2.2, 14.6)
}

interface FlyToControllerProps {
  latitude: number | null
  longitude: number | null
  radiusKm: number
  posterAspectRatio: number
  syncLockUntilRef: MutableRefObject<number>
}

const FlyToController = ({ latitude, longitude, radiusKm, posterAspectRatio, syncLockUntilRef }: FlyToControllerProps) => {
  const map = useMap()
  const firstSyncDoneRef = useRef(false)

  useEffect(() => {
    const center: [number, number] = latitude != null && longitude != null
      ? [latitude, longitude]
      : BUDAPEST_CENTER
    const zoom = radiusToZoom(radiusKm)
    const distanceFromCurrentMeters = map.distance(map.getCenter(), {
      lat: center[0],
      lng: center[1],
    })
    const zoomDelta = Math.abs(map.getZoom() - zoom)

    if (!firstSyncDoneRef.current) {
      syncLockUntilRef.current = performance.now() + 240
      map.setView(center, zoom, { animate: false })
      firstSyncDoneRef.current = true
      return
    }

    if (distanceFromCurrentMeters < 20 && zoomDelta < 0.05) {
      return
    }

    syncLockUntilRef.current = performance.now() + 1450
    map.flyTo(center, zoom, {
      animate: true,
      duration: 1.15,
      easeLinearity: 0.2,
    })
  }, [latitude, longitude, map, posterAspectRatio, radiusKm, syncLockUntilRef])

  return null
}

interface PlacementClickBridgeProps {
  onPlacementClick?: (point: PreviewPoint) => void
}

const PlacementClickBridge = ({ onPlacementClick }: PlacementClickBridgeProps) => {
  const map = useMapEvents({
    click(event) {
      if (!onPlacementClick) {
        return
      }

      const size = map.getSize()
      const normalizedPoint: PreviewPoint = {
        x: ((event.containerPoint.x / size.x) * 380) - 190,
        y: ((event.containerPoint.y / size.y) * 380) - 190,
      }
      onPlacementClick(normalizedPoint)
    },
  })

  return null
}

interface CenterSyncBridgeProps {
  onCenterChange?: (latitude: number, longitude: number) => void
  syncLockUntilRef: MutableRefObject<number>
}

const CenterSyncBridge = ({ onCenterChange, syncLockUntilRef }: CenterSyncBridgeProps) => {
  const emitCenter = (mapInstance: ReturnType<typeof useMap>) => {
    if (!onCenterChange) {
      return
    }

    if (performance.now() < syncLockUntilRef.current) {
      return
    }

    const center = mapInstance.getCenter()
    onCenterChange(center.lat, center.lng)
  }

  const map = useMapEvents({
    moveend() {
      emitCenter(map)
    },
  })

  return null
}

export const CityLiveMapPreview = ({ latitude, longitude, radiusKm, posterAspectRatio, onCenterChange, onPlacementClick }: CityLiveMapPreviewProps) => {
  const syncLockUntilRef = useRef(0)

  const startCenter: [number, number] = latitude != null && longitude != null
    ? [latitude, longitude]
    : BUDAPEST_CENTER

  const initialBounds: [[number, number], [number, number]] = [
    [startCenter[0] - 0.24, startCenter[1] - (0.24 * posterAspectRatio)],
    [startCenter[0] + 0.24, startCenter[1] + (0.24 * posterAspectRatio)],
  ]

  return (
    <div className="umc-live-map" aria-label="Varosterkep elonezet">
      <MapContainer
        bounds={initialBounds}
        zoomControl={false}
        doubleClickZoom={false}
        attributionControl
        className="umc-live-map-canvas"
      >
        <TileLayer
          url="https://a.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png"
          maxZoom={18}
          attribution="&copy; OpenStreetMap contributors &copy; CARTO"
        />
        <FlyToController
          latitude={latitude}
          longitude={longitude}
          radiusKm={radiusKm}
          posterAspectRatio={posterAspectRatio}
          syncLockUntilRef={syncLockUntilRef}
        />
        <CenterSyncBridge onCenterChange={onCenterChange} syncLockUntilRef={syncLockUntilRef} />
        <PlacementClickBridge onPlacementClick={onPlacementClick} />
      </MapContainer>
    </div>
  )
}
