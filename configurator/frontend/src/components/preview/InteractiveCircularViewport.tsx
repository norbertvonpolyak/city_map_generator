import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  UMCModuleKind,
  UMCPreviewObject,
  UMCPreviewObjectType,
  UMCPreviewPoint,
  UMCPreviewViewportState,
} from '@umc-shared/types'
import { ModuleMockMapLayer } from './ModuleMockMapLayer'

interface InteractiveCircularViewportProps {
  moduleKind: UMCModuleKind
  title: string
  subtitle: string
  viewport: UMCPreviewViewportState
  placementType: UMCPreviewObjectType
  selectedObjectId: string | null
  objects: UMCPreviewObject[]
  cityPreviewSvg: string | null
  cityPreviewStatus: 'idle' | 'loading' | 'ready' | 'city-not-found' | 'failed'
  onViewportChange: (viewport: UMCPreviewViewportState) => void
  onViewportReset: () => void
  onAddObject: (type: UMCPreviewObjectType, point: UMCPreviewPoint) => void
  onMoveObject: (id: string, point: UMCPreviewPoint) => void
  onSelectObject: (id: string | null) => void
  onDeleteSelected: () => void
}

interface PointerInteraction {
  mode: 'pan' | 'drag'
  pointerId: number
  startScreen: UMCPreviewPoint
  startPan: UMCPreviewPoint
  objectId?: string
  startObjectPosition?: UMCPreviewPoint
}

const objectIcon: Record<UMCPreviewObjectType, string> = {
  marker: '●',
  heart: '❤',
  star: '★',
  pin: '📍',
  text: 'T',
}

const clampZoom = (value: number): number => {
  return Math.min(3.2, Math.max(0.6, value))
}

const pointFromEvent = (event: React.PointerEvent | React.MouseEvent): UMCPreviewPoint => {
  return { x: event.clientX, y: event.clientY }
}

export const InteractiveCircularViewport = ({
  moduleKind,
  title,
  subtitle,
  viewport,
  placementType,
  selectedObjectId,
  objects,
  cityPreviewSvg,
  cityPreviewStatus,
  onViewportChange,
  onViewportReset,
  onAddObject,
  onMoveObject,
  onSelectObject,
  onDeleteSelected,
}: InteractiveCircularViewportProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [spacePanning, setSpacePanning] = useState(false)
  const [interaction, setInteraction] = useState<PointerInteraction | null>(null)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.code === 'Space') {
        setSpacePanning(true)
      }
      if (event.key === 'Delete' || event.key === 'Backspace') {
        onDeleteSelected()
      }
    }

    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === 'Space') {
        setSpacePanning(false)
      }
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)

    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [onDeleteSelected])

  const viewportSummary = useMemo(() => {
    return `${Math.round(viewport.zoom * 100)}%`
  }, [viewport.zoom])

  const toWorldPoint = (screen: UMCPreviewPoint): UMCPreviewPoint | null => {
    const container = containerRef.current
    if (!container) {
      return null
    }

    const rect = container.getBoundingClientRect()
    const localX = screen.x - rect.left
    const localY = screen.y - rect.top
    const centerX = rect.width / 2
    const centerY = rect.height / 2

    return {
      x: (localX - centerX - viewport.pan.x) / viewport.zoom,
      y: (localY - centerY - viewport.pan.y) / viewport.zoom,
    }
  }

  const onWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault()

    const container = containerRef.current
    if (!container) {
      return
    }

    const rect = container.getBoundingClientRect()
    const cursorX = event.clientX - rect.left
    const cursorY = event.clientY - rect.top
    const centerX = rect.width / 2
    const centerY = rect.height / 2

    const zoomFactor = event.deltaY < 0 ? 1.08 : 0.92
    const nextZoom = clampZoom(viewport.zoom * zoomFactor)

    const worldX = (cursorX - centerX - viewport.pan.x) / viewport.zoom
    const worldY = (cursorY - centerY - viewport.pan.y) / viewport.zoom

    const nextPan = {
      x: cursorX - centerX - worldX * nextZoom,
      y: cursorY - centerY - worldY * nextZoom,
    }

    onViewportChange({ zoom: nextZoom, pan: nextPan })
  }

  const startPan = (event: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current
    if (!container) {
      return
    }

    container.setPointerCapture(event.pointerId)
    setInteraction({
      mode: 'pan',
      pointerId: event.pointerId,
      startScreen: pointFromEvent(event),
      startPan: viewport.pan,
    })
  }

  const onContainerPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button === 2 || spacePanning) {
      startPan(event)
      return
    }

    if (event.button !== 0) {
      return
    }

    if (event.target !== event.currentTarget) {
      return
    }

    const point = toWorldPoint(pointFromEvent(event))
    if (!point) {
      return
    }

    onAddObject(placementType, point)
  }

  const onObjectPointerDown = (event: React.PointerEvent<HTMLButtonElement>, object: UMCPreviewObject) => {
    if (event.button !== 0) {
      return
    }

    const container = containerRef.current
    if (!container) {
      return
    }

    event.stopPropagation()
    onSelectObject(object.id)
    container.setPointerCapture(event.pointerId)

    setInteraction({
      mode: 'drag',
      pointerId: event.pointerId,
      startScreen: pointFromEvent(event),
      startPan: viewport.pan,
      objectId: object.id,
      startObjectPosition: object.position,
    })
  }

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!interaction || interaction.pointerId !== event.pointerId) {
      return
    }

    const deltaX = event.clientX - interaction.startScreen.x
    const deltaY = event.clientY - interaction.startScreen.y

    if (interaction.mode === 'pan') {
      onViewportChange({
        zoom: viewport.zoom,
        pan: {
          x: interaction.startPan.x + deltaX,
          y: interaction.startPan.y + deltaY,
        },
      })
      return
    }

    if (interaction.mode === 'drag' && interaction.objectId && interaction.startObjectPosition) {
      onMoveObject(interaction.objectId, {
        x: interaction.startObjectPosition.x + deltaX / viewport.zoom,
        y: interaction.startObjectPosition.y + deltaY / viewport.zoom,
      })
    }
  }

  const clearInteraction = (event: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current
    if (container && interaction && interaction.pointerId === event.pointerId) {
      container.releasePointerCapture(event.pointerId)
    }
    setInteraction(null)
  }

  return (
    <div className="relative flex h-full flex-col rounded-3xl border border-[var(--umc-border)] bg-[linear-gradient(160deg,rgba(7,9,13,0.9),rgba(5,7,10,0.62))] p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-[var(--umc-gold)]">Interactive Preview</p>
          <h3 className="umc-serif text-2xl text-[var(--umc-ivory)] md:text-3xl">{title}</h3>
          <p className="mt-1 text-sm text-[var(--umc-ivory-soft)]">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onViewportChange({ zoom: clampZoom(viewport.zoom * 1.12), pan: viewport.pan })}
            className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.8)] px-3 py-1.5 text-sm text-[var(--umc-ivory)] transition hover:border-[var(--umc-gold-soft)]"
          >
            +
          </button>
          <button
            type="button"
            onClick={() => onViewportChange({ zoom: clampZoom(viewport.zoom * 0.88), pan: viewport.pan })}
            className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.8)] px-3 py-1.5 text-sm text-[var(--umc-ivory)] transition hover:border-[var(--umc-gold-soft)]"
          >
            -
          </button>
          <button
            type="button"
            onClick={onViewportReset}
            className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.8)] px-3 py-1.5 text-sm text-[var(--umc-ivory)] transition hover:border-[var(--umc-gold-soft)]"
          >
            Reset
          </button>
          <span className="rounded-lg border border-[var(--umc-border)] px-3 py-1.5 text-xs uppercase tracking-[0.16em] text-[var(--umc-ivory-soft)]">
            {viewportSummary}
          </span>
        </div>
      </div>

      <div className="relative flex flex-1 items-center justify-center overflow-hidden rounded-2xl border border-[var(--umc-border)] bg-[radial-gradient(circle_at_20%_20%,rgba(201,171,120,0.2),transparent_42%),radial-gradient(circle_at_72%_12%,rgba(126,235,226,0.16),transparent_38%),linear-gradient(150deg,#070a11,#040507)]">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(233,226,212,0.08),transparent_62%)]" />
        <div className="pointer-events-none absolute h-[76vmin] w-[76vmin] max-h-[780px] max-w-[780px] rounded-full border border-[rgba(201,171,120,0.28)]" />

        <div
          ref={containerRef}
          className="relative aspect-square w-[min(76vmin,760px)] overflow-hidden rounded-full border border-[rgba(233,226,212,0.5)] bg-[radial-gradient(circle_at_35%_22%,rgba(126,235,226,0.14),transparent_44%),radial-gradient(circle_at_68%_80%,rgba(201,171,120,0.2),transparent_45%),rgba(4,6,10,0.95)] shadow-[0_28px_80px_rgba(0,0,0,0.55)]"
          onPointerDown={onContainerPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={clearInteraction}
          onPointerCancel={clearInteraction}
          onWheel={onWheel}
          onContextMenu={(event) => event.preventDefault()}
        >
          <div
            className="absolute inset-0"
            style={{
              transform: `translate(${viewport.pan.x}px, ${viewport.pan.y}px) scale(${viewport.zoom})`,
              transformOrigin: '50% 50%',
            }}
          >
            {moduleKind === 'city-map' ? (
              <>
                {cityPreviewSvg ? (
                  <div
                    className="umc-city-preview absolute inset-0 pointer-events-none"
                    aria-hidden="true"
                    dangerouslySetInnerHTML={{ __html: cityPreviewSvg }}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center px-6 text-center pointer-events-none">
                    {cityPreviewStatus === 'loading' ? (
                      <div className="rounded-2xl border border-[var(--umc-border)] bg-[rgba(7,9,13,0.82)] px-5 py-4 text-sm text-[var(--umc-ivory-soft)] shadow-[0_20px_50px_rgba(0,0,0,0.35)]">
                        Loading Preview...
                      </div>
                    ) : cityPreviewStatus === 'city-not-found' ? (
                      <div className="rounded-2xl border border-[rgba(220,90,90,0.45)] bg-[rgba(110,28,28,0.4)] px-5 py-4 text-sm text-[rgb(242,183,183)] shadow-[0_20px_50px_rgba(0,0,0,0.35)]">
                        City Not Found
                      </div>
                    ) : cityPreviewStatus === 'failed' ? (
                      <div className="rounded-2xl border border-[rgba(220,90,90,0.45)] bg-[rgba(110,28,28,0.4)] px-5 py-4 text-sm text-[rgb(242,183,183)] shadow-[0_20px_50px_rgba(0,0,0,0.35)]">
                        Preview Generation Failed
                      </div>
                    ) : (
                      <div className="max-w-[18rem] rounded-2xl border border-[var(--umc-border)] bg-[rgba(7,9,13,0.82)] px-5 py-4 text-sm text-[var(--umc-ivory-soft)] shadow-[0_20px_50px_rgba(0,0,0,0.35)]">
                        Generate Preview to render the real city SVG here.
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <ModuleMockMapLayer moduleKind={moduleKind} />
            )}
            <div className="absolute inset-[10%] rounded-full border border-dashed border-[rgba(233,226,212,0.2)]" />
            <div className="absolute inset-[23%] rounded-full border border-[rgba(201,171,120,0.18)]" />

            {objects.map((object) => {
              const selected = object.id === selectedObjectId

              return (
                <button
                  key={object.id}
                  type="button"
                  onPointerDown={(event) => onObjectPointerDown(event, object)}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelectObject(object.id)
                  }}
                  className={[
                    'absolute -translate-x-1/2 -translate-y-1/2 rounded-full border px-3 py-1 text-sm shadow-[0_10px_22px_rgba(0,0,0,0.4)] transition',
                    selected
                      ? 'border-[var(--umc-gold)] bg-[rgba(201,171,120,0.24)] text-[var(--umc-ivory)]'
                      : 'border-[var(--umc-border)] bg-[rgba(7,9,13,0.76)] text-[var(--umc-ivory-soft)] hover:border-[var(--umc-gold-soft)] hover:text-[var(--umc-ivory)]',
                  ].join(' ')}
                  style={{
                    left: `calc(50% + ${object.position.x}px)`,
                    top: `calc(50% + ${object.position.y}px)`,
                  }}
                >
                  <span className="mr-1">{objectIcon[object.type]}</span>
                  <span>{object.label}</span>
                </button>
              )
            })}
          </div>

          <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-[var(--umc-border)] bg-[rgba(6,8,12,0.82)] px-4 py-1.5 text-xs uppercase tracking-[0.16em] text-[var(--umc-ivory-soft)]">
            Right-click or hold Space to pan • Wheel to zoom
          </div>
        </div>
      </div>
    </div>
  )
}
