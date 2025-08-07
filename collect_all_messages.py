import asyncio
import re
from urllib.parse import urljoin
from playwright.async_api import async_playwright

BASE = "https://www.lists.kit.edu/sympa/arc/robotics-worldwide"

async def collect_all_messages():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print(f"🔗 Visiting archive index: {BASE}")
        await page.goto(BASE)
        try:
            await page.click("input[type='submit']", timeout=8000)
            print("🛡️ Clicked anti-spam button")
        except Exception:
            pass

        month_urls = []
        for link in await page.locator("a").all():
            href = await link.get_attribute("href")
            if href and re.search(r"/robotics-worldwide/\d{4}-\d{2}/$", href):
                full = urljoin(BASE, href)
                if full not in month_urls:
                    month_urls.append(full)

        print(f"📅 Found {len(month_urls)} months to process.")
        all_links = []

        for month_url in month_urls:
            print(f"\n📅 Visiting month: {month_url}")
            month_links = []
            try:
                await page.goto(month_url)
                try:
                    await page.click("input[type='submit']", timeout=5000)
                    print("🛡️ Clicked anti-spam inside month page")
                except Exception:
                    pass

                await page.wait_for_timeout(1000)
                html = await page.content()

                # Determine whether to use 'thrd' or 'mail'
                page_prefix = "thrd"
                if "thrd1.html" not in html and "mail1.html" in html:
                    page_prefix = "mail"

                # ✅ NEW: Visit thrdX.html until one fails or contains no messages
                i = 1
                while True:
                    page_path = f"{page_prefix}{i}.html"
                    page_url = urljoin(month_url, page_path)
                    print(f"   🔄 Checking: {page_url}")

                    try:
                        await page.goto(page_url)
                        await page.wait_for_timeout(500)
                        inner_html = await page.content()
                        msgs = re.findall(r'href="(msg\d+\.html)"', inner_html)
                        if not msgs:
                            print(f"     🛑 No messages on page {i}, stopping.")
                            break

                        for msg in msgs:
                            full_link = urljoin(page_url, msg)
                            month_links.append(full_link)

                        print(f"     ➕ Found {len(msgs)} messages on page {i}")
                        i += 1
                    except Exception as e:
                        print(f"     ⚠️ Failed to load page {i}: {e}")
                        break

                if not month_links:
                    print(f"❌ No messages found in {month_url}")

                all_links.extend(month_links)

            except Exception as e:
                print(f"⚠️ Error processing {month_url}: {e}")

        # Save to file
        with open("all_message_links.txt", "w", encoding="utf-8") as f:
            for link in all_links:
                f.write(link + "\n")

        print(f"\n✅ Done! Collected {len(all_links)} message links.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(collect_all_messages())
