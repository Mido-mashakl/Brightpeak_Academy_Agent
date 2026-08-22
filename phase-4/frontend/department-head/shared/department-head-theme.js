/**
 * department-head-theme.js
 * ---------------------------------------------------------------
 * Shared design tokens for the Department Head section, extracted
 * from the Brightpeak "Aura Intelligence Command" Stitch designs
 * (DESIGN.md included with the supplied screens).
 *
 * Load order required in every page <head>:
 *   1. <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
 *   2. <script src="../shared/department-head-theme.js"></script>
 *   3. page-specific .css file
 * ---------------------------------------------------------------
 */
(function () {
  if (typeof tailwind === "undefined") {
    console.warn("[department-head-theme] Tailwind CDN script must be loaded first.");
    return;
  }

  tailwind.config = {
    darkMode: "class",
    theme: {
      extend: {
        colors: {
          "surface-variant": "#32353c",
          "tertiary-container": "#4d8eff",
          "on-error-container": "#ffdad6",
          tertiary: "#adc6ff",
          secondary: "#ddb8ff",
          "surface-container-high": "#272a31",
          "on-secondary-fixed": "#2c0051",
          "secondary-fixed-dim": "#ddb8ff",
          "on-primary-container": "#340080",
          "surface-container": "#1d2026",
          "on-surface-variant": "#cbc3d7",
          outline: "#958ea0",
          "primary-container": "#a078ff",
          "inverse-primary": "#6d3bd7",
          "on-error": "#690005",
          "on-secondary": "#490081",
          "secondary-container": "#62259b",
          "on-surface": "#e1e2eb",
          "on-background": "#e1e2eb",
          "inverse-surface": "#e1e2eb",
          "surface-tint": "#d0bcff",
          "on-secondary-container": "#d1a1ff",
          surface: "#10131a",
          "surface-bright": "#363940",
          "surface-container-low": "#191c22",
          "on-primary-fixed-variant": "#5516be",
          background: "#10131a",
          "on-tertiary": "#002e6a",
          "on-tertiary-fixed": "#001a42",
          "on-secondary-fixed-variant": "#62259b",
          "secondary-fixed": "#f0dbff",
          "inverse-on-surface": "#2e3037",
          "on-primary-fixed": "#23005c",
          "on-tertiary-fixed-variant": "#004395",
          "on-primary": "#3c0091",
          "surface-container-highest": "#32353c",
          "error-container": "#93000a",
          primary: "#d0bcff",
          "primary-fixed": "#e9ddff",
          "primary-fixed-dim": "#d0bcff",
          "surface-dim": "#10131a",
          "on-tertiary-container": "#00285d",
          "outline-variant": "#494454",
          "tertiary-fixed-dim": "#adc6ff",
          "tertiary-fixed": "#d8e2ff",
          "surface-container-lowest": "#0b0e14",
          error: "#ffb4ab",
          success: "#8fd6a3",
          warning: "#f5c26b"
        },
        borderRadius: { DEFAULT: "0.25rem", lg: "0.5rem", xl: "0.75rem", full: "9999px" },
        spacing: { gutter: "24px", sm: "12px", xl: "64px", lg: "40px", base: "8px", "margin-safe": "32px", xs: "4px", md: "24px" },
        fontFamily: {
          "body-md": ["Inter", "sans-serif"],
          "body-sm": ["Inter", "sans-serif"],
          "body-lg": ["Inter", "sans-serif"],
          "label-caps": ["Geist", "monospace"],
          "display-lg": ["Hanken Grotesk", "sans-serif"],
          "headline-lg": ["Hanken Grotesk", "sans-serif"],
          "headline-md": ["Hanken Grotesk", "sans-serif"],
          "mono-data": ["Geist", "monospace"]
        },
        fontSize: {
          "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
          "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
          "body-lg": ["18px", { lineHeight: "28px", fontWeight: "400" }],
          "label-caps": ["12px", { lineHeight: "16px", letterSpacing: "0.1em", fontWeight: "600" }],
          "display-lg": ["48px", { lineHeight: "56px", letterSpacing: "-0.02em", fontWeight: "700" }],
          "headline-lg": ["32px", { lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: "600" }],
          "headline-md": ["24px", { lineHeight: "32px", fontWeight: "600" }],
          "mono-data": ["14px", { lineHeight: "20px", fontWeight: "500" }]
        }
      }
    }
  };

  const style = document.createElement("style");
  style.textContent = `
    body{background-color:#0B0E14;background-image:radial-gradient(circle at 100% 0%, #1A122B 0%, transparent 50%);background-attachment:fixed;color:#e1e2eb;min-height:100vh;}
    ::-webkit-scrollbar{width:8px;height:8px;}
    ::-webkit-scrollbar-track{background:transparent;}
    ::-webkit-scrollbar-thumb{background:#32353c;border-radius:4px;}
    ::-webkit-scrollbar-thumb:hover{background:#494454;}
    .glass-panel{background:rgba(30,27,75,0.4);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.1);box-shadow:inset 0 0 10px rgba(192,132,252,0.05);}
    .ai-glow{box-shadow:0 0 15px rgba(192,132,252,0.2);}
    .ai-border-gradient{border:1px solid transparent;background-image:linear-gradient(rgba(30,27,75,0.8),rgba(30,27,75,0.8)),linear-gradient(to right,#a078ff,#ddb8ff);background-origin:border-box;background-clip:padding-box, border-box;}
    .badge{display:inline-flex;align-items:center;gap:4px;padding:2px 10px;border-radius:9999px;font-family:'Geist',monospace;font-size:11px;letter-spacing:.05em;font-weight:600;text-transform:uppercase;}
    .badge-ai{background:rgba(208,188,255,0.12);color:#d0bcff;border:1px solid rgba(208,188,255,0.3);}
    .badge-human{background:rgba(173,198,255,0.12);color:#adc6ff;border:1px solid rgba(173,198,255,0.3);}
    .badge-open{background:rgba(255,180,171,0.12);color:#ffb4ab;border:1px solid rgba(255,180,171,0.3);}
    .badge-investigating{background:rgba(245,194,107,0.12);color:#f5c26b;border:1px solid rgba(245,194,107,0.3);}
    .badge-resolved{background:rgba(143,214,163,0.12);color:#8fd6a3;border:1px solid rgba(143,214,163,0.3);}
    .badge-severe{background:rgba(255,180,171,0.15);color:#ffb4ab;}
    .badge-major{background:rgba(245,194,107,0.15);color:#f5c26b;}
    .badge-minor{background:rgba(173,198,255,0.15);color:#adc6ff;}
  `;
  document.head.appendChild(style);
})();
