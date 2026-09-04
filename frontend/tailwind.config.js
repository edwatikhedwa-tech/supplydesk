/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: 'var(--sd-surface)',
          subtle: 'var(--sd-surface-subtle)',
          elevated: 'var(--sd-surface-elevated)',
        },
        line: {
          DEFAULT: 'var(--sd-border)',
          subtle: 'var(--sd-border-subtle)',
        },
        'ink-text': 'var(--sd-text)',
        accent: {
          50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa',
          500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a',
        },
        ink: {
          50: '#f8fafc', 100: '#f1f5f9', 200: '#e2e8f0', 300: '#cbd5e1', 400: '#94a3b8',
          500: '#64748b', 600: '#475569', 700: '#334155', 800: '#1e293b', 900: '#0f172a',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
      fontFamily: {
        sans: ['Public Sans', 'Geist', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
        'page-title': ['clamp(1.75rem, 1.55rem + 0.55vw, 2rem)', { lineHeight: '1.15', letterSpacing: '-0.022em' }],
        'display-title': ['clamp(2rem, 1.75rem + 0.9vw, 2.25rem)', { lineHeight: '1.1', letterSpacing: '-0.03em' }],
        metric: ['clamp(1.75rem, 1.55rem + 0.45vw, 1.875rem)', { lineHeight: '1.1', letterSpacing: '-0.025em' }],
      },
      borderRadius: {
        'sd-sm': 'var(--sd-radius-sm)',
        'sd-md': 'var(--sd-radius-md)',
        'sd-lg': 'var(--sd-radius-lg)',
        xl: '0.875rem',
        '2xl': '1.25rem',
      },
      boxShadow: {
        soft: '0 1px 2px 0 rgba(15, 23, 42, 0.04), 0 1px 3px 0 rgba(15, 23, 42, 0.06)',
        panel: '0 4px 12px -2px rgba(15, 23, 42, 0.06), 0 2px 6px -1px rgba(15, 23, 42, 0.04)',
        float: '0 12px 32px -8px rgba(15, 23, 42, 0.12), 0 4px 12px -4px rgba(15, 23, 42, 0.06)',
      },
      keyframes: {
        'fade-in': { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        'slide-up': { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        'scale-in': { '0%': { opacity: '0', transform: 'scale(0.96)' }, '100%': { opacity: '1', transform: 'scale(1)' } },
        'ring-pulse': { '0%': { transform: 'scale(0.55)', opacity: '0.9' }, '75%': { opacity: '0' }, '100%': { transform: 'scale(1.6)', opacity: '0' } },
        'ring-spin': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } },
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.4s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
        'ring-pulse': 'ring-pulse 2.4s cubic-bezier(0.25,0.6,0.4,1) infinite',
        'ring-spin-slow': 'ring-spin 6s linear infinite',
        'ring-spin-slow-reverse': 'ring-spin 8s linear infinite reverse',
      },
    },
  },
  plugins: [],
};
