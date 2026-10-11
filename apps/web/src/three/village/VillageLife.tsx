// The village's page side (F-11 card 5, 6, 8; ux/scenes/village.md 3, 5): lazy, only for scene.village.
// - the weather: clouds by the clock from 12:20 on the wedding day, rain once a commit names var.weather (13:00 at the
//   latest), cleared in beat.15's window (time.ts). The clouds take the sun's direct light towards nothing, the sky's
//   light down and colder (through Lighting's adjust, settled again as they move); the rain is one instanced mesh of
//   streaks round the camera (fewer with reduced motion);
// - on the ground: splash rings round the camera and puddles by the spots, filling and drying (rainGround.ts);
// - the baked light outside: the light sub-packs' bakes on the ground and the walls, mixed by the clock (outdoorLight.ts);
// - the light sets: which baked set the outside and the house show now (villageLight, for the pack's light sub-packs:
//   code 2), the house dimmed with the daylight and its exposure eased in over about a second at the door;
// - the house's camera zone (scene.json cameraZones): the near follow camera, with 0.5 m either way at the threshold;
// - the yard by the clock (the altar dressed, myrtle on the ground), the vine's lamp at the groom's and the lantern in
//   the hand (one warm point light each, no shadow, flickering), the feast's warm door on the rainy night;
// - the room inside the house, its sub-pack and its own light (Interior.tsx).
// The pack's nodes it looks for by name: altar-dressing, myrtle-leaves, door-glow (any missing is left alone).
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AdditiveBlending,
  Color,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  PointLight,
  ShaderMaterial,
  type Object3D,
} from "three";
import { useWorld } from "../../stores/world";
import { ease } from "../castle/hall";
import { lighting, lightState } from "../Lighting";
import { reducedMotion } from "../motion";
import { rig } from "../rig";
import type { LoadedScene } from "../scene/loadScene";
import { fetchJson } from "../scene/manifest";
import { interiorBase, type InteriorPack } from "./interior";
import {
  flicker,
  lamps,
  outsideLight,
  roomLight,
  weather,
  yard,
  type LightSet,
  type RoomSet,
  type Weather,
} from "./time";
import {
  outdoorBake,
  type LightSets,
  type OutdoorBake,
  type SubPack,
} from "./outdoorLight";
import { fill, puddles, splashMesh } from "./rainGround";
import Interior from "./Interior";
import { inZone, roomWalls, roomZone, type CameraZone } from "./zones";

// what the page shows now, for the light sub-packs (code 2) and the test hook; force: the test page's weather switch
export const villageLight = {
  outside: { a: "day", b: "day", w: 0, rain: 0 } as {
    a: LightSet;
    b: LightSet;
    w: number;
    rain: number;
  },
  room: { set: "day", dim: 1 } as { set: RoomSet; dim: number },
  weather: { cloud: 0, rain: 0 } as Weather,
  inside: false,
  force: null as Weather | null,
};

// the test page (?scene=village&dev&weather=clear|cloud|rain): the weather held, whatever the clock says
const FORCE: Record<string, Weather> = {
  clear: { cloud: 0, rain: 0 },
  cloud: { cloud: 1, rain: 0 },
  rain: { cloud: 1, rain: 1 },
};
const asked = new URLSearchParams(location.search).get("weather");
if (asked && FORCE[asked]) villageLight.force = FORCE[asked];

const RAIN_DROPS = 3000;
const RAIN_BOX = 14; // metres round the camera
const WARM = new Color(1.0, 0.55, 0.22);
const ROOM_EXPOSURE = 2.2; // the house by day against the yard: dark, the door a bright patch (UX 3)

// the weather's commits: the first one naming var.weather starts the rain, a later one stops it
function weatherCommits(
  events: readonly {
    t: number;
    visibleEffects: readonly { kind: string; var?: string }[];
  }[],
): { rainAt: number | null; clearAt: number | null } {
  const at = events
    .filter((e) =>
      e.visibleEffects.some((v) => v.kind === "var" && v.var === "var.weather"),
    )
    .map((e) => e.t);
  return { rainAt: at[0] ?? null, clearAt: at[1] ?? null };
}

function rainMesh(): InstancedMesh {
  const geo = new PlaneGeometry(0.012, 0.55);
  const mat = new ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
    uniforms: {
      uTime: { value: 0 },
      uAmount: { value: 0 },
      uBox: { value: RAIN_BOX },
      uColor: { value: new Color(0.55, 0.6, 0.68) },
    },
    vertexShader: `
uniform float uTime; uniform float uAmount; uniform float uBox;
varying float vA;
void main() {
  vec4 seed = instanceMatrix[3];
  float h = fract(seed.y - uTime * 1.6);
  vec3 p = vec3((seed.x - 0.5) * uBox, (h - 0.5) * uBox, (seed.z - 0.5) * uBox);
  vA = step(seed.w, uAmount);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  mv.xy += position.xy;
  gl_Position = projectionMatrix * mv;
}`,
    fragmentShader: `
uniform vec3 uColor; varying float vA;
void main() { if (vA < 0.5) discard; gl_FragColor = vec4(uColor * 0.35, 0.35); }`,
  });
  const m = new InstancedMesh(geo, mat, RAIN_DROPS);
  const mx = new Matrix4();
  for (let i = 0; i < RAIN_DROPS; i++) {
    // the translation column carries the drop's seed (x, height phase, z) and its share (w: drawn below uAmount)
    mx.identity();
    mx.elements[12] = Math.random();
    mx.elements[13] = Math.random();
    mx.elements[14] = Math.random();
    mx.elements[15] = Math.random();
    m.setMatrixAt(i, mx);
  }
  m.frustumCulled = false;
  m.renderOrder = 10;
  return m;
}

// the lit door: the pack's quads (the light on the ground before the door, the windows) drawn as added light, so they
// are nothing until the feast's night lights them
function glow(node: Object3D | undefined) {
  if (!node) return undefined;
  const mat = new MeshBasicMaterial({
    blending: AdditiveBlending,
    transparent: true,
    depthWrite: false,
    fog: false,
  });
  node.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    (o.material as MeshStandardMaterial).dispose();
    o.material = mat;
    o.castShadow = o.receiveShadow = false;
  });
  node.visible = false;
  return { node, mat };
}

export default function VillageLife({ scene }: { scene: LoadedScene }) {
  const { scene: three, camera, size, gl } = useThree();
  const { manifest } = scene;
  // scene.json's cameraZones (the layout's, card 6); until the pack carries them, the room's box from village-interior
  const listed = (manifest as { cameraZones?: CameraZone[] }).cameraZones;
  const [zones, setZones] = useState<CameraZone[]>(listed ?? []);
  useEffect(() => {
    let live = true;
    let walls: Mesh | null = null;
    fetchJson<InteriorPack>(`${interiorBase(scene.base)}pack.json`)
      .then((p) => {
        if (!live) return;
        if (!listed?.length) setZones([roomZone(p.room)]);
        // the room's walls and ceiling seen from inside, for the camera's wall check (the proxy faces only outwards)
        walls = roomWalls(p.room);
        scene.blockers.push(walls);
      })
      .catch(() => {});
    return () => {
      live = false;
      if (!walls) return;
      const i = scene.blockers.indexOf(walls);
      if (i >= 0) scene.blockers.splice(i, 1);
      walls.geometry.dispose();
      (walls.material as MeshBasicMaterial).dispose();
    };
  }, [listed, scene]);
  const st = useRef({
    inside: false,
    k: 0,
    cloud: -1,
    settled: 0,
    wet: 0,
    lastT: -1,
  });

  // the baked light outside by the clock and the weather (outdoorLight.ts): scene.json lightSets and the light sub-packs
  const bake = useRef<OutdoorBake | null>(null);
  useEffect(() => {
    const m = manifest as { lightSets?: LightSets; subPacks?: SubPack[] };
    if (!m.lightSets || !m.subPacks) return;
    const b = outdoorBake(scene, gl, m.lightSets, m.subPacks);
    bake.current = b;
    return () => {
      bake.current = null;
      b.dispose();
    };
  }, [scene, manifest, gl]);

  const parts = useMemo(() => {
    const find = (name: string): Object3D | undefined =>
      scene.root.getObjectByName(name);
    const vine = new PointLight(WARM, 0, 4, 2);
    const lantern = new PointLight(WARM, 0, 6, 2);
    const spot = manifest.spots["groom-table"];
    if (spot) vine.position.set(spot.pos[0], spot.pos[1] + 2.0, spot.pos[2]);
    return {
      altar: find("altar-dressing"),
      myrtle: find("myrtle-leaves"),
      door: glow(find("door-glow")),
      vine,
      lantern,
      rain: rainMesh(),
      splash: splashMesh(),
      puddles: puddles(manifest.spots, scene.walkable),
    };
  }, [scene, manifest]);

  useEffect(() => {
    three.add(parts.vine, parts.lantern, parts.rain, parts.splash);
    for (const m of parts.puddles) three.add(m);
    // the clouds on the sun and the sky after the clock (and after any adjust before this one)
    const prev = lighting.adjust;
    lighting.adjust = (pos, sun, skies) => {
      prev(pos, sun, skies);
      const c = villageLight.weather.cloud;
      sun.intensity *= 1 - 0.95 * c;
      lightState.direct = sun.intensity;
      for (const s of skies) {
        const u = s.material.uniforms;
        if (u.uSkyGain) u.uSkyGain.value *= 1 - 0.55 * c;
        if (u.mieDirectionalG) u.mieDirectionalG.value *= 1 - c;
      }
    };
    lighting.settle();
    return () => {
      lighting.adjust = prev;
      three.remove(parts.vine, parts.lantern, parts.rain, parts.splash);
      for (const m of [parts.rain, parts.splash]) {
        m.geometry.dispose();
        (m.material as ShaderMaterial).dispose();
      }
      for (const m of parts.puddles) {
        three.remove(m);
        m.geometry.dispose();
        (m.material as MeshStandardMaterial).dispose();
      }
      parts.vine.dispose();
      parts.lantern.dispose();
      lightState.zoneExposure = 1;
      rig.follow = null;
      villageLight.inside = false;
    };
  }, [parts, three]);

  useFrame(({ clock }, dt) => {
    const world = useWorld.getState().world;
    const t = world?.clock.t ?? 0;
    const s = st.current;
    const now = performance.now();
    const { rainAt, clearAt } = weatherCommits(world?.events ?? []);
    const w = villageLight.force ?? weather(t, rainAt, clearAt);
    villageLight.weather = w;
    villageLight.outside = outsideLight(t, w);
    villageLight.room = roomLight(t, w);
    bake.current?.set(t, w.cloud);
    // the sky follows the clouds: the environment again when they have moved enough, at most twice a second
    if (Math.abs(w.cloud - s.cloud) > 0.04 && now - s.settled > 500) {
      s.cloud = w.cloud;
      s.settled = now;
      lighting.settle();
    }

    // the rain round the camera
    const u = (parts.rain.material as ShaderMaterial).uniforms;
    u.uTime!.value = clock.elapsedTime;
    u.uAmount!.value = w.rain * (reducedMotion() ? 0.35 : 1);
    parts.rain.visible = w.rain > 0.01;
    parts.rain.position.copy(camera.position);

    // on the ground: splashes at the player's feet round the camera, puddles filling and drying with the story clock
    // (a jump in the clock, a page loaded mid-storm or the test page's switch, sets them at once)
    const su = (parts.splash.material as ShaderMaterial).uniforms;
    su.uTime!.value = clock.elapsedTime;
    su.uAmount!.value = u.uAmount!.value;
    parts.splash.visible = parts.rain.visible;
    parts.splash.position.set(
      camera.position.x,
      rig.player.y + 0.02,
      camera.position.z,
    );
    const step = s.lastT < 0 ? Infinity : t - s.lastT;
    s.lastT = t;
    s.wet =
      villageLight.force || step < 0 || step > 60
        ? w.rain
        : fill(s.wet, w.rain, step);
    for (const m of parts.puddles) {
      m.visible = s.wet > 0.02;
      (m.material as MeshStandardMaterial).opacity = 0.85 * s.wet;
    }

    // the house: the near camera for the player inside, the exposure for the camera inside
    const p = rig.player;
    const zone = zones.find((z) => inZone(z.polygon, p.x, p.z, s.inside));
    s.inside = !!zone;
    villageLight.inside = s.inside;
    if (zone) {
      const f = size.width < size.height ? zone.portrait : zone.landscape;
      rig.follow = { back: f.back, up: f.up, fov: f.fov };
    } else rig.follow = null;
    const camIn = zones.some((z) =>
      inZone(z.polygon, camera.position.x, camera.position.z, s.k > 0.5),
    );
    s.k = reducedMotion() ? (camIn ? 1 : 0) : ease(s.k, camIn ? 1 : 0, dt);
    const room = villageLight.room;
    const roomExp =
      room.set === "feast" ? 1 : ROOM_EXPOSURE / Math.max(room.dim, 0.3);
    lightState.zoneExposure = 1 + (roomExp - 1) * s.k;

    // the yard, the lamps, the door
    const y = yard(t);
    if (parts.altar) parts.altar.visible = y.altarDressed;
    if (parts.myrtle) parts.myrtle.visible = y.myrtle;
    const l = lamps(t);
    const wave = flicker(clock.elapsedTime, 0);
    parts.vine.intensity = l.vine ? 6 * wave : 0;
    parts.lantern.intensity = l.lantern ? 9 * flicker(clock.elapsedTime, 3) : 0;
    if (l.lantern) parts.lantern.position.set(p.x + 0.3, p.y + 1.1, p.z);
    if (parts.door) {
      parts.door.node.visible = l.door;
      parts.door.mat.color.copy(WARM).multiplyScalar(0.6 * wave);
    }
  });

  return <Interior scene={scene} />;
}
