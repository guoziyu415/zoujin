// What the app shell's e2e checks share (f0, f1): driving B-1's mock and getting into a story.
import { expect, type BrowserContext, type Page } from "@playwright/test";

export const ORIGIN = "http://127.0.0.1:4173";
export const MOCK = "http://127.0.0.1:8787";
export const PT = /\/play\/(pt_[0-9A-Z]+)$/;

export async function mock(page: Page, path: string, data: unknown = {}) {
  const r = await page.request.post(`${MOCK}/__mock/${path}`, {
    data,
    headers: { Origin: MOCK },
  });
  expect(r.ok(), `/__mock/${path}`).toBeTruthy();
}

// the checks that are only about the HUD and the voice leave the 3D out (app/flags.ts): quicker, and the timing
// checks don't share the CPU with software rendering. gate.spec.ts plays with the plaza.
export async function without3d(context: BrowserContext) {
  await context.addInitScript(() => {
    (window as { __zoujinNo3d?: boolean }).__zoujinNo3d = true;
  });
}

// the mock's state and scenario are global: reset them (the cookie-less reset needs no session)
export async function resetMock(page: Page) {
  const r = await page.request.post(`${MOCK}/__mock/reset`, { data: {} });
  expect(r.ok()).toBeTruthy();
}

export async function login(page: Page) {
  await page.getByLabel("招待コード").fill("mock");
  await page.getByRole("button", { name: "すすむ" }).click();
}

export async function startStory(page: Page): Promise<string> {
  await page.goto("/");
  await login(page);
  await page.getByRole("button", { name: "書をひらく" }).click();
  await page.getByRole("button", { name: "旅人として、はじめる" }).click();
  await expect(page).toHaveURL(PT);
  await expect(page.getByTestId("sunband")).toHaveText("約束の日・夕方");
  await expect(page.getByText("人に近づくと話せます")).toBeVisible(); // connected: the welcome came
  return PT.exec(page.url())![1]!;
}

export async function talkTo(page: Page, name: string) {
  await page.getByRole("button", { name: "近くの人" }).click();
  await page
    .getByRole("listitem")
    .filter({ hasText: name })
    .getByRole("button", { name: "話しかける" })
    .click();
}
