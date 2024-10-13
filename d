from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CallbackQueryHandler, MessageHandler, Filters
from googletrans import Translator

# Initialize the translator
translator = Translator()

# Dictionary to store message IDs and their content (text + formatting and media)
messages = {}
# Dictionary to track which messages have an active translation
active_translations = {}

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
    context.bot.send_message(chat_id=message.chat_id, text="Click to translate this post to English:", reply_markup=reply_markup)

# Function to delete the translated message and allow the button to work again
def revert_translation(context):
    chat_id = context.job.context['chat_id']
    translated_message_id = context.job.context['translated_message_id']
    message_id = context.job.context['message_id']

    # Delete the translated message
    context.bot.delete_message(chat_id=chat_id, message_id=translated_message_id)

    # Allow the button to show a new translated post after the deletion
    if message_id in active_translations:
        del active_translations[message_id]  # Remove the message ID from active translations so a new one can be shown

# Callback function to handle button clicks for translation
def button(update, context):
    query = update.callback_query
    message_id = int(query.data.split('_')[1])

    # Check if this message already has an active translation
    if message_id in active_translations:
        query.answer(text="The translation is already shown. Please wait for it to be removed.")
        return

    # Fetch the original message data
    message_data = messages.get(message_id)

    if message_data:
        russian_text = message_data['text']
        media = message_data['media']

        if russian_text:
            # Translate the Russian text to English
            translated_text = translator.translate(russian_text, src='ru', dest='en').text

            # Handle media (if present) and translation
            if media:
                if isinstance(media, list):  # Handle photos
                    # Send the translated message and keep the button visible
                    translated_message = context.bot.send_photo(chat_id=query.message.chat_id, photo=media[-1].file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
                elif hasattr(media, 'file_id'):  # Handle video, GIF, etc.
                    # Send the translated message and keep the button visible
                    translated_message = context.bot.send_document(chat_id=query.message.chat_id, document=media.file_id, caption=f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)
            else:
                # If no media, send the translated text without removing the button
                translated_message = query.message.reply_text(f"🇺🇸 {translated_text}", parse_mode=ParseMode.HTML)

            # Mark this message as having an active translation
            active_translations[message_id] = translated_message.message_id

            # Schedule a job to delete the translated message after 1 minute
            context.job_queue.run_once(revert_translation, 60, context={
                'chat_id': query.message.chat_id,
                'message_id': message_id,
                'translated_message_id': translated_message.message_id  # Save the translated message ID for deletion
            })
    else:
        query.answer(text="Error: Original message not found.")

# Main function to start the bot
def main():
    # Initialize the bot
    updater = Updater("7951430297:AAGn0GhfW83Btw-FR-wgWMaW-U35SCygf08", use_context=True)
    dp = updater.dispatcher

    # Add handler to detect new posts
    dp.add_handler(MessageHandler(Filters.chat_type.channel, handle_new_channel_post))

    # Add handler for button clicks
    dp.add_handler(CallbackQueryHandler(button))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
