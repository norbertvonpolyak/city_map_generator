import { umcModuleDefinitions } from '@umc-shared/modules'
import type { UMCModuleKind } from '@umc-shared/types'
import type { UMCPreviewObject } from '@umc-shared/types'
import type { UMCPreviewObjectType } from '@umc-shared/types'
import type { UMCPreviewPoint } from '@umc-shared/types'
import type { UMCPreviewViewportState } from '@umc-shared/types'
import type { UMCPosterConfig } from '@umc-shared/types'
import { InteractiveCircularViewport } from '../preview/InteractiveCircularViewport'
import { ObjectsPanel } from '../preview/ObjectsPanel'
import {
  LocationSection,
  ModuleSelectorSection,
  ObjectsSection,
  StyleSection,
  TemplateSection,
} from '../sections'

interface ConfiguratorShellProps {
  activeModule: UMCModuleKind
  activeConfig: UMCPosterConfig
  onModuleChange: (moduleKind: UMCModuleKind) => void
  onTitleChange: (title: string) => void
  onLocationChange: (query: string) => void
  onGenerateCityPreview: () => void | Promise<void>
  onTemplateChange: (templateId: string) => void
  onPaletteChange: (paletteId: string) => void
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

export const ConfiguratorShell = ({
  activeModule,
  activeConfig,
  onModuleChange,
  onTitleChange,
  onLocationChange,
  onGenerateCityPreview,
  onTemplateChange,
  onPaletteChange,
  onObjectToggle,
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
  const moduleDefinition = umcModuleDefinitions[activeModule]

  return (
    <div className="min-h-screen bg-[var(--umc-bg-ink)] text-[var(--umc-ivory)]">
      <div className="umc-background absolute inset-0 -z-0" aria-hidden="true" />
      <div className="relative z-10 mx-auto grid min-h-screen w-full max-w-[1800px] grid-cols-1 gap-6 p-4 md:p-6 xl:grid-cols-[430px_1fr]">
        <aside className="rounded-3xl border border-[var(--umc-border)] bg-[var(--umc-panel)] p-4 shadow-[0_20px_65px_rgba(0,0,0,0.55)] backdrop-blur-md md:p-5">
          <header className="mb-5 border-b border-[var(--umc-border)] pb-4">
            <p className="text-xs uppercase tracking-[0.24em] text-[var(--umc-gold)]">Universal Map Configurator</p>
            <h1 className="umc-serif mt-2 text-3xl leading-tight md:text-4xl">Premium Poster Foundation</h1>
            <p className="mt-2 text-sm text-[var(--umc-ivory-soft)]">{moduleDefinition.tagline}</p>
            <label className="mt-4 flex flex-col gap-1 text-xs uppercase tracking-[0.18em] text-[var(--umc-ivory-soft)]">
              Poster Title
              <input
                value={activeConfig.title}
                onChange={(event) => onTitleChange(event.target.value)}
                className="normal-case tracking-normal rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.65)] px-3 py-2 text-sm text-[var(--umc-ivory)] outline-none transition focus:border-[var(--umc-gold)]"
              />
            </label>
          </header>

          <div className="space-y-4 overflow-y-auto pr-1 md:max-h-[calc(100vh-220px)]">
            <ModuleSelectorSection activeModule={activeModule} onChange={onModuleChange} />
            <LocationSection
              config={activeConfig}
              isCityModule={activeModule === 'city-map'}
              onLocationChange={onLocationChange}
              onGenerateCityPreview={onGenerateCityPreview}
              cityPreviewStatus={cityPreviewStatus}
              cityPreviewError={cityPreviewError}
            />
            <TemplateSection config={activeConfig} onTemplateChange={onTemplateChange} />
            <StyleSection config={activeConfig} onPaletteChange={onPaletteChange} />
            <ObjectsSection config={activeConfig} onToggle={onObjectToggle} />
          </div>
        </aside>

        <main className="relative flex min-h-[520px] flex-col rounded-3xl border border-[var(--umc-border)] bg-[rgba(7,9,13,0.52)] p-3 shadow-[0_30px_80px_rgba(0,0,0,0.45)] md:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-[var(--umc-gold)]">Active Module</p>
              <h2 className="umc-serif text-2xl text-[var(--umc-ivory)]">{moduleDefinition.label}</h2>
            </div>
            <div className="rounded-full border border-[var(--umc-border)] bg-[rgba(7,9,13,0.75)] px-4 py-2 text-xs uppercase tracking-[0.18em] text-[var(--umc-ivory-soft)]">
              Architecture mode only
            </div>
          </div>

          <div className="grid flex-1 grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
            <InteractiveCircularViewport
              moduleKind={activeModule}
              title={activeConfig.title}
              subtitle={moduleDefinition.previewHint}
              viewport={previewViewport}
              placementType={placementType}
              selectedObjectId={selectedObjectId}
              objects={previewObjects}
              cityPreviewSvg={cityPreviewSvg}
              cityPreviewStatus={cityPreviewStatus}
              onViewportChange={onPreviewViewportChange}
              onViewportReset={onPreviewViewportReset}
              onAddObject={onAddPreviewObject}
              onMoveObject={onMovePreviewObject}
              onSelectObject={onSelectPreviewObject}
              onDeleteSelected={onDeleteSelectedPreviewObject}
            />
            <ObjectsPanel
              objects={previewObjects}
              selectedObjectId={selectedObjectId}
              placementType={placementType}
              onPlacementTypeChange={onPlacementTypeChange}
              onSelectObject={onSelectPreviewObject}
              onDeleteObject={onDeletePreviewObject}
            />
          </div>
        </main>
      </div>
    </div>
  )
}
