// Draws the ending card on a 1080×1350 canvas from layout.ts (frontend-design 10.5): Canvas 2D, no screenshot library.
// The illustration is the frame the staging captured (S-055) or, when there is none, the card's fallback picture;
// either is same-origin, so the canvas exports. Fonts are loaded for exactly these characters first.
import { BANDS, H, layoutCard, LINE, PAD, W, type CardText } from "./layout";

export const MINCHO =
  '"Hiragino Mincho ProN", "Yu Mincho", "Noto Serif JP", serif';
const INK = "#14110e";
const INK2 = "#6b6256";
const PAPER = "#f1e9d8";
const HI = "#a8402c";

const font = (px: number) => `${px}px ${MINCHO}`;

export async function loadFonts(c: CardText): Promise<void> {
  const text = [
    c.title,
    c.subtitle,
    c.contrast,
    c.footer,
    c.diffLabel,
    ...c.people.flatMap((p) => [p.name, p.line]),
  ].join("");
  try {
    await Promise.all(
      [64, 34, 30, 28].map((px) => document.fonts.load(font(px), text)),
    );
  } catch {
    // system fonts only: fine
  }
}

export async function loadImage(
  url: string,
): Promise<CanvasImageSource | null> {
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return img;
  } catch {
    return null;
  }
}

// cover-fit into the art band
function drawArt(
  g: CanvasRenderingContext2D,
  art: CanvasImageSource | null,
): void {
  if (!art) {
    const grad = g.createLinearGradient(0, 0, 0, BANDS.art);
    grad.addColorStop(0, "#3a2a20");
    grad.addColorStop(1, "#c98a4a");
    g.fillStyle = grad;
    g.fillRect(0, 0, W, BANDS.art);
    return;
  }
  const w = "width" in art ? Number(art.width) : W;
  const h = "height" in art ? Number(art.height) : BANDS.art;
  const s = Math.max(W / w, BANDS.art / h);
  const dw = w * s;
  const dh = h * s;
  g.drawImage(art, (W - dw) / 2, (BANDS.art - dh) / 2, dw, dh);
}

export function drawCard(
  canvas: HTMLCanvasElement,
  c: CardText,
  art: CanvasImageSource | null,
): void {
  canvas.width = W;
  canvas.height = H;
  const g = canvas.getContext("2d")!;
  g.textBaseline = "top";
  const m = (t: string, px: number) => {
    g.font = font(px);
    return g.measureText(t).width;
  };
  const l = layoutCard(c, m);
  g.fillStyle = PAPER;
  g.fillRect(0, 0, W, H);
  g.save();
  g.beginPath();
  g.rect(0, 0, W, BANDS.art);
  g.clip();
  drawArt(g, art);
  g.restore();

  const text = (
    lines: string[],
    px: number,
    x: number,
    y: number,
    color: string,
  ) => {
    g.font = font(px);
    g.fillStyle = color;
    lines.forEach((s, i) =>
      g.fillText(s, x, y + i * px * LINE + (px * (LINE - 1)) / 2),
    );
  };
  text(l.title.lines, l.title.px, PAD, l.title.y, INK);
  text(l.subtitle.lines, l.subtitle.px, PAD, l.subtitle.y, INK2);
  for (const p of l.people) {
    text([p.name], 28, PAD, p.y + (p.text.px - 28) / 2, INK2);
    text(p.text.lines, p.text.px, PAD + p.nameW, p.y, INK);
  }
  g.fillStyle = "rgba(20,17,14,0.15)";
  g.fillRect(PAD, BANDS.art + BANDS.title + BANDS.people, W - PAD * 2, 1);
  text(l.diffLabel.lines, l.diffLabel.px, PAD, l.diffLabel.y, HI);
  text(l.diff.lines, l.diff.px, PAD + 240, l.diff.y, INK);
  text(l.footer.lines, l.footer.px, PAD, l.footer.y, INK2);
}

export const toBlob = (canvas: HTMLCanvasElement): Promise<Blob | null> =>
  new Promise((r) => canvas.toBlob(r, "image/png"));
