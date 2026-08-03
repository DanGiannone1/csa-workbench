// Live AG-UI verification for issue #50: send a real message, capture the
// in-flight (tool trace/thinking) state and the finished reply.
// Usage: DEMO_PASSWORD=... SHOT_DIR=... node scripts/ui50_chat_shot.mjs
import { runWalk, signIn } from "./ui_shot_lib.mjs";

await runWalk(async (page, shot) => {
  await signIn(page);
  await page.waitForTimeout(1500);
  await shot("01b-home");

  await page.getByTestId("starter-prompt-0").click(); // "Review my engagements"
  await page.waitForTimeout(2500);
  await shot("13-chat-inflight");

  // RUN_FINISHED → turn-meta appears (steps > 0 for a tool-using turn).
  await page.getByTestId("turn-meta").waitFor({ timeout: 180_000 });
  await page.waitForTimeout(800);
  await shot("14-chat-reply");
  console.log("CHAT OK");
});
