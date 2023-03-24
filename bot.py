import logging
import os
import time
import html

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardRemove, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, ConversationHandler, filters, MessageHandler, \
    Application, ChatMemberHandler, CallbackContext, CallbackQueryHandler
from telegram.constants import ParseMode
from database import Database
from scraper import scrape, filter_items
from utils import split_message

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
        text="Here's what I can do:\n" + \
             "- /subscribe: subscribe to a new item\n" + \
             "- /unsubscribe: unsubscribe from an item\n" + \
             "- /subscriptions: view existing subscriptions\n" + \
             "- /help: view this message\n"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""

    chat_id = update.message.chat_id
    user = update.message.from_user

    # add chat_id to the database. if already exist, just set active to True.
    db.chats.update_one(
        filter={"chat_id": chat_id},
        update={
            "$setOnInsert": {"chat_id": chat_id},  # if chat_id doesn't exist, create it
            "$set": {"active": True}
        },
        upsert=True
    )

    # greet with welcome message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Hi {user.first_name}, welcome to CarouSpot!\nType /help to see the list of commands."
    )


async def subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retrieves and sends the user a list of subscribed items."""

    chat_id = update.message.chat_id

    # get all subscribed items in the database
    count = db.items.count_documents({"chats": chat_id})
    subscribed_items = db.items.find({"chats": chat_id})

    # prepare message
    message = ""
    for item in subscribed_items:
        message += f"\n- {item['name']}"
    message = f"<b>You are subscribed to {count} items!</b>" + html.escape(message)

    # send message
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)


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
    await context.bot.send_message(chat_id=chat_id, text=f"Okay, you are now subscribed to '{item_name}'! 🎉")
    await context.bot.send_message(chat_id=chat_id, text=f"You will be notified when new listings are posted!")

    return ConversationHandler.END


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the conversation and asks the user for the item they want to unsubscribe from."""

    chat_id = update.message.chat_id

    # get subscribed items of this user in the database
    subscribed_items = db.items.find({"chats": chat_id})

    # if the user has subscribed items, present a inline keyboard
    if subscribed_items:
        # prepare inline keyboard
        keyboard = [[InlineKeyboardButton(x['name'], callback_data=x['name'])] for x in subscribed_items]

        # send reply with the inline keyboard
        await update.message.reply_text("Which item would you like to unsubscribe from?", reply_markup=InlineKeyboardMarkup(keyboard))

        return 0

    # the user is not subscribed to any items, end the conversation
    await update.message.reply_text("You are not subscribed to any items!")

    return ConversationHandler.END


async def unsubscribe_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # wait for answer
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"Which item would you like to unsubscribe from?\n\nYou have selected '{query.data}'.")

    chat_id = query.message.chat_id

    # update database, remove chat from list of subscribed chats
    db.items.update_one(filter={"name": query.data}, update={"$pull": {"chats": chat_id}})

    # todo: remove item from database if no more chats are subscribed to it

    # send success message
    await context.bot.send_message(chat_id=chat_id, text=f"Success! You have been unsubscribed from '{query.data}!' ✅")

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
        # scrape carousell
        try:
            logging.info(f"Scraping '{item['name']}'")
            scraped_items = scrape(item["name"])
        except Exception as e:
            logging.error(f"An error has occurred while scraping '{item['name']}', skipped.")
            logging.error(e, exc_info=True)
            continue

        logging.info(f"Processing '{item['name']}'")

        # filter items
        filtered_items = filter_items(scraped_items, last_id=item["last_item_id"])

        # if there are new items, send notification to subscribed chats
        if len(filtered_items) > 0:
            # update item with new last_item_id and last_updated
            db.items.update_one(
                filter={"name": item["name"]},
                update={"$set": {"last_item_id": filtered_items[0].item_id, "last_updated": time.time()}},
                upsert=False
            )

            # filter for active chat_ids
            active_chats = db.chats.find(filter={"chat_id": {"$in": item['chats']}, "active": True},
                                         projection={"chat_id": True})
            active_chats = [x['chat_id'] for x in active_chats]

            # prepare message
            n = len(filtered_items)
            message = f"<b>I found {n} new {'listing' if n == 1 else 'listings'} for '{item['name']}'! ✨</b>\n\n"
            message += "\n\n".join([x.msg_str for x in filtered_items])

            # iterate through each subscriber of this item
            for chat_id in active_chats:
                # iterate through each message and send
                for m in split_message(message):
                    try:
                        await context.bot.send_message(chat_id=chat_id, text=m, disable_web_page_preview=True,
                                                       parse_mode=ParseMode.HTML)
                    except Forbidden as ex:
                        logger.error(str(ex))
        else:
            db.items.update_one(
                filter={"name": item["name"]},
                update={"$set": {"last_updated": time.time()}},
                upsert=False
            )

        logging.info(f"Done processing '{item['name']}'")


async def chat_member_updates(update: Update, context: CallbackContext):
    """Updates database if bot was kicked from a chat"""

    new_status = update.my_chat_member.new_chat_member.status
    chat_id = update.my_chat_member.chat.id

    if new_status in ["kicked", "left"]:
        db.chats.update_one(filter={"chat_id": chat_id}, update={"$set": {"active": False}}, upsert=False)
        logger.info(f"Chat ID {chat_id} has stopped the bot. Database updated.")


async def startup(application: Application):
    """Runs when the bot is first started"""

    # set bot commands (to enable command suggestions and "menu" button in Telegram clients)
    await application.updater.bot.set_my_commands(commands=[
        BotCommand(command="start", description="let's begin!"),
        BotCommand(command="help", description="what the bot can do"),
        BotCommand(command="subscribe", description="subscribe to a new keyword"),
        BotCommand(command="unsubscribe", description="unsubscribe to a keyword"),
        BotCommand(command="subscriptions", description="view existing subscriptions")
    ])


def main():
    # create bot application
    application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    application.post_init = startup

    # periodic jobs
    job_queue = application.job_queue
    job_half_hourly = job_queue.run_repeating(callback=check_new_items, interval=1800, first=5)

    # create handlers
    # todo: create unsubscribe handler
    start_handler = CommandHandler("start", start)
    help_handler = CommandHandler("help", help_msg)
    subscriptions_handler = CommandHandler("subscriptions", subscriptions)

    subscribe_handler = ConversationHandler(
        entry_points=[CommandHandler("subscribe", subscribe)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmation)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
    )

    unsubscribe_handler = ConversationHandler(
        entry_points=[CommandHandler("unsubscribe", unsubscribe)],
        states={
            0: [CallbackQueryHandler(unsubscribe_confirmation)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
    )

    chat_member_handler = ChatMemberHandler(chat_member_updates)

    # add handlers
    application.add_handler(start_handler)
    application.add_handler(help_handler)
    application.add_handler(subscriptions_handler)
    application.add_handler(unsubscribe_handler)
    application.add_handler(subscribe_handler)
    application.add_handler(chat_member_handler)

    # continuously poll for updates
    application.run_polling()


if __name__ == "__main__":
    main()
