from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CallbackQueryHandler, CommandHandler, MessageHandler, Filters
from telegram.error import Unauthorized
from googletrans import Translator

# Initialize the translator
translator = Translator()

# Dictionary to store message IDs and their content (text + formatting and media)
messages = {}

# Handle the /start command in a private chat
def start(update, context):
    user_id = update.message.from_user.id
    context.bot.send_message(chat_id=user_id, text="Hello! You can now receive translations by clicking the 'Translate to English' button on posts.")

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
    #To receive translations in DM, click [Start Chat](https://t.me/Meta7Helper7Bot?start=1) to open a conversation with the bot.
    context.bot.send_message(chat_id=message.chat_id, text="Click to translate this post to English.", reply_markup=reply_markup)

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
                query.answer(text="Please start a conversation with the bot first by clicking [here](https://t.me/YourBotUsername?start=1).")
            except Exception as e:
                query.answer(text=f"An error occurred: {str(e)}")

            # Acknowledge the button click without changing the channel post
            query.answer(text="Translation sent to your DM.")
    else:
        query.answer(text="Error: Original message not found.")

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

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
