// Aetheric Command — shared Tailwind design tokens (from DESIGN.md)
// Load this AFTER the Tailwind CDN <script> and BEFORE your page content.
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "on-tertiary": "#4f2500",
        "error-container": "#93000a",
        "on-error-container": "#ffdad6",
        "primary-fixed": "#e1e0ff",
        "primary-container": "#8083ff",
        "on-surface": "#e5deff",
        "primary": "#c0c1ff",
        "on-background": "#e5deff",
        "inverse-primary": "#494bd6",
        "secondary": "#ffb0cd",
        "tertiary-container": "#d97721",
        "tertiary-fixed-dim": "#ffb783",
        "surface-container-high": "#292549",
        "outline-variant": "#464554",
        "secondary-fixed-dim": "#ffb0cd",
        "surface-variant": "#343055",
        "background": "#120e31",
        "primary-fixed-dim": "#c0c1ff",
        "secondary-fixed": "#ffd9e4",
        "surface-container": "#1f1b3e",
        "on-secondary-container": "#ffbad3",
        "on-surface-variant": "#c7c4d7",
        "on-secondary-fixed": "#3e0022",
        "on-primary": "#1000a9",
        "error": "#ffb4ab",
        "surface-container-low": "#1b163a",
        "on-tertiary-container": "#452000",
        "inverse-on-surface": "#302c50",
        "tertiary-fixed": "#ffdcc5",
        "on-primary-container": "#0d0096",
        "on-tertiary-fixed-variant": "#703700",
        "surface-container-highest": "#343055",
        "surface": "#120e31",
        "on-error": "#690005",
        "on-primary-fixed-variant": "#2f2ebe",
        "on-secondary": "#640039",
        "surface-container-lowest": "#0d082c",
        "tertiary": "#ffb783",
        "secondary-container": "#aa0266",
        "surface-tint": "#c0c1ff",
        "surface-dim": "#120e31",
        "inverse-surface": "#e5deff",
        "surface-bright": "#39355a",
        "outline": "#908fa0",
        "on-secondary-fixed-variant": "#8c0053",
        "on-primary-fixed": "#07006c",
        "on-tertiary-fixed": "#301400"
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.5rem",
        xl: "0.75rem",
        full: "9999px"
      },
      spacing: {
        "component-gap": "16px",
        "gutter": "24px",
        "container-max": "1440px",
        "margin-mobile": "20px",
        "margin-desktop": "48px"
      },
      fontFamily: {
        "display-lg": ["Sora"],
        "body-sm": ["Inter"],
        "label-caps": ["JetBrains Mono"],
        "headline-md": ["Sora"],
        "body-md": ["Inter"],
        "display-lg-mobile": ["Sora"]
      },
      fontSize: {
        "display-lg": ["48px", { lineHeight: "56px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "label-caps": ["12px", { lineHeight: "16px", letterSpacing: "0.1em", fontWeight: "500" }],
        "headline-md": ["24px", { lineHeight: "32px", fontWeight: "600" }],
        "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "display-lg-mobile": ["32px", { lineHeight: "40px", letterSpacing: "-0.02em", fontWeight: "700" }]
      }
    }
  }
};
