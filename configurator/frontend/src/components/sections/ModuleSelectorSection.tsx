import { umcModuleList } from '@umc-shared/modules'
import type { UMCModuleKind } from '@umc-shared/types'
import { SectionCard } from './SectionCard'

interface ModuleSelectorSectionProps {
  activeModule: UMCModuleKind
  onChange: (moduleKind: UMCModuleKind) => void
}

export const ModuleSelectorSection = ({
  activeModule,
  onChange,
}: ModuleSelectorSectionProps) => {
  return (
    <SectionCard
      title="Module Selector"
      description="Switch between City, Building, and Star map foundations."
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {umcModuleList.map((moduleDefinition) => {
          const isActive = moduleDefinition.kind === activeModule
          return (
            <button
              key={moduleDefinition.kind}
              type="button"
              onClick={() => onChange(moduleDefinition.kind)}
              className={[
                'rounded-xl border px-3 py-2 text-left transition duration-300',
                isActive
                  ? 'border-[var(--umc-gold)] bg-[rgba(201,171,120,0.18)] text-[var(--umc-ivory)]'
                  : 'border-[var(--umc-border)] bg-[rgba(10,12,18,0.35)] text-[var(--umc-ivory-soft)] hover:border-[var(--umc-gold-soft)] hover:text-[var(--umc-ivory)]',
              ].join(' ')}
            >
              <div className="umc-serif text-base">{moduleDefinition.label}</div>
              <div className="mt-1 text-xs">{moduleDefinition.status}</div>
            </button>
          )
        })}
      </div>
    </SectionCard>
  )
}
