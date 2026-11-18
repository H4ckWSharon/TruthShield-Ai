import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        navy: {
          950: "#060A17",
          900: "#0B132B",
          850: "#101B38",
          800: "#1C2541",
          700: "#2A3B66",
        },
        cyber: {
          bg: "#070C18",
          card: "#0E172A",
          cardHover: "#132038",
          border: "#1E293B",
          borderGlow: "#0284C7",
          cyan: "#00B4D8",
          blue: "#3B82F6",
        }
      },
    },
  },
  plugins: [],
};
export default config;
