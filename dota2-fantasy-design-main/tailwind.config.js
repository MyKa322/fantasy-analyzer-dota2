/**
 * Tailwind config — Dota 2 Fantasy Analytics
 * Direction: modern minimalist. Monochrome UI, semantic colour only.
 * Pairs with: src/styles/tokens.css
 *
 * There is no accent colour by design. If a component reaches for a hue that
 * isn't an emblem group or a team crest, that's a mistake — colour in this
 * product means something.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        n: {
          950: 'var(--n-950)', 900: 'var(--n-900)', 850: 'var(--n-850)',
          800: 'var(--n-800)', 750: 'var(--n-750)', 700: 'var(--n-700)',
          600: 'var(--n-600)', 500: 'var(--n-500)', 400: 'var(--n-400)',
          300: 'var(--n-300)', 200: 'var(--n-200)', 100: 'var(--n-100)',
          50:  'var(--n-050)',
        },
        bg: {
          page:   'var(--color-bg-page)',
          base:   'var(--color-bg-base)',
          card:   'var(--color-bg-card)',
          raised: 'var(--color-bg-raised)',
          hover:  'var(--color-bg-hover)',
        },
        fg: {
          heading:   'var(--color-text-heading)',
          DEFAULT:   'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
          tertiary:  'var(--color-text-tertiary)',
        },
        line: {
          DEFAULT: 'var(--color-border)',
          strong:  'var(--color-border-strong)',
        },
        // Semantic only. `group` resolves from the [data-group] scope.
        group: {
          DEFAULT: 'var(--group)',
          dim:     'var(--group-dim)',
          line:    'var(--group-line)',
        },
        red:   { DEFAULT: 'var(--group-red)',   dim: 'var(--group-red-dim)',   line: 'var(--group-red-line)' },
        blue:  { DEFAULT: 'var(--group-blue)',  dim: 'var(--group-blue-dim)',  line: 'var(--group-blue-line)' },
        green: { DEFAULT: 'var(--group-green)', dim: 'var(--group-green-dim)', line: 'var(--group-green-line)' },
      },

      spacing: {
        1: 'var(--space-1)', 2: 'var(--space-2)', 3: 'var(--space-3)',
        4: 'var(--space-4)', 5: 'var(--space-5)', 6: 'var(--space-6)',
        7: 'var(--space-7)', 8: 'var(--space-8)', 9: 'var(--space-9)',
        10: 'var(--space-10)', 11: 'var(--space-11)', 12: 'var(--space-12)',
        touch: 'var(--touch-min)',
        control: 'var(--control-height)',
        tile: 'var(--icon-tile)',
      },

      fontFamily: {
        display: 'var(--font-display)',
        body:    'var(--font-body)',
        mono:    'var(--font-mono)',
      },

      fontSize: {
        '2xs':  'var(--text-2xs)',
        xs:     'var(--text-xs)',
        sm:     'var(--text-sm)',
        base:   'var(--text-base)',
        md:     'var(--text-md)',
        lg:     'var(--text-lg)',
        xl:     'var(--text-xl)',
        '2xl':  'var(--text-2xl)',
        '3xl':  'var(--text-3xl)',
      },

      fontWeight: {
        regular:  'var(--weight-regular)',
        medium:   'var(--weight-medium)',
        semibold: 'var(--weight-semibold)',
        bold:     'var(--weight-bold)',
      },

      lineHeight: {
        tight:   'var(--leading-tight)',
        snug:    'var(--leading-snug)',
        normal:  'var(--leading-normal)',
        relaxed: 'var(--leading-relaxed)',
      },

      letterSpacing: {
        tight:  'var(--track-tight)',
        normal: 'var(--track-normal)',
        label:  'var(--track-label)',
      },

      borderRadius: {
        sm:   'var(--radius-sm)',
        md:   'var(--radius-md)',
        lg:   'var(--radius-lg)',
        full: 'var(--radius-full)',
      },

      maxWidth: {
        page:   'var(--width-page)',
        banner: 'var(--width-banner)',
        prose:  'var(--width-prose)',
      },

      boxShadow: {
        none:    'var(--shadow-none)',
        overlay: 'var(--shadow-overlay)',
      },

      transitionDuration: {
        fast:   'var(--dur-fast)',
        normal: 'var(--dur-normal)',
        slow:   'var(--dur-slow)',
      },
      transitionTimingFunction: { DEFAULT: 'var(--ease)' },

      zIndex: {
        header:  'var(--z-header)',
        overlay: 'var(--z-overlay)',
        popover: 'var(--z-popover)',
      },

      screens: { sm: '420px', md: '768px', lg: '1024px', xl: '1280px', '2xl': '1536px' },
    },
  },
  plugins: [],
};
