import tailwindcssAnimate from 'tailwindcss-animate';

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        primary: 'rgb(var(--color-primary) / <alpha-value>)',
        canvas: 'rgb(var(--color-canvas) / <alpha-value>)',
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        ink: 'rgb(var(--color-ink) / <alpha-value>)',
        muted: 'rgb(var(--color-muted) / <alpha-value>)',
        line: 'rgb(var(--color-line) / <alpha-value>)',
        success: '#58d6af',
        warning: '#f5c979',
        error: '#ff8b9b',
      },
      fontFamily: {
        editorial: ['Georgia', 'Times New Roman', 'serif'],
        display: ['Space Grotesk', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        arabic: ['Cairo', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        micro: ['10px', { letterSpacing: '0.1em' }],
        lead: ['clamp(1.5rem, 2.3vw, 2.2rem)', { lineHeight: '1.3' }],
        'display-lg': ['clamp(2rem, 4vw, 3.5rem)', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
        'display-xl': ['clamp(2.5rem, 6vw, 5rem)', { lineHeight: '1', letterSpacing: '-0.03em' }],
        'display-2xl': ['clamp(3.5rem, 8vw, 8rem)', { lineHeight: '0.95', letterSpacing: '-0.04em' }],
        'editorial-hero': ['clamp(3rem, 6.5vw, 6.8rem)', { lineHeight: '1.05', letterSpacing: '-0.03em' }],
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-up': { from: { opacity: '0', transform: 'translateY(30px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        shimmer: { '0%': { backgroundPosition: '200% 0' }, '100%': { backgroundPosition: '-200% 0' } },
      },
      animation: {
        'fade-in': 'fade-in 0.6s ease-out forwards',
        'slide-up': 'slide-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        shimmer: 'shimmer 2s linear infinite',
        'mesh-drift': 'mesh-drift 18s ease-in-out infinite alternate',
      },
    },
  },
  plugins: [tailwindcssAnimate],
};
