// The castle's lamps (F-14, ux/scenes/castle.md 3, 5): the throne hall lit by its own lamps day and night, the
// courtyard's braziers at night, the eye adapting across the threshold, the flames. Lazy: only a scene whose
// scene.json has `lamps` (assets/pipeline/castle/lamps.mjs) loads this.
// - the baked lamp light (lightmaps.<mesh>.full) goes on the scene's materials as ZJ_LAMP (shaderPatches.ts): inside
//   the hall it replaces the sky's light, outside it is scaled by lampsOutside (braziers lit from sunset);
// - people and anything else without the bake get a warm fill inside the hall (HALL.fill);
// - the live sun and its shadows stay: the patch of sun through the door is the real one (castle.md 3 「大门」);
// - the camera inside the hall eases the exposure to the lamps' (the night's) over about a second.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import {
  AdditiveBlending,
  CanvasTexture,
  Color,
  Mesh,
  MeshStandardMaterial,
  Sprite,
  SpriteMaterial,
  type Texture,
} from "three";
import { lightState } from "../Lighting";
import type { LoadedScene } from "../scene/loadScene";
import { textureLoader } from "../scene/loadScene";
import { lightmapOf } from "../scene/manifest";
import { fogUniforms, HALL } from "../shaderPatches";
import { ease, flicker, insideHall, lampsOutside, zoneExposure } from "./hall";

const WARM = new Color(1.0, 0.5, 0.17); // about 1900 K, linear (castle.md 5.1), as the bake's lights
const FILL = 0.55; // irradiance on a person in the hall, in the bake's units (tune with the step-26 shots)
const FLAME = { chandelier: 0.16, brazier: 0.55 }; // flame size, metres

function flameTexture(): Texture {
  const c = document.createElement("canvas");
  c.width = 32;
  c.height = 64;
  const g = c.getContext("2d")!;
  const r = g.createRadialGradient(16, 44, 1, 16, 40, 30);
  r.addColorStop(0, "rgba(255,240,200,1)");
  r.addColorStop(0.25, "rgba(255,170,70,0.85)");
  r.addColorStop(0.6, "rgba(220,90,20,0.3)");
  r.addColorStop(1, "rgba(120,30,0,0)");
  g.fillStyle = r;
  g.fillRect(0, 0, 32, 64);
  return new CanvasTexture(c);
}

type Flame = { sprite: Sprite; size: number; indoor: boolean; seed: number };

export default function HallLight({ scene }: { scene: LoadedScene }) {
  const { gl, scene: three, camera } = useThree();
  const { manifest } = scene;
  const lampK = useRef<{ value: number; base: number }[]>([]);
  const state = useRef({ inside: false, k: 0 });

  // the room's box and the uniforms on; off again when the castle goes
  useEffect(() => {
    const h = manifest.hall;
    if (!h) return;
    HALL.min.value.set(...h.min);
    HALL.max.value.set(...h.max);
    HALL.on.value = 1;
    return () => {
      HALL.on.value = 0;
      HALL.lampOut.value = 0;
      HALL.fill.value.setRGB(0, 0, 0);
      lightState.zoneExposure = 1;
    };
  }, [manifest]);

  // the lamps' bake on the scene's materials
  useEffect(() => {
    const load = textureLoader(scene, gl, () => {});
    const ks: { value: number; base: number }[] = [];
    for (const [nodeName, info] of Object.entries(manifest.nodes)) {
      const full = info.lightmap
        ? lightmapOf(manifest, info.lightmap)?.full
        : undefined;
      if (!full) continue;
      const tex = load(full.file, true, false);
      scene.root.getObjectByName(nodeName)?.traverse((o) => {
        if (
          !(o instanceof Mesh) ||
          !(o.material instanceof MeshStandardMaterial)
        )
          return;
        const mat = o.material;
        const uMap = { value: null as Texture | null };
        // three.js: lightMapIntensity = PI * K (encode.py)
        const uK = { value: Math.PI * full.K, base: Math.PI * full.K };
        ks.push(uK);
        mat.defines = { ...mat.defines, ZJ_LAMP: "" };
        mat.onBeforeCompile = (sh) => {
          fogUniforms(sh);
          sh.uniforms.zjLampMap = uMap;
          sh.uniforms.zjLampK = uK;
        };
        mat.needsUpdate = true;
        void tex.then((t) => (uMap.value = t));
      });
    }
    lampK.current = ks;
  }, [scene, manifest, gl]);

  // the flames: soft additive cards over each cup and bowl
  const flames = useMemo(() => {
    const map = flameTexture();
    const out: Flame[] = [];
    let seed = 0;
    for (const l of manifest.lamps ?? []) {
      for (const f of l.flames) {
        const m = new SpriteMaterial({
          map,
          color: new Color(3.2, 1.7, 0.7),
          blending: AdditiveBlending,
          depthWrite: false,
          transparent: true,
          fog: false,
        });
        const s = new Sprite(m);
        const size = FLAME[l.kind];
        s.position.set(f[0], f[1] + size * 0.45, f[2]);
        s.scale.set(size * 0.6, size, 1);
        out.push({ sprite: s, size, indoor: l.indoor, seed: seed++ });
      }
    }
    return { map, list: out };
  }, [manifest]);

  useEffect(() => {
    for (const f of flames.list) three.add(f.sprite);
    return () => {
      for (const f of flames.list) {
        three.remove(f.sprite);
        f.sprite.material.dispose();
      }
      flames.map.dispose();
    };
  }, [flames, three]);

  useFrame(({ clock }, dt) => {
    const h = manifest.hall;
    if (!h) return;
    const t = clock.elapsedTime;
    const s = state.current;
    s.inside = insideHall(camera.position.toArray(), h, s.inside);
    s.k = ease(s.k, s.inside ? 1 : 0, dt);
    lightState.zoneExposure = zoneExposure(lightState.exposure, s.k);
    const out = lampsOutside(lightState.sunDir.y);
    HALL.lampOut.value = out;
    const wave = flicker(t, 0);
    for (const k of lampK.current) k.value = k.base * wave;
    HALL.fill.value.copy(WARM).multiplyScalar(FILL * wave);
    for (const f of flames.list) {
      const lit = f.indoor ? 1 : out;
      f.sprite.visible = lit > 0.02;
      const w = flicker(t * 1.8, f.seed + 1);
      f.sprite.scale.set(f.size * 0.6 * (2 - w), f.size * w * w * lit, 1);
    }
  });

  return null;
}
