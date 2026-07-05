/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060d18',
          900: '#0d1b2a',
          800: '#1a2744',
          700: '#1a3a6e',
          600: '#1565c0',
        },
        accent: {
          DEFAULT: '#1a73e8',
          hover:   '#1557b0',
        },
        success: '#34a853',
        warning: '#fbbc04',
        danger:  '#ea4335',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        ticker: 'ticker 50s linear infinite',
        'pulse-slow': 'pulse 2s ease-in-out infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        ticker: {
          from: { transform: 'translateX(100%)' },
          to:   { transform: 'translateX(-200%)' },
        },
        fadeIn: {
          from: { opacity: 0, transform: 'translateY(8px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
