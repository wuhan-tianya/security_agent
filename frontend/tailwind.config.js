/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'security-bg': '#0a0a0a',
        'security-primary': '#00ff41', // Matrix Green
        'security-alert': '#ff3333', // Alert Red
        'security-surface': '#111111',
        'security-text': '#e5e5e5',
        'security-dim': '#888888',
      },
      fontFamily: {
        mono: ['"Fira Code"', '"JetBrains Mono"', 'monospace'],
        sans: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'neon-green': '0 0 5px #00ff41, 0 0 10px #00ff41',
        'neon-red': '0 0 5px #ff3333, 0 0 10px #ff3333',
      },
      animation: {
        'scanline': 'scanline 8s linear infinite',
      },
      keyframes: {
        scanline: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        }
      }
    },
  },
  plugins: [],
}
