import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        foundation: {
          dark: "#0a0a0a",
          "dark-secondary": "#171717",
          light: "#fafafa",
          "light-secondary": "#f5f5f4",
          warm: "#F4F1EA",
        },
        accent: {
          primary: "#c2410c",
          "primary-hover": "#ea580c",
          secondary: "#78716c",
          action: "#dc2626",
        },
        stone: {
          50: "#fafafa",
          100: "#f5f5f4",
          200: "#e7e5e4",
          300: "#d6d3d1",
          400: "#a8a29e",
          500: "#78716c",
          600: "#57534e",
          700: "#44403c",
          800: "#292524",
          900: "#1c1917",
        },
      },
      fontFamily: {
        serif: ["Playfair Display", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      borderRadius: {
        "3xl": "24px",
        "2xl": "16px",
        xl: "12px",
      },
      boxShadow: {
        "warm-sm": "0 4px 16px rgba(42, 30, 24, 0.06)",
        "warm-md": "0 8px 32px rgba(42, 30, 24, 0.08)",
        "warm-lg": "0 24px 80px rgba(42, 30, 24, 0.08)",
        "accent-sm": "0 8px 24px rgba(194, 65, 12, 0.15)",
        "accent-md": "0 12px 32px rgba(194, 65, 12, 0.22)",
      },
      animation: {
        "fade-in": "fadeIn 0.4s ease-out forwards",
        "fade-in-up": "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "scale-in": "scaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      },
    },
  },
  plugins: [],
};

export default config;
