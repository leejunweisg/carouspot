<img src="./assets/logo-transparent.png" width="50%" height="50%" title="Logo" alt="Logo">

CarouSpot is a Telegram bot that notifies you of new listings on Carousell SG, a community marketplace and classifieds platform.
Subscribe to keywords to be the first to know about new listings and get notified when they are posted!

Try it out https://t.me/carouspot_bot

## Features
1. Subscribe to keywords and get notified when new listings are posted.
2. Spotlight and Bumped listings (old listings) are automatically excluded.

## Instructions
### Docker

```shell
docker run -itd --env MONGO_URL="your_mongo_url" --env BOT_TOKEN="your_bot_token" ghcr.io/leejunweisg/carouspot:main
```
Two environment variables must be passed into the Docker container:
- `MONGO_URL`: The connection URL to your MongoDB instance.
- `BOT_TOKEN`: The token of your telegram bot, this can be retrieved from BotFather.

### Manual
1. Clone the repository
    ```shell
    git clone https://github.com/leejunweisg/carouspot && cd carouspot
    ```
2. Create Python virtual environment and install packages
    ```shell
    python3 -m venv venv
    source ./venv/scripts/activate
    pip install -r ./requirements.txt
    ```
3. Update the `.env` file to fill in `MONGO_URL` and `BOT_TOKEN`.
4. Run the bot.
   ```shell
   python3 bot.py
   ```

## Todo
1. Refactor to scrape all items using one instance of the Selenium webdriver.
   - Currently, a new webdriver is instantiated to scrape each search term.
2. Improve user experience on the bot (e.g. inline keyboard instead of typing)
3. Add support for filters (e.g. price range, condition, etc) in subscriptions.
4. Support for other countries (e.g. Carousell MY, Carousell PH, etc).
