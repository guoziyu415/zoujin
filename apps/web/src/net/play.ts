// The verbs the world screen's components call (frontend-design 4): they reach the open playthrough's session (and
// its voice controller) through here, never a socket. With no playthrough open they do nothing.
import type { Api } from "@zoujin/contracts";
import { usePlayer } from "../stores/player";
import { Session, type SessionHooks } from "./session";

type Manifest = Pick<Api.ManifestResponse, "characters">;

let current: Session | null = null;
let manifest: Manifest | null = null; // may arrive before or after the session opens

export function openPlay(
  pid: string,
  snapshot: Api.Snapshot,
  hooks: SessionHooks,
): Session {
  current?.stop();
  current = new Session(pid, hooks);
  if (manifest) apply(current, manifest);
  current.start(snapshot);
  return current;
}

export function closePlay(): void {
  current?.stop();
  current = null;
}

// display names for the light reactions, prerecorded lines for the voice (manifest 2.1)
function apply(s: Session, m: Manifest): void {
  s.setNames(Object.fromEntries(m.characters.map((c) => [c.id, c.name])));
  s.voice.setClips(
    Object.fromEntries(
      m.characters.flatMap((c) =>
        c.prerecorded ? [[c.id, c.prerecorded]] : [],
      ),
    ),
  );
}

const voice = () => current?.voice;

export const play = {
  focus: (character: string) => current?.focus(character),
  unfocus: () => current?.unfocus("menu"),
  // the 3D (frontend-design 9.4, api-contract 3.2): walking off from the one in the conversation, into another place
  // of the scene, near a talkable character and away again. The place is the client's to keep even with no story
  // open (the 3D sandbox), so walking on doesn't ask again every frame.
  walkAway: () => current?.unfocus("walk_away"),
  move: (place: string) => {
    const from = usePlayer.getState().place;
    usePlayer.setState({ place });
    current?.move(place, from);
  },
  near: (character: string) => current?.near(character),
  far: (character: string) => current?.far(character),
  say: (text: string, via: Api.TextMessage["via"] = "typed") =>
    current?.say(text, via),
  examine: (target: string) => current?.examine(target),
  reconnect: () => current?.reconnect(),
  // pagehide: close the socket so the page can go into the back/forward cache (9.5)
  suspend: () => current?.suspend(),
  setManifest: (m: Manifest) => {
    manifest = m;
    if (current) apply(current, m);
  },
  // the talk key and what goes with it (frontend-design 7)
  press: () => voice()?.press(),
  release: () => voice()?.release(),
  slide: (armed: boolean) => voice()?.slide(armed),
  retract: () => voice()?.retract(),
  again: () => voice()?.again(),
  openText: (draft?: { text: string; replaces: string | null }) =>
    voice()?.openText(draft ?? null),
  closeText: () => voice()?.closeText(),
  correct: (text: string, of: string) => voice()?.correct(text, of),
  primer: (choice: "mic" | "text") => voice()?.primer(choice),
  backToVoice: () => voice()?.backToVoice(),
  continueInText: () => voice()?.continueInText(),
  resumeAudio: () => voice()?.resumeAudio(),
  // the safety card (frontend-design 12)
  clearPausedTurn: () => voice()?.clearPausedTurn(),
  resumeStory: () => voice()?.resume(),
};
