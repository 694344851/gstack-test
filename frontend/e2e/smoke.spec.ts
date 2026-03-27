import { expect, test } from "@playwright/test";

test("smoke home loads", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: /我的作品库/i })).toBeVisible();
});
