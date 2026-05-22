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
          black: '#0a0505',
          dark: '#140808',
          card: '#1c0e0e',
          border: '#4a2828',
          crimson: '#7a1029',
          'crimson-bright': '#b71c3a',
          gold: '#c9a227',
          'gold-dim': '#8b7312',
          'gold-bright': '#e8c547',
          bronze: '#8b6914',
          red: '#8b2222',
          'red-bright': '#d45555',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Cinzel', 'Inter', 'serif'],
      },
      boxShadow: {
        '40k-gold': '0 0 18px rgba(201, 162, 39, 0.35)',
        '40k-crimson': '0 0 18px rgba(183, 28, 58, 0.35)',
      },
    },
  },
  plugins: [],
}
