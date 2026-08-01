import { cn } from '@/lib/utils'
import { HTMLMotionProps, motion } from 'framer-motion'

interface CardProps extends HTMLMotionProps<'div'> {
  variant?: 'default' | 'glow-gold' | 'glow-crimson'
  hoverable?: boolean
  accent?: boolean | 'gold' | 'crimson'
  notch?: boolean
}

export function Card({ className, variant = 'default', hoverable = false, accent, notch = false, children, ...props }: CardProps) {
  const variantClasses = {
    default: '',
    'glow-gold':
      'border-40k-gold/30 hover:border-40k-gold hover:shadow-[0_0_20px_rgb(var(--40k-gold-rgb)/0.25)]',
    'glow-crimson':
      'border-40k-crimson-bright/30 hover:border-40k-crimson-bright hover:shadow-[0_0_20px_rgb(var(--40k-crimson-bright-rgb)/0.25)]',
  }
  const accentClass = accent === 'crimson' ? 'accent-rail-crimson' : accent ? 'accent-rail' : ''

  return (
    <motion.div
      className={cn(
        'bg-40k-card border border-40k-border transition-all duration-300 inset-border',
        notch && 'corner-notch',
        accentClass,
        variantClasses[variant],
        hoverable && 'cursor-pointer',
        className
      )}
      {...(hoverable ? {
        whileHover: { scale: 1.02, y: -3, transition: { type: 'spring', stiffness: 200, damping: 15 } },
        whileTap: { scale: 0.98 },
      } : {})}
      {...props}
    >
      {children}
    </motion.div>
  )
}

interface StatCardProps {
  label: string
  value: string | number | React.ReactNode
  icon?: React.ReactNode
  trend?: { value: number; positive: boolean }
  delay?: number
}

export function StatCard({ label, value, icon, trend, delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, delay, ease: [0.25, 0.1, 0.25, 1] }}
      className="bg-40k-card border border-40k-border transition-all duration-300 inset-border accent-rail hover:border-40k-gold/50 hover:shadow-[0_0_20px_rgb(var(--40k-gold-rgb)/0.15)]"
    >
      <div className="flex items-center justify-between p-[var(--card-padding,1rem)]">
        <div>
          <p className="terminal-label mb-1">{label}</p>
          <p className="text-[length:var(--stat-value-size,1.5rem)] font-display font-bold text-40k-gold-bright leading-none">{value}</p>
          {trend && (
            <motion.p
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: delay + 0.2 }}
              className={cn(
                'text-xs mt-1',
                trend.positive ? 'text-40k-gold-dim' : 'text-40k-red-bright'
              )}
            >
              {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </motion.p>
          )}
        </div>
        {icon && (
          <motion.div
            initial={{ rotate: -10, scale: 0 }}
            animate={{ rotate: 0, scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15, delay: delay + 0.15 }}
            className="w-10 h-10 md:w-12 md:h-12 rounded bg-40k-gold/10 border border-40k-gold/25 flex items-center justify-center text-40k-gold"
          >
            {icon}
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}
