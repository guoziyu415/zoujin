// Public opening background only; never a plot timeline or possible endings.
// Each book owns its introduction; an unavailable or unknown book gets no invented story.
export const bookIntroductions: Readonly<
  Record<string, { background: string; people: readonly string[] }>
> = {
  "hashire-merosu": {
    background:
      "舞台は古代ギリシャの町シラクス。人を信じない王が治める町で、友情と信頼が問われる物語です。",
    people: [
      "メロス — 村に暮らす青年。",
      "セリヌンティウス — 石工。メロスの古くからの友人。",
      "王（ディオニス） — シラクスを治める王。",
    ],
  },
};
