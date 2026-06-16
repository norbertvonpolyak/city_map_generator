import type { PropsWithChildren } from 'react'

interface SectionCardProps extends PropsWithChildren {
  title: string
  description: string
}

export const SectionCard = ({ title, description, children }: SectionCardProps) => {
  return (
    <section className="rounded-2xl border border-[var(--umc-border)] bg-[var(--umc-panel-soft)] p-4 shadow-[0_10px_30px_rgba(4,5,7,0.35)] backdrop-blur-sm">
      <header className="mb-3">
        <h3 className="umc-serif text-lg text-[var(--umc-ivory)]">{title}</h3>
        <p className="mt-1 text-sm text-[var(--umc-ivory-soft)]">{description}</p>
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  )
}
