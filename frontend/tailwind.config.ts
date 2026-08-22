import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#100E0B",
          raised: "#1C1712",
          line: "#2C2519",
        },
        paper: {
          DEFAULT: "#F6F1E4",
          dim: "#E8E1CE",
          ink: "#17140F",
        },
        signal: {
          DEFAULT: "#F0631F",
          soft: "#F7935C",
          dim: "#7A3A17",
        },
        mint: {
          DEFAULT: "#35C488",
          dim: "#173B2B",
        },
        brick: {
          DEFAULT: "#C1443A",
          dim: "#3A1D19",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      backgroundImage: {
        "halftone":
          "radial-gradient(rgba(246,241,228,0.06) 1px, transparent 1px)",
      },
      backgroundSize: {
        "halftone-sm": "12px 12px",
      },
      keyframes: {
        "rise-in": {
          "0%": { opacity: "0", transform: "translateY(18px) rotate(-0.6deg)" },
          "100%": { opacity: "1", transform: "translateY(0) rotate(0)" },
        },
        "tear-in": {
          "0%": { opacity: "0", transform: "scaleY(0.85) translateY(10px)" },
          "100%": { opacity: "1", transform: "scaleY(1) translateY(0)" },
        },
        "print-line": {
          "0%": { opacity: "0", transform: "translateY(-4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "count-flicker": {
          "0%": { opacity: "0.4" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        "rise-in": "rise-in 0.6s cubic-bezier(0.16,1,0.3,1) both",
        "tear-in": "tear-in 0.5s cubic-bezier(0.16,1,0.3,1) both",
        "print-line": "print-line 0.25s ease-out both",
        "blink": "blink 1s step-end infinite",
        "shimmer": "shimmer 2.2s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
