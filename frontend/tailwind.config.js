/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Syne"', 'system-ui', 'sans-serif'],
        mono: ['"DM Mono"', 'monospace'],
      },
      colors: {
        bg:       '#0a0a0c',
        elevated: '#111114',
        surface:  '#18181c',
        border:   '#242428',
        dim:      '#1c1c20',
        primary:  '#ede9df',
        secondary:'#6b6b73',
        muted:    '#3a3a42',
        accent:   '#c8923a',
        'accent-hover': '#d9a34a',
        'accent-dim':   '#7a5820',
        success:  '#4a9a6a',
        danger:   '#9a4a4a',
      },
      aspectRatio: {
        'eink': '5 / 3',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-amber': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.4s ease-out both',
        'pulse-amber': 'pulse-amber 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
