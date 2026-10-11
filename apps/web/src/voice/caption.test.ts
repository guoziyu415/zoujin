import { describe, expect, it } from "vitest";
import { Caption, segments } from "./caption";

describe("segments", () => {
  it("split after 、 and 。; closing marks stay with the segment before", () => {
    expect(segments("下がれ、旅の者。ここから先は、通さぬ。")).toEqual([
      "下がれ、",
      "旅の者。",
      "ここから先は、",
      "通さぬ。",
    ]);
    expect(segments("「待て。」と言った")).toEqual(["「待て。」", "と言った"]);
    expect(segments("そうか。……なんだと。")).toEqual([
      "そうか。",
      "……なんだと。",
    ]);
  });
});

describe("Caption (frontend-design 7.5: the words follow the voice)", () => {
  it("live: a partial shows once the voice that came before it has been heard", () => {
    const c = new Caption();
    c.partial("……なんだと。", 400); // 400 ms of voice had arrived
    expect(c.update(0, 400)).toBe(false);
    expect(c.shown).toBe("");
    expect(c.update(400, 800)).toBe(true);
    expect(c.shown).toBe("……なんだと。");
    // the final while the voice still plays waits for its end
    c.finish("……なんだと。そんな王を、", "live", 1600);
    c.update(1000, 1600);
    expect(c.shown).toBe("……なんだと。");
    c.update(1600, 1600);
    expect(c.shown).toBe("……なんだと。そんな王を、");
    expect(c.final).toBe(true);
  });

  it("script: segments by their share of the characters, the length known at turn_complete", () => {
    const c = new Caption();
    c.finish("下がれ、旅の者。", "script", 0);
    c.complete(1600); // 8 characters over 1.6 s: 「下がれ、」 is half
    c.update(700, 1600);
    expect(c.shown).toBe("");
    c.update(800, 1600);
    expect(c.shown).toBe("下がれ、");
    c.update(1600, 1600);
    expect(c.shown).toBe("下がれ、旅の者。");
  });

  it("a prerecorded line has its length from the manifest", () => {
    const c = new Caption();
    c.scripted("すまない、風の音で聞こえなかった。", 3000);
    c.update(500, 0);
    expect(c.shown).toBe("");
    c.update(3000, 0);
    expect(c.shown).toBe("すまない、風の音で聞こえなかった。");
  });

  it("fallback shows the whole line at once; a failed one shows nothing", () => {
    const c = new Caption();
    c.finish("聞き取れた言葉", "fallback", 0);
    expect(c.update(0, 0)).toBe(true); // reported as a change, even after the voice has played out
    expect(c.shown).toBe("聞き取れた言葉");
    const failed = new Caption();
    failed.finish(null, "fallback", 0);
    expect(failed.final).toBe(true);
    expect(failed.shown).toBe("");
  });

  it("flush shows what still waits (the voice ended); stop keeps the line where it is (a cut)", () => {
    const c = new Caption();
    c.partial("一", 100);
    c.partial("一、二", 500);
    expect(c.flush()).toBe(true);
    expect(c.shown).toBe("一、二");
    const cut = new Caption();
    cut.partial("一", 0);
    cut.update(0, 100);
    cut.partial("一、二", 100);
    cut.stop();
    cut.update(1000, 1000);
    expect(cut.shown).toBe("一");
    expect(cut.flush()).toBe(false);
  });
});
