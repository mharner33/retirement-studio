import { expect, test } from "@playwright/test";
import household from "./sample-household.json" with { type: "json" };

test("shows a reply with a change card, applies it, and the profile changes", async ({
  page,
  request,
}) => {
  expect((await request.put("/api/profile", { data: household })).ok()).toBe(true);
  expect((await request.delete("/api/chat")).status()).toBeLessThan(500);
  const sent = await request.post("/api/chat/messages", {
    data: { text: "What if I retire at 65" },
  });
  expect(sent.status()).toBe(202);
  const stored = await request.post("/api/chat/reply", {
    data: {
      text: "Working two more years is worth a look.",
      sources: [{ kind: "engine", label: "Plan run", url: null }],
      tool_results: [],
      unchecked: false,
      proposals: [
        {
          changes: [{ op: "set", path: "self.retirement_age", value: 65 }],
          reason: "Retire at 65",
        },
      ],
    },
  });
  expect(stored.ok()).toBe(true);

  await page.goto("/");
  await page.getByRole("button", { name: "Chat" }).click();
  await expect(page.getByText("Working two more years is worth a look.")).toBeVisible();
  const card = page.getByRole("region", { name: "Proposed change" });
  await expect(card).toContainText("Retire at 65");
  await card.getByRole("button", { name: "Apply" }).click();
  await expect(card.getByText("Applied")).toBeVisible();

  await page.getByRole("button", { name: "Profile" }).click();
  await expect(page.getByLabel("Retirement age").first()).toHaveValue("65");
  expect(await page.locator("main").innerText()).not.toContain("!");
});
