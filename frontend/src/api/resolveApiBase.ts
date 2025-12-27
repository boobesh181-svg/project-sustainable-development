/**
 * Single source of truth for API base URL selection.
 *
 * Default behavior (recommended): use relative URLs so Vite's dev proxy handles API calls.
 *
 * Note on LAN/"Network" testing:
 * - If the UI is opened via a LAN IP (e.g. http://192.168.x.x:5173), any API base
 *   like http://localhost:8000 will point to the *client* device, not this dev machine.
 * - To keep things working across devices in dev, we force relative URLs in that case.
 */
export function resolveApiBase(): string {
  const envBase =
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    "";

  if (import.meta.env.DEV) {
    // In dev, always use relative URLs so the Vite dev-server proxy handles API calls.
    // This avoids CORS and also works when testing from LAN devices.
    return "";
  }

  return envBase;
}
