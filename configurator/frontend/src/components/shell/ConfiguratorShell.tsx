import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { UMCModuleKind } from '@umc-shared/types'
import type { UMCPreviewObject } from '@umc-shared/types'
import type { UMCPreviewObjectType } from '@umc-shared/types'
import type { UMCPreviewPoint } from '@umc-shared/types'
import type { UMCPreviewViewportState } from '@umc-shared/types'
import type { UMCPosterConfig } from '@umc-shared/types'
import type { UMCPosterTypographyStyle } from '@umc-shared/types'
import {
  huObjectTypeLabels,
  huUiText,
  toHuPreviewError,
} from '../../content/hu'
import {
  resolveUmcPrice,
  umcFrameOptions,
  umcPaperOptions,
  umcSizeOptions,
} from '../../content/productCatalog'
import {
  cityMapStyles,
  type CityMapStyleId,
  getPaletteThemesForCityStyle,
  resolveCityStyleFromTemplate,
} from '../../content/mapStyleCatalog'
import type { SelectedLocation } from '../../services/locationSearch'
import { InteractiveCircularViewport } from '../preview/InteractiveCircularViewport'
import { LocationAutocomplete } from '../sections/LocationAutocomplete'

interface ConfiguratorShellProps {
  activeModule: UMCModuleKind
  activeConfig: UMCPosterConfig
  onModuleChange: (moduleKind: UMCModuleKind) => void
  onTitleChange: (title: string) => void
  onLocationSelect: (location: SelectedLocation) => void
  onLocationCenterChange: (latitude: number, longitude: number) => void
  onGenerateCityPreview: () => void | Promise<void>
  onTemplateChange: (templateId: string) => void
  onPaletteChange: (paletteId: string) => void
  onTypographyStyleChange: (typographyStyle: UMCPosterTypographyStyle) => void
  onStarDateChange: (dateIso: string) => void
  onStarSkyStyleChange: (skyStyle: 'constellation' | 'minimal') => void
  onObjectToggle: (key: keyof UMCPosterConfig['objects']) => void
  previewViewport: UMCPreviewViewportState
  previewObjects: UMCPreviewObject[]
  selectedObjectId: string | null
  placementType: UMCPreviewObjectType
  cityPreviewSvg: string | null
  cityPreviewStatus: 'idle' | 'loading' | 'ready' | 'city-not-found' | 'failed'
  cityPreviewError: string | null
  onPlacementTypeChange: (type: UMCPreviewObjectType) => void
  onPreviewViewportChange: (viewport: UMCPreviewViewportState) => void
  onPreviewViewportReset: () => void
  onAddPreviewObject: (type: UMCPreviewObjectType, point: UMCPreviewPoint) => void
  onMovePreviewObject: (id: string, point: UMCPreviewPoint) => void
  onSelectPreviewObject: (id: string | null) => void
  onDeletePreviewObject: (id: string) => void
  onDeleteSelectedPreviewObject: () => void
}

type TextFieldKey = 'title' | 'subtitle' | 'date' | 'custom'

interface TextAppearanceSettings {
  scale: number
  positionY: number
  variant: 'normal' | 'italic'
  weight: '500' | '700' | '900'
  fontFamily: 'manrope' | 'montserrat' | 'poppins' | 'lora'
  tone: 'black' | 'gray' | 'brown'
}

type FrameOption = 'none' | 'wood-brown' | 'black' | 'white'

type StepId = 1 | 2 | 3 | 4
type ActiveStepId = StepId | null

const frameOptions = umcFrameOptions
const placementTypesForCity: UMCPreviewObjectType[] = ['heart', 'pin', 'star', 'marker']
const cityRadiusMaxByStyle: Record<CityMapStyleId, number> = {
  minimal: 50,
  district: 4.5,
  architecture: 2,
}

const typographyStyleOptions: Array<{
  id: UMCPosterTypographyStyle
  name: string
  description: string
}> = [
  {
    id: 'urban',
    name: 'Urban',
    description: 'Modern, karakteres megjelenés',
  },
  {
    id: 'nordic',
    name: 'Nordic',
    description: 'Letisztult, skandináv stílus',
  },
  {
    id: 'classic',
    name: 'Classic',
    description: 'Elegáns, időtálló tipográfia',
  },
]

const parseLocationParts = (displayName: string): { city: string; country: string } => {
  const parts = displayName
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)

  if (parts.length === 0) {
    return { city: '', country: '' }
  }

  if (parts.length === 1) {
    return { city: parts[0], country: '' }
  }

  return {
    city: parts[0],
    country: parts[parts.length - 1],
  }
}


interface StepCardProps {
  number: number
  title: string
  open: boolean
  summaryLines: string[]
  onToggle: () => void
  children: ReactNode
}

const StepCard = ({ number, title, open, summaryLines, onToggle, children }: StepCardProps) => {
  return (
    <section className={open ? 'umc-step-card umc-step-open' : 'umc-step-card'}>
      <button type="button" className="umc-step-header" onClick={onToggle}>
        <span className="umc-step-index">{number}</span>
        <div>
          <h3>{title}</h3>
          {!open ? (
            <div className="umc-step-summary-list">
              {summaryLines.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          ) : null}
        </div>
      </button>
      {open ? <div className="umc-step-content">{children}</div> : null}
    </section>
  )
}

const withCheck = (text: string): string => {
  return `${huUiText.donePrefix} ${text}`
}

export const ConfiguratorShell = ({
  activeModule,
  activeConfig,
  onModuleChange,
  onTitleChange,
  onLocationSelect,
  onLocationCenterChange,
  onGenerateCityPreview,
  onTemplateChange,
  onPaletteChange,
  onTypographyStyleChange,
  onStarDateChange,
  onStarSkyStyleChange,
  onObjectToggle: _onObjectToggle,
  previewViewport,
  previewObjects,
  selectedObjectId,
  placementType,
  cityPreviewSvg,
  cityPreviewStatus,
  cityPreviewError,
  onPlacementTypeChange,
  onPreviewViewportChange,
  onPreviewViewportReset,
  onAddPreviewObject,
  onMovePreviewObject,
  onSelectPreviewObject,
  onDeletePreviewObject,
  onDeleteSelectedPreviewObject,
}: ConfiguratorShellProps) => {
  const [activeStep, setActiveStep] = useState<ActiveStepId>(1)
  const [radiusKm, setRadiusKm] = useState(5)
  const [showRadiusNotice, setShowRadiusNotice] = useState(false)
  const [frameOption, setFrameOption] = useState<FrameOption>('wood-brown')
  const [paperOption] = useState(umcPaperOptions[0])
  const [sizeOption] = useState(umcSizeOptions[0])

  const [posterSubtitle, setPosterSubtitle] = useState('')
  const [posterDateText, setPosterDateText] = useState('')
  const [posterCustomText, setPosterCustomText] = useState('')
  const [openTextSettingsField, setOpenTextSettingsField] = useState<TextFieldKey | null>(null)
  const [textAppearanceByField, setTextAppearanceByField] = useState<Record<TextFieldKey, TextAppearanceSettings>>({
    title: {
      scale: 1,
      positionY: 0,
      variant: 'normal',
      weight: '700',
      fontFamily: 'manrope',
      tone: 'black',
    },
    subtitle: {
      scale: 1,
      positionY: 0,
      variant: 'normal',
      weight: '700',
      fontFamily: 'manrope',
      tone: 'black',
    },
    date: {
      scale: 1,
      positionY: 0,
      variant: 'normal',
      weight: '700',
      fontFamily: 'manrope',
      tone: 'black',
    },
    custom: {
      scale: 1,
      positionY: 0,
      variant: 'normal',
      weight: '700',
      fontFamily: 'manrope',
      tone: 'black',
    },
  })
  const [titleTouched, setTitleTouched] = useState(false)
  const [subtitleTouched, setSubtitleTouched] = useState(false)
  const [, setCustomTextTouched] = useState(false)
  const radiusNoticeTimerRef = useRef<number | null>(null)

  const isCityModule = activeModule === 'city-map'
  const selectedCityStyle = resolveCityStyleFromTemplate(activeConfig.template.templateId)
  const cityRadiusMaxKm = cityRadiusMaxByStyle[selectedCityStyle.id]
  const radiusStep = selectedCityStyle.id === 'minimal' ? 1 : 0.1
  const paletteThemes = getPaletteThemesForCityStyle(selectedCityStyle.id)
  const markerCount = previewObjects.filter((item) => item.type !== 'text').length
  const textObjectCount = previewObjects.filter((item) => item.type === 'text').length
  const resolvedPrice = resolveUmcPrice(isCityModule ? 'city-map' : 'star-map', frameOption, sizeOption.id, paperOption.id)

  const selectedStyleLabel = useMemo(() => {
    if (!isCityModule) {
      return huUiText.starMap
    }
    return selectedCityStyle.name
  }, [isCityModule, selectedCityStyle.name])

  const shouldShowMapCta = isCityModule && cityPreviewStatus !== 'ready'
  const isMapRenderLoading = cityPreviewStatus === 'loading'

  const locationDefaults = useMemo(() => {
    const { city, country } = parseLocationParts(activeConfig.location.query)
    return {
      city,
      country,
    }
  }, [activeConfig.location.query])

  const stepCompletion = useMemo(() => {
    return {
      1: activeConfig.location.query.trim().length > 0,
      2: activeConfig.template.templateId.trim().length > 0 && !!frameOption,
      3: activeConfig.title.trim().length > 0 || posterSubtitle.trim().length > 0 || posterDateText.trim().length > 0,
      4: true,
    } as Record<1 | 2 | 3 | 4, boolean>
  }, [activeConfig.location.query, activeConfig.template.templateId, activeConfig.title, frameOption, posterDateText, posterSubtitle])

  const previousCompletion = useRef(stepCompletion)

  useEffect(() => {
    const transitions: Array<[1 | 2 | 3, StepId]> = [
      [1, 2],
      [2, 3],
      [3, 4],
    ]

    transitions.forEach(([step, next]) => {
      const nowComplete = stepCompletion[step]
      const wasComplete = previousCompletion.current[step]
      if (nowComplete && !wasComplete && activeStep === step) {
        setActiveStep(next)
      }
    })

    previousCompletion.current = stepCompletion
  }, [activeStep, stepCompletion])

  const onToggleStep = (step: StepId) => {
    setActiveStep((current) => (current === step ? null : step))
  }

  const toggleTextSettings = (field: TextFieldKey) => {
    setOpenTextSettingsField((current) => (current === field ? null : field))
  }

  const focusTextSettingsFromPreview = (field: TextFieldKey) => {
    setActiveStep(3)
    setOpenTextSettingsField(field)

    window.requestAnimationFrame(() => {
      const inputByField: Record<TextFieldKey, string> = {
        title: 'poster-title-input',
        subtitle: 'poster-subtitle-input',
        date: 'poster-date-input',
        custom: 'poster-custom-input',
      }

      const input = document.getElementById(inputByField[field])
      if (!input) {
        return
      }

      input.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      })
    })
  }

  const updateTextAppearance = (field: TextFieldKey, patch: Partial<TextAppearanceSettings>) => {
    setTextAppearanceByField((current) => ({
      ...current,
      [field]: {
        ...current[field],
        ...patch,
      },
    }))
  }

  const renderTextSettingsPanel = (field: TextFieldKey) => {
    const appearance = textAppearanceByField[field]
    if (openTextSettingsField !== field) {
      return null
    }

    return (
      <div className="umc-text-settings-panel" id={`text-appearance-settings-${field}`}>
        <div className="umc-text-settings-row">
          <label className="umc-field-label" htmlFor={`text-size-range-${field}`}>{huUiText.textSize}</label>
          <input
            id={`text-size-range-${field}`}
            type="range"
            min={0.8}
            step={0.01}
            max={1.25}
            value={appearance.scale}
            onChange={(event) => updateTextAppearance(field, { scale: Number(event.target.value) })}
          />
          <p className="umc-helper-text">{appearance.scale.toFixed(2)}x</p>
        </div>

        <div className="umc-text-settings-row">
          <label className="umc-field-label" htmlFor={`text-position-range-${field}`}>{huUiText.textPosition}</label>
          <input
            id={`text-position-range-${field}`}
            type="range"
            min={-28}
            step={1}
            max={28}
            value={appearance.positionY}
            onChange={(event) => updateTextAppearance(field, { positionY: Number(event.target.value) })}
          />
          <p className="umc-helper-text">
            {appearance.positionY > 0 ? `+${appearance.positionY}` : appearance.positionY}px • {huUiText.textPositionDescription}
          </p>
        </div>

        <div className="umc-text-settings-row">
          <p className="umc-field-label">{huUiText.textStyle}</p>
          <div className="umc-option-pills">
            <button
              type="button"
              className={appearance.variant === 'normal' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { variant: 'normal' })}
            >
              {huUiText.textStyleNormal}
            </button>
            <button
              type="button"
              className={appearance.variant === 'italic' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { variant: 'italic' })}
            >
              {huUiText.textStyleItalic}
            </button>
          </div>
        </div>

        <div className="umc-text-settings-row">
          <p className="umc-field-label">{huUiText.textWeight}</p>
          <div className="umc-option-pills">
            <button
              type="button"
              className={appearance.weight === '500' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { weight: '500' })}
            >
              {huUiText.textWeightRegular}
            </button>
            <button
              type="button"
              className={appearance.weight === '700' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { weight: '700' })}
            >
              {huUiText.textWeightSemiBold}
            </button>
            <button
              type="button"
              className={appearance.weight === '900' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { weight: '900' })}
            >
              {huUiText.textWeightBold}
            </button>
          </div>
        </div>

        <div className="umc-text-settings-row">
          <p className="umc-field-label">{huUiText.textFont}</p>
          <div className="umc-option-pills">
            <button
              type="button"
              className={appearance.fontFamily === 'manrope' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { fontFamily: 'manrope' })}
            >
              Manrope
            </button>
            <button
              type="button"
              className={appearance.fontFamily === 'montserrat' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { fontFamily: 'montserrat' })}
            >
              Montserrat
            </button>
            <button
              type="button"
              className={appearance.fontFamily === 'poppins' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { fontFamily: 'poppins' })}
            >
              Poppins
            </button>
            <button
              type="button"
              className={appearance.fontFamily === 'lora' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { fontFamily: 'lora' })}
            >
              Lora
            </button>
          </div>
        </div>

        <div className="umc-text-settings-row">
          <p className="umc-field-label">{huUiText.textColor}</p>
          <div className="umc-option-pills">
            <button
              type="button"
              className={appearance.tone === 'black' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { tone: 'black' })}
            >
              <span className="umc-color-swatch umc-color-swatch-black" aria-hidden="true" />
              {huUiText.textColorBlack}
            </button>
            <button
              type="button"
              className={appearance.tone === 'gray' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { tone: 'gray' })}
            >
              <span className="umc-color-swatch umc-color-swatch-gray" aria-hidden="true" />
              {huUiText.textColorGray}
            </button>
            <button
              type="button"
              className={appearance.tone === 'brown' ? 'umc-option-pill umc-option-pill-active' : 'umc-option-pill'}
              onClick={() => updateTextAppearance(field, { tone: 'brown' })}
            >
              <span className="umc-color-swatch umc-color-swatch-brown" aria-hidden="true" />
              {huUiText.textColorBrown}
            </button>
          </div>
        </div>
      </div>
    )
  }

  useEffect(() => {
    if (activeModule === 'star-map' && placementType !== 'text') {
      onPlacementTypeChange('text')
    }
  }, [activeModule, onPlacementTypeChange, placementType])

  useEffect(() => {
    setTitleTouched(false)
    setSubtitleTouched(false)
    setCustomTextTouched(false)
  }, [activeModule])

  useEffect(() => {
    if (!titleTouched && locationDefaults.city && activeConfig.title !== locationDefaults.city) {
      onTitleChange(locationDefaults.city)
    }
  }, [activeConfig.title, locationDefaults.city, onTitleChange, titleTouched])

  useEffect(() => {
    if (!subtitleTouched && locationDefaults.country && posterSubtitle !== locationDefaults.country) {
      setPosterSubtitle(locationDefaults.country)
    }
  }, [locationDefaults.country, posterSubtitle, subtitleTouched])

  useEffect(() => {
    setRadiusKm((current) => Math.min(current, cityRadiusMaxKm))
  }, [cityRadiusMaxKm])

  useEffect(() => {
    return () => {
      if (radiusNoticeTimerRef.current !== null) {
        window.clearTimeout(radiusNoticeTimerRef.current)
      }
    }
  }, [])

  const onRadiusChange = (nextRadiusRaw: number) => {
    const nextRadius = Math.min(Math.max(nextRadiusRaw, 1), cityRadiusMaxKm)

    if (nextRadius > radiusKm) {
      setShowRadiusNotice(true)
      if (radiusNoticeTimerRef.current !== null) {
        window.clearTimeout(radiusNoticeTimerRef.current)
      }
      radiusNoticeTimerRef.current = window.setTimeout(() => {
        setShowRadiusNotice(false)
      }, 2400)
    }

    setRadiusKm(nextRadius)
  }

  const onSelectPosterType = (moduleKind: UMCModuleKind) => {
    onModuleChange(moduleKind)
    if (moduleKind === 'star-map') {
      onTemplateChange('stellar-classic')
      onPaletteChange('nordic')
    } else if (moduleKind === 'city-map') {
      onTemplateChange(cityMapStyles[0].templateId)
      onPaletteChange('linen')
    }
  }

  const selectCityStyle = (styleTemplateId: string) => {
    onTemplateChange(styleTemplateId)
    const style = resolveCityStyleFromTemplate(styleTemplateId)
    const supportedPalettes = getPaletteThemesForCityStyle(style.id)
    const paletteExists = supportedPalettes.some((item) => item.id === activeConfig.style.paletteId)

    if (!paletteExists && supportedPalettes.length > 0) {
      onPaletteChange(supportedPalettes[0].id)
    }
  }

  const selectedStarDate = activeConfig.moduleKind === 'star-map'
    ? activeConfig.star.dateIso.slice(0, 10)
    : new Date().toISOString().slice(0, 10)

  const stepSummaries = useMemo(() => {
    const locationLines = stepCompletion[1]
      ? [withCheck(activeConfig.location.query)]
      : [huUiText.summaryNotConfigured]

    const styleLines = [
      withCheck(isCityModule ? huUiText.cityMap : huUiText.starMap),
    ]

    if (isCityModule) {
      styleLines.push(withCheck(selectedStyleLabel))
    }

    const frameLabel = frameOptions.find((item) => item.id === frameOption)?.label ?? huUiText.frameNone
    styleLines.push(withCheck(`${frameLabel} ${huUiText.summaryFrameSuffix}`))

    const posterLines: string[] = []
    if (activeConfig.title.trim().length > 0) {
      posterLines.push(withCheck(huUiText.summaryTitleSet))
    }
    if (posterSubtitle.trim().length > 0) {
      posterLines.push(withCheck(huUiText.summarySubtitleSet))
    }
    if (posterDateText.trim().length > 0) {
      posterLines.push(withCheck(huUiText.summaryDateSet))
    }
    if (posterCustomText.trim().length > 0) {
      posterLines.push(withCheck(huUiText.summaryCustomSet))
    }
    posterLines.push(withCheck(huUiText.summaryTypography(activeConfig.style.typographyStyle)))

    const objectLines = [
      withCheck(huUiText.summaryObjects(markerCount)),
      withCheck(huUiText.summaryLabels(textObjectCount)),
    ]

    return {
      locationLines,
      styleLines,
      posterLines: posterLines.length > 0 ? posterLines : [huUiText.summaryNotConfigured],
      objectLines,
    }
  }, [
    activeConfig.location.query,
    activeConfig.title,
    frameOption,
    isCityModule,
    markerCount,
    posterCustomText,
    posterDateText,
    posterSubtitle,
    activeConfig.style.typographyStyle,
    resolvedPrice,
    selectedStyleLabel,
    stepCompletion,
    textObjectCount,
  ])

  return (
    <div className="umc-app-shell">
      <aside className="umc-sidebar">
        <header className="umc-sidebar-header">
          <p>{huUiText.brand}</p>
          <h1>{huUiText.heroSubtitle}</h1>
        </header>

        <StepCard
          number={1}
          title={huUiText.stepLocation}
          open={activeStep === 1}
          summaryLines={stepSummaries.locationLines}
          onToggle={() => onToggleStep(1)}
        >
          <label className="umc-field-label">{huUiText.cityLabel}</label>
          <LocationAutocomplete
            value={activeConfig.location.query}
            onSelect={onLocationSelect}
          />

          <div className="umc-location-coordinates">
            <div className="umc-location-coordinate-item">
              <span className="umc-location-coordinate-label">{huUiText.latitude}:</span>
              <span className="umc-location-coordinate-value">{activeConfig.location.latitude ?? huUiText.notAvailable}</span>
            </div>
            <div className="umc-location-coordinate-item">
              <span className="umc-location-coordinate-label">{huUiText.longitude}:</span>
              <span className="umc-location-coordinate-value">{activeConfig.location.longitude ?? huUiText.notAvailable}</span>
            </div>
          </div>

          {isCityModule ? (
            <>
              <button type="button" className="umc-primary-button" onClick={() => void onGenerateCityPreview()}>
                {huUiText.updatePreview}
              </button>
              {cityPreviewStatus === 'failed' ? <p className="umc-error-text">{toHuPreviewError(cityPreviewError)}</p> : null}
              {cityPreviewStatus === 'city-not-found' ? <p className="umc-error-text">{huUiText.cityNotFound}</p> : null}
            </>
          ) : null}
        </StepCard>

        <StepCard
          number={2}
          title={huUiText.stepStyle}
          open={activeStep === 2}
          summaryLines={stepSummaries.styleLines}
          onToggle={() => onToggleStep(2)}
        >
          <div className="umc-type-switch">
            <button
              type="button"
              onClick={() => onSelectPosterType('city-map')}
              className={isCityModule ? 'umc-switch-active' : ''}
            >
              {huUiText.cityMap}
            </button>
            <button
              type="button"
              onClick={() => onSelectPosterType('star-map')}
              className={!isCityModule ? 'umc-switch-active' : ''}
            >
              {huUiText.starMap}
            </button>
          </div>

          {isCityModule ? (
            <>
              <p className="umc-field-label">{huUiText.cityStyleTitle}</p>
              <div className="umc-style-grid">
                {cityMapStyles.map((option) => (
                  <button
                    key={option.templateId}
                    type="button"
                    className={activeConfig.template.templateId === option.templateId ? 'umc-style-card umc-style-card-active' : 'umc-style-card'}
                    onClick={() => selectCityStyle(option.templateId)}
                  >
                    <div className={option.thumbnailClass} />
                    <strong>{option.name}</strong>
                    <span>{option.description}</span>
                  </button>
                ))}
              </div>

              <p className="umc-field-label">{huUiText.recommendedPalette}</p>
              <div className="umc-palette-grid">
                {paletteThemes.map((palette) => (
                  <button
                    key={palette.id}
                    type="button"
                    className={activeConfig.style.paletteId === palette.id ? 'umc-palette-card umc-palette-card-active' : 'umc-palette-card'}
                    onClick={() => onPaletteChange(palette.id)}
                    title={`${palette.name} - ${palette.description}`}
                    aria-label={`${palette.name} - ${palette.description}`}
                  >
                    <span
                      className="umc-palette-dot"
                      style={{
                        background: `linear-gradient(90deg, ${palette.colors.join(', ')})`,
                      }}
                    />
                    <strong>{palette.name}</strong>
                    <small>{palette.description}</small>
                  </button>
                ))}
              </div>

              <div className="umc-radius-control">
                {showRadiusNotice ? (
                  <p className="umc-radius-notice" role="status">
                    Nagyobb teruletet valasztottam, ezert a rendereles most picit tobb idot ker.
                  </p>
                ) : null}
                <label className="umc-field-label" htmlFor="radius-range">{huUiText.radius}</label>
                <input
                  id="radius-range"
                  type="range"
                  min={1}
                  step={radiusStep}
                  max={cityRadiusMaxKm}
                  value={radiusKm}
                  onChange={(event) => onRadiusChange(Number(event.target.value))}
                />
                <p className="umc-helper-text">
                  {radiusKm} km / max. {cityRadiusMaxKm} km • {huUiText.radiusDescription}
                </p>
              </div>
            </>
          ) : (
            <>
              <label className="umc-field-label" htmlFor="event-date">{huUiText.eventDate}</label>
              <input
                id="event-date"
                type="date"
                value={selectedStarDate}
                onChange={(event) => onStarDateChange(`${event.target.value}T20:00:00.000Z`)}
                className="umc-input"
              />
              <p className="umc-field-label">{huUiText.displayMode}</p>
              <label className="umc-radio-item">
                <input
                  type="radio"
                  name="sky-display"
                  checked={activeConfig.moduleKind === 'star-map' && activeConfig.star.skyStyle === 'minimal'}
                  onChange={() => onStarSkyStyleChange('minimal')}
                />
                {huUiText.gridMode}
              </label>
              <label className="umc-radio-item">
                <input
                  type="radio"
                  name="sky-display"
                  checked={activeConfig.moduleKind === 'star-map' && activeConfig.star.skyStyle === 'constellation'}
                  onChange={() => onStarSkyStyleChange('constellation')}
                />
                {huUiText.constellationMode}
              </label>
            </>
          )}

          <p className="umc-field-label">{huUiText.frame}</p>
          <div className="umc-frame-grid">
            {frameOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                className={frameOption === option.id ? 'umc-frame-option umc-frame-option-active' : 'umc-frame-option'}
                onClick={() => setFrameOption(option.id as FrameOption)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </StepCard>

        <StepCard
          number={3}
          title={huUiText.stepPosterText}
          open={activeStep === 3}
          summaryLines={stepSummaries.posterLines}
          onToggle={() => onToggleStep(3)}
        >
          <p className="umc-field-label">{huUiText.typographyStyleTitle}</p>
          <div className="umc-typography-grid">
            {typographyStyleOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                className={activeConfig.style.typographyStyle === option.id ? 'umc-style-card umc-style-card-active' : 'umc-style-card'}
                onClick={() => onTypographyStyleChange(option.id)}
                aria-label={`${option.name} - ${option.description}`}
                title={`${option.name} - ${option.description}`}
              >
                <div className={`umc-typography-thumb umc-typography-thumb-${option.id}`}>
                  <div className="umc-typography-thumb-map" />
                  <div className="umc-typography-thumb-copy">
                    <span className="umc-typography-thumb-title">BUDAPEST</span>
                    <span className="umc-typography-thumb-subtitle">MAGYARORSZÁG</span>
                    <span className="umc-typography-thumb-divider" />
                  </div>
                </div>
                <strong>{option.name}</strong>
                <span>{option.description}</span>
              </button>
            ))}
          </div>

          <div className="umc-field-label-row">
            <label className="umc-field-label" htmlFor="poster-title-input">{huUiText.posterTextTitle}</label>
            <button
              type="button"
              className="umc-inline-gear-button"
              onClick={() => toggleTextSettings('title')}
              aria-label={huUiText.textAppearanceSettings}
              aria-expanded={openTextSettingsField === 'title'}
              aria-controls="text-appearance-settings-title"
            >
              ⚙
            </button>
          </div>
          <input
            id="poster-title-input"
            value={activeConfig.title}
            onChange={(event) => {
              setTitleTouched(true)
              onTitleChange(event.target.value)
            }}
            className="umc-input"
            placeholder={huUiText.defaultPosterTitle}
          />
          {renderTextSettingsPanel('title')}

          <div className="umc-field-label-row">
            <label className="umc-field-label" htmlFor="poster-subtitle-input">{huUiText.posterTextSubtitle}</label>
            <button
              type="button"
              className="umc-inline-gear-button"
              onClick={() => toggleTextSettings('subtitle')}
              aria-label={huUiText.textAppearanceSettings}
              aria-expanded={openTextSettingsField === 'subtitle'}
              aria-controls="text-appearance-settings-subtitle"
            >
              ⚙
            </button>
          </div>
          <input
            id="poster-subtitle-input"
            value={posterSubtitle}
            onChange={(event) => {
              setSubtitleTouched(true)
              setPosterSubtitle(event.target.value)
            }}
            className="umc-input"
            placeholder={huUiText.posterTextPlaceholderSubtitle}
          />
          {renderTextSettingsPanel('subtitle')}

          <div className="umc-field-label-row">
            <label className="umc-field-label" htmlFor="poster-date-input">{huUiText.posterTextDate}</label>
            <button
              type="button"
              className="umc-inline-gear-button"
              onClick={() => toggleTextSettings('date')}
              aria-label={huUiText.textAppearanceSettings}
              aria-expanded={openTextSettingsField === 'date'}
              aria-controls="text-appearance-settings-date"
            >
              ⚙
            </button>
          </div>
          <input
            id="poster-date-input"
            type="date"
            value={posterDateText}
            onChange={(event) => setPosterDateText(event.target.value)}
            className="umc-input"
          />
          {renderTextSettingsPanel('date')}

          <div className="umc-field-label-row">
            <label className="umc-field-label" htmlFor="poster-custom-input">{huUiText.posterTextCustom}</label>
            <button
              type="button"
              className="umc-inline-gear-button"
              onClick={() => toggleTextSettings('custom')}
              aria-label={huUiText.textAppearanceSettings}
              aria-expanded={openTextSettingsField === 'custom'}
              aria-controls="text-appearance-settings-custom"
            >
              ⚙
            </button>
          </div>
          <input
            id="poster-custom-input"
            value={posterCustomText}
            onChange={(event) => {
              setCustomTextTouched(true)
              setPosterCustomText(event.target.value)
            }}
            className="umc-input"
            placeholder={huUiText.posterTextPlaceholderCustom}
          />
          {renderTextSettingsPanel('custom')}

        </StepCard>

        <StepCard
          number={4}
          title={huUiText.stepObjects}
          open={activeStep === 4}
          summaryLines={stepSummaries.objectLines}
          onToggle={() => onToggleStep(4)}
        >
          {isCityModule ? (
            <>
              <p className="umc-field-label">{huUiText.objectsForCity}</p>
              <div className="umc-object-pills">
                {placementTypesForCity.map((type) => (
                  <button
                    key={type}
                    type="button"
                    className={placementType === type ? 'umc-pill umc-pill-active' : 'umc-pill'}
                    onClick={() => onPlacementTypeChange(type)}
                  >
                    {huObjectTypeLabels[type]}
                  </button>
                ))}
              </div>

              <div className="umc-object-list">
                {previewObjects.map((item) => (
                  <div key={item.id} className={item.id === selectedObjectId ? 'umc-object-row umc-object-row-active' : 'umc-object-row'}>
                    <button type="button" onClick={() => onSelectPreviewObject(item.id)}>{item.label}</button>
                    <button type="button" onClick={() => onDeletePreviewObject(item.id)}>{huUiText.delete}</button>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="umc-helper-text">{huUiText.starTextOnly}</p>
          )}
        </StepCard>

        <section className="umc-style-preview-notice" aria-label={huUiText.stylePreviewNoticeTitle}>
          <span className="umc-style-preview-notice-icon" aria-hidden="true">!</span>
          <div className="umc-style-preview-notice-copy">
            <p className="umc-style-preview-notice-title">{huUiText.stylePreviewNoticeTitle}</p>
            <p>{huUiText.stylePreviewNoticeBodyLine1}</p>
            <p>{huUiText.stylePreviewNoticeBodyLine2}</p>
          </div>
        </section>
      </aside>

      <main className="umc-main-column">
        <InteractiveCircularViewport
          moduleKind={activeModule}
          title={activeConfig.title}
          subtitle={activeConfig.location.query}
          posterSubtitle={posterSubtitle}
          posterDate={posterDateText}
          posterCustomText={posterCustomText}
          titleTextAppearance={textAppearanceByField.title}
          subtitleTextAppearance={textAppearanceByField.subtitle}
          dateTextAppearance={textAppearanceByField.date}
          customTextAppearance={textAppearanceByField.custom}
          typographyStyle={activeConfig.style.typographyStyle}
          styleSummary={isCityModule ? `${huUiText.cityMap} • ${selectedStyleLabel}` : huUiText.starMap}
          viewport={previewViewport}
          placementType={placementType}
          selectedObjectId={selectedObjectId}
          objects={previewObjects}
          cityPreviewSvg={cityPreviewSvg}
          cityPreviewStatus={cityPreviewStatus}
          locationLatitude={activeConfig.location.latitude}
          locationLongitude={activeConfig.location.longitude}
          radiusKm={radiusKm}
          onLocationCenterChange={onLocationCenterChange}
          frameOption={frameOption}
          onViewportChange={onPreviewViewportChange}
          onViewportReset={onPreviewViewportReset}
          onAddObject={onAddPreviewObject}
          onMoveObject={onMovePreviewObject}
          onSelectObject={onSelectPreviewObject}
          onDeleteSelected={onDeleteSelectedPreviewObject}
          onTextFieldFocus={focusTextSettingsFromPreview}
        />

        <section className="umc-product-bar">
          <div>
            <p>{huUiText.size}</p>
            <strong>{sizeOption.label}</strong>
          </div>
          <div>
            <p>{huUiText.frame}</p>
            <strong>{frameOptions.find((item) => item.id === frameOption)?.label}</strong>
          </div>
          <div>
            <p>{huUiText.paper}</p>
            <strong>{paperOption.label}</strong>
          </div>
          <div className="umc-price-highlight">
            <p>{huUiText.price}</p>
            <strong>{resolvedPrice.toLocaleString('hu-HU')} Ft</strong>
          </div>
          {shouldShowMapCta ? (
            <button type="button" onClick={() => void onGenerateCityPreview()} disabled={isMapRenderLoading}>
              {isMapRenderLoading ? huUiText.showMapLoading : huUiText.showMap}
            </button>
          ) : (
            <button type="button">{huUiText.addToCart}</button>
          )}
        </section>
      </main>
    </div>
  )
}
