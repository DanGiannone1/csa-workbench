// Shared boilerplate for the ad hoc UI verification shot scripts: browser +
// viewport, the shot() helper, demo sign-in, and the fail-with-screenshot wrapper.
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

export async function launchShotPage() {
  const out = process.env.SHOT_DIR || ".ui-shots";
  mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
  const shot = async (name) => {
    await page.waitForTimeout(700);
    await page.screenshot({ path: join(out, `${name}.png`) });
    console.log(`shot ${name}`);
  };
  return { browser, page, shot };
}

export async function signIn(page, username = "dan") {
  const app = process.env.MVP_APP_URL || "http://localhost:13000";
  await page.goto(app, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.getByTestId("signin-username").waitFor({ timeout: 60_000 });
  await page.getByTestId("signin-username").fill(username);
  await page.getByTestId("signin-password").fill(process.env.DEMO_PASSWORD);
  await page.getByTestId("signin-submit").click();
  await page.getByTestId("home-screen").waitFor({ timeout: 90_000 });
}

// Runs the walk, screenshots the failure state on error, and always closes the browser.
export async function runWalk(walk) {
  const { browser, page, shot } = await launchShotPage();
  try {
    await walk(page, shot);
  } catch (error) {
    await shot("99-failure-state");
    console.error("FAILED:", error.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}
