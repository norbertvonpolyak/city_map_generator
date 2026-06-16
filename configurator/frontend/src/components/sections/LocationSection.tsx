import type { UMCPosterConfig } from '@umc-shared/types'
import { SectionCard } from './SectionCard'

interface LocationSectionProps {
  config: UMCPosterConfig
  isCityModule: boolean
  onLocationChange: (query: string) => void
  onGenerateCityPreview: () => void | Promise<void>
  cityPreviewStatus: 'idle' | 'loading' | 'ready' | 'city-not-found' | 'failed'
  cityPreviewError: string | null
}

export const LocationSection = ({
  config,
  isCityModule,
  onLocationChange,
  onGenerateCityPreview,
  cityPreviewStatus,
  cityPreviewError,
}: LocationSectionProps) => {
  const isLoading = cityPreviewStatus === 'loading'

  return (
    <SectionCard
      title="Location Section"
      description="Placeholder location controls for future map targeting."
    >
      <label className="flex flex-col gap-1 text-sm text-[var(--umc-ivory-soft)]">
        City
        <input
          value={config.location.query}
          onChange={(event) => onLocationChange(event.target.value)}
          placeholder="Enter city, address, or coordinates"
          className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.75)] px-3 py-2 text-[var(--umc-ivory)] outline-none transition focus:border-[var(--umc-gold)]"
        />
      </label>
      {isCityModule && (
        <>
          <button
            type="button"
            onClick={() => void onGenerateCityPreview()}
            disabled={isLoading}
            className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.78)] px-3 py-2 text-sm text-[var(--umc-ivory)] transition hover:border-[var(--umc-gold-soft)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading ? 'Loading Preview...' : 'Generate Preview'}
          </button>
          {cityPreviewStatus === 'city-not-found' && (
            <div className="rounded-lg border border-[rgba(220,90,90,0.45)] bg-[rgba(110,28,28,0.28)] px-3 py-2 text-sm text-[rgb(242,183,183)]">
              City Not Found
            </div>
          )}
          {cityPreviewStatus === 'failed' && (
            <div className="rounded-lg border border-[rgba(220,90,90,0.45)] bg-[rgba(110,28,28,0.28)] px-3 py-2 text-sm text-[rgb(242,183,183)]">
              Preview Generation Failed{cityPreviewError ? `: ${cityPreviewError}` : ''}
            </div>
          )}
        </>
      )}
      <div className="grid grid-cols-2 gap-2 text-sm text-[var(--umc-ivory-soft)]">
        <div className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.55)] px-3 py-2">
          Latitude: {config.location.latitude ?? 'n/a'}
        </div>
        <div className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.55)] px-3 py-2">
          Longitude: {config.location.longitude ?? 'n/a'}
        </div>
      </div>
    </SectionCard>
  )
}
