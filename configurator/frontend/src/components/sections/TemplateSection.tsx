import type { UMCPosterConfig } from '@umc-shared/types'
import { SectionCard } from './SectionCard'

interface TemplateSectionProps {
  config: UMCPosterConfig
  onTemplateChange: (templateId: string) => void
}

const templateOptions = [
  { id: 'city-signature', label: 'City Signature' },
  { id: 'building-elevation', label: 'Building Elevation' },
  { id: 'stellar-classic', label: 'Stellar Classic' },
]

export const TemplateSection = ({ config, onTemplateChange }: TemplateSectionProps) => {
  return (
    <SectionCard
      title="Template Section"
      description="Select compositional presets without rendering behavior."
    >
      <label className="flex flex-col gap-1 text-sm text-[var(--umc-ivory-soft)]">
        Template
        <select
          value={config.template.templateId}
          onChange={(event) => onTemplateChange(event.target.value)}
          className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.75)] px-3 py-2 text-[var(--umc-ivory)] outline-none transition focus:border-[var(--umc-gold)]"
        >
          {templateOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-2 text-xs uppercase tracking-[0.18em] text-[var(--umc-ivory-soft)]">
        <div className="rounded-lg border border-[var(--umc-border)] px-3 py-2">Ratio: {config.template.ratio}</div>
        <div className="rounded-lg border border-[var(--umc-border)] px-3 py-2">
          Orientation: {config.template.orientation}
        </div>
      </div>
    </SectionCard>
  )
}
