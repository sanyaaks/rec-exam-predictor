/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#faf8f4",
        ink: { DEFAULT: "#1f2440", soft: "#4a4f6a", mute: "#7c8098" },
        line: "#ebe7df",
        lav: { 50: "#f5f3ff", 100: "#ece9fb", 200: "#dcd6fa", 400: "#a99cf8", 500: "#8b7cf6", 600: "#6f5ee8", 700: "#5847c9" },
        sky2: { 50: "#eef4fd", 100: "#dde9fb", 400: "#7aa2e8", 500: "#5b86d9", 600: "#3f6fd8" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["'DM Sans'", "Inter", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(31,36,64,0.04), 0 4px 16px rgba(31,36,64,0.05)",
        lift: "0 2px 4px rgba(31,36,64,0.05), 0 12px 32px rgba(31,36,64,0.08)",
      },
      borderRadius: { "2xl": "1rem", "3xl": "1.5rem" },
    },
  },
  plugins: [],
};
