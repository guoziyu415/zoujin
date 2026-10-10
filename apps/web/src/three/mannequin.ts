// Grey stand-in person until A-0's realistic characters come in (F-2 range 2: 人物先用灰色假人). 1.7 m, front = +Z.
import {
  CapsuleGeometry,
  Group,
  Mesh,
  MeshStandardMaterial,
  SphereGeometry,
} from "three";
import { fogUniforms } from "./shaderPatches";

const body = new CapsuleGeometry(0.2, 0.95, 4, 12);
body.translate(0, 0.2 + 0.475 + 0.02, 0);
const head = new SphereGeometry(0.12, 16, 12);
head.translate(0, 1.56, 0.01);
const nose = new SphereGeometry(0.035, 8, 6); // which way it faces
nose.translate(0, 1.56, 0.12);

export function makeMannequin(tone = 0.32): Group {
  const mat = new MeshStandardMaterial({ roughness: 0.62, metalness: 0 });
  mat.color.setRGB(tone, tone, tone + 0.01);
  mat.onBeforeCompile = fogUniforms;
  const g = new Group();
  for (const geo of [body, head, nose]) {
    const m = new Mesh(geo, mat);
    m.castShadow = true;
    m.receiveShadow = true;
    g.add(m);
  }
  return g;
}
