import { expect, test } from "@playwright/test";

const SEED = "retirement_rules_2026-01-01.md";

test("reviews and accepts a pending rules file", async ({ page, request }) => {
  const seed = await (await request.get(`/api/rules/${SEED}`)).text();
  expect(seed).toContain('"rate": 0.044');
  const saved = await request.post("/api/rules", {
    data: { markdown: seed.replace('"rate": 0.044', '"rate": 0.045') },
  });
  expect(saved.ok()).toBe(true);

  await page.goto("/");
  await page.getByRole("button", { name: "Rules" }).click();
  await expect(page.getByText("Rules are out of date")).toBeVisible();
  await expect(page.getByLabel("Current rules")).toContainText("2026-01-01");

  const table = page.getByRole("table", { name: "Pending changes" });
  const row = table.getByRole("row", { name: /colorado\.rate/ });
  await expect(row).toContainText("0.044");
  await expect(row).toContainText("0.045");

  await page.getByRole("button", { name: "Accept" }).click();
  await expect(table).toHaveCount(0);
  const status = (await (await request.get("/api/rules/status")).json()) as {
    current_date: string;
  };
  expect(status.current_date).not.toBe("2026-01-01");
  await expect(page.getByLabel("Current rules")).toContainText(status.current_date);
  await expect(page.getByText("Rules are out of date")).toHaveCount(0);
  expect(await page.locator("main").innerText()).not.toContain("!");
});
