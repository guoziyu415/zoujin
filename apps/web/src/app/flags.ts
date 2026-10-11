// Page-wide switches, read once when the page starts. ?test (or window.__zoujinTest from a Playwright init script)
// puts the e2e test hook on window (three/dev/testHook.ts); window.__zoujinNo3d leaves the 3D out of the world screen,
// for the e2e checks that are only about the HUD and the voice. ?crowd=20 stands a crowd on the execution ground (F-4,
// until the ending's staging places it).
const params = new URLSearchParams(location.search);
const g = globalThis as { __zoujinTest?: boolean; __zoujinNo3d?: boolean };

export const flags = {
  test: params.has("test") || g.__zoujinTest === true,
  no3d: g.__zoujinNo3d === true,
  // whole people, at most 40 (?crowd=Infinity would never finish scattering)
  crowd: Math.min(
    40,
    Math.max(0, Math.floor(Number(params.get("crowd")) || 0)),
  ),
};
