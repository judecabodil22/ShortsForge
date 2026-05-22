import { cn } from '@/lib/utils'
import { HTMLMotionProps, motion } from 'framer-motion'

interface CardProps extends HTMLMotionProps<'div'> {
  variant?: 'default' | 'glow-gold' | 'glow-crimson'
  hoverable?: boolean
}

export function Card({ className, variant = 'default', hoverable = false, children, ...props }: CardProps) {
  const variantClasses = {
    default: '',
    'glow-gold': 'border-40k-gold/30 hover:border-40k-gold hover:shadow-40k-gold',
    'glow-crimson': 'border-40k-crimson-bright/30 hover:border-40k-crimson-bright hover:shadow-40k-crimson',
  }
  
  return (
    <motion.div 
      className={cn(
        'bg-40k-card border border-40k-border rounded-lg p-4 transition-all duration-300',
        variantClasses[variant],
        className
      )}
      whileHover={hoverable ? { scale: 1.02, y: -2 } : {}}
      whileTap={hoverable ? { scale: 0.98 } : {}}
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
}

export function StatCard({ label, value, icon, trend }: StatCardProps) {
  return (
    <Card className="flex items-center justify-between">
      <motion.div>
        <p className="text-sm text-stone-400 mb-1">{label}</p>
        <p className="text-2xl font-display font-bold text-40k-gold-bright">{value}</p>
        {trend && (
          <p className={cn(
            'text-xs mt-1',
            trend.positive ? 'text-40k-gold-dim' : 'text-40k-red-bright'
          )}>
            {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
          </p>
        )}
      </motion.div>
      {icon && (
        <motion.div className="w-12 h-12 rounded-lg bg-40k-gold/10 border border-40k-gold/25 flex items-center justify-center text-40k-gold">
          {icon}
        </motion.div>
      )}
    </Card>
  )
}
