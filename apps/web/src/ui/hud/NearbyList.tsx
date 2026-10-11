// 「近くの人」 (ux-design 6.2): the people the player can talk to, nearest first, and the things to examine. Picking
// one walks there (the 3D does the walking): a person is focused at once, a thing examined at once (0 minutes).
import { play } from "../../net/play";
import { usePlayer, walkToSpot } from "../../stores/player";
import { useWorld } from "../../stores/world";
import { useUi } from "../../stores/ui";
import { copy } from "../copy";

export function NearbyList({ names }: { names: Record<string, string> }) {
  const open = useUi((s) => s.overlay === "nearby");
  const characters = useWorld((s) => s.world?.characters);
  const interactables = useWorld((s) => s.world?.interactables);
  const distances = usePlayer((s) => s.distances);
  if (!open) return null;
  const close = () => useUi.setState({ overlay: null });
  const far = (id: string) => distances[id] ?? Infinity;
  const people = Object.values(characters ?? {})
    .filter((c) => c.talkable)
    .sort((a, b) => far(a.id) - far(b.id));
  const things = (interactables ?? []).filter(
    (i) => i.kind === "examine" && i.enabled,
  );
  return (
    <div className="sheet" role="dialog" aria-label={copy["nearby.title"]}>
      <h2>{copy["nearby.title"]}</h2>
      {!people.length && !things.length && <p>{copy["nearby.empty"]}</p>}
      <ul>
        {people.map((c) => (
          <li key={c.id}>
            <span>{names[c.id] ?? c.id}</span>
            <button
              onClick={() => {
                play.focus(c.id);
                close();
              }}
            >
              {copy["nearby.talk"]}
            </button>
          </li>
        ))}
        {things.map((i) => (
          <li key={i.id}>
            <span>{i.label}</span>
            <button
              onClick={() => {
                walkToSpot(i.spot);
                play.examine(i.id);
                close();
              }}
            >
              {copy["nearby.examine"]}
            </button>
          </li>
        ))}
      </ul>
      <button onClick={close} style={{ marginTop: 12 }}>
        {copy["common.close"]}
      </button>
    </div>
  );
}
