const PLOTLY_VERSION = "3.3.1";
const PLOTLY_VENDOR_PATH = "../vendor/plotly.min.js";
const PLOTLY_LOCAL_URL = new URL(PLOTLY_VENDOR_PATH, import.meta.url).href;

let plotlyPromise = null;

function installedPlotly() {
  const Plotly = globalThis.Plotly;
  if (!Plotly) return null;
  if (String(Plotly.version || "") !== PLOTLY_VERSION) {
    throw new Error(`Unexpected Plotly.js version ${Plotly.version || "unknown"}; expected ${PLOTLY_VERSION}`);
  }
  return Plotly;
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const selector = `script[data-living-assistant-chart-src="${src}"]`;
    const existing = document.querySelector(selector);
    if (existing) {
      try {
        const Plotly = installedPlotly();
        if (Plotly) { resolve(Plotly); return; }
      } catch (error) { reject(error); return; }
      existing.addEventListener("load", () => {
        try {
          const Plotly = installedPlotly();
          Plotly ? resolve(Plotly) : reject(new Error("Plotly.js loaded without global Plotly"));
        } catch (error) { reject(error); }
      }, {once: true});
      existing.addEventListener("error", () => reject(new Error(`Plotly.js failed to load from ${src}`)), {once: true});
      return;
    }

    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.dataset.livingAssistantChartSrc = src;
    script.referrerPolicy = "no-referrer";
    script.addEventListener("load", () => {
      try {
        const Plotly = installedPlotly();
        Plotly ? resolve(Plotly) : reject(new Error("Plotly.js loaded without global Plotly"));
      } catch (error) { reject(error); }
    }, {once: true});
    script.addEventListener("error", () => {
      script.remove();
      reject(new Error(`Plotly.js failed to load from ${src}`));
    }, {once: true});
    document.head.appendChild(script);
  });
}

export function loadPlotly() {
  try {
    const Plotly = installedPlotly();
    if (Plotly) return Promise.resolve(Plotly);
  } catch (error) {
    return Promise.reject(error);
  }
  if (plotlyPromise) return plotlyPromise;
  plotlyPromise = loadScript(PLOTLY_LOCAL_URL).catch((error) => {
    plotlyPromise = null;
    throw error;
  });
  return plotlyPromise;
}

export { PLOTLY_VERSION, PLOTLY_VENDOR_PATH, PLOTLY_LOCAL_URL };
