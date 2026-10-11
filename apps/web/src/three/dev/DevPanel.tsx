// ?dev: move the world clock (in the village over the whole day, any of its three days, and its weather), play the sunset (art-direction 10 check 2: 18:00 -> 19:10), shut the workshop, and a
// frame-time / draw-call readout with the quality level. For the team, not players; the numbers for decisions come
// from the measuring page (?measure).
import { useEffect, useRef, useState } from "react";
import { frameStats } from "../PostFX";
import { useQuality } from "../quality/quality";
import { usePlayer } from "../../stores/player";
import { useWorld } from "../../stores/world";
import { sandbox } from "./sandbox";
import type { LoadStage } from "../World";

// the village's test page (F-11): the weather held, or back to the clock and the commits
const WEATHER = { clear: [0, 0], cloud: [1, 0], rain: [1, 1] } as const;
async function villageWeather(w: keyof typeof WEATHER | null) {
  const { villageLight } = await import("../village/VillageLife");
  villageLight.force =
    w === null ? null : { cloud: WEATHER[w][0], rain: WEATHER[w][1] };
}
const village = new URLSearchParams(location.search).get("scene") === "village";

const hhmm = (t: number) => {
  const m = ((t % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(Math.round(m % 60)).padStart(2, "0")}`;
};

export function DevPanel({ stage }: { stage: LoadStage }) {
  const t = useWorld((s) => s.world?.clock.t ?? 0);
  const place = usePlayer((s) => s.place) ?? "";
  const workshopOpen = useWorld(
    (s) => s.world?.places["place.stonemason-workshop"]?.enabled ?? true,
  );
  const q = useQuality();
  const [hud, setHud] = useState("");
  const anim = useRef(0);

  useEffect(() => {
    const ft: number[] = [];
    let last = performance.now();
    let raf = 0;
    const tick = () => {
      const now = performance.now();
      ft.push(now - last);
      last = now;
      if (ft.length > 120) ft.shift();
      if (ft.length % 15 === 0) {
        const s = [...ft].sort((a, b) => a - b);
        const p50 = s[Math.floor(s.length * 0.5)] ?? 0;
        const p95 = s[Math.floor(s.length * 0.95)] ?? 0;
        setHud(
          `${(1000 / p50).toFixed(0)} fps  p95 ${p95.toFixed(1)} ms  draw ${frameStats.calls}  tri ${(frameStats.triangles / 1000).toFixed(0)}k`,
        );
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const sunset = () => {
    if (anim.current) {
      cancelAnimationFrame(anim.current);
      anim.current = 0;
      return;
    }
    const t0 = performance.now();
    const step = () => {
      const f = Math.min(1, (performance.now() - t0) / 40000);
      sandbox.setClock(1080 + 70 * f);
      anim.current = f < 1 ? requestAnimationFrame(step) : 0;
    };
    step();
  };

  return (
    <div
      style={{
        position: "fixed",
        left: 8,
        right: 8,
        top: "max(8px, env(safe-area-inset-top))",
        padding: "6px 8px",
        borderRadius: 8,
        background: "rgba(0,0,0,.5)",
        color: "#f1e9d8",
        font: "12px/1.4 ui-monospace, Menlo, monospace",
      }}
    >
      <div>
        {stage} · {hhmm(t)} · {place.replace("place.", "")} · {q.level}
        {q.applied !== q.level ? `（${q.applied}）` : ""} {q.assetTier}
        {q.lowPower ? " lowPower" : ""}
      </div>
      <div>{hud}</div>
      <input
        aria-label="clock"
        type="range"
        min={village ? 0 : 270}
        max={village ? 1435 : 1230}
        step={5}
        value={t % 1440}
        onChange={(e) =>
          sandbox.setClock(Math.floor(t / 1440) * 1440 + Number(e.target.value))
        }
        style={{ width: "100%" }}
      />
      {village && (
        <div>
          {[1, 2, 3].map((d) => (
            <button
              key={d}
              onClick={() => sandbox.setClock(d * 1440 + (t % 1440))}
            >
              {d}日目
            </button>
          ))}{" "}
          {(["clear", "cloud", "rain"] as const).map((w) => (
            <button key={w} onClick={() => void villageWeather(w)}>
              {w}
            </button>
          ))}
          <button onClick={() => void villageWeather(null)}>clock</button>
        </div>
      )}
      <button onClick={sunset}>18:00 → 19:10</button>{" "}
      <button
        onClick={() =>
          sandbox.setPlaceEnabled("place.stonemason-workshop", !workshopOpen)
        }
      >
        workshop {workshopOpen ? "open" : "shut"}
      </button>
    </div>
  );
}
