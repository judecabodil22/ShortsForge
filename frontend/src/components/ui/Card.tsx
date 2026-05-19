import { cn } from '@/lib/utils'
import { HTMLMotionProps, motion } from 'framer-motion'

interface CardProps extends HTMLMotionProps<"div"> {
  variant?: 'default' | 'glow-cyan' | 'glow-magenta'
  hoverable?: boolean
}

export function Card({ className, variant = 'default', hoverable = false, children, ...props }: CardProps) {
  const variantClasses = {
    default: '',
    'glow-cyan': 'border-cyber-cyan/30 hover:border-cyber-cyan hover:shadow-[0_0_20px_rgba(0,255,245,0.1)]',
    'glow-magenta': 'border-cyber-magenta/30 hover:border-cyber-magenta hover:shadow-[0_0_20px_rgba(255,0,255,0.1)]',
  }
  
  return (
    <motion.div 
      className={cn(
        'bg-cyber-card border border-cyber-border rounded-lg p-4 transition-all duration-300',
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
      <div>
        <p className="text-sm text-gray-400 mb-1">{label}</p>
        <p className="text-2xl font-display font-bold text-white">{value}</p>
        {trend && (
          <p className={cn(
            'text-xs mt-1',
            trend.positive ? 'text-cyber-green' : 'text-cyber-red'
          )}>
            {trend.positive ? '↑' : '↓'} {Math.abs(trend.value)}%
          </p>
        )}
      </div>
      {icon && (
        <div className="w-12 h-12 rounded-lg bg-cyber-cyan/10 border border-cyber-cyan/20 flex items-center justify-center text-cyber-cyan">
          {icon}
        </div>
      )}
    </Card>
  )
}