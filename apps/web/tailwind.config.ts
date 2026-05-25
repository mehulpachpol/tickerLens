import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "hsl(var(--bg))",
        panel: "hsl(var(--panel))",
        text: "hsl(var(--text))",
        muted: "hsl(var(--muted))",
        border: "hsl(var(--border))",
        primary: "hsl(var(--primary))",
        primaryFg: "hsl(var(--primary-fg))",
        danger: "hsl(var(--danger))",
        dangerFg: "hsl(var(--danger-fg))",
      },
      boxShadow: {
        soft: "0 20px 60px rgba(0,0,0,0.35)",
      },
    },
  },
  plugins: [],
} satisfies Config;

