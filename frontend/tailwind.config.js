/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        title:   ['"Sarina"', 'cursive'],
        display: ['"Funnel Display"', 'sans-serif'],
        mono:    ['"Funnel Display"', 'sans-serif'],
      },
      colors: {
        bg:              '#F1EBD9',
        deep:            '#E8E0CA',
        surface:         '#ECE4D2',
        'surface-hover': '#E4DAC6',
        elevated:        '#DDD1BB',
        'elevated-hover':'#D5C5AC',
        border:          'rgba(74,75,89,0.08)',
        'border-default':'rgba(74,75,89,0.15)',
        'border-strong': 'rgba(74,75,89,0.28)',
        primary:         '#4A4B59',
        secondary:       '#7A6B62',
        tertiary:        '#9C8E84',
        muted:           '#BDB0A5',
        accent:          '#CA796D',
        'accent-hover':  '#B86860',
        'accent-dim':    'rgba(202,121,109,0.12)',
        peach:           '#E8CAA2',
        teal:            '#8DA495',
        success:         '#8DA495',
        warning:         '#C8974A',
        danger:          '#C05050',
        cream:           '#F1EBD9',
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
