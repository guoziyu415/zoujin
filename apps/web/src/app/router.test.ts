import { describe, expect, it } from "vitest";
import { parse } from "./router";

describe("parse", () => {
  it("knows the five screens", () => {
    expect(parse("/", "")).toEqual({ name: "cover" });
    expect(parse("/roles", "")).toEqual({ name: "roles" });
    expect(parse("/play/pt_1", "")).toEqual({ name: "play", pid: "pt_1" });
    expect(parse("/ending/pt_1", "")).toEqual({ name: "ending", pid: "pt_1" });
    expect(parse("/nope", "")).toEqual({ name: "notFound" });
  });

  it("only goes back to our own paths after login", () => {
    expect(parse("/login", "?next=%2Fplay%2Fpt_1")).toEqual({
      name: "login",
      next: "/play/pt_1",
    });
    expect(parse("/login", "?next=https%3A%2F%2Fevil.example")).toEqual({
      name: "login",
      next: "/",
    });
    expect(parse("/login", "?next=%2F%2Fevil.example")).toEqual({
      name: "login",
      next: "/",
    });
    expect(parse("/login", "")).toEqual({ name: "login", next: "/" });
  });
});
