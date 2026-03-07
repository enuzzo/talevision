/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Montserrat"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"Space Mono"', '"SF Mono"', '"Fira Code"', 'monospace'],
      },
      colors: {
        bg:       '#070D2D',
        deep:     '#0B1437',
        surface:  '#111C44',
        'surface-hover': '#162052',
        elevated: '#1A2558',
        'elevated-hover': '#1E2D66',
        border:   'rgba(255,255,255,0.06)',
        'border-default': 'rgba(255,255,255,0.1)',
        'border-strong': 'rgba(255,255,255,0.18)',
        primary:  '#FFFFFF',
        secondary:'#A3AED0',
        tertiary: '#707EAE',
        muted:    '#4A5568',
        accent:   '#7551FF',
        'accent-hover': '#8B6FFF',
        'accent-dim':   'rgba(117,81,255,0.12)',
        cyan:     '#39B8FF',
        success:  '#01B574',
        warning:  '#FFB547',
        danger:   '#EE5D50',
      },
      borderRadius: {
        xs:  '4px',
        sm:  '8px',
        md:  '12px',
        lg:  '16px',
        xl:  '20px',
        '2xl': '24px',
      },
      boxShadow: {
        sm:  '0 2px 8px rgba(0,0,0,0.2)',
        md:  '0 4px 16px rgba(0,0,0,0.25)',
        lg:  '0 8px 32px rgba(0,0,0,0.35)',
        xl:  '0 16px 48px rgba(0,0,0,0.4)',
        'glow-sm': '0 0 20px rgba(117,81,255,0.15)',
        'glow-md': '0 0 40px rgba(117,81,255,0.2)',
      },
      aspectRatio: {
        'eink': '5 / 3',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-accent': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.4s ease-out both',
        'pulse-accent': 'pulse-accent 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
