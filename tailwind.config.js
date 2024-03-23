/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./AkmalExpress/**/*.{html,js}", "./node_modules/flowbite/**/*.js"],
  theme: {
    extend: {},
  },
  plugins: [
        require('flowbite/plugin')
    ],
}