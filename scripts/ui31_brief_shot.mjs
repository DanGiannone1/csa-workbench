// Live verification of the async session-start brief: it renders without any
// user turn, and clicking an item routes into the record.
// Usage: DEMO_PASSWORD=... SHOT_DIR=... node scripts/ui31_brief_shot.mjs
import { runWalk, signIn } from "./ui_shot_lib.mjs";

await runWalk(async (page, shot) => {
  await signIn(page);

  // The brief must appear with no user interaction at all.
  await page.getByTestId("session-brief").waitFor({ timeout: 30_000 });
  const message = await page.getByTestId("session-brief").locator("h2").textContent();
  const items = await page.locator('[data-testid^="brief-item-"]').count();
  console.log(`brief message: ${message}`);
  console.log(`brief items: ${items}`);
  await shot("15-session-brief");

  if (items > 0) {
    await page.getByTestId("brief-item-0").click();
    // Ranked items route into the record: an engagement surface must appear.
    await page.locator('[data-testid="engagement-overview"], [data-testid="engagement-tasks-screen"], [data-testid="todo-screen"]').first().waitFor({ timeout: 15_000 });
    await shot("16-brief-item-navigated");
  }
  console.log("BRIEF OK");
});
