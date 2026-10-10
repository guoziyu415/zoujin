// Runs the start probe (probe.ts) in the render loop while the first scene downloads, then hands the result to the
// quality level. Nothing with a fixed level (?quality=, ?test).
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import { levelDpr } from "./levels";
import { Probe } from "./probe";
import { fixedLevel, quality } from "./quality";

export function QualityProbe() {
  const { gl, size } = useThree();
  const probe = useRef<Probe | null>(null);
  const width = useRef(size.width);
  const height = useRef(size.height);

  useEffect(() => {
    if (fixedLevel || quality.probe) return;
    const p = new Probe(
      gl,
      width.current,
      height.current,
      levelDpr("L1", devicePixelRatio),
    );
    probe.current = p;
    quality.probeStarted();
    return () => {
      p.abort();
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
