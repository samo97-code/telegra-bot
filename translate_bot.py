import os
import json
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telegram.error import Unauthorized, BadRequest
from googletrans import Translator

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your Telegram User ID for the admin check
ADMIN_USER_ID = 763267268  # Replace with your actual Telegram user ID

# Your bot token from BotFather
BOT_TOKEN = "7951430297:AAGn0GhfW83Btw-FR-wgWMaW-U35SCygf08"  # Replace with your actual bot token

# JSON file setup for storing stats
STATS_FILE = "user_stats.json"

# Initialize the translator
translator = Translator()

# Dictionary to store message IDs and their content (text + formatting and media)
messages = {}

# Function to load stats from a JSON file
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}  # Return an empty dict if the file is corrupted or empty
    return {}

# Function to save stats to a JSON file
def save_stats(stats):
    with open(STATS_FILE, "w") as file:
        json.dump(stats, file)

# Handle the /start command in a private chat
def start(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    stats = load_stats()

    if user_id not in stats:
        stats[user_id] = {"times_started": 1}
    else:
        stats[user_id]["times_started"] += 1

    save_stats(stats)

    update.message.reply_text("Hello! You can now receive translations by clicking the 'Translate to English' button on posts.")

# Function to handle new posts in the channel and add the translation button without a new notification
def handle_new_channel_post(update: Update, context: CallbackContext):
    message = update.channel_post

    if not message:
        return  # Exit if the message is None

    # Store the caption (or text) and media
    message_text = getattr(message, 'caption_html', None) or getattr(message, 'text_html', None) or message.caption or message.text
    if not message_text:
        logger.error(f"No text or caption found for message ID: {message.message_id}")
        return

    logger.info(f"Received message for translation: {message_text}")

    messages[message.message_id] = {
        'text': message_text,
        'media': message.photo or message.video or message.animation or message.document
    }

    # Create a translation button
    keyboard = [[InlineKeyboardButton("Translate to English", callback_data=f'translate_{message.message_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Try editing the original post to add the translation button (no new notification sent)
        context.bot.edit_message_reply_markup(chat_id=message.chat_id, message_id=message.message_id, reply_markup=reply_markup)
    except BadRequest as e:
        # Handle invalid message_id (message might not exist or be uneditable)
        logger.error(f"Error editing message: {e}")

# Function to handle button clicks for translation and send DM
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    message_id = int(query.data.split('_')[1])

    # Fetch the original message data
    message_data = messages.get(message_id)

    if message_data:
        russian_text = message_data['text']
        media = message_data['media']

        if russian_text:
            try:
                # Debug: Print or log the message text before translation
                logger.info(f"Translating text: {russian_text}")

                # Retry mechanism for translation
                attempts = 3
                translated_text = None

                for attempt in range(attempts):
                    try:
                        # Translate the Russian text to English
                        translated_text = translator.translate(russian_text, src='ru', dest='en').text
                        if translated_text:  # If valid response is received, break the loop
                            break
                    except json.decoder.JSONDecodeError as e:
                        logger.warning(f"Translation API error, attempt {attempt + 1} of {attempts}: {e}")
                        if attempt == attempts - 1:  # If it's the last attempt, raise the exception
                            raise

                if not translated_text or translated_text == russian_text:
                    query.answer(text="Translation failed, please try again.")
                    return

                # Send the translation as a private message (DM) to the user who clicked the button
                if media:
                    if isinstance(media, list):  # Handle photos
                        context.bot.send_photo(chat_id=user_id, photo=media[-1].file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
                    elif hasattr(media, 'file_id'):  # Handle video, GIF, etc.
                        context.bot.send_document(chat_id=user_id, document=media.file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
                else:
                    # Send the translated text as a DM
                    context.bot.send_message(chat_id=user_id, text=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
            except Unauthorized:
                # Notify the user they need to start a chat with the bot first
                query.answer(text="You need to start a chat with the bot first.")
            except json.decoder.JSONDecodeError as e:
                # Handle JSON errors from translation API
                query.answer(text="An error occurred during translation. Please try again.")
                logger.error(f"JSONDecodeError: {e}")
            except Exception as e:
                # Log the error with details
                logger.error(f"Unexpected error during translation: {e}")
                query.answer(text=f"An error occurred: {str(e)}")

            # Acknowledge the button click without changing the channel post
            query.answer(text="Translation sent to your DM.")
    else:
        query.answer(text="Error: Original message not found.")

# Admin-only /stats command
def stats(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        update.message.reply_text("You are not authorized to view the statistics.")
        return

    # Load statistics
    stats = load_stats()
    total_users = len(stats)
    total_starts = sum([user_data["times_started"] for user_data in stats.values()])

    update.message.reply_text(f"Total unique users: {total_users}")
    update.message.reply_text(f"Total /start commands issued: {total_starts}")

# Main function to start the bot
def main():
    # Initialize the bot
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add handler for the /start command
    dp.add_handler(CommandHandler("start", start))

    # Add handler to detect new posts
    dp.add_handler(MessageHandler(Filters.chat_type.channel, handle_new_channel_post))

    # Add handler for button clicks
    dp.add_handler(CallbackQueryHandler(button))

    # Add handler for the /stats command (admin only)
    dp.add_handler(CommandHandler("stats", stats))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
