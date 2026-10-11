// 独立于任何书中世界的原创玩家书房。米制建模、分材质合批，无远程素材和网络调用。
import {
  BoxGeometry,
  BufferGeometry,
  Color,
  CylinderGeometry,
  DoubleSide,
  ExtrudeGeometry,
  Float32BufferAttribute,
  Group,
  LatheGeometry,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  Shape,
  SphereGeometry,
  TorusGeometry,
  Vector2,
  Vector3,
  type Material,
} from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { homeMaterials, random } from "./materials";

type XYZ = [number, number, number];
export type HomeTarget = "books" | "memories";

export function buildRoom() {
  const root = new Group();
  root.name = "reader-home";
  const m = homeMaterials();
  const rng = random(121024);
  const buckets = new Map<Material, BufferGeometry[]>();
  const resources = new Set<Material>(m.all);
  // Preserve the book/board colours as vertex data: two materials instead of twelve,
  // including in the shadow and AO passes on the baseline phone.
  const coloredBatch = (source: MeshStandardMaterial) => {
    const material = source.clone();
    material.color.set("#ffffff");
    material.vertexColors = true;
    resources.add(material);
    return material;
  };
  const floorBatch = coloredBatch(m.floor[0]!);
  const booksBatch = coloredBatch(m.books[0]!);
  const hits: Mesh[] = [];
  const temp = new Matrix4();
  const add = (
    geo: BufferGeometry,
    mat: Material,
    pos: XYZ,
    rotation: XYZ = [0, 0, 0],
  ) => {
    const mesh = new Mesh(geo);
    mesh.position.set(...pos);
    mesh.rotation.set(...rotation);
    mesh.updateMatrix();
    temp.copy(mesh.matrix);
    geo.applyMatrix4(temp);
    if (!geo.getAttribute("uv")) throw new Error("Missing room UVs");
    if (
      m.floor.includes(mat as MeshStandardMaterial) ||
      m.books.includes(mat as MeshStandardMaterial)
    ) {
      const color = (mat as MeshStandardMaterial).color;
      const colors = new Float32Array(geo.getAttribute("position").count * 3);
      for (let i = 0; i < colors.length; i += 3) color.toArray(colors, i);
      geo.setAttribute("color", new Float32BufferAttribute(colors, 3));
      mat = m.floor.includes(mat as MeshStandardMaterial)
        ? floorBatch
        : booksBatch;
    }
    const list = buckets.get(mat) ?? [];
    if (geo.index) {
      const source = geo;
      geo = source.toNonIndexed();
      source.dispose();
    }
    list.push(geo);
    buckets.set(mat, list);
  };
  const box = (pos: XYZ, size: XYZ, mat: Material, rotation: XYZ = [0, 0, 0]) =>
    add(new BoxGeometry(...size), mat, pos, rotation);
  const rounded = (
    pos: XYZ,
    size: XYZ,
    mat: Material,
    rotation: XYZ = [0, 0, 0],
  ) =>
    add(
      new RoundedBoxGeometry(...size, 2, Math.min(...size) * 0.24),
      mat,
      pos,
      rotation,
    );
  const cylinder = (
    pos: XYZ,
    radius: number,
    height: number,
    mat: Material,
    top = radius,
    rotation: XYZ = [0, 0, 0],
  ) => add(new CylinderGeometry(top, radius, height, 16), mat, pos, rotation);
  const sphere = (pos: XYZ, radius: number, mat: Material) =>
    add(new SphereGeometry(radius, 20, 12), mat, pos);
  const lathe = (pos: XYZ, profile: [number, number][], mat: Material) =>
    add(
      new LatheGeometry(
        profile.map((p) => new Vector2(...p)),
        24,
      ),
      mat,
      pos,
    );
  const target = (kind: HomeTarget, pos: XYZ, size: XYZ) => {
    const mat = new MeshBasicMaterial({ visible: false });
    resources.add(mat);
    const mesh = new Mesh(new BoxGeometry(...size), mat);
    mesh.position.set(...pos);
    mesh.userData.homeTarget = kind;
    mesh.updateMatrixWorld(true);
    hits.push(mesh);
  };

  // Wall panels and mouldings are dimensional, so sun and lamps catch their edges.
  box([0, -0.13, 0], [9.2, 0.22, 10], m.walnut);
  box([0, 2.45, -4.7], [9.4, 4.9, 0.24], m.plaster);
  box([-4.62, 2.45, 0], [0.24, 4.9, 9.4], m.plaster);
  box([4.62, 0.57, 0], [0.24, 1.14, 9.4], m.plaster);
  box([4.62, 4.48, 0], [0.24, 0.85, 9.4], m.plaster);
  // Three high French windows: an original study silhouette, outside the ancient book's period.
  for (const z of [-4.06, -0.25, 3.62])
    box([4.62, 2.65, z], [0.24, 3.05, 1.15], m.plaster);
  box([0, 4.87, 0], [9.3, 0.18, 9.5], m.cream);
  // Raised ceiling borders and the panelled doorway give the room architectural depth.
  for (const x of [-3.95, 3.95]) box([x, 4.72, 0], [0.09, 0.1, 8.2], m.cream);
  for (const z of [-4.0, 0.1, 4.2])
    box([0, 4.72, z], [8.0, 0.1, 0.09], m.cream);
  box([-4.4, 1.34, 1.72], [0.14, 2.64, 1.56], m.wood);
  for (const z of [0.86, 2.58])
    box([-4.28, 1.41, z], [0.16, 2.82, 0.13], m.cream);
  box([-4.28, 2.82, 1.72], [0.16, 0.15, 1.87], m.cream);
  for (const y of [0.66, 1.87])
    for (const z of [1.35, 2.08]) {
      box([-4.31, y, z], [0.05, 1.0, 0.61], m.walnut);
      box([-4.275, y, z], [0.025, 0.88, 0.49], m.wood);
    }
  sphere([-4.19, 1.19, 2.31], 0.042, m.brass);
  for (const y of [0.12, 1.1, 4.44, 4.62, 4.74]) {
    const size = y > 4 ? 0.14 : 0.1;
    box([0, y, -4.49], [9.1, size, 0.16], m.cream);
    box([-4.43, y, 0], [0.16, size, 9.2], m.cream);
    box([4.43, y, 0], [0.16, size, 9.2], m.cream);
  }
  for (let x = -4; x <= 4; x += 1) {
    box([x, 0.59, -4.52], [0.91, 0.91, 0.06], m.green);
    box([x, 0.59, -4.465], [0.71, 0.67, 0.025], m.dark);
    box([x, 0.59, -4.442], [0.67, 0.63, 0.025], m.green);
  }
  for (let z = -4; z <= 4; z += 1)
    for (const x of [-4.5, 4.5]) {
      box([x, 0.59, z], [0.06, 0.91, 0.91], m.green);
      box([x > 0 ? x - 0.04 : x + 0.04, 0.59, z], [0.025, 0.67, 0.71], m.dark);
      box([x > 0 ? x - 0.06 : x + 0.06, 0.59, z], [0.025, 0.63, 0.67], m.green);
    }
  // Parquet: real alternating boards, restrained variation, five colours in one batch.
  for (let row = 0; row < 17; row++)
    for (let col = 0; col < 16; col++) {
      const x = -4.35 + col * 0.56,
        z = -4.35 + row * 0.56;
      const rotate = (row + col) % 2;
      for (let k = 0; k < 4; k++) {
        box(
          [
            x + (rotate ? (k - 1.5) * 0.138 : 0),
            0,
            z + (rotate ? 0 : (k - 1.5) * 0.138),
          ],
          [0.549, 0.028, 0.13],
          m.floor[Math.floor(rng() * m.floor.length)]!,
          [0, rotate ? Math.PI / 2 : 0, 0],
        );
      }
    }
  box([0.1, 0.034, 0.5], [3.1, 0.019, 4.4], m.rug);
  // Outside the windows: a quiet garden, distant foliage and sky in true geometry.
  const sky = new MeshBasicMaterial({ color: "#cbd2c2", side: DoubleSide });
  resources.add(sky);
  box([24, 5, 0], [0.1, 22, 60], sky);
  const leaves = new MeshStandardMaterial({ color: "#687860", roughness: 1 });
  resources.add(leaves);
  for (let i = 0; i < 18; i++) {
    const z = -12 + rng() * 25,
      h = 2 + rng() * 2.2;
    cylinder([13.7 + rng(), h / 2, z], 0.07, h, m.walnut);
    sphere([13.9, h + 0.2, z], 0.6 + rng() * 0.7, leaves);
  }
  for (const z of [-2.25, 1.67]) {
    const group = new Group();
    // Arch frame drawn as an extruded ring in XY, then turned onto the east wall.
    const arch = new Shape();
    const w = 1.18,
      base = 1.18,
      spring = 3.05;
    arch.moveTo(-w, base);
    arch.lineTo(-w, spring);
    arch.absarc(0, spring, w, Math.PI, 0, true);
    arch.lineTo(w, base);
    arch.lineTo(w - 0.11, base);
    arch.lineTo(w - 0.11, spring);
    arch.absarc(0, spring, w - 0.11, 0, Math.PI, false);
    arch.lineTo(-w + 0.11, base);
    arch.closePath();
    const geo = new ExtrudeGeometry(arch, {
      depth: 0.1,
      bevelEnabled: true,
      bevelSegments: 1,
      steps: 1,
      bevelSize: 0.017,
      bevelThickness: 0.017,
      curveSegments: 24,
    });
    add(geo, m.cream, [4.39, 0, z], [0, -Math.PI / 2, 0]);
    box([4.39, 1.15, z], [0.38, 0.12, 2.58], m.stone);
    box([4.42, 2.64, z], [0.08, 2.95, 0.065], m.cream);
    for (const y of [2.0, 2.83, 3.37])
      box([4.41, y, z], [0.075, 0.055, y === 3.37 ? 2.02 : 2.28], m.cream);
    // Gathered linen curtains. Folds have volume, never alpha-blended wall cards.
    for (const side of [-1, 1])
      for (let i = 0; i < 5; i++) {
        const zz = z + side * (1.12 + i * 0.055);
        cylinder(
          [4.15 + Math.sin(i * 1.5) * 0.05, 2.73, zz],
          0.055,
          2.91,
          m.fabric,
          0.041,
        );
      }
    root.add(group);
  }

  function book(
    x: number,
    y: number,
    z: number,
    height: number,
    width: number,
    color: Material,
    stack = false,
  ) {
    const r: XYZ = stack ? [0, 0, Math.PI / 2] : [0, 0, 0];
    box([x, y + height / 2, z], [width, height, 0.27], color, r);
    if (!stack) {
      for (const yy of [
        y + height * 0.15,
        y + height * 0.78,
        y + height * 0.87,
      ])
        box([x, yy, z + 0.139], [width * 0.83, 0.009, 0.009], m.brass);
      box(
        [x, y + height * 0.57, z + 0.139],
        [width * 0.55, 0.055, 0.005],
        m.pages,
      );
    }
  }
  function shelf(cx: number, z: number) {
    const width = 2.35;
    box([cx, 1.99, z - 0.15], [width, 3.67, 0.1], m.walnut);
    for (const x of [cx - width / 2, cx + width / 2]) {
      box([x, 2.03, z + 0.035], [0.16, 3.88, 0.48], m.wood);
      box([x, 2.03, z + 0.295], [0.08, 3.75, 0.045], m.wood);
      for (const y of [0.27, 3.88])
        box([x, y, z + 0.06], [0.23, 0.13, 0.53], m.wood);
    }
    for (const y of [0.22, 0.95, 1.58, 2.21, 2.84, 3.5, 3.95]) {
      box([cx, y, z + 0.075], [width + 0.12, 0.085, 0.52], m.wood);
      box([cx, y - 0.04, z + 0.345], [width + 0.14, 0.035, 0.037], m.walnut);
    }
    // Lower cupboards make this furniture, not a grid of floating blocks.
    for (const x of [cx - 0.54, cx + 0.54]) {
      box([x, 0.59, z + 0.33], [1.03, 0.59, 0.055], m.wood);
      box([x, 0.59, z + 0.368], [0.83, 0.41, 0.032], m.walnut);
      sphere([x + 0.36, 0.59, z + 0.42], 0.018, m.brass);
    }
    for (const [row, base] of [1.0, 1.63, 2.26, 2.89].entries()) {
      let x = cx - 1.06;
      while (x < cx + 0.98) {
        const bw = 0.055 + rng() * 0.07,
          h = 0.31 + rng() * 0.19;
        // a little breathing room and leaning stacks, never titles of unimplemented books.
        if (row === 2 && x > cx + 0.45 && x < cx + 0.9) {
          x += 0.15;
          continue;
        }
        book(
          x + bw / 2,
          base,
          z + 0.11 + rng() * 0.045,
          h,
          bw,
          m.books[Math.floor(rng() * m.books.length)]!,
        );
        x += bw + 0.011;
      }
    }
    target("books", [cx, 2.07, z + 0.13], [2.6, 3.8, 0.7]);
  }
  shelf(-2.75, -4.2);
  shelf(2.75, -4.2);

  // Fireplace, limestone surround, raised mantel and a hand-generated landscape painting.
  box([0, 0.62, -4.38], [1.5, 1.23, 0.21], m.dark);
  box([0, 0.07, -3.97], [2.25, 0.12, 1.05], m.stone);
  for (const x of [-0.89, 0.89]) {
    box([x, 0.8, -4.03], [0.32, 1.5, 0.46], m.stone);
    box([x, 0.15, -3.98], [0.43, 0.15, 0.53], m.stone);
    for (let j = -1; j <= 1; j++)
      box([x + j * 0.065, 0.77, -3.786], [0.025, 1.1, 0.026], m.cream);
  }
  box([0, 1.56, -4.02], [2.12, 0.27, 0.51], m.stone);
  box([0, 1.73, -3.99], [2.3, 0.11, 0.66], m.cream);
  box([0, 1.66, -3.78], [2.17, 0.055, 0.07], m.stone);
  for (const y of [2.29, 3.59])
    box([0, y, -4.31], [2.28, 0.08, 0.095], m.brass);
  for (const x of [-1.1, 1.1])
    box([x, 2.94, -4.31], [0.08, 1.3, 0.095], m.brass);
  for (const y of [2.35, 3.53])
    box([0, y, -4.29], [2.13, 0.04, 0.055], m.walnut);
  add(new PlaneGeometry(2.1, 1.16), m.painting, [0, 2.94, -4.34]);
  for (let i = 0; i < 4; i++)
    cylinder([-0.43 + i * 0.29, 0.25, -4.0], 0.08, 0.65, m.walnut, 0.07, [
      Math.PI / 2,
      0.12 * i,
      0.15,
    ]);
  for (const x of [-0.7, 0.7]) {
    cylinder([x, 0.3, -3.72], 0.025, 0.53, m.bronze);
    sphere([x, 0.59, -3.72], 0.049, m.bronze);
  }
  box([0, 0.3, -3.7], [1.4, 0.025, 0.025], m.bronze);

  // Writing desk, turned legs, inlaid leather and a readable volume placed on the table.
  const dx = -1.54,
    dz = -0.36;
  rounded([dx, 0.91, dz], [2.45, 0.12, 1.21], m.wood);
  box([dx, 0.985, dz], [1.35, 0.018, 0.77], m.leather);
  for (const x of [dx - 1.01, dx + 1.01])
    for (const z of [dz - 0.43, dz + 0.43]) {
      lathe(
        [x, 0.04, z],
        [
          [0.052, 0],
          [0.04, 0.1],
          [0.045, 0.25],
          [0.061, 0.35],
          [0.044, 0.42],
          [0.042, 0.61],
          [0.08, 0.66],
          [0.072, 0.83],
        ],
        m.wood,
      );
    }
  box([dx, 0.75, dz + 0.45], [2.15, 0.21, 0.09], m.walnut);
  for (const x of [dx - 0.62, dx + 0.62]) {
    box([x, 0.75, dz + 0.515], [0.81, 0.16, 0.025], m.wood);
    cylinder([x, 0.75, dz + 0.56], 0.025, 0.018, m.brass, 0.025, [
      Math.PI / 2,
      0,
      0,
    ]);
  }
  // The open book uses actual folded paper; the cover belongs to the catalogue's selected volume.
  for (const side of [-1, 1]) {
    box([dx + side * 0.14, 1.016, dz + 0.06], [0.27, 0.038, 0.4], m.pages, [
      0,
      0,
      side * 0.035,
    ]);
    box(
      [dx + side * 0.14, 0.998, dz + 0.06],
      [0.29, 0.018, 0.425],
      m.books[0]!,
    );
    for (let line = 0; line < 11; line++)
      box(
        [dx + side * 0.145, 1.04, dz - 0.087 + line * 0.023],
        [0.2 - (line % 3) * 0.02, 0.002, 0.002],
        m.ink,
      );
  }
  box([dx + 0.027, 1.043, dz + 0.1], [0.018, 0.003, 0.48], m.books[2]!);
  target("books", [dx, 1.04, dz + 0.08], [0.85, 0.28, 0.7]);
  // Lamp: hand-spun metal, warm porcelain, a physical source lights the book from above.
  lathe(
    [dx - 0.81, 0.98, dz - 0.23],
    [
      [0.14, 0],
      [0.14, 0.025],
      [0.1, 0.06],
      [0.04, 0.1],
      [0.025, 0.44],
      [0.06, 0.47],
    ],
    m.brass,
  );
  cylinder([dx - 0.81, 1.53, dz - 0.23], 0.25, 0.26, m.cream, 0.14);
  const bulb = new MeshStandardMaterial({
    color: "#fff0c5",
    emissive: "#ffce82",
    emissiveIntensity: 3,
    roughness: 1,
  });
  resources.add(bulb);
  cylinder([dx - 0.81, 1.409, dz - 0.23], 0.22, 0.009, bulb);
  for (let i = 0; i < 3; i++)
    box(
      [dx + 0.8, 1.02 + i * 0.045, dz - 0.2],
      [0.4, 0.04, 0.29],
      m.books[2 + i]!,
      [0, i * 0.1, 0],
    );
  lathe(
    [dx + 0.67, 0.98, dz + 0.35],
    [
      [0.05, 0],
      [0.045, 0.07],
      [0.06, 0.09],
      [0.055, 0.105],
    ],
    m.ink,
  );
  cylinder(
    [dx + 0.68, 1.15, dz + 0.35],
    0.004,
    0.3,
    m.brass,
    0.003,
    [0.1, 0, -0.21],
  );

  // Reader's chair: upholstered seat and back, curved wooden arms, brass nailheads.
  function chair(cx: number, cz: number) {
    rounded([cx, 0.47, cz], [0.86, 0.2, 0.82], m.leather);
    rounded([cx, 0.84, cz - 0.36], [0.85, 0.87, 0.16], m.leather, [-0.1, 0, 0]);
    box([cx, 1.31, cz - 0.4], [0.86, 0.07, 0.16], m.wood);
    for (const x of [cx - 0.47, cx + 0.47]) {
      rounded([x, 0.83, cz], [0.13, 0.12, 0.86], m.wood);
      for (const z of [cz - 0.3, cz + 0.3])
        lathe(
          [x, 0.04, z],
          [
            [0.045, 0],
            [0.032, 0.17],
            [0.06, 0.34],
            [0.032, 0.48],
            [0.04, 0.71],
          ],
          m.wood,
        );
      for (let i = 0; i < 9; i++)
        sphere(
          [x > cx ? x - 0.06 : x + 0.06, 0.93 + i * 0.035, cz - 0.235],
          0.009,
          m.brass,
        );
    }
    for (let i = 0; i < 3; i++)
      for (let j = 0; j < 2; j++)
        sphere(
          [cx - 0.21 + i * 0.21, 0.82 + j * 0.24, cz - 0.25],
          0.018,
          m.dark,
        );
  }
  chair(2.42, 0.18);
  // Stool behind the writing desk.
  rounded([dx, 0.5, dz - 1.07], [0.7, 0.16, 0.6], m.leather);
  for (const x of [dx - 0.26, dx + 0.26])
    for (const z of [dz - 1.29, dz - 0.85])
      cylinder([x, 0.25, z], 0.033, 0.44, m.wood);
  // Memories belong to the player, kept in a clothbound album on a round reading table.
  const ax = 1.45,
    az = 1.53;
  lathe(
    [ax, 0.02, az],
    [
      [0.35, 0],
      [0.34, 0.045],
      [0.15, 0.09],
      [0.075, 0.2],
      [0.065, 0.49],
      [0.15, 0.63],
    ],
    m.wood,
  );
  cylinder([ax, 0.71, az], 0.58, 0.07, m.wood);
  box(
    [ax - 0.04, 0.79, az + 0.09],
    [0.45, 0.075, 0.57],
    m.books[0]!,
    [0, -0.16, 0],
  );
  box(
    [ax - 0.04, 0.832, az + 0.09],
    [0.34, 0.008, 0.43],
    m.leather,
    [0, -0.16, 0],
  );
  box(
    [ax - 0.04, 0.84, az + 0.09],
    [0.14, 0.006, 0.06],
    m.brass,
    [0, -0.16, 0],
  );
  target("memories", [ax, 0.82, az], [1.0, 0.28, 0.85]);
  // Tea and ceramics leave evidence of an inhabited room without invented story progress.
  lathe(
    [ax + 0.29, 0.75, az - 0.23],
    [
      [0.06, 0],
      [0.075, 0.03],
      [0.09, 0.12],
      [0.083, 0.13],
      [0.077, 0.11],
    ],
    m.cream,
  );
  cylinder([ax + 0.29, 0.873, az - 0.23], 0.076, 0.004, m.walnut);
  add(new TorusGeometry(0.039, 0.009, 8, 20), m.cream, [
    ax + 0.375,
    0.825,
    az - 0.23,
  ]);
  cylinder([ax + 0.29, 0.754, az - 0.23], 0.13, 0.014, m.cream);
  // A globe in the far corner, ornamental rail and a small ceramic vase.
  lathe(
    [-3.36, 0.02, -1.6],
    [
      [0.26, 0],
      [0.28, 0.035],
      [0.1, 0.13],
      [0.055, 0.57],
      [0.16, 0.79],
    ],
    m.wood,
  );
  sphere([-3.36, 1.18, -1.6], 0.34, m.books[4]!);
  add(
    new TorusGeometry(0.375, 0.012, 8, 64),
    m.brass,
    [-3.36, 1.18, -1.6],
    [0.1, 0.25, 0.3],
  );
  for (const a of [-0.58, 0, 0.58])
    add(
      new TorusGeometry(Math.cos(a) * 0.343, 0.003, 4, 48),
      m.brass,
      [-3.36, 1.18 + Math.sin(a) * 0.343, -1.6],
      [Math.PI / 2, 0, 0],
    );
  lathe(
    [0.64, 1.8, -4.0],
    [
      [0.11, 0],
      [0.14, 0.04],
      [0.14, 0.21],
      [0.07, 0.29],
      [0.06, 0.43],
      [0.08, 0.44],
    ],
    m.cream,
  );
  for (let i = 0; i < 5; i++) {
    const x = 0.64 + (rng() - 0.5) * 0.18;
    cylinder([x, 2.32, -4.0], 0.004, 0.45, m.green, 0.003, [
      0,
      0,
      (rng() - 0.5) * 0.6,
    ]);
    sphere([x - 0.03, 2.47 + rng() * 0.09, -4.0], 0.045, m.books[4]!);
  }

  for (const [material, parts] of buckets) {
    // All room primitives have index+normal+uv; merging avoids hundreds of draw calls on phones.
    const geometry = mergeGeometries(parts);
    parts.forEach((g) => g.dispose());
    if (!geometry) throw new Error("書斎の形を組み立てられませんでした。");
    const mesh = new Mesh(geometry, material);
    mesh.castShadow =
      !(material instanceof MeshBasicMaterial) && material !== leaves;
    mesh.receiveShadow = true;
    root.add(mesh);
  }
  root.updateMatrixWorld(true);
  return {
    root,
    hits,
    lamp: new Vector3(dx - 0.81, 1.39, dz - 0.23),
    fireColor: new Color("#eabd78"),
    dispose() {
      for (const hit of hits) hit.geometry.dispose();
      root.traverse((o) => {
        if (o instanceof Mesh) o.geometry.dispose();
      });
      const textures = new Set(
        m.all.flatMap((mat) => [mat.map]).filter((t) => t !== null),
      );
      for (const t of textures) t.dispose();
      for (const mat of resources) mat.dispose();
    },
  };
}
