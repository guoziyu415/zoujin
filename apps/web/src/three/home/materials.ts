// Reproducible materials for the original study. Textures hold surface information only; window light and lamplight come from real light sources.
// オリジナルの書斎の再現可能な素材。テクスチャは表面の情報だけを持ち、窓の光と灯りは実際の光源が与える。
import {
  CanvasTexture,
  MeshStandardMaterial,
  RepeatWrapping,
  SRGBColorSpace,
} from "three";

export function random(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function canvas(w: number, h = w) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d");
  if (!g) throw new Error("書斎の質感を準備できませんでした。");
  return { c, g };
}

function texture(c: HTMLCanvasElement) {
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  t.wrapS = t.wrapT = RepeatWrapping;
  t.anisotropy = 4;
  return t;
}

function wood(seed: number, light: boolean) {
  const { c, g } = canvas(512);
  const rng = random(seed);
  g.fillStyle = light ? "#9b7950" : "#66513a";
  g.fillRect(0, 0, 512, 512);
  // Long fibers, faint growth rings and irregular pores, so no two pieces of wood look like the same noise decal.
  // 長い繊維、かすかな年輪、不規則な孔。どの木材も同じノイズのステッカーにはならない。
  for (let i = 0; i < 1800; i++) {
    const y = rng() * 512;
    const k = rng();
    g.strokeStyle =
      k < 0.45
        ? `rgba(35,20,10,${0.012 + rng() * 0.05})`
        : `rgba(221,189,137,${rng() * 0.055})`;
    g.lineWidth = 0.3 + rng() * 1.1;
    g.beginPath();
    for (let x = 0; x <= 512; x += 8) {
      const z =
        y + Math.sin(x * 0.012 + y * 0.017) * (3 + Math.sin(y * 0.03) * 2);
      if (x === 0) g.moveTo(x, z);
      else g.lineTo(x, z);
    }
    g.stroke();
  }
  for (let i = 0; i < 8; i++) {
    const y = 30 + rng() * 450;
    g.strokeStyle = "rgba(29,20,12,0.07)";
    g.lineWidth = 0.8;
    g.beginPath();
    g.ellipse(
      rng() * 512,
      y,
      35 + rng() * 70,
      2 + rng() * 5,
      0,
      0,
      Math.PI * 2,
    );
    g.stroke();
  }
  return texture(c);
}

function weave() {
  const { c, g } = canvas(256);
  const rng = random(909);
  g.fillStyle = "#cbc5b5";
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 256; i += 2) {
    g.fillStyle = `rgba(45,36,23,${0.1 + rng() * 0.12})`;
    g.fillRect(i, 0, 1, 256);
    g.fillStyle = "rgba(249,243,220,0.25)";
    g.fillRect(0, i, 256, 1);
  }
  return texture(c);
}

function rug() {
  const { c, g } = canvas(768, 1024);
  const rng = random(381);
  g.fillStyle = "#39423b";
  g.fillRect(0, 0, 768, 1024);
  const frame = (pad: number, color: string, width: number) => {
    g.strokeStyle = color;
    g.lineWidth = width;
    g.strokeRect(pad, pad, 768 - 2 * pad, 1024 - 2 * pad);
  };
  frame(16, "#b6a283", 10);
  frame(34, "#786e56", 4);
  frame(71, "#b6a283", 26);
  frame(90, "#666f5b", 5);
  for (let y = 25; y < 1000; y += 42)
    for (const x of [60, 708]) {
      g.fillStyle = "#586249";
      g.beginPath();
      g.ellipse(x, y, 8, 13, 0, 0, Math.PI * 2);
      g.fill();
    }
  for (let y = 144; y < 920; y += 75)
    for (let x = 137; x < 655; x += 75) {
      const cx = x + (Math.floor(y / 75) % 2) * 12;
      g.strokeStyle = "#889079";
      g.lineWidth = 2;
      g.beginPath();
      g.moveTo(cx, y - 19);
      g.lineTo(cx + 13, y);
      g.lineTo(cx, y + 19);
      g.lineTo(cx - 13, y);
      g.closePath();
      g.stroke();
      g.fillStyle = "#b3a17c";
      g.fillRect(cx - 2, y - 2, 4, 4);
    }
  for (let i = 0; i < 85000; i++) {
    g.fillStyle =
      rng() > 0.5 ? "rgba(226,218,185,0.055)" : "rgba(6,15,10,0.08)";
    g.fillRect(rng() * 768, rng() * 1024, 1, 3);
  }
  return texture(c);
}

function landscape() {
  const { c, g } = canvas(768, 512);
  const rng = random(501);
  const sky = g.createLinearGradient(0, 0, 0, 512);
  sky.addColorStop(0, "#8d9b94");
  sky.addColorStop(0.56, "#d1c6a2");
  sky.addColorStop(1, "#626b55");
  g.fillStyle = sky;
  g.fillRect(0, 0, 768, 512);
  ["#919e91", "#7e8972", "#576959", "#394b41"].forEach((color, layer) => {
    g.fillStyle = color;
    g.beginPath();
    g.moveTo(0, 512);
    for (let x = 0; x <= 768; x += 10) {
      const y =
        235 +
        layer * 54 +
        Math.sin(x * 0.009 + layer * 1.5) * 37 +
        Math.sin(x * 0.022) * 13;
      g.lineTo(x, y);
    }
    g.lineTo(768, 512);
    g.fill();
  });
  g.fillStyle = "#b5b494";
  g.beginPath();
  g.moveTo(410, 304);
  g.bezierCurveTo(670, 350, 40, 405, 350, 512);
  g.lineTo(575, 512);
  g.bezierCurveTo(155, 405, 700, 350, 430, 304);
  g.fill();
  for (let i = 0; i < 18000; i++) {
    g.fillStyle =
      rng() > 0.5 ? "rgba(244,230,194,0.07)" : "rgba(20,36,24,0.06)";
    g.fillRect(rng() * 768, rng() * 512, 3 + rng() * 5, 1);
  }
  return texture(c);
}

export function homeMaterials() {
  const darkWood = wood(421, false);
  const oak = wood(627, true);
  const linen = weave();
  const all: MeshStandardMaterial[] = [];
  const mat = (
    color: string,
    roughness = 0.7,
    metalness = 0,
    map?: CanvasTexture,
  ) => {
    const m = new MeshStandardMaterial({
      color,
      roughness,
      metalness,
      ...(map ? { map } : {}),
    });
    all.push(m);
    return m;
  };
  const woodM = mat("#e0cdb4", 0.47, 0, darkWood);
  woodM.bumpMap = darkWood;
  woodM.bumpScale = 0.002;
  const floor = ["#e6d6bb", "#dfc7a4", "#dccbaa", "#c9b692", "#dcc3a0"].map(
    (c) => mat(c, 0.48, 0, oak),
  );
  return {
    all,
    wood: woodM,
    walnut: mat("#b4a38e", 0.4, 0, darkWood),
    floor,
    plaster: mat("#d4cebd", 0.94),
    stone: mat("#b6b29f", 0.78),
    green: mat("#45594d", 0.7),
    dark: mat("#202821", 0.86),
    brass: mat("#b59a59", 0.32, 0.78),
    bronze: mat("#7c694b", 0.42, 0.65),
    pages: mat("#ddd0aa", 0.93),
    rug: mat("#e0d9bd", 0.99, 0, rug()),
    painting: mat("#f1dfbd", 0.95, 0, landscape()),
    fabric: mat("#aaa48c", 0.94, 0, linen),
    leather: mat("#405045", 0.67, 0, linen),
    cream: mat("#d0c5a8", 0.58),
    ink: mat("#24312c", 0.38),
    books: [
      "#4b605a",
      "#665044",
      "#9b8a69",
      "#4b555d",
      "#676b50",
      "#816956",
      "#374c46",
    ].map((c) => mat(c, 0.83, 0, linen)),
  };
}
