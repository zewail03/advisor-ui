// Browser walk of the newly-mounted pages. Logs in as 25100045, injects the
// auth token into localStorage, visits each page, and reports console errors,
// visible error banners, and a sample of rendered text + a screenshot.
import puppeteer from "puppeteer-core";
import fs from "fs";

const CHROME =
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const APP = "http://localhost:3000";
const API = "http://127.0.0.1:8000";
const OUT = "C:\\Users\\adham\\OneDrive - Al Alamein University\\Desktop\\advisor-ui\\backend\\walk_shots";
fs.mkdirSync(OUT, { recursive: true });

const PAGES = [
  ["financial-account", "/financial-account"],
  ["advisor", "/advisor"],
  ["petitions", "/petitions"],
  ["capstone", "/capstone"],
  ["attendance", "/attendance"],
  ["evaluations", "/evaluations"],
];

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ student_code: "25100045", password: "changeme123" }),
}).then((r) => r.json());

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox", "--window-size=1400,1000"],
});

const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 1000 });

// seed auth token before the app loads
await page.goto(APP, { waitUntil: "domcontentloaded" });
await page.evaluate((t) => {
  localStorage.setItem("advisor_token", t.access_token);
  localStorage.setItem("advisor_refresh", t.refresh_token);
}, login);

for (const [name, path] of PAGES) {
  const errors = [];
  const onErr = (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 200)); };
  const onPageErr = (e) => errors.push("PAGEERROR: " + String(e).slice(0, 200));
  page.on("console", onErr);
  page.on("pageerror", onPageErr);

  await page.goto(`${APP}${path}`, { waitUntil: "networkidle0", timeout: 60000 }).catch((e) => errors.push("NAV: " + e.message));
  await new Promise((r) => setTimeout(r, 1500)); // let client fetches settle

  // visible red error banners (the pages use bg-red-50 text-red-700)
  const banners = await page.evaluate(() => {
    const out = [];
    document.querySelectorAll('[class*="red-50"],[class*="red-700"],[class*="bg-red"]').forEach((el) => {
      const t = (el.textContent || "").trim();
      if (t) out.push(t.slice(0, 160));
    });
    return [...new Set(out)];
  });

  // a compact sample of body text to eyeball real data rendered
  const sample = await page.evaluate(() => {
    const main = document.querySelector("main") || document.body;
    return (main.innerText || "").replace(/\s+/g, " ").trim().slice(0, 400);
  });

  await page.screenshot({ path: `${OUT}\\${name}.png`, fullPage: true });

  page.off("console", onErr);
  page.off("pageerror", onPageErr);

  console.log("\n===== " + name + " (" + path + ") =====");
  console.log("console errors:", errors.length ? errors : "none");
  console.log("error banners:", banners.length ? banners : "none");
  console.log("sample:", sample);
}

await browser.close();
console.log("\nScreenshots in: " + OUT);
