// Runs the start probe (probe.ts) in the render loop while the first scene downloads, then hands the result to the
// quality level. Nothing with a fixed level (?quality=, ?test). The probe's code is its own small chunk, fetched while
// the scene does (it keeps the 3D chunk inside its budget, S-083 ⑤).
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import { levelDpr } from "./levels";
import type { Probe } from "./probe";
import { fixedLevel, quality } from "./quality";

export function QualityProbe() {
  const { gl, size } = useThree();
  const probe = useRef<Probe | null>(null);
  const width = useRef(size.width);
  const height = useRef(size.height);

  useEffect(() => {
    if (fixedLevel || quality.probe) return;
    let p: Probe | null = null;
    let gone = false;
    quality.probeStarted();
    import("./probe").then(
      ({ Probe }) => {
        if (gone) return;
        p = new Probe(
          gl,
          width.current,
          height.current,
          levelDpr("L1", devicePixelRatio),
        );
        probe.current = p;
      },
      () => {
        if (!gone) quality.setProbe(null);
      },
    );
    return () => {
      gone = true;
      p?.abort();
      probe.current = null;
    };
  }, [gl]);

  useFrame(() => {
    const p = probe.current;
    if (!p) return;
    p.frame(performance.now());
    if (!p.done) return;
    probe.current = null;
    quality.setProbe(p.result);
  }, 2);
  return null;
}
