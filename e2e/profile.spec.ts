import { expect, test, type Locator, type Page } from "@playwright/test";

async function fillMoney(scope: Locator, label: string, value: string): Promise<void> {
  const input = scope.getByLabel(label, { exact: true });
  await input.focus();
  await input.fill(value);
  await input.blur();
}

async function fillPerson(
  page: Page,
  name: string,
  p: { first: string; birth: string; retire: string },
): Promise<void> {
  const group = page.getByRole("group", { name, exact: true });
  await group.getByLabel("First name").fill(p.first);
  await group.getByLabel("Birth date").fill(p.birth);
  await group.getByLabel("Retirement age").fill(p.retire);
}

async function fillIncome(
  page: Page,
  name: string,
  v: { wages?: string; k401?: string; ss62: string; ssFra: string; ss70: string },
): Promise<void> {
  const group = page.getByRole("group", { name, exact: true });
  await fillMoney(group, "Wages per year", v.wages ?? "0");
  await fillMoney(group, "401(k) contributions per year (with match)", v.k401 ?? "0");
  await fillMoney(group, "Social Security per month at 62", v.ss62);
  await fillMoney(group, "Social Security per month at full retirement age", v.ssFra);
  await fillMoney(group, "Social Security per month at 70", v.ss70);
}

async function addAccount(
  page: Page,
  n: number,
  a: { label: string; kind: string; balance: string; basis?: string; last4?: string },
): Promise<void> {
  await page.getByRole("button", { name: "Add account" }).click();
  const group = page.getByRole("group", { name: `Account ${String(n)}`, exact: true });
  await group.getByLabel("Label").fill(a.label);
  await group.getByLabel("Type").selectOption(a.kind);
  await fillMoney(group, "Balance", a.balance);
  if (a.basis) await fillMoney(group, "Cost basis", a.basis);
  if (a.last4) await group.getByLabel("Last 4 digits").fill(a.last4);
  await group.getByLabel("Balance as of").fill("2026-11-01");
}

test("fills the guided form, saves, and keeps every value after a reload", async ({ page }) => {
  // The backend is shared across spec files: show the empty-profile wizard whatever it holds.
  await page.route("**/api/profile", (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ status: 404, json: { detail: "Not Found" } })
      : route.fallback(),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Profile" }).click();

  await fillPerson(page, "You", { first: "Alex", birth: "1963-06-15", retire: "63" });
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Add spouse" }).click();
  await fillPerson(page, "Spouse", { first: "Sam", birth: "1965-03-01", retire: "62" });
  await page.getByRole("button", { name: "Next" }).click();
  await fillIncome(page, "Your income", {
    wages: "120000",
    k401: "20000",
    ss62: "2200",
    ssFra: "3100",
    ss70: "3900",
  });
  await fillIncome(page, "Spouse income", { ss62: "1400", ssFra: "2000", ss70: "2500" });
  await page.getByRole("button", { name: "Next" }).click();

  await addAccount(page, 1, { label: "401(k)", kind: "pretax", balance: "900000", last4: "1234" });
  await addAccount(page, 2, { label: "Roth IRA", kind: "roth", balance: "60000", last4: "5678" });
  await addAccount(page, 3, {
    label: "Brokerage",
    kind: "taxable",
    balance: "250000",
    basis: "150000",
    last4: "9012",
  });
  await addAccount(page, 4, { label: "Savings", kind: "cash", balance: "40000" });
  await page.getByRole("button", { name: "Next" }).click();

  const spending = page.getByRole("group", { name: "Spending", exact: true });
  await fillMoney(spending, "Essential spending per year", "60000");
  await fillMoney(spending, "Discretionary spending per year", "15000");
  await fillMoney(spending, "COBRA premium per month", "1800");
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByLabel("Return rate (%)")).toHaveValue("6");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Profile saved");

  await page.unroute("**/api/profile");
  await page.reload();
  await page.getByRole("button", { name: "Profile" }).click();

  const you = page.getByRole("group", { name: "You", exact: true });
  await expect(you.getByLabel("First name")).toHaveValue("Alex");
  await expect(you.getByLabel("Birth date")).toHaveValue("1963-06-15");
  await expect(you.getByLabel("Retirement age")).toHaveValue("63");
  const spouse = page.getByRole("group", { name: "Spouse", exact: true });
  await expect(spouse.getByLabel("First name")).toHaveValue("Sam");
  const income = page.getByRole("group", { name: "Your income", exact: true });
  await expect(income.getByLabel("Wages per year")).toHaveValue("$120,000.00");
  await expect(income.getByLabel("Social Security per month at 70")).toHaveValue("$3,900.00");
  const first = page.getByRole("group", { name: "Account 1", exact: true });
  await expect(first.getByLabel("Balance", { exact: true })).toHaveValue("$900,000.00");
  await expect(first.getByLabel("Last 4 digits")).toHaveValue("1234");
  const third = page.getByRole("group", { name: "Account 3", exact: true });
  await expect(third.getByLabel("Cost basis")).toHaveValue("$150,000.00");
  await expect(
    page
      .getByRole("group", { name: "Account 4", exact: true })
      .getByLabel("Balance", { exact: true }),
  ).toHaveValue("$40,000.00");
  await expect(
    page
      .getByRole("group", { name: "Spending", exact: true })
      .getByLabel("COBRA premium per month"),
  ).toHaveValue("$1,800.00");
});
