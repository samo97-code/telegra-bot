from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import json

# A file to store the users who have issued the /start command
STATS_FILE = "user_stats.json"

# Function to load the user data from the stats file
def load_stats():
    try:
        with open(STATS_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Function to save the user data to the stats file
def save_stats(stats):
    with open(STATS_FILE, "w") as file:
        json.dump(stats, file)

# /start command handler
def start(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    stats = load_stats()

    if user_id not in stats:
        stats[user_id] = {"times_started": 1}
    else:
        stats[user_id]["times_started"] += 1

    save_stats(stats)

    update.message.reply_text("Welcome! You've started the bot.")
    total_users = len(stats)
    update.message.reply_text(f"Total unique users who started the bot: {total_users}")

# /stats command for the admin to check the stats
def stats(update: Update, context: CallbackContext):
    stats = load_stats()
    total_users = len(stats)
    total_starts = sum([user_data["times_started"] for user_data in stats.values()])
    update.message.reply_text(f"Total unique users: {total_users}")
    update.message.reply_text(f"Total /start commands issued: {total_starts}")

# Main function to start the bot
def main():
    # Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your actual bot token from BotFather
    updater = Updater("7951430297:AAGn0GhfW83Btw-FR-wgWMaW-U35SCygf08", use_context=True)

    dp = updater.dispatcher

    # Handle the /start command
    dp.add_handler(CommandHandler("start", start))

    # Handle the /stats command (for admins or personal tracking)
    dp.add_handler(CommandHandler("stats", stats))

    # Start polling
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
