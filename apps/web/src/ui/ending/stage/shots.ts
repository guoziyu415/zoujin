// Which shot each ending line is in (project folder ux/slice/ending-shots.md「句子对镜头」, data #107's set pieces):
// by set piece, the shot of each line in order (1-based like setPieceVoices keys). The 3D layer frames the shots;
// lines not listed here (narration from the server, an unknown piece) stay in whatever shot is on.
const CURTAIN = [1, 2, 2, 2, 3, 3, 3, 4, 5, 5]; // storm-in / crowd-makes-way and their -you variants
const KING = [7, 9, 10, 10];

export const SHOTS: Record<string, number[]> = {
  "piece.storm-in": CURTAIN,
  "piece.storm-in-you": CURTAIN,
  "piece.crowd-makes-way": CURTAIN,
  "piece.crowd-makes-way-you": CURTAIN,
  "piece.made-it": [2], // Melos came before his friend was brought out: shot 2's camera, then shot 6
  "piece.embrace": Array(7).fill(6),
  "piece.embrace-melos-doubted": Array(6).fill(6),
  "piece.embrace-selinuntius-doubted": Array(5).fill(6),
  "piece.embrace-neither": Array(3).fill(6),
  "piece.king-asks": KING,
  "piece.king-asks-you": KING,
  "piece.scarlet-cloak": [11, 11, 11],
};

// king-asks/1 cuts from shot 7 to 8 halfway through, at 「やがて」 (the subtitle stays)
export const MID_CUT = "やがて";

export function shotOf(
  pieceId: string,
  n: number, // 1-based
  text: string,
): { shot: number | null; midShot?: { at: number; shot: number } } {
  const shot = SHOTS[pieceId]?.[n - 1] ?? null;
  if (shot === 7) {
    const at = text.indexOf(MID_CUT);
    if (at > 0)
      return { shot, midShot: { at: at / [...text].length, shot: 8 } };
  }
  return { shot };
}

// the ending card's illustration (S-055, ending-shots.md): shot 6 (the two on the platform against the west sky);
// without it — the player was the hostage (the `-you` pieces: beat.25 doesn't happen, so no shot 6; M3) — shot 5,
// the rope loosened and the crowd stirring; when Melos didn't make it, shot 1's camera
export const CARD_SHOTS = [6, 5, 1];

// the shot the card takes from the shots the staging went through (null: none of them; the card's fallback picture)
export function cardShot(seen: Iterable<number>): number | null {
  let best: number | null = null;
  for (const n of seen) {
    const r = CARD_SHOTS.indexOf(n);
    if (r >= 0 && (best === null || r < CARD_SHOTS.indexOf(best))) best = n;
  }
  return best;
}
