import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { motionSafe, slideLeft } from '@/lib/animations'

interface PageHeaderProps {
  /** Full title; if accentWord is set, that prefix renders in gold */
  title: string
  /** Optional gold prefix (e.g. "DASH" for "DASHBOARD") */
  accentWord?: string
  subtitle?: string
  actions?: React.ReactNode
  className?: string
}

export function PageHeader({ title, accentWord, subtitle, actions, className }: PageHeaderProps) {
  const reduced = useReducedMotion()
  const rest =
    accentWord && title.toUpperCase().startsWith(accentWord.toUpperCase())
      ? title.slice(accentWord.length)
      : accentWord
        ? title
        : null

  return (
    <motion.div
      variants={motionSafe(slideLeft, reduced)}
      initial="hidden"
      animate="show"
      className={cn('flex items-start justify-between gap-4 mb-[var(--section-gap,1.5rem)]', className)}
    >
      <div>
        <h1 className="text-3xl font-display font-bold text-white tracking-wide">
          {accentWord ? (
            <>
              <span className="text-40k-gold">{accentWord}</span>
              {rest}
            </>
          ) : (
            title
          )}
        </h1>
        {subtitle && <p className="terminal-label mt-2 normal-case tracking-wider opacity-80">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </motion.div>
  )
}
