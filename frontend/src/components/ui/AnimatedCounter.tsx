import { useEffect, useRef } from 'react'
import { motion, useSpring, useTransform } from 'framer-motion'

interface AnimatedCounterProps {
  value: number
  format?: (val: number) => string
}

export function AnimatedCounter({ value, format = (v) => Math.round(v).toString() }: AnimatedCounterProps) {
  const formatRef = useRef(format)
  formatRef.current = format
  const spring = useSpring(0, { stiffness: 50, damping: 20 })
  const displayValue = useTransform(spring, (current) => formatRef.current(current))

  useEffect(() => {
    spring.set(value)
  }, [spring, value])

  return <motion.span>{displayValue}</motion.span>
}
