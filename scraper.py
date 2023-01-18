import re
from typing import List

import requests
import urllib.parse
from bs4 import BeautifulSoup


class CarousellItem:
    """Represents a Carousell item"""

    def __init__(self, name: str, url: str, price: str, condition: str, username: str, bumped: bool):
        self.name: str = name
        self.url: str = url
        self.condition: str = condition
        self.price: str = price
        self.username: str = username
        self.bumped: bool = bumped
        self.item_id: int = int(re.findall(r'\d+', url)[-1])

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
               f"{self.price} ({self.condition})\n"  + \
               f"https://carousell.sg{self.url}"


def scrape(item_name: str) -> List[CarousellItem]:
    """Scrapes Carousell for items with the given item_name

    :param item_name: the name of the item to search on Carousell
    :return: a list of CarousellItem objects representing the scraped items
    """

    # encode item name for URL
    encoded_item_name = urllib.parse.quote_plus(item_name)

    # carousell search URL, sorted by "most recent"
    url = f"https://www.carousell.sg/search/\"{encoded_item_name}\"?addRecent=false&canChangeKeyword=false&includeSuggestions=false&sort_by=3"

    # make the request
    page = requests.get(url)

    # use beautiful soup to parse the HTML
    soup = BeautifulSoup(page.content, "html.parser")

    # extract list of item listings
    raw_items = soup.main.main.contents[0].contents[0].contents  # each item is class="D_rA D_wQ"

    # parse each item
    items = []
    for item in raw_items:
        # extract details
        name = item.contents[0].contents[0].contents[1].contents[1].string
        url = item.contents[0].contents[0].contents[1]['href']
        condition = item.contents[0].contents[0].contents[1].contents[4].string
        price = item.contents[0].contents[0].contents[1].contents[2].p['title']
        username = item.contents[0].contents[0].contents[0].contents[1].contents[0].string
        bumped = len(item.contents[0].contents[0].contents[0].contents[1].contents[1]) == 2

        # instantiate and store item
        items.append(CarousellItem(name, url, price, condition, username, bumped))

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
