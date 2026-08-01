import { Variants, Transition } from 'framer-motion'

export const spring = { type: 'spring' as const, stiffness: 60, damping: 20, mass: 1 }
export const springSnap = { type: 'spring' as const, stiffness: 200, damping: 20 }
export const springGentle = { type: 'spring' as const, stiffness: 40, damping: 15 }

export const fast: Transition = { duration: 0.15, ease: 'easeOut' }
export const normal: Transition = { duration: 0.25, ease: 'easeOut' }
export const slow: Transition = { duration: 0.4, ease: 'easeOut' }

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 24, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: -12, scale: 0.98 },
}

export const pageTransition: Transition = { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 },
}

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
}

export const fadeScale: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  show: { opacity: 1, scale: 1 },
}

export const slideLeft: Variants = {
  hidden: { opacity: 0, x: -20 },
  show: { opacity: 1, x: 0 },
}

export const slideRight: Variants = {
  hidden: { opacity: 0, x: 20 },
  show: { opacity: 1, x: 0 },
}

export const stagger = {
  container: {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.06, delayChildren: 0.1 },
    },
  } as Variants,
  item: {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0 },
  } as Variants,
}

export const staggerFast = {
  container: {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.03, delayChildren: 0.05 },
    },
  } as Variants,
  item: {
    hidden: { opacity: 0, y: 8 },
    show: { opacity: 1, y: 0 },
  } as Variants,
}

export const scaleOnHover = {
  whileHover: { scale: 1.03 },
  whileTap: { scale: 0.97 },
  transition: springGentle,
}

export const glowOnHover = {
  whileHover: { scale: 1.02, y: -3 },
  whileTap: { scale: 0.98 },
}

export const modalOverlay: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 },
  exit: { opacity: 0 },
}

export const modalPanel: Variants = {
  hidden: { opacity: 0, scale: 0.92, y: 20 },
  show: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.92, y: 20 },
}

export const progressSpring = {
  initial: { width: 0 },
  animate: { width: '{{pct}}%' },
  transition: spring,
}

export const pulseRing = {
  animate: {
    scale: [1, 1.08, 1],
    opacity: [0.3, 0.6, 0.3],
  },
  transition: {
    duration: 2.5,
    repeat: Infinity,
    ease: 'easeInOut',
  },
}

export const shimmer = {
  animate: {
    backgroundPosition: ['200% 0', '-200% 0'],
  },
  transition: {
    duration: 3,
    repeat: Infinity,
    ease: 'linear',
  },
}
