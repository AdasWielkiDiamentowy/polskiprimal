/** Tailwind build config (used by the Docker image and `npm run build:css`).
 *
 * Colours and font are mapped to the CSS custom properties that the layout injects from
 * `content/config/theme.json`, so editing the theme restyles the site without a rebuild (R9).
 */
module.exports = {
  content: ["./app/templates/**/*.html", "./app/**/*.py"],
  theme: {
    extend: {
      colors: { primary: "var(--primary-color)", accent: "var(--accent-color)" },
      fontFamily: { sans: ["var(--font-family)"] },
    },
  },
  plugins: [],
};
