export default {
  rules: {
    "color-no-hex": true,
    "declaration-property-value-disallowed-list": {
      "/^(?:margin|padding|gap|row-gap|column-gap|inset|top|right|bottom|left)(?:-.+)?$/":
        ["/(?:^|\\s)-?\\d*\\.?\\d+(?:px|rem)(?:\\s|$)/"],
    },
  },
  overrides: [
    {
      files: ["src/styles/tokens.css"],
      rules: {
        "color-no-hex": null,
        "declaration-property-value-disallowed-list": null,
      },
    },
  ],
};
