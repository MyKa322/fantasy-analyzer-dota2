/**
 * Tailwind config — Dota 2 Fantasy: Banner Builder & Advisor
 * Philosophy: Heraldic Deco
 * Pairs with: .design/dota-fantasy/DESIGN_TOKENS.css
 *
 * Every value maps to a CSS custom property. Nothing is hardcoded here, so
 * the token file stays the single source of truth and a theme change never
 * requires touching a component.
 *
 * NAMING: token names are semantic, not visual. Use `bg-surface-parchment`,
 * never `bg-tan`. If a component reaches for a raw palette value, that's a
 * missing semantic token — add one rather than working around it.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // --- Surfaces -----------------------------------------------------
        bg: {
          primary:   'var(--color-bg-primary)',
          secondary: 'var(--color-bg-secondary)',
          tertiary:  'var(--color-bg-tertiary)',
          elevated:  'var(--color-bg-elevated)',
          sunken:    'var(--color-bg-sunken)',
          inverse:   'var(--color-bg-inverse)',
        },
        surface: {
          parchment:      'var(--color-surface-parchment)',
          'parchment-hi': 'var(--color-surface-parchment-hi)',
          'parchment-lo': 'var(--color-surface-parchment-lo)',
          'parchment-edge':'var(--color-surface-parchment-edge)',
          slate:          'var(--color-surface-slate)',
          'slate-hi':     'var(--color-surface-slate-hi)',
          'slate-panel':  'var(--color-surface-slate-panel)',
          overlay:        'var(--color-surface-overlay)',
        },

        // --- Text. `text-*` is for DARK surfaces, `onparch-*` for parchment.
        // Mixing them is the most likely contrast bug in this system.
        ink: {
          primary:   'var(--color-text-primary)',
          heading:   'var(--color-text-heading)',
          secondary: 'var(--color-text-secondary)',
          tertiary:  'var(--color-text-tertiary)',
          accent:    'var(--color-text-accent)',
          link:      'var(--color-text-link)',
        },
        onparch: {
          DEFAULT:   'var(--color-text-on-parch)',
          heading:   'var(--color-text-on-parch-heading)',
          secondary: 'var(--color-text-on-parch-secondary)',
          tertiary:  'var(--color-text-on-parch-tertiary)',
        },
        onslate: 'var(--color-text-on-slate)',

        // --- Gold, forked by use. `gold-ornament` FAILS as body text. -----
        gold: {
          ornament:      'var(--color-gold-ornament)',
          text:          'var(--color-gold-text)',
          'text-parch':  'var(--color-gold-text-on-parch)',
          pale:  '#F2DFAE',
          light: '#E5C87E',
          base:  '#C9A24E',
          mid:   '#A8822F',
          deep:  '#7E601F',
          shadow:'#4E3A12',
        },

        // --- Emblem groups. SEMANTIC — never decorative. ------------------
        emblem: {
          'red-glyph':    'var(--color-emblem-red-glyph)',
          'red-header':   'var(--color-emblem-red-header)',
          'red-body':     'var(--color-emblem-red-body)',
          'blue-glyph':   'var(--color-emblem-blue-glyph)',
          'blue-header':  'var(--color-emblem-blue-header)',
          'blue-body':    'var(--color-emblem-blue-body)',
          'green-glyph':  'var(--color-emblem-green-glyph)',
          'green-header': 'var(--color-emblem-green-header)',
          'green-body':   'var(--color-emblem-green-body)',
        },

        // --- Deltas. Gold/terracotta, NOT green/red — see token file. -----
        delta: {
          gain:    'var(--color-delta-gain)',
          loss:    'var(--color-delta-loss)',
          neutral: 'var(--color-delta-neutral)',
        },

        status: {
          success: 'var(--color-status-success)',
          warning: 'var(--color-status-warning)',
          error:   'var(--color-status-error)',
          info:    'var(--color-status-info)',
        },

        border: {
          primary:   'var(--color-border-primary)',
          secondary: 'var(--color-border-secondary)',
          subtle:    'var(--color-border-subtle)',
          ornament:  'var(--color-border-ornament)',
          onparch:   'var(--color-border-on-parch)',
        },

        // Darkened vs. the client reference so a light glyph passes AA.
        // A mid-tone plate carries neither dark nor light text — see tokens.
        steel: {
          light:  '#66655E',
          base:   '#4E4D47',
          deep:   '#38372F',
          shadow: '#1F1E1A',
        },
      },

      spacing: {
        0:  'var(--space-0)',
        1:  'var(--space-1)',
        2:  'var(--space-2)',
        3:  'var(--space-3)',
        4:  'var(--space-4)',
        5:  'var(--space-5)',
        6:  'var(--space-6)',
        7:  'var(--space-7)',
        8:  'var(--space-8)',
        9:  'var(--space-9)',
        10: 'var(--space-10)',
        11: 'var(--space-11)',
        12: 'var(--space-12)',
        'touch': 'var(--btn-touch-min)',
      },

      fontFamily: {
        display: 'var(--font-family-display)',
        body:    'var(--font-family-body)',
        numeric: 'var(--font-family-numeric)',
        mono:    'var(--font-family-mono)',
      },

      fontSize: {
        xs:    'var(--font-size-xs)',
        sm:    'var(--font-size-sm)',
        base:  'var(--font-size-base)',
        md:    'var(--font-size-md)',
        lg:    'var(--font-size-lg)',
        xl:    'var(--font-size-xl)',
        '2xl': 'var(--font-size-2xl)',
        '3xl': 'var(--font-size-3xl)',
        '4xl': 'var(--font-size-4xl)',
      },

      fontWeight: {
        normal:   'var(--font-weight-normal)',
        medium:   'var(--font-weight-medium)',
        semibold: 'var(--font-weight-semibold)',
        bold:     'var(--font-weight-bold)',
      },

      lineHeight: {
        tight:   'var(--line-height-tight)',
        snug:    'var(--line-height-snug)',
        normal:  'var(--line-height-normal)',
        relaxed: 'var(--line-height-relaxed)',
      },

      letterSpacing: {
        tight:   'var(--letter-spacing-tight)',
        normal:  'var(--letter-spacing-normal)',
        wide:    'var(--letter-spacing-wide)',
        wider:   'var(--letter-spacing-wider)',
        widest:  'var(--letter-spacing-widest)',
      },

      borderRadius: {
        sm:   'var(--border-radius-sm)',
        md:   'var(--border-radius-md)',
        lg:   'var(--border-radius-lg)',
        full: 'var(--border-radius-full)',
      },

      borderWidth: {
        hair:  'var(--border-width-hair)',
        base:  'var(--border-width-base)',
        frame: 'var(--border-width-frame)',
      },

      maxWidth: {
        content: 'var(--max-width-content)',
        wide:    'var(--max-width-wide)',
        page:    'var(--max-width-page)',
        banner:  'var(--max-width-banner)',
        popover: 'var(--popover-max-width)',
        advisor: 'var(--advisor-width)',
      },

      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
        // Bevels — the signature. Use these instead of soft shadows on
        // anything that should read as Source 2 hardware.
        'bevel-gold':         'var(--bevel-gold-raised)',
        'bevel-gold-pressed': 'var(--bevel-gold-pressed)',
        'bevel-well':         'var(--bevel-well)',
        'bevel-panel':        'var(--bevel-panel-raised)',
        'bevel-parchment':    'var(--bevel-parchment)',
        // Glows
        'glow-sm':    'var(--glow-emblem-sm)',
        'glow-md':    'var(--glow-emblem-md)',
        'glow-lg':    'var(--glow-emblem-lg)',
        'glow-gold':  'var(--glow-gold)',
        'glow-gold-lg':'var(--glow-gold-lg)',
        // Focus
        'ring-dark':  'var(--ring-on-dark)',
        'ring-parch': 'var(--ring-on-parch)',
      },

      backgroundImage: {
        'banner':      'var(--banner-bg)',
        'btn-gold':    'var(--btn-gold-bg)',
        'btn-gold-hover': 'var(--btn-gold-bg-hover)',
        'btn-steel':   'var(--btn-steel-bg)',
        'modal':       'var(--modal-bg)',
        'teamcard':    'var(--teamcard-bg)',
      },

      transitionDuration: {
        instant:  'var(--duration-instant)',
        fast:     'var(--duration-fast)',
        normal:   'var(--duration-normal)',
        slow:     'var(--duration-slow)',
        slower:   'var(--duration-slower)',
        ceremony: 'var(--duration-ceremony)',
      },

      transitionTimingFunction: {
        default: 'var(--easing-default)',
        in:      'var(--easing-in)',
        out:     'var(--easing-out)',
        settle:  'var(--easing-settle)',
        bounce:  'var(--easing-bounce)',
      },

      zIndex: {
        base:     'var(--z-base)',
        raised:   'var(--z-raised)',
        sticky:   'var(--z-sticky)',
        header:   'var(--z-header)',
        backdrop: 'var(--z-backdrop)',
        overlay:  'var(--z-overlay)',
        popover:  'var(--z-popover)',
        toast:    'var(--z-toast)',
      },

      screens: {
        sm:   '375px',
        md:   '768px',
        lg:   '1024px',
        xl:   '1280px',
        '2xl':'1536px',
      },

      keyframes: {
        'emblem-land': {
          '0%':   { opacity: '0', transform: 'translateY(-8px) scale(0.94)' },
          '60%':  { opacity: '1', transform: 'translateY(2px) scale(1.02)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        'emblem-dissolve': {
          '0%':   { opacity: '1', filter: 'blur(0)' },
          '100%': { opacity: '0', filter: 'blur(6px)', transform: 'scale(1.08)' },
        },
        'gold-sheen': {
          '0%':   { backgroundPosition: '-120% 0' },
          '100%': { backgroundPosition: '220% 0' },
        },
        'token-spend': {
          '0%':   { transform: 'scale(1)' },
          '35%':  { transform: 'scale(1.22)' },
          '100%': { transform: 'scale(1)' },
        },
      },

      animation: {
        'emblem-land':     'emblem-land var(--duration-slow) var(--easing-settle) both',
        'emblem-dissolve': 'emblem-dissolve var(--duration-normal) var(--easing-in) forwards',
        'gold-sheen':      'gold-sheen var(--duration-ceremony) var(--easing-out)',
        'token-spend':     'token-spend var(--duration-slow) var(--easing-bounce)',
      },
    },
  },
  plugins: [],
};
