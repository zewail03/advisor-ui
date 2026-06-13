// Drives the admin portal: login -> dashboard, captures console errors + screenshot.
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

const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 200)));
page.on("pageerror", (e) => errors.push("PAGEERROR: " + String(e).slice(0, 200)));

// 1. login page
await page.goto(APP, { waitUntil: "networkidle0", timeout: 60000 });
await page.screenshot({ path: `${OUT}\\admin-login.png` });

// 2. fill + submit
await page.type('input[placeholder="admin"]', "admin");
await page.type('input[type="password"]', "admin123");
await Promise.all([
  page.waitForNavigation({ waitUntil: "networkidle0", timeout: 60000 }).catch(() => {}),
  page.click('button[type="submit"]'),
]);
await new Promise((r) => setTimeout(r, 2000));

const url = page.url();
const sample = await page.evaluate(() => {
  const m = document.querySelector("main") || document.body;
  return (m.innerText || "").replace(/\s+/g, " ").trim().slice(0, 600);
});
await page.screenshot({ path: `${OUT}\\admin-dashboard.png`, fullPage: true });

console.log("landed on:", url);
console.log("console errors:", errors.length ? errors : "none");
console.log("dashboard sample:", sample);

await browser.close();
