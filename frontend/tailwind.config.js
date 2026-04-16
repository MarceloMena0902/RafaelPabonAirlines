/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          wine:   "#8B1B3D",   // vino oscuro (Qatar-style primary)
          wine2:  "#6B1430",   // vino más profundo
          wine3:  "#4A0E22",   // vino muy oscuro (hover)
          gold:   "#D4A017",   // dorado
          gold2:  "#B8860B",   // dorado oscuro
          navy:   "#0A1F44",   // azul marino (footer)
          light:  "#FAFAFA",   // fondo general
          cream:  "#FDF6EC",   // crema suave
          // compat aliases
          900: "#4A0E22",
          800: "#8B1B3D",
          700: "#6B1430",
          600: "#C0002A",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "hero-sky": "linear-gradient(105deg, #1a0a05 0%, #3d1a0a 30%, #8B4513 60%, #D2691E 80%, #DAA520 100%)",
      },
    },
  },
  plugins: [],
};
