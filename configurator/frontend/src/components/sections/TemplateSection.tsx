import type { UMCPosterConfig } from '@umc-shared/types'
import {
  huOrientationLabels,
  huTemplateLabels,
  huUiText,
  toHuLabel,
} from '../../content/hu'
import { SectionCard } from './SectionCard'

interface TemplateSectionProps {
  config: UMCPosterConfig
  onTemplateChange: (templateId: string) => void
}

const templateOptions = [
  { id: 'city-signature', label: huTemplateLabels['city-signature'] },
  { id: 'building-elevation', label: huTemplateLabels['building-elevation'] },
  { id: 'stellar-classic', label: huTemplateLabels['stellar-classic'] },
]

export const TemplateSection = ({ config, onTemplateChange }: TemplateSectionProps) => {
  return (
    <SectionCard
      title={huUiText.templateSectionTitle}
      description={huUiText.templateSectionDescription}
    >
      <label className="flex flex-col gap-1 text-sm text-[var(--umc-ivory-soft)]">
        {huUiText.template}
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
        <div className="rounded-lg border border-[var(--umc-border)] px-3 py-2">{huUiText.ratio}: {config.template.ratio}</div>
        <div className="rounded-lg border border-[var(--umc-border)] px-3 py-2">
          {huUiText.orientation}: {toHuLabel(config.template.orientation, huOrientationLabels)}
        </div>
      </div>
    </SectionCard>
  )
}
