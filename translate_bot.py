from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telegram.error import Unauthorized  # Import the Unauthorized exception
from googletrans import Translator
import json

# A file to store the users who have issued the /start command
STATS_FILE = "user_stats.json"

# Your Telegram User ID for the admin check
ADMIN_USER_ID = 763267268  # Replace with your actual Telegram user ID

# Initialize the translator
translator = Translator()

# Dictionary to store message IDs and their content (text + formatting and media)
messages = {}

# Function to load the user data from the stats file
def load_stats():
    try:
        with open(STATS_FILE, "r") as file:
            content = file.read().strip()
            if not content:  # Check if the file is empty
                return {}
            return json.loads(content)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # If the file contains invalid JSON, reset it
        return {}

# Function to save the user data to the stats file
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

# Function to handle new posts in the channel
def handle_new_channel_post(update, context):
    message = update.channel_post

    # Store the caption (or text) and media
    message_text = message.caption_html or message.text_html or message.caption or message.text
    messages[message.message_id] = {
        'text': message_text if message_text else "",
        'media': message.photo or message.video or message.animation or message.document
    }

    # Create a translation button
    keyboard = [[InlineKeyboardButton("Translate to English", callback_data=f'translate_{message.message_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the button below the post
    context.bot.send_message(chat_id=message.chat_id, text="To receive translations in DM, click [Start Chat](https://t.me/Meta7Helper7Bot?start=1) to open a conversation with the bot.", reply_markup=reply_markup)

# Function to handle button clicks for translation
def button(update, context):
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
                # Translate the Russian text to English
                translated_text = translator.translate(russian_text, src='ru', dest='en').text
                if translated_text:
                    # Send the translation as a private message (DM) to the user who clicked the button
                    if media:
                        if isinstance(media, list):  # Handle photos
                            context.bot.send_photo(chat_id=user_id, photo=media[-1].file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
                        elif hasattr(media, 'file_id'):  # Handle video, GIF, etc.
                            context.bot.send_document(chat_id=user_id, document=media.file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
                    else:
                        # Send the translated text as a DM
                        context.bot.send_message(chat_id=user_id, text=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
                else:
                    query.answer(text="Translation failed, please try again.")
            except Unauthorized:
                # Notify the user they need to start a chat with the bot first
                query.answer(text="You need to start a chat with the bot first.")
            except Exception as e:
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
    updater = Updater("7951430297:AAGn0GhfW83Btw-FR-wgWMaW-U35SCygf08", use_context=True)
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
