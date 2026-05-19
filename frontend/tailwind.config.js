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
          black: '#0d1117',
          dark: '#161b22',
          card: '#21262d',
          border: '#30363d',
          cyan: '#58a6ff',
          magenta: '#bc8cff',
          yellow: '#d29922',
          green: '#3fb950',
          orange: '#db6d28',
          red: '#f85149',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        display: ['Inter', 'Rajdhani', 'sans-serif'],
      },
      animation: {
        'glow-pulse': 'glow-pulse 3s ease-in-out infinite',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 3px currentColor' },
          '50%': { boxShadow: '0 0 8px currentColor' },
        },
      },
    },
  },
  plugins: [],
}