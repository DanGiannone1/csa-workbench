// Visual verification for issue #50: sign in, walk every screen, screenshot.
// Usage: DEMO_PASSWORD=... SHOT_DIR=... node scripts/ui50_screenshots.mjs
import { runWalk, signIn } from "./ui_shot_lib.mjs";

await runWalk(async (page, shot) => {
  await signIn(page);
  await page.waitForTimeout(2000);
  await shot("01-home-digest");

  await page.getByTestId("nav--engagements").click();
  await page.getByTestId("engagements-screen").waitFor();
  await shot("02-engagements");

  await page.locator('[data-testid^="engagement-row-"]').first().click();
  await page.getByTestId("engagement-overview").waitFor();
  await shot("03-engagement-overview");

  await page.getByTestId("engagement-tab-timeline").click();
  await page.getByTestId("engagement-timeline-screen").waitFor();
  await shot("04-engagement-timeline");

  await page.getByTestId("engagement-tab-tasks").click();
  await page.getByTestId("engagement-tasks-screen").waitFor();
  await shot("05-engagement-tasks");

  await page.getByTestId("engagement-tab-artifacts").click();
  await page.getByTestId("engagement-artifacts-screen").waitFor();
  await shot("06-engagement-docs");

  await page.getByTestId("engagement-tab-settings").click();
  await page.getByTestId("engagement-settings-screen").waitFor();
  await shot("07-engagement-team");

  await page.getByTestId("nav--todo").click();
  await page.getByTestId("todo-screen").waitFor();
  await shot("08-tasks");

  await page.getByTestId("nav--calendar").click();
  await page.getByTestId("calendar-screen").waitFor();
  await shot("09-calendar");

  await page.getByTestId("nav--reminders").click();
  await page.getByTestId("reminders-screen").waitFor();
  await shot("10-reminders");

  await page.getByTestId("nav--settings").click();
  await page.getByTestId("settings-screen").waitFor();
  await shot("11-settings");

  // Collapse the dock → FAB, then reopen.
  await page.getByTestId("dock-collapse").click();
  await page.getByTestId("dock-launcher").waitFor();
  await shot("12-collapsed-fab");
  await page.getByTestId("dock-launcher").click();
  await page.getByTestId("copilot-dock").waitFor();

  // AI Mode.
  await page.getByTestId("nav-assistant").click();
  await page.getByTestId("assistant-workspace").waitFor({ timeout: 60_000 });
  await shot("13-ai-mode");

  console.log("ALL SHOTS OK");
});
