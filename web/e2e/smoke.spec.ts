import { expect, test } from "@playwright/test";

test("/ redirects to /today and renders the placeholder", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/today$/);
  await expect(page.getByRole("heading", { name: "Today", level: 1 })).toBeVisible();
});
