import json
import logging
import os
from typing import List

from selenium.webdriver import Keys
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from seleniumwire import webdriver
from seleniumwire.utils import decode
from slugify import slugify
from webdriver_manager.chrome import ChromeDriverManager

# reduce selenium-wire logging level
selenium_logger = logging.getLogger('seleniumwire')
selenium_logger.setLevel(logging.WARNING)

# turn off WebDriver Manager logging, there seems to be no way to define logging level
os.environ['WDM_LOG'] = str(logging.NOTSET)


class CarousellItem:
    """Represents a Carousell item"""

    def __init__(self, name: str, url: str, price: str, condition: str, username: str, bumped: bool, item_id: int):
        self.name: str = name
        self.url: str = url
        self.condition: str = condition
        self.price: str = price
        self.username: str = username
        self.bumped: bool = bumped
        self.item_id: int = item_id

    def __str__(self) -> str:
        return f"{self.name}\n" + \
               f"URL: {self.url}\n" + \
               f"Item ID: {self.item_id}\n" + \
               f"Price: {self.price}\n" + \
               f"Condition: {self.condition}\n" + \
               f"Username: {self.username}\n" + \
               f"Bumped: {self.bumped}\n"

    @property
    def msg_str(self) -> str:
        return f"<b>{self.name[:36] + '...' if len(self.name) > 36 else self.name}\n</b>" + \
               f"{self.price} ({self.condition})\n" + \
               f"https://carousell.sg{self.url}"


def scrape(item_name: str) -> List[CarousellItem]:
    """
    Scrapes carousell for items with the given item_name
    :param item_name: the search term to scrape
    :return: list of CarousellItem objects
    """

    # create headless chrome driver
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    # browse to carousell
    driver.get(
        f"https://www.carousell.sg/search/\"placeholder\"?addRecent=false&canChangeKeyword=false&includeSuggestions=false&sort_by=3")

    # find search box
    search_box = driver.find_element(
        By.XPATH,
        '//*[@id="root"]/div[2]/header/div/div[2]/div/div[1]/div/div[1]/div/div/div/input'
    )

    # clear and populate textbox with item name
    for _ in range(100):
        search_box.send_keys(Keys.BACKSPACE)
    search_box.send_keys(f'"{item_name}"')

    # find and click search button
    search_button = driver.find_element(By.XPATH, '//*[@id="root"]/div[2]/header/div/div[2]/div/div/div/div[5]/button')
    search_button.click()

    items = []

    # wait until search completed
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="main"]/div[1]/div/section[2]/div[1]/div/div/button'))
        )

        # find the request containing the listing search results
        for request in driver.requests:
            if request.response and '/ds/filter/cf/4.0/search/' in request.path:
                body = decode(request.response.body,
                              request.response.headers.get('Content-Encoding', 'identity')).decode('utf-8')
                items_dict = json.loads(body)

                for item in items_dict['data']['results']:
                    # ignore spotlight items ("promotedListingCard")
                    if "listingCard" not in item:
                        continue

                    # extract details
                    item_id = int(item['listingCard']['id'])
                    name = item['listingCard']['belowFold'][0]['stringContent']
                    url = f'/p/{slugify(name)}-{item_id}/'
                    price = item['listingCard']['belowFold'][1]['stringContent']
                    condition = item['listingCard']['belowFold'][3]['stringContent']
                    username = item['listingCard']['seller']['username']
                    bumped = item['listingCard']['aboveFold'][0]['component'] == "active_bump"

                    # instantiate and store CarousellItems
                    items.append(CarousellItem(name, url, price, condition, username, bumped, item_id))

                break
    finally:
        driver.quit()

    return items


def filter_items(items: List[CarousellItem], last_id: int = -1, removed_bumped: bool = True) -> List[CarousellItem]:
    """Filters a list of CarousellItem objects
    :param items: a list of CarousellItem objects
    :param last_id: the last item_id that was previously scraped for this item
    :param removed_bumped: whether to exclude bumped items
    :return: a list of CarousellItem objects that have not been scraped before
    """
    if removed_bumped:
        filtered = filter(lambda x: x.item_id > last_id and x.bumped is False, items)
    else:
        filtered = filter(lambda x: x.item_id > last_id, items)
    return list(filtered)


if __name__ == "__main__":
    # scrape on "xbox"
    scraped_items = scrape("xbox")

    # print all scraped items
    for i in scraped_items:
        print(i)
        print("-" * 30)

    print(f"Total items scraped: {len(scraped_items)}")
