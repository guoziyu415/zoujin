// The realistic characters (F-16): which built character stands for a world character or the player's role, where its
// files are, and the small pure rules the bodies follow (how much of each clip, how open the mouth is, the blinks).
// assets/pipeline/cast/build.sh writes /cast/<name>/{walk,talk_std,talk_high,anims}.glb (assets/cast/cast.json lists
// them); a character not listed here stays a grey stand-in (mannequin.ts).

export const CAST: Readonly<Record<string, string>> = {
  "char.king": "king",
  "char.selinuntius": "selinuntius",
  "char.sister": "sister",
  "char.groom": "groom",
  "char.philostratus": "philostratus",
  "role.apprentice": "apprentice",
  "role.shepherd-boy": "shepherd-boy",
  "role.traveler": "traveler",
  "char.melos": "melos",
  "char.old-man": "old-man",
  "char.young-man": "young-man",
  "char.maiden": "maiden",
};

// wedding clothes (village.md: the saffron dress and veil Melos bought in town; the groom's myrtle wreath)
export const WEDDING: Readonly<Record<string, string>> = {
  "char.sister": "sister-wedding",
  "char.groom": "groom-wedding",
};

export type CastFile = "walk" | "talk_std" | "talk_high" | "anims";

export function castName(id: string, wedding = false): string | null {
  return (wedding ? WEDDING[id] : undefined) ?? CAST[id] ?? null;
}

export function castUrl(name: string, file: CastFile): string {
  return `/cast/${name}/${file}.glb`;
}

// the clips' own ground speeds (lod_report.json from the UAL retarget, m/s): playback rate = speed / this
export const GROUND_SPEED = { walk: 0.99, run: 3.76 } as const;
const WALK_FROM = 0.15; // below this they stand
const RUN_FROM = 2.2; // between the walk (1.4) and the run (3.2) in People.tsx

export type Gait = { idle: number; walk: number; run: number };

/** How much of each clip at this ground speed (m/s); the weights add up to 1. */
export function gaitWeights(speed: number): Gait {
  if (speed <= WALK_FROM) return { idle: 1, walk: 0, run: 0 };
  if (speed < 1) {
    const t = (speed - WALK_FROM) / (1 - WALK_FROM);
    return { idle: 1 - t, walk: t, run: 0 };
  }
  if (speed < RUN_FROM) return { idle: 0, walk: 1, run: 0 };
  const t = Math.min(1, (speed - RUN_FROM) / 0.8);
  return { idle: 0, walk: 1 - t, run: t };
}

/** Playback rate of a clip so the feet don't slide. */
export function clipRate(clip: "walk" | "run", speed: number): number {
  return Math.max(0.6, Math.min(1.6, speed / GROUND_SPEED[clip]));
}

/** Mouth shapes from the voice's level (0..1, audio/engine.ts levels.mouth): the jaw opens with loudness, the round
 * vowel shapes come and go a little so the mouth doesn't just hinge (no phonemes from Gemini Live, so no visemes). */
export function mouthWeights(level: number, t: number): Record<string, number> {
  const l = Math.max(0, Math.min(1, level));
  const open = Math.pow(l, 0.7);
  const wobble = 0.5 + 0.5 * Math.sin(t * 9.1) * Math.sin(t * 3.7);
  return {
    jawOpen: 0.45 * open,
    viseme_aa: 0.55 * open * (1 - wobble * 0.6),
    viseme_O: 0.35 * open * wobble,
    viseme_E: 0.2 * open * (1 - wobble),
  };
}

/** Eyelids (0..1): a blink of about 150 ms every 3-5 s, each person on their own rhythm. */
export function blinkAt(t: number, seed: number): number {
  const period = 3 + (((seed * 9301 + 49297) % 233280) / 233280) * 2;
  const phase = (t + seed * 0.37) % period;
  const d = 0.15;
  return phase < d ? Math.sin((phase / d) * Math.PI) : 0;
}

export function seedOf(id: string): number {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % 1000;
}
