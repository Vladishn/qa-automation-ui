const js = require("@eslint/js");
const globals = require("globals");
const tseslint = require("typescript-eslint");
const qaGridFourCols = require("./eslint-rules/qaGridFourCols.js");

module.exports = [
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx,js,jsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      "qa-grid": {
        rules: {
          "four-cols": qaGridFourCols,
        },
      },
    },
    rules: {
      "qa-grid/four-cols": "error",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/ban-ts-comment": "off",
      "no-empty": "off",
      "no-console": "off",
      "no-unused-disable-directive": "off",
    },
  },
];
