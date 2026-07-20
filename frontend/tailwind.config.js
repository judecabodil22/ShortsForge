/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        '40k': {
          black: 'rgb(var(--40k-black-rgb) / <alpha-value>)',
          dark: 'rgb(var(--40k-dark-rgb) / <alpha-value>)',
          card: 'rgb(var(--40k-card-rgb) / <alpha-value>)',
          border: 'rgb(var(--40k-border-rgb) / <alpha-value>)',
          crimson: 'rgb(var(--40k-crimson-rgb) / <alpha-value>)',
          'crimson-bright': 'rgb(var(--40k-crimson-bright-rgb) / <alpha-value>)',
          gold: 'rgb(var(--40k-gold-rgb) / <alpha-value>)',
          'gold-dim': 'rgb(var(--40k-gold-dim-rgb) / <alpha-value>)',
          'gold-bright': 'rgb(var(--40k-gold-bright-rgb) / <alpha-value>)',
          bronze: 'rgb(var(--40k-bronze-rgb) / <alpha-value>)',
          red: 'rgb(var(--40k-red-rgb) / <alpha-value>)',
          'red-bright': 'rgb(var(--40k-red-bright-rgb) / <alpha-value>)',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Cinzel', 'Inter', 'serif'],
      },
      boxShadow: {
        '40k-gold': 'var(--40k-shadow-gold)',
        '40k-crimson': 'var(--40k-shadow-crimson)',
      },
    },
  },
  plugins: [],
}
