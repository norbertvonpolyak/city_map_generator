import type { UMCPreviewObject, UMCPreviewObjectType } from '@umc-shared/types'

interface ObjectsPanelProps {
  objects: UMCPreviewObject[]
  selectedObjectId: string | null
  placementType: UMCPreviewObjectType
  onPlacementTypeChange: (type: UMCPreviewObjectType) => void
  onSelectObject: (id: string) => void
  onDeleteObject: (id: string) => void
}

const typeDisplay: Record<UMCPreviewObjectType, string> = {
  marker: 'Marker',
  heart: 'Heart',
  star: 'Star',
  pin: 'Pin',
  text: 'Text',
}

const typeIcon: Record<UMCPreviewObjectType, string> = {
  marker: '●',
  heart: '❤',
  star: '⭐',
  pin: '📍',
  text: 'T',
}

const placementTypes: UMCPreviewObjectType[] = ['marker', 'heart', 'star', 'pin', 'text']

export const ObjectsPanel = ({
  objects,
  selectedObjectId,
  placementType,
  onPlacementTypeChange,
  onSelectObject,
  onDeleteObject,
}: ObjectsPanelProps) => {
  return (
    <aside className="rounded-3xl border border-[var(--umc-border)] bg-[rgba(7,9,13,0.6)] p-4">
      <header className="mb-4">
        <p className="text-xs uppercase tracking-[0.22em] text-[var(--umc-gold)]">Object System</p>
        <h3 className="umc-serif mt-1 text-2xl text-[var(--umc-ivory)]">Objects Panel</h3>
      </header>

      <div className="mb-4">
        <p className="mb-2 text-xs uppercase tracking-[0.16em] text-[var(--umc-ivory-soft)]">Placement Tool</p>
        <div className="grid grid-cols-2 gap-2">
          {placementTypes.map((type) => {
            const selected = type === placementType

            return (
              <button
                key={type}
                type="button"
                onClick={() => onPlacementTypeChange(type)}
                className={[
                  'rounded-lg border px-2 py-2 text-left text-sm transition',
                  selected
                    ? 'border-[var(--umc-gold)] bg-[rgba(201,171,120,0.2)] text-[var(--umc-ivory)]'
                    : 'border-[var(--umc-border)] bg-[rgba(7,9,13,0.66)] text-[var(--umc-ivory-soft)] hover:border-[var(--umc-gold-soft)] hover:text-[var(--umc-ivory)]',
                ].join(' ')}
              >
                <span className="mr-1">{typeIcon[type]}</span>
                {typeDisplay[type]}
              </button>
            )
          })}
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs uppercase tracking-[0.16em] text-[var(--umc-ivory-soft)]">Current Objects</p>
        <div className="space-y-2">
          {objects.length === 0 && (
            <div className="rounded-lg border border-[var(--umc-border)] bg-[rgba(7,9,13,0.5)] px-3 py-3 text-sm text-[var(--umc-ivory-soft)]">
              No objects yet. Click in the viewport to place one.
            </div>
          )}

          {objects.map((object) => {
            const selected = object.id === selectedObjectId

            return (
              <div
                key={object.id}
                className={[
                  'flex items-center justify-between rounded-lg border px-3 py-2 transition',
                  selected
                    ? 'border-[var(--umc-gold)] bg-[rgba(201,171,120,0.2)]'
                    : 'border-[var(--umc-border)] bg-[rgba(7,9,13,0.55)]',
                ].join(' ')}
              >
                <button
                  type="button"
                  onClick={() => onSelectObject(object.id)}
                  className="text-left text-sm text-[var(--umc-ivory)]"
                >
                  <span className="mr-1">{typeIcon[object.type]}</span>
                  {object.label}
                </button>
                <button
                  type="button"
                  onClick={() => onDeleteObject(object.id)}
                  className="rounded-md border border-[var(--umc-border)] px-2 py-0.5 text-xs text-[var(--umc-ivory-soft)] transition hover:border-[rgba(220,90,90,0.7)] hover:text-[rgb(236,152,152)]"
                >
                  Delete
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </aside>
  )
}
