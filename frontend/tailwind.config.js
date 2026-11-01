import colors from 'tailwindcss/colors';
import plugin from 'tailwindcss/plugin';

/*
 * Theming: every colour class (slate-*, brand-*, emerald-*, ...) reads a CSS variable, so the whole UI
 * switches between dark and light, and between accent colours, without touching components.
 *   :root            -> dark theme (default)
 *   .light           -> light theme
 *   [data-accent=x]  -> picks the "brand" colour
 */

const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];

// Light theme: lighter shades become darker and vice versa. Solid fills (500-700) keep their shade so
// white text on buttons stays readable.
const LIGHT_SHADE = { 50: 950, 100: 900, 200: 800, 300: 700, 400: 600, 500: 500, 600: 600, 700: 700, 800: 200, 900: 100, 950: 50 };

const SLATE_DARK = { ...colors.slate, 850: '#151e2e', 950: '#070b14' };
const SLATE_LIGHT = {
  50: '#020617', 100: '#0f172a', 200: '#1e293b', 300: '#334155', 400: '#475569', 500: '#64748b',
  600: '#94a3b8', 700: '#cbd5e1', 800: '#e2e8f0', 850: '#f8fafc', 900: '#ffffff', 950: '#f3f5f9',
};

const ACCENTS = ['violet', 'emerald', 'sky', 'rose', 'amber'];
const SEMANTIC = ['emerald', 'sky', 'amber', 'rose'];

const rgb = (hex) => {
  const h = hex.replace('#', '');
  return `${parseInt(h.slice(0, 2), 16)} ${parseInt(h.slice(2, 4), 16)} ${parseInt(h.slice(4, 6), 16)}`;
};

const ramp = (name, extra = []) =>
  Object.fromEntries([...SHADES, ...extra].map((s) => [s, `rgb(var(--${name}-${s}) / <alpha-value>)`]));

const vars = (name, palette, light) =>
  Object.fromEntries(
    Object.keys(light ? LIGHT_SHADE : palette)
      .map(Number)
      .filter((s) => SHADES.includes(s))
      .map((s) => [`--${name}-${s}`, rgb(palette[light ? LIGHT_SHADE[s] : s])]),
  );

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '"Segoe UI Variable"', '"Segoe UI"', 'system-ui', '-apple-system', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Cascadia Code"', 'Consolas', '"Fira Code"', 'monospace'],
      },
      colors: {
        slate: ramp('slate', [850]),
        brand: ramp('brand'),
        emerald: ramp('emerald'),
        sky: ramp('sky'),
        amber: ramp('amber'),
        rose: ramp('rose'),
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-up': { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'slide-in-left': { from: { transform: 'translateX(-100%)' }, to: { transform: 'translateX(0)' } },
        'pop-in': { '0%': { opacity: '0', transform: 'scale(0.92)' }, '100%': { opacity: '1', transform: 'scale(1)' } },
        'bounce-dot': { '0%, 80%, 100%': { transform: 'translateY(0)', opacity: '0.4' }, '40%': { transform: 'translateY(-5px)', opacity: '1' } },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'slide-up': 'slide-up 180ms ease-out',
        'slide-in-left': 'slide-in-left 200ms ease-out',
        'pop-in': 'pop-in 220ms cubic-bezier(0.34, 1.56, 0.64, 1)',
        'bounce-dot': 'bounce-dot 1.2s infinite ease-in-out',
      },
    },
  },
  plugins: [
    plugin(({ addBase }) => {
      const dark = {
        ...vars('slate', SLATE_DARK, false),
        '--slate-850': rgb(SLATE_DARK[850]),
        '--slate-950': rgb(SLATE_DARK[950]),
        ...Object.assign({}, ...SEMANTIC.map((n) => vars(n, colors[n], false))),
        ...vars('brand', colors.violet, false),
        '--glow': rgb(colors.violet[300]),
      };
      const light = {
        ...Object.fromEntries(Object.entries(SLATE_LIGHT).map(([s, hex]) => [`--slate-${s}`, rgb(hex)])),
        ...Object.assign({}, ...SEMANTIC.map((n) => vars(n, colors[n], true))),
        ...vars('brand', colors.violet, true),
      };
      addBase({ ':root': dark, '.light': light });

      // Accent choices: set the brand ramp (and the mascot glow) for each theme
      for (const a of ACCENTS) {
        addBase({
          [`[data-accent="${a}"]`]: { ...vars('brand', colors[a], false), '--glow': rgb(colors[a][300]) },
          [`.light[data-accent="${a}"]`]: vars('brand', colors[a], true),
        });
      }
    }),
  ],
};
