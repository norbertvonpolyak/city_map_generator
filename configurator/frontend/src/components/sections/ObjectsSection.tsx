import type { UMCPosterConfig } from '@umc-shared/types'
import { huObjectLayerLabels, huUiText, toHuLabel } from '../../content/hu'
import { SectionCard } from './SectionCard'

interface ObjectsSectionProps {
  config: UMCPosterConfig
  onToggle: (key: keyof UMCPosterConfig['objects']) => void
}

const objectKeys: Array<keyof UMCPosterConfig['objects']> = [
  'roads',
  'labels',
  'buildings',
  'water',
  'stars',
  'constellations',
  'grid',
]

export const ObjectsSection = ({ config, onToggle }: ObjectsSectionProps) => {
  return (
    <SectionCard
      title={huUiText.objectsSectionTitle}
      description={huUiText.objectsSectionDescription}
    >
      <div className="grid grid-cols-2 gap-2 text-sm text-[var(--umc-ivory-soft)]">
        {objectKeys.map((key) => {
          const isActive = config.objects[key]
          return (
            <button
              key={key}
              type="button"
              onClick={() => onToggle(key)}
              className={[
                'rounded-lg border px-3 py-2 text-left capitalize transition',
                isActive
                  ? 'border-[var(--umc-gold)] bg-[rgba(201,171,120,0.14)] text-[var(--umc-ivory)]'
                  : 'border-[var(--umc-border)] bg-[rgba(7,9,13,0.55)] hover:border-[var(--umc-gold-soft)]',
              ].join(' ')}
            >
              {toHuLabel(key, huObjectLayerLabels)}
            </button>
          )
        })}
      </div>
    </SectionCard>
  )
}
