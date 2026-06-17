import type { UMCPosterConfig } from '@umc-shared/types'
import {
  huLineWeightLabels,
  huPaletteLabels,
  huToneLabels,
  huUiText,
  toHuLabel,
} from '../../content/hu'
import { SectionCard } from './SectionCard'

interface StyleSectionProps {
  config: UMCPosterConfig
  onPaletteChange: (paletteId: string) => void
}

const paletteOptions = ['heritage-sand', 'graphite-ivory', 'night-gilded', 'amber-mineral']

export const StyleSection = ({ config, onPaletteChange }: StyleSectionProps) => {
  return (
    <SectionCard
      title={huUiText.styleSectionTitle}
      description={huUiText.styleSectionDescription}
    >
      <label className="flex flex-col gap-1 text-sm text-[var(--umc-ivory-soft)]">
        {huUiText.palette}
        <select
          value={config.style.paletteId}
          onChange={(event) => onPaletteChange(event.target.value)}
          className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.75)] px-3 py-2 text-[var(--umc-ivory)] outline-none transition focus:border-[var(--umc-gold)]"
        >
          {paletteOptions.map((palette) => (
            <option key={palette} value={palette}>
              {toHuLabel(palette, huPaletteLabels)}
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-2 text-sm text-[var(--umc-ivory-soft)]">
        <div className="rounded-lg border border-[var(--umc-border)] px-3 py-2">
          {huUiText.tone}: {toHuLabel(config.style.tone, huToneLabels)}
        </div>
        <div className="rounded-lg border border-[var(--umc-border)] px-3 py-2">
          {huUiText.lineWeight}: {toHuLabel(config.style.lineWeight, huLineWeightLabels)}
        </div>
      </div>
    </SectionCard>
  )
}
