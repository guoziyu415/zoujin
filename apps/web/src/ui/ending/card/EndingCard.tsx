// The ending card (ux-design 11.3, S-026, S-051, S-055, S-076): the same canvas drawing on screen and in the saved
// PNG. Saving shares the picture through the system sheet on phones (iOS has 「画像を保存」, LINE, X); without it, a
// download on desktops, and the picture with 「画像を長押しすると、保存できます。」 elsewhere. Never the player's words,
// personal details, a URL or a QR code.
import type { Api } from "@zoujin/contracts";
import { useEffect, useMemo, useRef, useState } from "react";
import { endingFrame } from "../../../stores/story";
import { track } from "../../../telemetry/telemetry";
import { copy, fill } from "../../copy";
import { drawCard, loadFonts, loadImage, toBlob } from "./draw";
import type { CardText } from "./layout";

export function EndingCard({
  card,
  endingId,
  names,
  role,
}: {
  card: Api.EndingCardView;
  endingId: string;
  names: Record<string, string>;
  role: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false);
  const [fallback, setFallback] = useState<string | null>(null); // the picture to long-press
  const text: CardText = useMemo(
    () => ({
      title: card.title,
      subtitle: card.subtitle,
      people: card.characterLines.map((p) => ({
        name: names[p.character] ?? p.character,
        line: p.line,
      })),
      contrast: card.contrast,
      footer: fill(copy["card.footer"], { role }),
      diffLabel: copy["card.diff"],
    }),
    [card, names, role],
  );

  useEffect(() => {
    let alive = true;
    void (async () => {
      await loadFonts(text);
      const art = endingFrame.get() ?? (await loadImage(card.fallbackImageUrl));
      if (!alive || !canvas.current) return;
      drawCard(canvas.current, text, art);
      setReady(true);
    })();
    return () => {
      alive = false;
    };
  }, [text, card.fallbackImageUrl]);

  async function save() {
    if (!canvas.current) return;
    const blob = await toBlob(canvas.current);
    if (!blob) return;
    track("ending_card_saved", { endingId });
    const file = new File([blob], "hashire-merosu.png", { type: "image/png" });
    if (navigator.canShare?.({ files: [file] })) {
      try {
        await navigator.share({ files: [file] });
        track("ending_shared", { endingId, completed: true });
      } catch {
        track("ending_shared", { endingId, completed: false });
      }
      return;
    }
    const url = URL.createObjectURL(blob);
    if (matchMedia("(pointer: fine)").matches) {
      const a = document.createElement("a");
      a.href = url;
      a.download = file.name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } else setFallback(url);
  }

  return (
    <div className="end-card">
      <canvas
        ref={canvas}
        width={1080}
        height={1350}
        className="end-card-canvas"
        role="img"
        aria-label={[
          card.title,
          card.subtitle,
          ...text.people.map((p) => `${p.name}\u3000${p.line}`),
          `${copy["card.diff"]}\u3000${card.contrast}`,
        ].join("。")}
        data-ready={ready}
      />
      <p className="small">{copy["card.note"]}</p>
      <button className="primary" disabled={!ready} onClick={() => void save()}>
        {copy["card.save"]}
      </button>
      {fallback && (
        <div className="end-card-fallback">
          <img src={fallback} alt={card.title} />
          <p>{copy["card.saveFallback"]}</p>
        </div>
      )}
    </div>
  );
}
