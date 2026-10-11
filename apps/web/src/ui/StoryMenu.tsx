// The book button (ux-design 9.3, 10.1): the memory book and the map, and the one setting the ending reads
// (「結末を自動で進める」, S-089). The settings page proper is a later card.
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { libraryQuery, meQuery } from "../app/queries";
import { navigate } from "../app/router";
import { openOverlay } from "../stores/story";
import { copy } from "./copy";
import { endingSettings, useEndingAuto } from "./ending/settings";

export function StoryMenu() {
  const qc = useQueryClient();
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
                void qc.invalidateQueries({ queryKey: libraryQuery.queryKey });
                void qc.invalidateQueries({ queryKey: meQuery.queryKey });
                navigate("/");
              }}
            >
              書斎に戻る
            </button>
            <p className="small">物語は、続きから再開できます。</p>
          </li>
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
