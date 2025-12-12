/***** Tailwind config (CommonJS) *****/

module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eef9ff",
          100: "#d9efff",
          500: "#1f7ae0",
          600: "#175fb1",
        },
      },
    },
  },
  plugins: [],
};
