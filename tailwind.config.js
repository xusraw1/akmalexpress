/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./akmalexpress/templates/**/*.html",
    "./node_modules/flowbite/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "sans-serif"],
        display: ["Space Grotesk", "sans-serif"],
      },
      colors: {
        brand: {
          DEFAULT: "#0f766e",
          warm: "#ea580c",
          ink: "#132333",
        },
      },
    },
  },
  plugins: [require("flowbite/plugin")],
};
