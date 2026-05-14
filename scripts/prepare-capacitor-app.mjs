import { readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const mode = process.argv[2] === "driver" ? "driver" : "shop";
const shouldSync = process.argv.includes("--sync");

const settings = {
  shop: {
    appId: "com.farmsource.shop",
    appName: "Farmsource Shop",
  },
  driver: {
    appId: "com.farmsource.driver",
    appName: "Farmsource Driver",
  },
}[mode];

if (shouldSync) {
  const command = process.platform === "win32" ? "cmd.exe" : "npx";
  const args = process.platform === "win32" ? ["/c", "npx", "cap", "sync", "android"] : ["cap", "sync", "android"];
  const result = spawnSync(command, args, {
    stdio: "inherit",
    env: { ...process.env, FARMSOURCE_APP_MODE: mode },
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

patchText("android/app/build.gradle", [
  [/namespace = ".*?"/, 'namespace = "com.farmsource.app"'],
  [/applicationId ".*?"/, `applicationId "${settings.appId}"`],
]);

patchText("android/app/src/main/res/values/strings.xml", [
  [/<string name="app_name">.*?<\/string>/, `<string name="app_name">${settings.appName}</string>`],
  [/<string name="title_activity_main">.*?<\/string>/, `<string name="title_activity_main">${settings.appName}</string>`],
  [/<string name="package_name">.*?<\/string>/, `<string name="package_name">${settings.appId}</string>`],
  [/<string name="custom_url_scheme">.*?<\/string>/, `<string name="custom_url_scheme">${settings.appId}</string>`],
]);

console.log(`Prepared Android wrapper for ${settings.appName} (${settings.appId}).`);

function patchText(path, replacements) {
  let content = readFileSync(path, "utf8");
  for (const [pattern, replacement] of replacements) {
    content = content.replace(pattern, replacement);
  }
  writeFileSync(path, content);
}
