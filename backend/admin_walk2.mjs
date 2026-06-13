// Full admin walk: login -> students list -> student detail -> audit trail.
import puppeteer from "puppeteer-core";
import fs from "fs";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const APP = "http://localhost:3001";
const OUT = "C:\\Users\\adham\\OneDrive - Al Alamein University\\Desktop\\advisor-ui\\backend\\walk_shots";
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox", "--window-size=1400,1100"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 1100 });

const errs = [];
page.on("console", (m) => m.type() === "error" && errs.push(m.text().slice(0, 160)));
page.on("pageerror", (e) => errs.push("PAGEERROR: " + String(e).slice(0, 160)));

async function report(name, path, waitFor) {
  errs.length = 0;
  await page.goto(`${APP}${path}`, { waitUntil: "networkidle0", timeout: 60000 }).catch((e) => errs.push("NAV " + e.message));
  if (waitFor) await page.waitForSelector(waitFor, { timeout: 15000 }).catch(() => errs.push("no selector " + waitFor));
  await new Promise((r) => setTimeout(r, 1200));
  const sample = await page.evaluate(() => (document.querySelector("main")?.innerText || document.body.innerText || "").replace(/\s+/g, " ").trim().slice(0, 500));
  await page.screenshot({ path: `${OUT}\\${name}.png`, fullPage: true });
  console.log(`\n===== ${name} (${path}) =====`);
  console.log("console errors:", errs.filter((e) => !e.includes("favicon")).length ? errs.filter((e) => !e.includes("favicon")) : "none");
  console.log("sample:", sample);
}

// login
await page.goto(APP, { waitUntil: "networkidle0" });
await page.type('input[placeholder="admin"]', "admin");
await page.type('input[type="password"]', "admin123");
await Promise.all([
  page.waitForNavigation({ waitUntil: "networkidle0", timeout: 60000 }).catch(() => {}),
  page.click('button[type="submit"]'),
]);
await new Promise((r) => setTimeout(r, 1500));

await report("admin-offerings", "/offerings", "select");

await browser.close();
