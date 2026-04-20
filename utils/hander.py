from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
from datetime import datetime
import asyncio
from config import CHANNEL_LINK, UPDATES_CHANNEL, ADMIN_ID
from utils.json_io import track_user, track_group, get_stats

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type != "private":
        track_group(message.chat.id, message.chat.username, message.chat.title)
    else:
        track_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    typing_msg = await message.answer("Finalizing Setup....")
    await asyncio.sleep(1.5)
    await typing_msg.edit_text("Preparing Server.....")
    await asyncio.sleep(1.5)
    
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Main Menu", callback_data="main_menu"))
    kb.row(InlineKeyboardButton(text="About Us", callback_data="about_us"))
    kb.row(InlineKeyboardButton(text="Status", callback_data="status"))
    kb.row(InlineKeyboardButton(text="Privacy & Terms", callback_data="privacy_terms"))
    kb.row(InlineKeyboardButton(text="📢 Join Updates", url=CHANNEL_LINK))
    
    welcome_text = (
        f"Hi {message.from_user.first_name}! Welcome to this bot\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Babu Utils is your ultimate toolkit on Telegram, packed with AI tools, educational resources, downloaders, temp mail, crypto utilities, and more. Simplify your tasks with ease!\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Don't forget to join for updates!\n"
        f"[Join Channel]({CHANNEL_LINK})"
    )
    await typing_msg.edit_text(welcome_text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🤖 AI Tools", callback_data="cat_ai"))
    kb.row(InlineKeyboardButton(text="📥 Downloaders", callback_data="cat_dwn"))
    kb.row(InlineKeyboardButton(text="🎵 Converter & Editing", callback_data="cat_conv"))
    kb.row(InlineKeyboardButton(text="🔤 Text & Encoding", callback_data="cat_txt"))
    kb.row(InlineKeyboardButton(text="🌐 Domain & Network", callback_data="cat_net"))
    kb.row(InlineKeyboardButton(text="📚 Language & Translate", callback_data="cat_lang"))
    kb.row(InlineKeyboardButton(text="🖼 Photo & Sticker", callback_data="cat_edit"))
    kb.row(InlineKeyboardButton(text="🔗 URL & QR Tools", callback_data="cat_url"))
    kb.row(InlineKeyboardButton(text="📧 Temp Mail & PDF", callback_data="cat_util"))
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="start"))
    await call.message.edit_text("Select a category:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("cat_"))
async def cb_category(call: CallbackQuery):
    cat = call.data.split("_")[1]
    commands_map = {
        "ai": "/gpt /gem /cl /per /gk /ar\n(Babu [text] triggers AI)",
        "dwn": "/fb /pn /ig /tik /tdl /yt /song /clip",
        "conv": "/aud /voice /vnote /vth /bg /enh /res",
        "txt": "/en /de /text /wc /style",
        "net": "/dmn /ip /px /info",
        "lang": "/spell /gra /syn /prn /tr /asr",
        "edit": "/bg /enh /res /q /kang /ytag /yth",
        "url": "/qr /short /fake /rnd",
        "util": "/mail /cmail /pdf /mpdf /cpdf /git"
    }
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Back to Menu", callback_data="main_menu"))
    await call.message.edit_text(f"Available commands for {cat.upper()}:\n{commands_map.get(cat, 'Coming Soon')}", reply_markup=kb.as_markup())

@router.callback_query(F.data == "about_us")
async def cb_about(call: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="👨‍💻 Nafis", url="https://t.me/nafis_69x_bd"))
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="start"))
    text = (
        "Name: Babu Utils\n"
        "Version: v69.0 (Beta) 🛠\n"
        "Development Team:\n"
        "- Creator: Nafis 👨‍💻\n"
        "- Helper: Safin 🙀\n"
        "Technical Stack:\n"
        "- Language: Python 🐍\n"
        "- Libraries: Aiogram 📚\n"
        "- Database: json 🗄\n"
        "- Hosting: Vps 🤩\n"
        "About: The all-in-one Telegram toolkit for seamless education, AI, downloads, and more!"
    )
    await call.message.edit_text(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "status")
async def cb_status(call: CallbackQuery):
    stats = get_stats()
    text = (
        "📊 Bot Usage Report\n"
        "━━━━━━━━━━━\n"
        "🚀 User Engagements:\n"
        f"- Daily Starts: {stats['daily_starts']}\n"
        f"- Weekly Starts: {stats['weekly_starts']}\n"
        f"- Monthly Starts: {stats['monthly_starts']}\n"
        f"- Annual Starts: {stats['annual_starts']}\n"
        "📈 Total Metrics:\n"
        f"- Total Groups: {stats['total_groups']}\n"
        f"- Users Registered: {stats['users_registered']}"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="start"))
    await call.message.edit_text(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "privacy_terms")
async def cb_privacy_terms(call: CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="Privacy Policy", callback_data="view_privacy"))
    kb.row(InlineKeyboardButton(text="Terms & Conditions", callback_data="view_terms"))
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="start"))
    text = (
        "📜 Policy & Terms\n"
        "At Babu Utils, we value your privacy and safety. Please review our policies to understand how the bot works and what rules apply when using our services.\n"
        "🔹 Privacy Policy\nLearn how basic data is handled and protected while using the bot.\n"
        "🔹 Terms & Conditions\nUnderstand the rules and guidelines for using Babu Utils.\n"
        "💡 Select an option below to continue."
    )
    await call.message.edit_text(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "view_privacy")
async def cb_view_privacy(call: CallbackQuery):
    text = (
        "📜 Privacy Policy for Babu Utils\n"
        "By using Babu Utils, you agree to this privacy policy.\n"
        "1. Information Collected:\n"
        "• User ID and username for basic functionality.\n"
        "• Anonymous usage logs to improve the bot.\n"
        "2. How We Use Data:\n"
        "• To process commands and deliver results.\n"
        "• To prevent abuse and ensure fair usage.\n"
        "3. Third-Party Services:\nSome features use external APIs. Only the minimum data required is sent to process your request.\n"
        "4. Data Security:\nTemporary data is deleted after processing. We do not store passwords, phone numbers, or private messages.\n"
        "5. Your Rights:\nYou may stop using the bot at any time or request data deletion from the bot owner.\n"
        "We respect your privacy and aim to keep your data safe."
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="privacy_terms"))
    await call.message.edit_text(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "view_terms")
async def cb_view_terms(call: CallbackQuery):
    text = (
        "📜 Terms & Conditions for Babu Utils\n"
        "By using Babu Utils, you agree to these terms.\n"
        "1. Usage\n• You must be at least 13 years old.\n• This bot complies with Telegram Bot ToS: https://telegram.org/tos/bot-developers\n"
        "2. Prohibited Activities\n• Illegal use, abuse, or spam is strictly prohibited.\n• Misuse of tools or attempts to bypass limits may lead to restrictions.\n"
        "3. Tools & Services\n• Tools are provided for personal and legitimate use only.\n• Some features rely on third-party APIs.\n• We are not responsible for misuse of any tool.\n"
        "4. User Responsibility\n• Users are responsible for how they use the bot.\n• Activities must follow Telegram rules and applicable laws.\n"
        "5. Disclaimer\n• Services are provided as-is without guarantee of uptime or accuracy.\n• We are not liable for damages or consequences of misuse.\n"
        "6. Termination\n• Violating these terms may result in suspension or ban.\n"
        "7. Contact\n• For questions or concerns: https://t.me/nafis_69x_bd\nThank you for using Babu Utils!"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="privacy_terms"))
    await call.message.edit_text(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "start")
async def cb_back_start(call: CallbackQuery):
    await cmd_start(call.message)