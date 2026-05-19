/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          black: '#09090b',
          dark: '#18181b',
          card: '#27272a',
          border: '#3f3f46',
          cyan: '#22d3ee',
          magenta: '#e879f9',
          yellow: '#facc15',
          green: '#4ade80',
          orange: '#fb923c',
          red: '#f87171',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Inter', 'Rajdhani', 'sans-serif'],
      },
    },
  },
  plugins: [],
}