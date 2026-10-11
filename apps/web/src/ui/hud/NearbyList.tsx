// 「近くの人」 (ux-design 6): the people the player can talk to and the things to examine. In F-0 it lists the
// talkable characters of the snapshot; F-2d sorts them by distance from the player and walks there when picked.
import { play } from "../../net/play";
import { useWorld } from "../../stores/world";
import { useUi } from "../../stores/ui";
import { copy } from "../copy";

export function NearbyList({ names }: { names: Record<string, string> }) {
  const open = useUi((s) => s.overlay === "nearby");
  const characters = useWorld((s) => s.world?.characters);
  const interactables = useWorld((s) => s.world?.interactables);
  if (!open) return null;
  const close = () => useUi.setState({ overlay: null });
  const people = Object.values(characters ?? {}).filter((c) => c.talkable);
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
