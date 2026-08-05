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

export const staggerFast = {
  container: {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.04, delayChildren: 0.05 },
    },
  } as Variants,
  item: {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0 },
  } as Variants,
}

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0 },
}

/** Theme-aware gold glow (uses CSS vars so Chaos/Ork/Eldar glow in-faction). */
export const hoverGlow = {
  scale: 1.03,
  boxShadow: '0 0 20px rgb(var(--40k-gold-rgb) / 0.35)',
}

export const pressScale = { scale: 0.97 }

const reducedOpacityOnly: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 },
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
}

/** Collapse motion to opacity-only when prefers-reduced-motion is on. */
export function motionSafe(variants: Variants, reduced: boolean | null): Variants {
  if (reduced) return reducedOpacityOnly
  return variants
}

export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
