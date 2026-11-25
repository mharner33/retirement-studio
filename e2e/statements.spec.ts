import { expect, test } from "@playwright/test";
import household from "./sample-household.json" with { type: "json" };

interface Row {
  id: number;
  filename: string;
}

function pdf(label: string): Buffer {
  return Buffer.from(`%PDF-1.4\n% ${label}\n%%EOF\n`);
}

test("uploads two statements, reviews and accepts them, and the profile updates", async ({
  page,
  request,
}) => {
  const saved = await request.put("/api/profile", { data: household });
  expect(saved.ok()).toBe(true);

  await page.goto("/");
  await page.getByRole("button", { name: "Statements" }).click();
  await page.getByLabel("Choose files").setInputFiles([
    { name: "e2e-account.pdf", mimeType: "application/pdf", buffer: pdf("account") },
    { name: "e2e-social-security.pdf", mimeType: "application/pdf", buffer: pdf("ss") },
  ]);
  const results = page.getByRole("list", { name: "Upload results" });
  await expect(results.getByRole("listitem")).toHaveText([
    "e2e-account.pdf: Saved",
    "e2e-social-security.pdf: Saved",
  ]);

  // No model runs here: the extraction results are put through the API.
  const rows = (await (await request.get("/api/statements")).json()) as Row[];
  const idOf = (name: string): number => rows.find((r) => r.filename === name)?.id ?? -1;
  const account = await request.put(
    `/api/statements/${String(idOf("e2e-account.pdf"))}/extraction`,
    {
      data: {
        doc_type: "account",
        institution: "Example Bank",
        statement_date: "2026-11-20",
        accounts: [
          {
            kind: "pretax",
            owner_hint: "Alex",
            owner: "self",
            label: "401(k)",
            balance: 912345.67,
            cost_basis: null,
            last4: "1234",
          },
        ],
      },
    },
  );
  expect(account.ok()).toBe(true);
  const social = await request.put(
    `/api/statements/${String(idOf("e2e-social-security.pdf"))}/extraction`,
    {
      data: {
        doc_type: "social_security",
        statement_date: "2026-11-01",
        person: null,
        monthly_at_62: 1500,
        monthly_at_fra: 2100,
        fra_age: "67",
        monthly_at_70: 2600,
      },
    },
  );
  expect(social.ok()).toBe(true);

  await page.reload();
  await page.getByRole("button", { name: "Statements" }).click();
  await expect(page.getByRole("table", { name: "Statements" })).toContainText("Ready to review");

  const accountReview = page.getByRole("region", { name: "Review e2e-account.pdf" });
  await expect(accountReview.getByLabel("Balance, account 1")).toHaveValue("$912,345.67");
  await accountReview.getByRole("button", { name: "Accept" }).click();

  const socialReview = page.getByRole("region", { name: "Review e2e-social-security.pdf" });
  await expect(socialReview.getByRole("button", { name: "Accept" })).toBeDisabled();
  await socialReview.getByLabel("Spouse").check();
  await socialReview.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByRole("table", { name: "Statements" })).not.toContainText(
    "Ready to review",
  );
  await expect(page.getByRole("table", { name: "Statements" })).toContainText("Accepted");
  expect(await page.locator("main").innerText()).not.toContain("!");

  await page.getByRole("button", { name: "Profile" }).click();
  const first = page.getByRole("group", { name: "Account 1", exact: true });
  await expect(first.getByLabel("Balance", { exact: true })).toHaveValue("$912,345.67");
  const spouse = page.getByRole("group", { name: "Spouse income", exact: true });
  await expect(spouse.getByLabel("Social Security per month at 62")).toHaveValue("$1,500.00");
  await expect(spouse.getByLabel("Social Security per month at full retirement age")).toHaveValue(
    "$2,100.00",
  );
  await expect(spouse.getByLabel("Social Security per month at 70")).toHaveValue("$2,600.00");
});
