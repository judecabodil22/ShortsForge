import { Variants, Transition } from 'framer-motion'

export const springGentle = { type: 'spring' as const, stiffness: 40, damping: 15 }

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 24, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: -12, scale: 0.98 },
}

export const pageTransition: Transition = { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }

export const slideLeft: Variants = {
  hidden: { opacity: 0, x: -20 },
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
