"""
announcement_crawler.py

Scrapes Binance's delisting-announcement board, extracts the affected
trading pairs, and diffs them against previously-seen announcements so
downstream code (margin_trader.py) only acts on genuinely new events.
"""

import logging
import os
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OLD_ANNOUNCEMENTS_PATH = DATA_DIR / "old_announcements.csv"
NEW_ANNOUNCEMENTS_PATH = DATA_DIR / "new_announcements.csv"

ANNOUNCEMENT_URL = "https://www.binance.com/en/support/announcement/delisting?c=161&navId=161"


class AnnouncementCrawler:
    """Scrapes and tracks Binance delisting announcements."""

    def __init__(self, url: str = ANNOUNCEMENT_URL):
        self.url = url
        self.driver = self._initialize_driver()
        self.df = pd.DataFrame(columns=["announcement_pair", "issued_date"])
        DATA_DIR.mkdir(exist_ok=True)

    @staticmethod
    def _initialize_driver() -> webdriver.Chrome:
        """Initializes a headless Selenium WebDriver."""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-notifications")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def _get_page_source(self, url: str) -> str:
        self.driver.get(url)
        return self.driver.page_source

    def parse_announcement_links(self) -> list:
        """Parses the announcement rows from the main listing page.

        NOTE: relies on Binance's obfuscated CSS class names (css-1q4wrpt,
        css-1tl1y3y, etc.). These change without notice when Binance ships a
        frontend update — if the crawler suddenly returns nothing, this is
        the first place to check.
        """
        html = self._get_page_source(self.url)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("div", {"class": "css-1q4wrpt"})
        if table is None:
            logger.warning("Announcement table not found — page structure may have changed.")
            return []
        return table.find_all("div", {"class": "css-1tl1y3y"})

    def extract_announcement_details(self, row):
        """Extracts the link + issued date from a single announcement row."""
        title_el = row.find("div", {"class": "css-1yxx6id"})
        if title_el is None or "Binance Will Delist" not in title_el.text:
            return None, None

        link = row.find("a")["href"]
        issued_date = self._extract_issued_date(title_el.text)
        return link, issued_date

    @staticmethod
    def _extract_issued_date(title: str) -> str:
        """Pulls the trailing date out of the announcement title text.

        Fragile by nature (string-slicing on a fixed offset) since it depends
        on Binance's title format staying consistent. Consider replacing with
        a regex date match if titles start varying in length.
        """
        title = (title[:-10] + " " + title[-10:]).replace(",", "").replace(" - ", " ")
        return title.split(" ")[-1]

    def fetch_filtered_pairs(self, link: str) -> list:
        """Opens an announcement detail page and extracts the USDT pairs being delisted."""
        self.driver.execute_script(f"window.open('{link}', '_blank');")
        time.sleep(2)  # page load — replace with WebDriverWait for reliability

        self.driver.switch_to.window(self.driver.window_handles[1])
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        content = soup.find("div", {"class": "richtext-container css-fbxu07"})
        filtered_pairs = []
        if content:
            for line in content.get_text(separator="\n", strip=True).split("\n"):
                if "The exact trading pairs being removed are: " in line:
                    pairs_str = line.split("The exact trading pairs being removed are: ")[1]
                    filtered_pairs = [p for p in pairs_str.split(", ") if p.endswith("USDT")]
                    break

        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        return filtered_pairs

    def append_to_dataframe(self, filtered_pairs: list, issued_date: str) -> None:
        if not filtered_pairs:
            return
        new_rows = pd.DataFrame(
            {"announcement_pair": filtered_pairs, "issued_date": issued_date}
        )
        self.df = pd.concat([self.df, new_rows], ignore_index=True)

    def compare_and_update_data(self) -> None:
        """Diffs newly-scraped announcements against history and persists the delta."""
        try:
            old_data = pd.read_csv(OLD_ANNOUNCEMENTS_PATH)
        except FileNotFoundError:
            old_data = pd.DataFrame(columns=["announcement_pair", "issued_date"])

        new_announcements = self.df[~self.df["announcement_pair"].isin(old_data["announcement_pair"])]

        if new_announcements.empty:
            logger.info("No new announcements found.")
            return

        for pair in new_announcements["announcement_pair"]:
            logger.info("New delisting announcement: %s", pair.replace("/", ""))

        new_announcements.to_csv(NEW_ANNOUNCEMENTS_PATH, index=False)
        combined = pd.concat([new_announcements, old_data], ignore_index=True)
        combined.to_csv(OLD_ANNOUNCEMENTS_PATH, index=False)
        logger.info("Saved %d new announcement(s) to %s", len(new_announcements), OLD_ANNOUNCEMENTS_PATH)

    def run(self) -> None:
        """Scrapes the latest delisting announcement and updates local records."""
        try:
            rows = self.parse_announcement_links()
            for row in rows:
                link, issued_date = self.extract_announcement_details(row)
                if link and issued_date:
                    filtered_pairs = self.fetch_filtered_pairs(link)
                    self.append_to_dataframe(filtered_pairs, issued_date)
                    break  # only the newest announcement is checked
            self.compare_and_update_data()
        finally:
            self.driver.quit()  # always release the browser, even on error


if __name__ == "__main__":
    start = time.time()
    AnnouncementCrawler().run()
    logger.info("Run completed in %.2fs", time.time() - start)