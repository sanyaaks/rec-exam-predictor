/** @type {import('tailwindcss').Config} */
// Theme colours are CSS variables (see src/index.css) so light/dark switch without touching components.
const v = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: v("canvas"),
        surface: v("surface"),
        subtle: v("subtle"),
        sidebar: v("sidebar"),
        ink: { DEFAULT: v("ink"), soft: v("ink-soft"), mute: v("ink-mute") },
        line: v("line"),
        lav: { 50: v("lav-50"), 100: v("lav-100"), 200: v("lav-200"), 400: v("lav-400"), 500: v("lav-500"), 600: v("lav-600"), 700: v("lav-700") },
        // neutral greys used for tints/hover states - theme-aware too
        stone: { 50: v("stone-50"), 100: v("stone-100"), 200: v("stone-200"), 300: v("stone-300") },
        slate: { 100: v("stone-100"), 200: v("stone-200") },
        sky2: { 50: v("sky2-50"), 100: v("sky2-100"), 400: v("sky2-400"), 500: v("sky2-500"), 600: v("sky2-600") },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["'DM Sans'", "Inter", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgb(var(--c-shadow) / 0.04), 0 4px 16px rgb(var(--c-shadow) / 0.05)",
        lift: "0 2px 4px rgb(var(--c-shadow) / 0.05), 0 12px 32px rgb(var(--c-shadow) / 0.08)",
      },
      borderRadius: { "2xl": "1rem", "3xl": "1.5rem" },
    },
  },
  plugins: [],
};
