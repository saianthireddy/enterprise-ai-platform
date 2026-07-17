import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          500: "#3b5bdb",
          600: "#2f4bc7",
          900: "#0d1b2a",
        },
      },
    },
  },
  plugins: [],
};

export default config;
