// The room inside Melos's house (F-11 range 5, 6; ux/scenes/village.md 3): the sub-pack village-interior, loaded in
// the background once the village stands (Melos goes in at 10:30 of the first day), and lit by its own bake.
// - the light set villageLight.room says (time.ts roomLight): the day's sky through the door and windows, dimmed with
//   the daylight outside, or the feast's hearth and lamps (flickering); the bake goes on the room's materials as the
//   castle's lamps do (shaderPatches ZJ_LAMP);
// - inside the room's box the sky's light is taken out (HALL): the room's walls get only their bake, people a fill
//   from the floor's light near them; the live sun stays, so the evening's slant through the door is the real one;
// - the feast's flames over the hearth and the lamps.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import {
  AdditiveBlending,
  CanvasTexture,
  Color,
  Mesh,
  MeshStandardMaterial,
  Sprite,
  SpriteMaterial,
  type Group,
  type Texture,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { flicker } from "../castle/hall";
import { rig } from "../rig";
import { textureLoader, type LoadedScene } from "../scene/loadScene";
import { fetchJson } from "../scene/manifest";
import { fogUniforms, HALL } from "../shaderPatches";
import {
  hallBox,
  interiorBase,
  personLight,
  type InteriorPack,
} from "./interior";
import { villageLight } from "./VillageLife";
import type { RoomSet } from "./time";

const FLAME_COLOUR = new Color(3.2, 1.7, 0.7);

// a soft flame card, as the castle's (castle/HallLight.tsx)
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

type Room = {
  pack: InteriorPack;
  root: Group;
  maps: Partial<Record<RoomSet, Texture>>;
  lamp: { value: Texture | null }; // the set's lightmap, on every material of the room
  k: { value: number };
  mats: MeshStandardMaterial[];
  flames: { sprite: Sprite; size: number; seed: number }[];
  flameMap: Texture;
  shown: RoomSet | null;
};

async function loadRoom(
  scene: LoadedScene,
  gl: Parameters<typeof textureLoader>[1],
): Promise<Room> {
  const base = interiorBase(scene.base);
  const pack = await fetchJson<InteriorPack>(`${base}pack.json`);
  const gltf = await new GLTFLoader()
    .setMeshoptDecoder(MeshoptDecoder)
    .loadAsync(`${base}${pack.geometry}`);
  // textureLoader reads only these of a loaded scene: where the pack is, its files' sizes, its texture cache
  const load = textureLoader(
    {
      base,
      manifest: { files: pack.files },
      textures: new Map(),
      bytes: 0,
    } as unknown as LoadedScene,
    gl,
    () => {},
  );
  const lamp = { value: null as Texture | null };
  const k = { value: 0 };
  const mats: MeshStandardMaterial[] = [];
  gltf.scene.traverse((o) => {
    if (!(o instanceof Mesh)) return;
    const old = o.material as MeshStandardMaterial;
    const e = pack.materials[old.name];
    const mat = new MeshStandardMaterial({
      color: e ? new Color().setRGB(...e.color) : 0x808080,
      roughness: e?.roughness ?? 0.9,
      metalness: e?.metalness ?? 0,
    });
    mat.name = old.name;
    old.dispose();
    // the bake through the castle's lamp path: it reads the aoMap's UVs, so the lightmap is also the aoMap, at no
    // strength
    mat.defines = { ...mat.defines, ZJ_LAMP: "" };
    mat.aoMapIntensity = 0;
    mat.onBeforeCompile = (sh) => {
      fogUniforms(sh);
      sh.uniforms.zjLampMap = lamp;
      sh.uniforms.zjLampK = k;
    };
    const tex = (key: string | undefined) =>
      key ? pack.textures[key] : undefined;
    const b = tex(e?.base);
    const n = tex(e?.nrm);
    const mr = tex(e?.mr);
    if (b)
      void load(b.std.file, true, true).then((t) => {
        mat.map = t;
        mat.needsUpdate = true;
      });
    if (n)
      void load(n.std.file, false, true).then((t) => {
        mat.normalMap = t;
        mat.normalScale.set(1, -1); // glTF normal maps with three's derivative tangents (S7)
        mat.needsUpdate = true;
      });
    if (mr)
      void load(mr.std.file, false, true).then((t) => {
        mat.roughnessMap = mat.metalnessMap = t;
        mat.needsUpdate = true;
      });
    o.material = mat;
    o.receiveShadow = true;
    mats.push(mat);
  });
  const maps: Room["maps"] = {};
  await Promise.all(
    (Object.keys(pack.lightSets) as RoomSet[]).map((set) =>
      load(pack.lightSets[set].file, true, false).then((t) => {
        t.channel = 1;
        maps[set] = t;
      }),
    ),
  );
  const flameMap = flameTexture();
  const flames = pack.flames.map((f, seed) => {
    const s = new Sprite(
      new SpriteMaterial({
        map: flameMap,
        color: FLAME_COLOUR,
        blending: AdditiveBlending,
        depthWrite: false,
        transparent: true,
        fog: false,
      }),
    );
    s.position.set(f.pos[0], f.pos[1] + f.size * 0.45, f.pos[2]);
    s.scale.set(f.size * 0.6, f.size, 1);
    s.visible = false;
    return { sprite: s, size: f.size, seed };
  });
  return {
    pack,
    root: gltf.scene,
    maps,
    lamp,
    k,
    mats,
    flames,
    flameMap,
    shown: null,
  };
}

export default function Interior({ scene }: { scene: LoadedScene }) {
  const { gl, scene: three } = useThree();
  const [room, setRoom] = useState<Room | null>(null);
  const fill = useRef(new Color());

  useEffect(() => {
    let gone = false;
    loadRoom(scene, gl).then(
      (r) => !gone && setRoom(r),
      (err: unknown) => console.warn("village-interior:", err), // the house stays an empty shell
    );
    return () => {
      gone = true;
    };
  }, [scene, gl]);

  useEffect(() => {
    if (!room) return;
    const box = hallBox(room.pack.room);
    HALL.min.value.set(...box.min);
    HALL.max.value.set(...box.max);
    HALL.on.value = 1;
    three.add(room.root);
    for (const f of room.flames) three.add(f.sprite);
    return () => {
      HALL.on.value = 0;
      HALL.fill.value.setRGB(0, 0, 0);
      three.remove(room.root);
      for (const f of room.flames) {
        three.remove(f.sprite);
        f.sprite.material.dispose();
      }
      room.flameMap.dispose();
      room.root.traverse((o) => {
        if (o instanceof Mesh) o.geometry.dispose();
      });
      for (const m of room.mats) m.dispose();
    };
  }, [room, three]);

  useFrame(({ clock }) => {
    if (!room) return;
    const { set, dim } = villageLight.room;
    const s = room.pack.lightSets[set];
    if (room.shown !== set && room.maps[set]) {
      room.shown = set;
      room.lamp.value = room.maps[set]!;
      for (const m of room.mats) {
        if (!m.aoMap) m.needsUpdate = true; // USE_AOMAP: the shader changes once
        m.aoMap = room.maps[set]!;
      }
    }
    const t = clock.elapsedTime;
    const wave = set === "feast" ? flicker(t, 0) : 1;
    const level = set === "feast" ? wave : dim;
    // three.js: lightMapIntensity = PI * K (pack_interior.mjs, as encode.py)
    room.k.value = Math.PI * s.K * level;
    const p = rig.player;
    const c = personLight(s.floor, p.x, p.z);
    fill.current.setRGB(c[0], c[1], c[2]).multiplyScalar(Math.PI * level);
    HALL.fill.value.copy(fill.current);
    for (const f of room.flames) {
      f.sprite.visible = set === "feast";
      const w = flicker(t * 1.8, f.seed + 1);
      f.sprite.scale.set(f.size * 0.6 * (2 - w), f.size * w * w, 1);
    }
  });

  return null;
}
