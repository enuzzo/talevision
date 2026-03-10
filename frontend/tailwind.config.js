/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Syne"', 'sans-serif'],
        mono:    ['"Syne Mono"', '"SF Mono"', '"Fira Code"', 'monospace'],
      },
      colors: {
        bg:             '#0B0C0A',
        deep:           '#111310',
        surface:        '#181A16',
        'surface-hover':'#1F211C',
        elevated:       '#252722',
        'elevated-hover':'#2C2E28',
        border:         'rgba(255,255,255,0.06)',
        'border-default':'rgba(255,255,255,0.10)',
        'border-strong': 'rgba(255,255,255,0.18)',
        primary:        '#EDE8DC',
        secondary:      '#8A8376',
        tertiary:       '#5C5850',
        muted:          '#3A3830',
        accent:         '#C8A84B',
        'accent-hover': '#D4B660',
        'accent-dim':   'rgba(200,168,75,0.12)',
        success:        '#7AB87A',
        warning:        '#D4A050',
        danger:         '#D45858',
        cyan:           '#7AB8D4',
      },
      borderRadius: {
        xs:  '3px',
        sm:  '6px',
        md:  '10px',
        lg:  '14px',
        xl:  '18px',
      },
      keyframes: {
        'fade-in': {
          '0%':   { opacity: '0', transform: 'translateY(5px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-accent': {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.35' },
        },
        scanSweep: {
          '0%':   { top: '-4px' },
          '100%': { top: 'calc(100% + 4px)' },
        },
        ringPulse: {
          '0%':   { transform: 'scale(0.8)', opacity: '1' },
          '70%':  { transform: 'scale(1.65)', opacity: '0' },
          '100%': { transform: 'scale(1.65)', opacity: '0' },
        },
        dotBlink: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%':      { opacity: '0.25', transform: 'scale(0.6)' },
        },
      },
      animation: {
        'fade-in':     'fade-in 0.35s ease-out both',
        'pulse-accent':'pulse-accent 2s ease-in-out infinite',
        'scanSweep':   'scanSweep 2.6s linear infinite',
        'ringPulse':   'ringPulse 2s ease-out infinite',
        'dotBlink':    'dotBlink 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
