import { expect, test } from "@playwright/test";
import household from "./sample-household.json" with { type: "json" };

test("shows the plan for the sample profile", async ({ page, request }) => {
  const saved = await request.put("/api/profile", { data: household });
  expect(saved.ok()).toBe(true);

  await page.goto("/");
  await page.getByRole("button", { name: "Plan" }).click();
  await expect(page.getByText("Calculating plan")).toBeVisible();

  const head = page.getByRole("region", { name: "Best plan" });
  await expect(head).toContainText("You can safely spend", { timeout: 30_000 });
  await expect(head).toContainText("of market paths");

  const comparison = page.getByRole("table", { name: "Strategy comparison" });
  await expect(comparison.getByRole("row")).toHaveCount(7);
  const years = page.getByRole("table", { name: "Year by year" });
  expect(await years.getByRole("row").count()).toBeGreaterThanOrEqual(21);
  await expect(page.getByRole("img", { name: /Stacked balances/ })).toBeVisible();

  await years.getByRole("button", { name: "How Social Security is worked out" }).click();
  await expect(years.getByRole("note")).toContainText("Both benefits together");
  await page.keyboard.press("Escape");
  await expect(years.getByRole("note")).toHaveCount(0);
  expect(await page.locator("main").innerText()).not.toContain("!");
});
