// The three.js classes our JSX writes as elements (<group>, <mesh>, …). r3f's Canvas registers the whole THREE
// namespace (extend(THREE)), which keeps all of three.js in the 3D chunk however little of it the game uses; the build
// points that registration here instead (vite.config.ts threeCatalogue), so the rest is left out (S-083 ⑤). Add a
// class here before writing its element; catalogue.test.ts checks every element in src/ is listed. <primitive> needs
// nothing.
export {
  Group,
  Mesh,
  MeshBasicMaterial,
  PointLight,
  SphereGeometry,
} from "three";
