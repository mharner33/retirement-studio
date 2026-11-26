import { expect, test } from "@playwright/test";

test("shows backend status and switches to the dark theme", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toHaveText("Backend is up");

  await page.getByRole("button", { name: "Dark theme" }).click();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(25, 27, 46)");
});
