import os
import sqlite3
import logging
import json  # Import the json module
from telegram import ParseMode, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from googletrans import Translator
from telegram.error import Unauthorized, BadRequest
import time  # for sleep

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your Telegram User ID for the admin check
ADMIN_USER_ID = 763267268  # Replace with your actual Telegram user ID

# Your bot token from BotFather
BOT_TOKEN = "7951430297:AAGn0GhfW83Btw-FR-wgWMaW-U35SCygf08"  # Replace with your actual bot token

# Initialize the translator
translator = Translator()

# Dictionary to store message IDs and their content (text + formatting and media)
messages = {}

# SQLite database file
DB_FILE = "bot_stats.db"

# Function to initialize the SQLite database and create the table
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create the table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_stats (
        user_id TEXT PRIMARY KEY,
        times_started INTEGER,
        translations INTEGER DEFAULT 0
    )
    ''')

    # Check if the 'translations' column exists, and if not, add it
    cursor.execute("PRAGMA table_info(user_stats);")
    columns = [col[1] for col in cursor.fetchall()]

    if 'translations' not in columns:
        cursor.execute("ALTER TABLE user_stats ADD COLUMN translations INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

# Function to get user stats from SQLite
def get_user_stats(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT times_started, translations FROM user_stats WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    conn.close()
    return result if result else (0, 0)

# Function to increment the /start count for a user in SQLite
def update_user_stats(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    current_stats = get_user_stats(user_id)
    times_started = current_stats[0]

    if times_started == 0:
        # Insert new user if they don't exist
        cursor.execute("INSERT INTO user_stats (user_id, times_started) VALUES (?, ?)", (user_id, 1))
    else:
        # Update the count for existing user
        cursor.execute("UPDATE user_stats SET times_started = times_started + 1 WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()

# Function to increment the translation count for a user
def increment_translation_count(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("UPDATE user_stats SET translations = translations + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Handle the /start command
def start(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)

    # Update user stats in SQLite
    update_user_stats(user_id)

    # Inform the user about the bot and its capabilities
    update.message.reply_text("Hello! You can now receive translations by clicking the '[Start Chat]' link on posts.")

# Handle the deep linking logic when entering from the "Start Chat" link
def deep_link_handler(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)

    # Get the message ID from the deep link and strip the "translate_" prefix
    message_id = context.args[0].replace("translate_", "") if context.args else None

    # Check if the user already exists in the database
    if get_user_stats(user_id)[0] > 0 and message_id:
        # User already exists, skip /start and go to /translate with the message ID
        translate(update, context, message_id)
    elif message_id:
        # New user, trigger /start and then translate the specific message
        start(update, context)
        translate(update, context, message_id)

# Function to translate the current message (passed via the deep link)
def translate(update: Update, context: CallbackContext, message_id=None):
    user_id = update.message.from_user.id  # User who typed the command

    # If no message_id is provided, inform the user
    if not message_id:
        update.message.reply_text("No message ID provided for translation.")
        return

    try:
        message_id = int(message_id)  # Convert message_id to an integer
    except ValueError:
        update.message.reply_text("Invalid message ID for translation.")
        return

    message_data = messages.get(message_id)

    if not message_data:
        update.message.reply_text("No message found for translation.")
        return

    russian_text = message_data['text']
    media = message_data['media']

    # Remove the instruction part if present
    instruction_text = "🤖 To receive translations in DM"
    if instruction_text in russian_text:
        russian_text = russian_text.split(instruction_text)[0].strip()

    # Show a "Loading..." message to the user
    loading_message = context.bot.send_message(chat_id=user_id, text="Loading...")

    if russian_text:
        try:
            # Retry mechanism for translation with automatic retry on error
            attempts = 5  # Set number of retry attempts
            delay_between_attempts = 2  # Delay between retries in seconds
            translated_text = None

            for attempt in range(attempts):
                try:
                    # Try to translate the Russian text to English
                    response = translator.translate(russian_text, src='ru', dest='en')
                    translated_text = response.text

                    # Ensure that the translated_text is valid and not None
                    if translated_text and isinstance(translated_text, str):
                        break  # Break out of the loop if translation is successful

                except json.decoder.JSONDecodeError as e:
                    logger.warning(f"Translation API error (attempt {attempt + 1}/{attempts}): {e}")
                    if attempt < attempts - 1:
                        time.sleep(delay_between_attempts)  # Wait before retrying
                    else:
                        raise  # Raise the exception if all attempts fail
                except Exception as e:
                    logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                    if attempt < attempts - 1:
                        time.sleep(delay_between_attempts)
                    else:
                        raise

            # If the translation is still unsuccessful after retries
            if not translated_text or translated_text == russian_text:
                context.bot.edit_message_text(chat_id=user_id, message_id=loading_message.message_id, text="Translation failed, please try again.")
                return

            # Send the translation as a private message (DM) to the user who typed the command
            if media:
                if isinstance(media, list):  # Handle photos
                    context.bot.send_photo(chat_id=user_id, photo=media[-1].file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
                elif hasattr(media, 'file_id'):  # Handle video, GIF, etc.
                    context.bot.send_document(chat_id=user_id, document=media.file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
            else:
                # Edit the "Loading..." message with the translation result
                context.bot.edit_message_text(chat_id=user_id, message_id=loading_message.message_id, text=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)

            # Increment the translation count for the user
            increment_translation_count(str(user_id))

            # Delete the "Loading..." message after translation is shown
            context.bot.delete_message(chat_id=user_id, message_id=loading_message.message_id)

        except Unauthorized:
            context.bot.edit_message_text(chat_id=user_id, message_id=loading_message.message_id, text="You need to start a chat with the bot first.")
        except Exception as e:
            logger.error(f"Unexpected error during translation: {e}")
            context.bot.edit_message_text(chat_id=user_id, message_id=loading_message.message_id, text=f"An error occurred: {str(e)}")
            context.bot.delete_message(chat_id=user_id, message_id=loading_message.message_id)  # Ensure deletion on error
    else:
        context.bot.edit_message_text(chat_id=user_id, message_id=loading_message.message_id, text="Error: Original message not found.")
        context.bot.delete_message(chat_id=user_id, message_id=loading_message.message_id)  # Ensure deletion if no message found


# Function to handle new posts in the channel and store the message for translation
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

    # Store the message in the global dictionary for translation
    messages[message.message_id] = {
        'text': message_text,
        'media': message.photo or message.video or message.animation or message.document
    }

    # Send the message ID to the admin
    try:
        context.bot.send_message(chat_id=ADMIN_USER_ID, text=f"New post ID: {message.message_id}")
    except BadRequest as e:
        logger.error(f"Error sending message ID to admin: {e}")

# Admin-only /stats command to include translations count
def stats(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    # Check if the user is the admin
    if user_id != ADMIN_USER_ID:
        update.message.reply_text("You are not authorized to view the statistics.")
        return

    # Fetch stats from SQLite
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM user_stats")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(times_started) FROM user_stats")
    total_starts = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(translations) FROM user_stats")
    total_translations = cursor.fetchone()[0] or 0

    conn.close()

    update.message.reply_text(f"Total unique users: {total_users}")
    update.message.reply_text(f"Total /start commands issued: {total_starts}")
    update.message.reply_text(f"Total translations made: {total_translations}")

# Main function to start the bot
def main():
    # Initialize the SQLite database
    init_db()

    # Initialize the bot
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add handler for the deep link handler (for checking if user should use /start or /translate)
    dp.add_handler(CommandHandler("start", deep_link_handler))

    # Add handler for the /translate command
    dp.add_handler(CommandHandler("translate", translate))

    # Add handler to detect new posts in the channel
    dp.add_handler(MessageHandler(Filters.chat_type.channel, handle_new_channel_post))

    # Add handler for the /stats command (admin only)
    dp.add_handler(CommandHandler("stats", stats))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
