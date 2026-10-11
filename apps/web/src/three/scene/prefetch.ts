// The next scene's pack ahead of time (F-10; UX on #103: start at the latest on the act-end page, so the act change
// shows no loading screen): its manifest and the files of its entry pack go into the HTTP cache, nothing is decoded.
// entry: the scene's scenes[].assetUrl in the book manifest (B-7: /scenes/<version>/<dir>/<entry>). A scene split by
// act (scene.road-river) has index.json as its entry, naming each act's pack, a directory next to it; any other scene
// has scene.json and is its own pack. Files marked shared live in that shared pack's directory (road-common), next to
// the pack's: they are fetched by their own URL, so a second stop of the road downloads only what it adds.
// act: the act the player will be in there ("act.4", the act-end destination's toActId); without it a scene with
// several packs fetches only the files they all share, the rest once the act is known.
// Safe to call again (another destination chosen): nothing is cancelled, a file already asked for is not asked again.
// No three.js here: the act-end page can load it on its own.

type Index = { packs: { pack: string; act: string }[] };
type Manifest = { files: { path: string; pack: string; shared?: string }[] };

const asked = new Map<string, Promise<unknown>>();
function once(url: string): Promise<unknown> {
  let p = asked.get(url);
  if (!p) {
    p = fetch(url)
      .then((r) =>
        r.ok ? r.blob() : Promise.reject(new Error(String(r.status))),
      )
      .catch(() => asked.delete(url)); // a failed file is asked for again next time
    asked.set(url, p);
  }
  return p;
}

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return (await r.json()) as T;
}

const at = (rel: string, base: string) =>
  new URL(rel, new URL(base, globalThis.location?.href ?? "http://localhost/"))
    .href;

export async function prefetch(entry: string, act?: string): Promise<void> {
  let manifest = entry;
  let known = true;
  if (/\/index\.json$/.test(entry)) {
    const { packs } = await json<Index>(entry);
    const p =
      (act !== undefined && packs.find((q) => q.act === act)) || packs[0];
    if (!p) return;
    known = act !== undefined || packs.length === 1;
    manifest = at(`../${p.pack}/scene.json`, entry);
  }
  const m = await json<Manifest>(manifest);
  await Promise.all(
    m.files
      .filter((f) => f.pack === "entry" && (known || f.shared))
      .map((f) =>
        once(at(f.shared ? `../${f.shared}/${f.path}` : f.path, manifest)),
      ),
  );
}

// for the tests
export function forget(): void {
  asked.clear();
}
