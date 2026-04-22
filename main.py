import os
import telebot
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from database import init_db, increment_work, get_total_work

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set.")

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize the database on startup
init_db()

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Build the persistent reply keyboard shown after /start."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("✅ Work Status"),
        KeyboardButton("📊 Total Completed"),
        KeyboardButton("👨‍💼 Admin"),
    )
    return kb


def work_status_keyboard() -> InlineKeyboardMarkup:
    """Build the inline keyboard for the work status prompt."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("❌ No", callback_data="work_no"),
        InlineKeyboardButton("✅ Yes, Completed", callback_data="work_yes"),
    )
    return kb

# ---------------------------------------------------------------------------
# Handlers — Commands
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message):
    """Send the welcome message and display the main menu keyboard."""
    name = message.from_user.first_name or "there"
    text = (
        f"👋 Welcome, {name}!\n\n"
        "This bot helps you track your completed work efficiently.\n"
        "Use the buttons below to log tasks, view your progress, or reach the admin."
    )
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=main_menu_keyboard(),
    )

# ---------------------------------------------------------------------------
# Handlers — Reply Keyboard Buttons
# ---------------------------------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "✅ Work Status")
def handle_work_status(message: telebot.types.Message):
    """Ask the user whether they have just completed a task."""
    bot.send_message(
        message.chat.id,
        "Have you completed a task just now?",
        reply_markup=work_status_keyboard(),
    )


@bot.message_handler(func=lambda m: m.text == "📊 Total Completed")
def handle_total_completed(message: telebot.types.Message):
    """Fetch and display the user's total completed task count."""
    user_id = message.from_user.id
    total = get_total_work(user_id)
    bot.send_message(
        message.chat.id,
        f"📊 Your total completed tasks: *{total}*",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: m.text == "👨‍💼 Admin")
def handle_admin(message: telebot.types.Message):
    """Send an inline button that links directly to the admin's Telegram profile."""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Open Admin Profile", url="https://t.me/Sefuax"))
    bot.send_message(
        message.chat.id,
        "Reach the admin directly on Telegram:",
        reply_markup=kb,
    )

# ---------------------------------------------------------------------------
# Handlers — Inline Callbacks
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda call: call.data in ("work_yes", "work_no"))
def handle_work_callback(call: telebot.types.CallbackQuery):
    """Process the user's response to the work status prompt."""
    bot.answer_callback_query(call.id)  # dismiss the loading indicator

    if call.data == "work_yes":
        increment_work(call.from_user.id)
        bot.edit_message_text(
            "✅ Great job! Your work has been recorded successfully.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )
    else:
        bot.edit_message_text(
            "No problem. You can update your work anytime.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
  
