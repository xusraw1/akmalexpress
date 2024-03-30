/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./AkmalExpress/**/*.{html,js}", "./node_modules/flowbite/**/*.js"],
  theme: {
    extend: {},
    screens: {
      'sm': '640px', // Small screens
      'md': '768px', // Medium screens
      'lg': '1024px', // Large screens
      'xl': '1280px', // Extra large screens
      // Add more breakpoints if needed
    },
  },
  plugins: [
        require('flowbite/plugin')
    ],
}