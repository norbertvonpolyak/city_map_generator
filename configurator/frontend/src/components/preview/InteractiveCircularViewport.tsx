import { useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type {
  UMCModuleKind,
  UMCPreviewObject,
  UMCPreviewObjectType,
  UMCPreviewPoint,
  UMCPosterTypographyStyle,
  UMCPreviewViewportState,
} from '@umc-shared/types'
import { huUiText } from '../../content/hu'
import { CityLiveMapPreview } from './CityLiveMapPreview'
import { ModuleMockMapLayer } from './ModuleMockMapLayer'

interface InteractiveCircularViewportProps {
  moduleKind: UMCModuleKind
  title: string
  subtitle: string
  posterSubtitle: string
  posterDate: string
  posterCustomText: string
  titleTextAppearance: TextAppearanceSettings
  subtitleTextAppearance: TextAppearanceSettings
  dateTextAppearance: TextAppearanceSettings
  customTextAppearance: TextAppearanceSettings
  typographyStyle: UMCPosterTypographyStyle
  styleSummary: string
  viewport: UMCPreviewViewportState
  placementType: UMCPreviewObjectType
  selectedObjectId: string | null
  objects: UMCPreviewObject[]
  cityPreviewSvg: string | null
  cityPreviewStatus: 'idle' | 'loading' | 'ready' | 'city-not-found' | 'failed'
  hasUserSelectedCityLocation: boolean
  locationLatitude: number | null
  locationLongitude: number | null
  radiusKm: number
  onLocationCenterChange: (latitude: number, longitude: number) => void
  frameOption: 'none' | 'wood-brown' | 'black' | 'white'
  onViewportChange: (viewport: UMCPreviewViewportState) => void
  onViewportReset: () => void
  onAddObject: (type: UMCPreviewObjectType, point: UMCPreviewPoint) => void
  onMoveObject: (id: string, point: UMCPreviewPoint) => void
  onSelectObject: (id: string | null) => void
  onDeleteSelected: () => void
  onTextFieldFocus: (field: 'title' | 'subtitle' | 'date' | 'custom') => void
  posterAspectRatio: number
  visibleMapAspectRatio: number
  sideMarginRatio: number
  topMarginRatio: number
  bottomBandRatio: number
  fadeHeightRatio: number
  passepartoutColor: string
  fadeColor: string
  useMinimalCityFade: boolean
  cityPlaceholderImageSrc: string | null
}

interface TextAppearanceSettings {
  scale: number
  positionY: number
  variant: 'normal' | 'italic'
  weight: '500' | '700' | '900'
  fontFamily: 'manrope' | 'montserrat' | 'poppins' | 'lora'
  tone: 'black' | 'gray' | 'brown'
}

const objectIcon: Record<UMCPreviewObjectType, string> = {
  marker: '●',
  heart: '❤',
  star: '★',
  pin: '📍',
  text: 'T',
}

interface DragState {
  pointerId: number
  objectId: string
  startScreen: UMCPreviewPoint
  startObject: UMCPreviewPoint
}

const toCanvasPoint = (container: HTMLDivElement, screen: UMCPreviewPoint): UMCPreviewPoint => {
  const rect = container.getBoundingClientRect()
  const localX = Math.min(Math.max(screen.x - rect.left, 0), rect.width)
  const localY = Math.min(Math.max(screen.y - rect.top, 0), rect.height)

  return {
    x: ((localX / rect.width) * 380) - 190,
    y: ((localY / rect.height) * 380) - 190,
  }
}

const toneByOption: Record<'black' | 'gray' | 'brown', string> = {
  black: '#20201f',
  gray: '#57534d',
  brown: '#70573b',
}

const fontByOption: Record<'manrope' | 'montserrat' | 'poppins' | 'lora', string> = {
  manrope: "'Manrope', 'Segoe UI', sans-serif",
  montserrat: "'Montserrat', 'Manrope', 'Segoe UI', sans-serif",
  poppins: "'Poppins', 'Manrope', 'Segoe UI', sans-serif",
  lora: "'Lora', Georgia, serif",
}

export const InteractiveCircularViewport = ({
  moduleKind,
  title,
  subtitle,
  posterSubtitle,
  posterDate,
  posterCustomText,
  titleTextAppearance,
  subtitleTextAppearance,
  dateTextAppearance,
  customTextAppearance,
  typographyStyle,
  styleSummary,
  viewport: _viewport,
  placementType,
  selectedObjectId,
  objects,
  cityPreviewSvg,
  cityPreviewStatus,
  hasUserSelectedCityLocation,
  locationLatitude,
  locationLongitude,
  radiusKm,
  onLocationCenterChange,
  frameOption,
  onViewportChange: _onViewportChange,
  onViewportReset: _onViewportReset,
  onAddObject,
  onMoveObject,
  onSelectObject,
  onDeleteSelected,
  onTextFieldFocus,
  posterAspectRatio,
  visibleMapAspectRatio,
  sideMarginRatio,
  topMarginRatio,
  bottomBandRatio,
  fadeHeightRatio,
  passepartoutColor,
  fadeColor,
  useMinimalCityFade,
  cityPlaceholderImageSrc,
}: InteractiveCircularViewportProps) => {
  const canvasRef = useRef<HTMLDivElement | null>(null)
  const [dragState, setDragState] = useState<DragState | null>(null)

  const markerObjects = useMemo(() => {
    return objects.filter((item) => item.type !== 'text')
  }, [objects])

  const textObjects = useMemo(() => {
    return objects.filter((item) => item.type === 'text')
  }, [objects])

  const frameClass = useMemo(() => {
    if (frameOption === 'none') {
      return 'umc-frame umc-frame-none'
    }
    if (frameOption === 'wood-brown') {
      return 'umc-frame umc-frame-wood'
    }
    if (frameOption === 'white') {
      return 'umc-frame umc-frame-white'
    }
    return 'umc-frame umc-frame-black'
  }, [frameOption])

  const urbanCustomLabel = useMemo(() => {
    const value = posterCustomText.trim()
    return value.length > 0 ? value : null
  }, [posterCustomText])

  const onCanvasPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) {
      return
    }

    if (event.target !== event.currentTarget) {
      return
    }

    if (placementType === 'text') {
      return
    }

    if (moduleKind === 'star-map') {
      return
    }

    const container = canvasRef.current
    if (!container) {
      return
    }

    const point = toCanvasPoint(container, { x: event.clientX, y: event.clientY })
    onAddObject(placementType, point)
  }

  const onMarkerPointerDown = (event: React.PointerEvent<HTMLButtonElement>, object: UMCPreviewObject) => {
    if (event.button !== 0 || object.type === 'text') {
      return
    }

    const container = canvasRef.current
    if (!container) {
      return
    }

    event.stopPropagation()
    onSelectObject(object.id)
    container.setPointerCapture(event.pointerId)

    setDragState({
      pointerId: event.pointerId,
      objectId: object.id,
      startScreen: { x: event.clientX, y: event.clientY },
      startObject: object.position,
    })
  }

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return
    }

    const container = canvasRef.current
    if (!container) {
      return
    }

    const rect = container.getBoundingClientRect()
    const unitX = 380 / rect.width
    const unitY = 380 / rect.height

    onMoveObject(dragState.objectId, {
      x: dragState.startObject.x + (event.clientX - dragState.startScreen.x) * unitX,
      y: dragState.startObject.y + (event.clientY - dragState.startScreen.y) * unitY,
    })
  }

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    const container = canvasRef.current
    if (container && dragState && dragState.pointerId === event.pointerId) {
      container.releasePointerCapture(event.pointerId)
    }
    setDragState(null)
  }

  const posterTypeStyle = useMemo(() => {
    const source = titleTextAppearance
    return {
      '--umc-type-scale': String(source.scale),
      '--umc-type-style': source.variant,
      '--umc-type-weight': source.weight,
      '--umc-type-font': fontByOption[source.fontFamily],
      '--umc-type-color': toneByOption[source.tone],
      '--umc-type-offset-y': `${source.positionY}px`,
    } as CSSProperties
  }, [titleTextAppearance])

  const subtitleTypeStyle = useMemo(() => {
    return {
      '--umc-type-scale': String(subtitleTextAppearance.scale),
      '--umc-type-style': subtitleTextAppearance.variant,
      '--umc-type-weight': subtitleTextAppearance.weight,
      '--umc-type-font': fontByOption[subtitleTextAppearance.fontFamily],
      '--umc-type-color': toneByOption[subtitleTextAppearance.tone],
      '--umc-type-offset-y': `${subtitleTextAppearance.positionY}px`,
    } as CSSProperties
  }, [subtitleTextAppearance])

  const dateTypeStyle = useMemo(() => {
    return {
      '--umc-type-scale': String(dateTextAppearance.scale),
      '--umc-type-style': dateTextAppearance.variant,
      '--umc-type-weight': dateTextAppearance.weight,
      '--umc-type-font': fontByOption[dateTextAppearance.fontFamily],
      '--umc-type-color': toneByOption[dateTextAppearance.tone],
      '--umc-type-offset-y': `${dateTextAppearance.positionY}px`,
    } as CSSProperties
  }, [dateTextAppearance])

  const customTypeStyle = useMemo(() => {
    return {
      '--umc-type-scale': String(customTextAppearance.scale),
      '--umc-type-style': customTextAppearance.variant,
      '--umc-type-weight': customTextAppearance.weight,
      '--umc-type-font': fontByOption[customTextAppearance.fontFamily],
      '--umc-type-color': toneByOption[customTextAppearance.tone],
      '--umc-type-offset-y': `${customTextAppearance.positionY}px`,
    } as CSSProperties
  }, [customTextAppearance])

  const cityHasComposedPoster = moduleKind === 'city-map' && !!cityPreviewSvg
  const shouldShowCityPlaceholder = useMinimalCityFade && !cityHasComposedPoster && !hasUserSelectedCityLocation && !!cityPlaceholderImageSrc
  const shouldRenderFullPosterAsset = cityHasComposedPoster || shouldShowCityPlaceholder
  const cityFallbackLayoutStyle = useMemo(() => {
    return {
      '--umc-city-side-margin': `${sideMarginRatio * 100}%`,
      '--umc-city-top-margin': `${topMarginRatio * 100}%`,
      '--umc-city-bottom-band': `${bottomBandRatio * 100}%`,
      '--umc-city-fade-height': `${fadeHeightRatio * 100}%`,
      '--umc-city-passepartout-color': passepartoutColor,
      '--umc-city-fade-color': fadeColor,
    } as CSSProperties
  }, [bottomBandRatio, fadeColor, fadeHeightRatio, passepartoutColor, sideMarginRatio, topMarginRatio])

  const fallbackCanvas = shouldShowCityPlaceholder
    ? (
        <div className="umc-city-placeholder-sheet">
          <img
            src={cityPlaceholderImageSrc ?? undefined}
            alt={styleSummary}
            className="umc-city-placeholder-image"
          />
        </div>
      )
    : moduleKind === 'city-map'
    ? (
        <div className="umc-city-fallback-sheet" style={cityFallbackLayoutStyle}>
          <div className="umc-city-fallback-map-shell">
            <div
              ref={canvasRef}
              className="umc-poster-art"
              onPointerDown={onCanvasPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
              onClick={() => onSelectObject(null)}
            >
              <CityLiveMapPreview
                latitude={locationLatitude}
                longitude={locationLongitude}
                radiusKm={radiusKm}
                posterAspectRatio={visibleMapAspectRatio}
                onCenterChange={onLocationCenterChange}
              />

              {cityPreviewStatus === 'loading' ? (
                <div className="umc-preview-loading-overlay" role="status" aria-live="polite">
                  <span className="umc-preview-loading-spinner" aria-hidden="true" />
                  <div className="umc-preview-loading-copy">
                    <strong>{huUiText.renderInProgressTitle}</strong>
                    <span>{huUiText.renderInProgressHint}</span>
                  </div>
                </div>
              ) : null}

              {cityPreviewStatus !== 'idle' && cityPreviewStatus !== 'loading' && !cityPreviewSvg ? (
                <div className="umc-preview-status-badge">
                  {cityPreviewStatus === 'city-not-found'
                    ? huUiText.previewStatusCityNotFound
                    : huUiText.previewStatusFailed}
                </div>
              ) : null}
            </div>
          </div>

          <div className={useMinimalCityFade ? 'umc-city-fallback-bottom-band umc-city-fallback-bottom-band-minimal' : 'umc-city-fallback-bottom-band'}>
            {typographyStyle === 'urban' ? (
              <div className="umc-poster-typo umc-poster-typo-urban" style={posterTypeStyle}>
                <div className="umc-poster-urban-accent" aria-hidden="true" />
                <div className="umc-poster-urban-copy">
                  <h2 className="umc-poster-title umc-preview-text-clickable" onClick={() => onTextFieldFocus('title')}>{title || huUiText.defaultPosterTitle}</h2>
                  <p className="umc-poster-subtitle umc-preview-text-clickable" style={subtitleTypeStyle} onClick={() => onTextFieldFocus('subtitle')}>{posterSubtitle || subtitle || huUiText.defaultPosterSubtitle}</p>
                  {urbanCustomLabel ? (
                    <p className="umc-poster-urban-coordinates umc-preview-text-clickable" style={customTypeStyle} onClick={() => onTextFieldFocus('custom')}>{urbanCustomLabel}</p>
                  ) : null}
                  {posterDate ? <p className="umc-poster-meta umc-preview-text-clickable" style={dateTypeStyle} onClick={() => onTextFieldFocus('date')}>{posterDate}</p> : null}
                </div>
              </div>
            ) : typographyStyle === 'nordic' ? (
              <div className="umc-poster-typo umc-poster-typo-nordic" style={posterTypeStyle}>
                <h2 className="umc-poster-title umc-preview-text-clickable" onClick={() => onTextFieldFocus('title')}>{title || huUiText.defaultPosterTitle}</h2>
                <div className="umc-poster-nordic-subline">
                  <span className="umc-poster-nordic-line" aria-hidden="true" />
                  <p className="umc-poster-subtitle umc-preview-text-clickable" style={subtitleTypeStyle} onClick={() => onTextFieldFocus('subtitle')}>{posterSubtitle || subtitle || huUiText.defaultPosterSubtitle}</p>
                  <span className="umc-poster-nordic-line" aria-hidden="true" />
                </div>
                <p className="umc-poster-nordic-dot" aria-hidden="true">•</p>
                {posterDate ? <p className="umc-poster-meta umc-preview-text-clickable" style={dateTypeStyle} onClick={() => onTextFieldFocus('date')}>{posterDate}</p> : null}
                {posterCustomText ? <p className="umc-poster-meta umc-preview-text-clickable" style={customTypeStyle} onClick={() => onTextFieldFocus('custom')}>{posterCustomText}</p> : null}
              </div>
            ) : (
              <div className={`umc-poster-typo umc-poster-typo-${typographyStyle}`} style={posterTypeStyle}>
                <h2 className="umc-poster-title umc-preview-text-clickable" onClick={() => onTextFieldFocus('title')}>{title || huUiText.defaultPosterTitle}</h2>
                <p className="umc-poster-subtitle umc-preview-text-clickable" style={subtitleTypeStyle} onClick={() => onTextFieldFocus('subtitle')}>{posterSubtitle || subtitle || huUiText.defaultPosterSubtitle}</p>
                <div className="umc-typo-divider" />
                {posterDate ? <p className="umc-poster-meta umc-preview-text-clickable" style={dateTypeStyle} onClick={() => onTextFieldFocus('date')}>{posterDate}</p> : null}
                {posterCustomText ? <p className="umc-poster-meta umc-preview-text-clickable" style={customTypeStyle} onClick={() => onTextFieldFocus('custom')}>{posterCustomText}</p> : null}
              </div>
            )}
          </div>
        </div>
      )
    : (
        <div
          ref={canvasRef}
          className="umc-poster-art"
          onPointerDown={onCanvasPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onClick={() => onSelectObject(null)}
        >
          <ModuleMockMapLayer moduleKind={moduleKind} />
        </div>
      )

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="umc-preview-toolbar">
        <div className="umc-preview-toolbar-main">
          <p className="umc-preview-kicker">{huUiText.summaryCardKicker}</p>
          <div className="umc-preview-location-row">
            <div className="umc-location-icon-box" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M12 21c3.2-4.2 6.4-7.3 6.4-11.1A6.4 6.4 0 0 0 12 3.5a6.4 6.4 0 0 0-6.4 6.4C5.6 13.7 8.8 16.8 12 21Z"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="12" cy="9.9" r="2.4" stroke="currentColor" strokeWidth="1.8" />
              </svg>
            </div>
            <div>
              <p className="umc-toolbar-value umc-toolbar-value-hero">{subtitle || huUiText.locationNotSelected}</p>
              <p className="umc-toolbar-subline">{styleSummary || huUiText.previewToolbarStyleValue(moduleKind)}</p>
            </div>
          </div>
        </div>
        <button type="button" className="umc-share-button">
          {huUiText.share}
        </button>
      </div>

      <div className="umc-stage-wrap">
        <div className={frameClass}>
          <article
            className={shouldRenderFullPosterAsset ? 'umc-poster-sheet umc-poster-sheet-rendered' : 'umc-poster-sheet'}
            style={{ aspectRatio: String(posterAspectRatio) }}
          >
            {cityHasComposedPoster ? (
              <div
                className="umc-city-poster-sheet"
                aria-hidden="true"
                dangerouslySetInnerHTML={{ __html: cityPreviewSvg }}
              />
            ) : null}

            {!cityHasComposedPoster ? fallbackCanvas : null}

            {!cityHasComposedPoster && moduleKind !== 'city-map' ? (typographyStyle === 'urban' ? (
              <div className="umc-poster-typo umc-poster-typo-urban" style={posterTypeStyle}>
                <div className="umc-poster-urban-accent" aria-hidden="true" />
                <div className="umc-poster-urban-copy">
                  <h2 className="umc-poster-title umc-preview-text-clickable" onClick={() => onTextFieldFocus('title')}>{title || huUiText.defaultPosterTitle}</h2>
                  <p className="umc-poster-subtitle umc-preview-text-clickable" style={subtitleTypeStyle} onClick={() => onTextFieldFocus('subtitle')}>{posterSubtitle || subtitle || huUiText.defaultPosterSubtitle}</p>
                  {urbanCustomLabel ? (
                    <p className="umc-poster-urban-coordinates umc-preview-text-clickable" style={customTypeStyle} onClick={() => onTextFieldFocus('custom')}>{urbanCustomLabel}</p>
                  ) : null}
                  {posterDate ? <p className="umc-poster-meta umc-preview-text-clickable" style={dateTypeStyle} onClick={() => onTextFieldFocus('date')}>{posterDate}</p> : null}
                </div>
              </div>
            ) : typographyStyle === 'nordic' ? (
              <div className="umc-poster-typo umc-poster-typo-nordic" style={posterTypeStyle}>
                <h2 className="umc-poster-title umc-preview-text-clickable" onClick={() => onTextFieldFocus('title')}>{title || huUiText.defaultPosterTitle}</h2>
                <div className="umc-poster-nordic-subline">
                  <span className="umc-poster-nordic-line" aria-hidden="true" />
                  <p className="umc-poster-subtitle umc-preview-text-clickable" style={subtitleTypeStyle} onClick={() => onTextFieldFocus('subtitle')}>{posterSubtitle || subtitle || huUiText.defaultPosterSubtitle}</p>
                  <span className="umc-poster-nordic-line" aria-hidden="true" />
                </div>
                <p className="umc-poster-nordic-dot" aria-hidden="true">•</p>
                {posterDate ? <p className="umc-poster-meta umc-preview-text-clickable" style={dateTypeStyle} onClick={() => onTextFieldFocus('date')}>{posterDate}</p> : null}
                {posterCustomText ? <p className="umc-poster-meta umc-preview-text-clickable" style={customTypeStyle} onClick={() => onTextFieldFocus('custom')}>{posterCustomText}</p> : null}
              </div>
            ) : (
              <div className={`umc-poster-typo umc-poster-typo-${typographyStyle}`} style={posterTypeStyle}>
                <h2 className="umc-poster-title umc-preview-text-clickable" onClick={() => onTextFieldFocus('title')}>{title || huUiText.defaultPosterTitle}</h2>
                <p className="umc-poster-subtitle umc-preview-text-clickable" style={subtitleTypeStyle} onClick={() => onTextFieldFocus('subtitle')}>{posterSubtitle || subtitle || huUiText.defaultPosterSubtitle}</p>
                <div className="umc-typo-divider" />
                {posterDate ? <p className="umc-poster-meta umc-preview-text-clickable" style={dateTypeStyle} onClick={() => onTextFieldFocus('date')}>{posterDate}</p> : null}
                {posterCustomText ? <p className="umc-poster-meta umc-preview-text-clickable" style={customTypeStyle} onClick={() => onTextFieldFocus('custom')}>{posterCustomText}</p> : null}
              </div>
            )) : null}
          </article>
        </div>
      </div>
    </div>
  )
}
