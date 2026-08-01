import { cn } from '@/lib/utils'

interface SectionHeaderProps {
  title: string
  subtitle?: string
  icon?: React.ReactNode
  terminal?: boolean
  className?: string
}

export function SectionHeader({ title, subtitle, icon, terminal = false, className }: SectionHeaderProps) {
  if (terminal) {
    return (
      <div className={cn('flex items-center gap-2 mb-4', className)}>
        {icon && <span className="text-40k-gold shrink-0">{icon}</span>}
        <div>
          <h3 className="section-header">{title}</h3>
          {subtitle && <p className="text-xs text-stone-500 mt-0.5 ml-[calc(0.75rem+2px)]">{subtitle}</p>}
        </div>
      </div>
    )
  }

  return (
    <div className={cn('flex items-center gap-2 mb-4', className)}>
      {icon && <span className="text-40k-gold shrink-0">{icon}</span>}
      <div>
        <h3 className="text-lg font-display font-semibold text-white">{title}</h3>
        {subtitle && <p className="text-sm text-stone-400 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  )
}
