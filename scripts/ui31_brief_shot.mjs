// Live verification of the async session-start brief: it renders without any
// user turn, and clicking an item routes into the record.
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const APP = process.env.MVP_APP_URL || "http://localhost:13000";
const OUT = process.env.SHOT_DIR || ".ui31-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const shot = async (name) => {
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log(`shot ${name}`);
};

try {
  await page.goto(APP, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.getByTestId("signin-username").fill("dan");
  await page.getByTestId("signin-password").fill(process.env.DEMO_PASSWORD);
  await page.getByTestId("signin-submit").click();
  await page.getByTestId("home-screen").waitFor({ timeout: 90_000 });

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
} catch (error) {
  await shot("97-brief-failure");
  console.error("FAILED:", error.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
