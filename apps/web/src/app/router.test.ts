import { describe, expect, it } from "vitest";
import { parse } from "./router";

describe("parse", () => {
  it("knows the library and story screens", () => {
    expect(parse("/", "")).toEqual({ name: "home" });
    expect(parse("/books/hashire-merosu", "")).toEqual({
      name: "cover",
      bookId: "hashire-merosu",
    });
    expect(parse("/books/another-book/roles", "")).toEqual({
      name: "roles",
      bookId: "another-book",
    });
    expect(parse("/roles", "")).toEqual({
      name: "roles",
      bookId: "hashire-merosu",
    });
    expect(parse("/play/pt_1", "")).toEqual({ name: "play", pid: "pt_1" });
    expect(parse("/ending/pt_1", "")).toEqual({ name: "ending", pid: "pt_1" });
    expect(parse("/nope", "")).toEqual({ name: "notFound" });
  });

  it("malformed URL encoding cannot crash the application", () => {
    expect(parse("/books/%E0%A4%A", "")).toEqual({ name: "notFound" });
    expect(parse("/play/%E0%A4%A", "")).toEqual({ name: "notFound" });
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
