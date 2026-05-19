import { useEffect } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'

interface AnimatedCounterProps {
  value: number
  format?: (val: number) => string
}

export function AnimatedCounter({ value, format = (v) => Math.round(v).toString() }: AnimatedCounterProps) {
  const spring = useSpring(0, { stiffness: 50, damping: 20 })
  const displayValue = useTransform(spring, (current) => format(current))

  useEffect(() => {
    spring.set(value)
  }, [spring, value])

  return <motion.span>{displayValue}</motion.span>
}
