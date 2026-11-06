/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: "#0a0c14",
          panel: "rgba(18, 22, 36, 0.85)",
          border: "rgba(0, 242, 254, 0.25)",
          cyan: "#00f2fe",
          pink: "#ff007f",
          purple: "#7928ca",
          yellow: "#ffe600",
        },
      },
      fontFamily: {
        orbitron: ["var(--font-orbitron)", "monospace"],
        rajdhani: ["var(--font-rajdhani)", "sans-serif"],
      },
    },
  },
  plugins: [],
};

