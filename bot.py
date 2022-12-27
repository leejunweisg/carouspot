import logging
import os
import time

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardRemove
from telegram.error import Forbidden
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, ConversationHandler, filters, MessageHandler
from telegram.constants import ParseMode
from database import Database
from scraper import scrape, filter_items, CarousellItem

# logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# load environment variables
load_dotenv()

# connect to database
db = Database(os.getenv("MONGO_URL"))


async def help_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Here's what I can do:\n- /subscribe: subscribe to a new item\n- /unsubscribe: unsubscribe from an item"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""

    chat_id = update.message.chat_id
    user = update.message.from_user

    # add chat_id to the database
    db.chats.update_one(
        filter={"chat_id": chat_id},
        update={
            "$setOnInsert": {"chat_id": chat_id, "active": True},  # if chat_id doesn't exist, create it
            "$set": {"active": True}  # if chat_id exists, set active to True
        },
        upsert=True
    )

    # greet with welcome message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {user.first_name}, welcome to CarouSpot!\nType /help to see the list of commands."
    )


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation and asks the user for the item they want to subscribe to."""

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="What would you like to subscribe to? (e.g. Xbox)"
    )
    return 0


async def confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes the item the user wants to subscribe to."""

    item_name = update.message.text.lower()
    chat_id = update.message.chat_id

    # scrape to get last_item_id
    scraped_items = scrape(item_name)
    filtered_items = filter_items(scraped_items)
    newest = filtered_items[0]

    # add item to mongodb
    db.items.update_one(
        filter={"name": item_name},
        update={
            "$setOnInsert": {"last_item_id": newest.item_id, "last_updated": time.time()},
            # if item doesn't exist, create last_updated field
            "$addToSet": {"chats": chat_id},  # add user_id to set
        },
        upsert=True
    )

    # send confirmation message
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Okay, you are now subscribed to '{item_name}'!\nYou will be notified when new listings are posted."
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""

    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)

    await update.message.reply_text(
        "Alright :( Feel free to let know if there is anything else!", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


async def check_new_items(context: ContextTypes.DEFAULT_TYPE):
    """Checks for new listings. This is a callback function that will be invoked by the job queue."""

    # get all subscribed items in the database
    subscribed_items = db.items.find()

    # iterate through each item
    for item in subscribed_items:
        # scrape and filer items
        scraped_items = scrape(item["name"])
        filtered_items = filter_items(scraped_items, last_id=item["last_item_id"])

        # if there are new items, send notification to subscribed chats
        if len(filtered_items) > 0:
            # update item with new last_item_id and last_updated
            db.items.update_one(
                filter={"name": item["name"]},
                update={"$set": {"last_item_id": filtered_items[0].item_id, "last_updated": time.time()}},
                upsert=False
            )

            # prepare message
            message = f"I found {len(filtered_items)} new listings for {item['name']}!\n\n"
            message += "\n\n".join([x.msg_str for x in filtered_items])

            for chat_id in item['chats']:
                try:
                    await context.bot.send_message(chat_id=chat_id, text=message)
                except Forbidden as ex:  # if user stopped the bot
                    logger.error(ex)
        else:
            db.items.update_one(
                filter={"name": item["name"]},
                update={"$set": {"last_updated": time.time()}},
                upsert=False
            )


def main():
    # create bot application
    application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    job_queue = application.job_queue

    # periodic jobs
    job_half_hourly = job_queue.run_repeating(callback=check_new_items, interval=1800, first=5)

    # create handlers
    # todo: create unsubscribe handler
    start_handler = CommandHandler("start", start)
    help_handler = CommandHandler("help", help_msg)
    subscribe_handler = ConversationHandler(
        entry_points=[CommandHandler("subscribe", subscribe)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmation)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
    )

    # add handlers
    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(subscribe_handler)

    # continuously poll for updates
    application.run_polling()


if __name__ == "__main__":
    main()