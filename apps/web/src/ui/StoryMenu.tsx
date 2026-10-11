// The book button (ux-design 9.3, 10.1): the memory book and the map, and the one setting the ending reads
// (「結末を自動で進める」, S-089). The settings page proper is a later card.
import { useState } from "react";
import { openOverlay } from "../stores/story";
import { copy } from "./copy";
import { endingSettings, useEndingAuto } from "./ending/settings";

export function StoryMenu() {
  const [open, setOpen] = useState(false);
  const auto = useEndingAuto();
  return (
    <div className="story-menu">
      <button
        aria-expanded={open}
        aria-controls="story-menu-list"
        aria-label={copy["menu.open.label"]}
        onClick={() => setOpen((o) => !o)}
      >
        {copy["menu.open"]}
      </button>
      {open && (
        <ul id="story-menu-list" className="story-menu-list">
          <li>
            <button
              onClick={() => {
                setOpen(false);
                openOverlay({ kind: "memory" });
              }}
            >
              {copy["menu.memory"]}
            </button>
          </li>
          <li>
            <button
              onClick={() => {
                setOpen(false);
                openOverlay({ kind: "map" });
              }}
            >
              {copy["menu.map"]}
            </button>
          </li>
          <li>
            <label className="story-menu-toggle">
              <input
                type="checkbox"
                checked={auto}
                onChange={(e) => endingSettings.setAuto(e.target.checked)}
              />
              <span>{copy["settings.endAuto"]}</span>
            </label>
            <p className="small">{copy["settings.endAuto.desc"]}</p>
          </li>
        </ul>
      )}
    </div>
  );
}
