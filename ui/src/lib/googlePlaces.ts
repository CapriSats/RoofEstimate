// Lightweight loader for Google Maps JS Places library.
// Returns the global `google` namespace once ready, or null if no key / load fails.

declare global {
  interface Window {
    google?: any;
    __gmapsPromise?: Promise<any> | null;
  }
}

export function loadGooglePlaces(apiKey: string | undefined): Promise<any> | null {
  if (typeof window === "undefined") return null;
  if (!apiKey) return null;
  if (window.google?.maps?.places) return Promise.resolve(window.google);
  if (window.__gmapsPromise) return window.__gmapsPromise;

  window.__gmapsPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      'script[data-gmaps-loader="1"]',
    );
    if (existing) {
      existing.addEventListener("load", () => resolve(window.google));
      existing.addEventListener("error", reject);
      return;
    }
    const s = document.createElement("script");
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
      apiKey,
    )}&libraries=places&v=weekly`;
    s.async = true;
    s.defer = true;
    s.dataset.gmapsLoader = "1";
    s.onload = () => resolve(window.google);
    s.onerror = (e) => {
      window.__gmapsPromise = null;
      reject(e);
    };
    document.head.appendChild(s);
  });

  return window.__gmapsPromise;
}
