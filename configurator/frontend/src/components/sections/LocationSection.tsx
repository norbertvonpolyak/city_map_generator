import type { UMCPosterConfig } from '@umc-shared/types'
import { huUiText, toHuPreviewError } from '../../content/hu'
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
      title={huUiText.locationSectionTitle}
      description={huUiText.locationSectionDescription}
    >
      <label className="flex flex-col gap-1 text-sm text-[var(--umc-ivory-soft)]">
        {huUiText.cityLabel}
        <input
          value={config.location.query}
          onChange={(event) => onLocationChange(event.target.value)}
          placeholder={huUiText.cityPlaceholder}
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
            {isLoading ? huUiText.loadingPreview : huUiText.generatePreview}
          </button>
          {cityPreviewStatus === 'city-not-found' && (
            <div className="rounded-lg border border-[rgba(220,90,90,0.45)] bg-[rgba(110,28,28,0.28)] px-3 py-2 text-sm text-[rgb(242,183,183)]">
              {huUiText.cityNotFound}
            </div>
          )}
          {cityPreviewStatus === 'failed' && (
            <div className="rounded-lg border border-[rgba(220,90,90,0.45)] bg-[rgba(110,28,28,0.28)] px-3 py-2 text-sm text-[rgb(242,183,183)]">
              {toHuPreviewError(cityPreviewError)}
            </div>
          )}
        </>
      )}
      <div className="grid grid-cols-2 gap-2 text-sm text-[var(--umc-ivory-soft)]">
        <div className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.55)] px-3 py-2">
          {huUiText.latitude}: {config.location.latitude ?? huUiText.notAvailable}
        </div>
        <div className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.55)] px-3 py-2">
          {huUiText.longitude}: {config.location.longitude ?? huUiText.notAvailable}
        </div>
      </div>
    </SectionCard>
  )
}
