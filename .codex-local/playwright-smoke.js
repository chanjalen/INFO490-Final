const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 600 });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const results = [];

  const record = async (name, fn) => {
    try {
      await fn();
      results.push(`${name}: PASS`);
    } catch (error) {
      results.push(`${name}: FAIL - ${error.message}`);
      throw error;
    }
  };

  await record("home page", async () => {
    await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    await page.locator("text=SoClose").first().waitFor();
    await page.locator("h1").filter({ hasText: "Find the movie you are searching for" }).waitFor();
  });

  await record("focus chips", async () => {
    await page.getByRole("button", { name: "Plot" }).click();
    await page.waitForTimeout(900);
    await page.getByPlaceholder("Describe the plot, central conflict, or ending you remember.").waitFor();
    await page.getByRole("button", { name: "Dialogue" }).click();
    await page.waitForTimeout(900);
    await page.getByPlaceholder("Type a quote, phrase, or fragment of dialogue.").waitFor();
  });

  await record("search results", async () => {
    await page.getByRole("button", { name: "Plot" }).click();
    await page.getByLabel("Movie search").fill("spirit world");
    await page.getByRole("button", { name: "Find" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.locator("text=Spirited Away").first().waitFor();
  });

  await record("movie detail", async () => {
    await page.locator("text=Spirited Away").first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.locator("text=Movie profile").waitFor();
    await page.locator("h1").filter({ hasText: "Spirited Away" }).waitFor();
  });

  await record("history page", async () => {
    await page.getByRole("link", { name: "History" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.getByRole("heading", { name: "Search History" }).waitFor();
    await page.locator("text=spirit world").waitFor();
  });

  await record("history filter and search again", async () => {
    await page.getByPlaceholder("Search your history...").fill("spirit");
    await page.getByRole("button", { name: "Filter" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(900);
    await page.getByRole("link", { name: "Search again" }).first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.locator("text=Spirited Away").first().waitFor();
  });

  await record("recommendations page", async () => {
    await page.getByRole("link", { name: "Recommended" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    await page.locator("text=Recommendations").waitFor();
    await page.locator("text=Why it fits").first().waitFor();
  });

  console.log(results.join("\n"));
  await page.waitForTimeout(2500);
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
