import type { UMCPosterConfig } from '@umc-shared/types'
import { SectionCard } from './SectionCard'

interface LocationSectionProps {
  config: UMCPosterConfig
  onLocationChange: (query: string) => void
}

export const LocationSection = ({ config, onLocationChange }: LocationSectionProps) => {
  return (
    <SectionCard
      title="Location Section"
      description="Placeholder location controls for future map targeting."
    >
      <label className="flex flex-col gap-1 text-sm text-[var(--umc-ivory-soft)]">
        Search Query
        <input
          value={config.location.query}
          onChange={(event) => onLocationChange(event.target.value)}
          placeholder="Enter city, address, or coordinates"
          className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.75)] px-3 py-2 text-[var(--umc-ivory)] outline-none transition focus:border-[var(--umc-gold)]"
        />
      </label>
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
