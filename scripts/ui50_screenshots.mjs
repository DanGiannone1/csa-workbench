// One-off visual verification for issue #50: sign in, walk every screen, screenshot.
// Usage: DEMO_PASSWORD=... SHOT_DIR=... node scripts/ui50_screenshots.mjs
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const APP = process.env.MVP_APP_URL || "http://localhost:13000";
const OUT = process.env.SHOT_DIR || ".ui50-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const shot = async (name) => {
  await page.waitForTimeout(700);
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: false });
  console.log(`shot ${name}`);
};

try {
  await page.goto(APP, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.getByTestId("signin-username").waitFor({ timeout: 60_000 });
  await page.getByTestId("signin-username").fill("dan");
  await page.getByTestId("signin-password").fill(process.env.DEMO_PASSWORD);
  await page.getByTestId("signin-submit").click();
  await page.getByTestId("home-screen").waitFor({ timeout: 90_000 });
  await page.waitForTimeout(2000);
  await shot("01-home-digest");

  await page.getByTestId("nav--engagements").click();
  await page.getByTestId("engagements-screen").waitFor();
  await shot("02-engagements");

  await page.locator('[data-testid^="engagement-row-"]').first().click();
  await page.getByTestId("engagement-overview").waitFor();
  await shot("03-engagement-overview");

  await page.getByTestId("engagement-tab-tasks").click();
  await page.getByTestId("engagement-tasks-screen").waitFor();
  await shot("04-engagement-tasks");

  await page.getByTestId("engagement-tab-artifacts").click();
  await page.getByTestId("engagement-artifacts-screen").waitFor();
  await shot("05-engagement-artifacts");

  await page.getByTestId("engagement-tab-settings").click();
  await page.getByTestId("engagement-settings-screen").waitFor();
  await shot("06-engagement-team");

  await page.getByTestId("nav--todo").click();
  await page.getByTestId("todo-screen").waitFor();
  await shot("07-tasks");

  await page.getByTestId("nav--calendar").click();
  await page.getByTestId("calendar-screen").waitFor();
  await shot("08-calendar");

  await page.getByTestId("nav--reminders").click();
  await page.getByTestId("reminders-screen").waitFor();
  await shot("09-reminders");

  await page.getByTestId("nav--settings").click();
  await page.getByTestId("settings-screen").waitFor();
  await shot("10-settings");

  // Collapse the dock → FAB, then reopen.
  await page.getByTestId("dock-collapse").click();
  await page.getByTestId("dock-launcher").waitFor();
  await shot("11-collapsed-fab");
  await page.getByTestId("dock-launcher").click();
  await page.getByTestId("copilot-dock").waitFor();

  // AI Mode.
  await page.getByTestId("nav-assistant").click();
  await page.getByTestId("assistant-workspace").waitFor({ timeout: 60_000 });
  await shot("12-ai-mode");

  console.log("ALL SHOTS OK");
} catch (error) {
  await shot("99-failure-state");
  console.error("FAILED:", error.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
