/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "warm-white": "#FAF8F5",
        "warm-beige": "#F5F0E8",
        ink: "#1A1A1A",
        "memphis-yellow": "#FFD600",
        "memphis-blue": "#2979FF",
        "memphis-coral": "#FF6B6B",
        "memphis-mint": "#00E5A0",
        "memphis-pink": "#FF4081",
        "memphis-purple": "#7C4DFF",
      },
      boxShadow: {
        brutal: "4px 4px 0 0 #1A1A1A",
        "brutal-lg": "8px 8px 0 0 #1A1A1A",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "sans-serif"],
        sans: ['"Noto Sans SC"', "Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
        metric: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
};
