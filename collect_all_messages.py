import asyncio
from urllib.parse import urljoin
from playwright.async_api import async_playwright

BASE = "https://www.lists.kit.edu/sympa/arc/robotics-worldwide"
all_links = []

async def collect_all_messages():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print(f"🔗 Visiting base archive: {BASE}")
        await page.goto(BASE)

        # Click anti-spam button if needed
        try:
            await page.click("input[type='submit']", timeout=8000)
            print("🛡️ Clicked anti-spam button")
            await page.wait_for_timeout(2000)
        except:
            print("⚠️ No anti-spam button found or needed")

        await page.wait_for_timeout(1000)
        await page.screenshot(path="base_archive.png")

        # Collect all month URLs
        month_urls = []
        archive_links = await page.locator("a").all()

        for a in archive_links:
            href = await a.get_attribute("href")
            if href and "/sympa/arc/robotics-worldwide/" in href and href.endswith("/"):
                full_url = urljoin(BASE, href)
                if full_url not in month_urls:
                    month_urls.append(full_url)

        print(f"✅ Found {len(month_urls)} monthly archive links.")

        # Go to each month and extract all msg links
        for month_url in month_urls:
            print(f"\n📅 Processing: {month_url}")
            try:
                await page.goto(month_url)
                try:
                    await page.click("input[type='submit']", timeout=5000)
                    await page.wait_for_timeout(1500)
                except:
                    pass  # No spam button again

                links = await page.locator("a").all()
                for a in links:
                    href = await a.get_attribute("href")
                    if href and href.startswith("msg") and href.endswith(".html"):
                        full_url = urljoin(month_url, href)
                        all_links.append(full_url)

            except Exception as e:
                print(f"⚠️ Failed to process {month_url}: {e}")

        await browser.close()

    # Save message URLs
    with open("all_message_links.txt", "w") as f:
        for url in all_links:
            f.write(url + "\n")

    print(f"\n✅ Done! Saved {len(all_links)} total message links to all_message_links.txt")

# Run it
asyncio.run(collect_all_messages())
