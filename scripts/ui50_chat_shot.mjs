// Live AG-UI verification for issue #50: send a real message, capture the
// in-flight (tool trace/thinking) state and the finished reply.
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "playwright";

const APP = process.env.MVP_APP_URL || "http://localhost:13000";
const OUT = process.env.SHOT_DIR || ".ui50-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const shot = async (name) => {
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log(`shot ${name}`);
};

try {
  await page.goto(APP, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.getByTestId("signin-username").fill("dan");
  await page.getByTestId("signin-password").fill(process.env.DEMO_PASSWORD);
  await page.getByTestId("signin-submit").click();
  await page.getByTestId("home-screen").waitFor({ timeout: 90_000 });
  await page.waitForTimeout(1500);
  await shot("01b-home-avatar-fixed");

  await page.getByTestId("starter-prompt-0").click(); // "Review my engagements"
  await page.waitForTimeout(2500);
  await shot("13-chat-inflight");

  // RUN_FINISHED → turn-meta appears (steps > 0 for a tool-using turn).
  await page.getByTestId("turn-meta").waitFor({ timeout: 180_000 });
  await page.waitForTimeout(800);
  await shot("14-chat-reply");
  console.log("CHAT OK");
} catch (error) {
  await shot("98-chat-failure");
  console.error("FAILED:", error.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
