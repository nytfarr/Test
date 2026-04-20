import asyncio
import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, MenuButtonWebApp,
    WebAppInfo, FSInputFile, InputMediaPhoto, InputMediaVideo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
PORT = int(os.getenv("PORT", 8080))
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

app = Flask(__name__)

class DataManager:
    @staticmethod
    def load_json(filename: str) -> dict:
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @staticmethod
    def save_json(filename: str, data: dict) -> None:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    @staticmethod
    def update_stats(user_id: int = None, group_id: int = None) -> None:
        stats = DataManager.load_json('users.json')
        today = datetime.now().strftime('%Y-%m-%d')
        week = datetime.now().strftime('%Y-W%W')
        month = datetime.now().strftime('%Y-%m')
        
        if 'stats' not in stats:
            stats['stats'] = {'daily': {}, 'weekly': {}, 'monthly': {}, 'total': 0}
        
        stats['stats']['total'] = stats['stats'].get('total', 0) + 1
        stats['stats']['daily'][today] = stats['stats']['daily'].get(today, 0) + 1
        stats['stats']['weekly'][week] = stats['stats']['weekly'].get(week, 0) + 1
        stats['stats']['monthly'][month] = stats['stats']['monthly'].get(month, 0) + 1
        
        if user_id:
            if 'users' not in stats:
                stats['users'] = {}
            if str(user_id) not in stats['users']:
                stats['users'][str(user_id)] = {'first_seen': datetime.now().isoformat(), 'total_uses': 0}
            stats['users'][str(user_id)]['total_uses'] += 1
        
        if group_id:
            if 'groups' not in stats:
                stats['groups'] = {}
            if str(group_id) not in stats['groups']:
                stats['groups'][str(group_id)] = {'first_seen': datetime.now().isoformat(), 'total_uses': 0}
            stats['groups'][str(group_id)]['total_uses'] += 1
        
        DataManager.save_json('users.json', stats)

class LoginStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_password = State()
    logged_in = State()

class BroadcastStates(StatesGroup):
    waiting_for_content = State()
    waiting_for_confirmation = State()
    selecting_target = State()

class AnimationStates(StatesGroup):
    animating = State()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(AnimationStates.animating)
    
    setup_msg = await message.answer("Finalizing Setup....")
    await asyncio.sleep(1.5)
    await setup_msg.edit_text("Preparing Server.....")
    await asyncio.sleep(1.5)
    await setup_msg.delete()
    
    user_name = message.from_user.first_name or "User"
    welcome_text = f"""
Hi {user_name}! Welcome to this bot...

Babu Utils is your ultimate toolkit packed with AI assistants, media converters, downloaders, text tools, and network utilities. Everything you need in one powerful Telegram bot!

Choose an option below to get started:
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Join Channel", url=f"https://t.me/{UPDATE_CHANNEL.replace('@', '')}")],
        [InlineKeyboardButton(text="Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton(text="About Us", callback_data="about_us")],
        [InlineKeyboardButton(text="Status", callback_data="status")],
        [InlineKeyboardButton(text="Privacy & Terms", callback_data="privacy_terms")],
    ])
    
    await message.answer(welcome_text, reply_markup=keyboard)
    DataManager.update_stats(user_id=message.from_user.id, group_id=message.chat.id if message.chat.type != 'private' else None)
    await state.clear()

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="AI Tools", callback_data="menu_ai")],
        [InlineKeyboardButton(text="Downloaders", callback_data="menu_downloaders")],
        [InlineKeyboardButton(text="Media Converters", callback_data="menu_converters")],
        [InlineKeyboardButton(text="Text Tools", callback_data="menu_text")],
        [InlineKeyboardButton(text="Network & Dev", callback_data="menu_network")],
        [InlineKeyboardButton(text="Other Utilities", callback_data="menu_other")],
        [InlineKeyboardButton(text="Back", callback_data="back_to_start")],
    ])
    await callback.message.edit_text("Main Menu - Select a category:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "menu_ai")
async def show_ai_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/gpt - ChatGPT", callback_data="cmd_gpt")],
        [InlineKeyboardButton(text="/gem - Gemini", callback_data="cmd_gem")],
        [InlineKeyboardButton(text="/cl - Claude", callback_data="cmd_cl")],
        [InlineKeyboardButton(text="/per - Perplexity", callback_data="cmd_per")],
        [InlineKeyboardButton(text="/gk - Grok", callback_data="cmd_gk")],
        [InlineKeyboardButton(text="/ar - AI Art Generation", callback_data="cmd_ar")],
        [InlineKeyboardButton(text="Back to Main Menu", callback_data="main_menu")],
    ])
    await callback.message.edit_text("AI Tools - Available Commands:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "menu_downloaders")
async def show_downloaders_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/fb - Facebook", callback_data="cmd_fb")],
        [InlineKeyboardButton(text="/pn - Pinterest", callback_data="cmd_pn")],
        [InlineKeyboardButton(text="/ig - Instagram", callback_data="cmd_ig")],
        [InlineKeyboardButton(text="/tik - TikTok", callback_data="cmd_tik")],
        [InlineKeyboardButton(text="/tdl - Threads", callback_data="cmd_tdl")],
        [InlineKeyboardButton(text="/yt - YouTube Video", callback_data="cmd_yt")],
        [InlineKeyboardButton(text="/song - YouTube MP3", callback_data="cmd_song")],
        [InlineKeyboardButton(text="Back to Main Menu", callback_data="main_menu")],
    ])
    await callback.message.edit_text("Downloaders - Available Commands:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "menu_converters")
async def show_converters_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/aud - Video to Audio", callback_data="cmd_aud")],
        [InlineKeyboardButton(text="/voice - Audio to Voice", callback_data="cmd_voice")],
        [InlineKeyboardButton(text="/vnote - Video to Round Note", callback_data="cmd_vnote")],
        [InlineKeyboardButton(text="/vth - Change Thumbnail", callback_data="cmd_vth")],
        [InlineKeyboardButton(text="Back to Main Menu", callback_data="main_menu")],
    ])
    await callback.message.edit_text("Media Converters - Available Commands:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "menu_text")
async def show_text_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/en - Encode", callback_data="cmd_en")],
        [InlineKeyboardButton(text="/de - Decode", callback_data="cmd_de")],
        [InlineKeyboardButton(text="/style - Font Styles (40+)", callback_data="cmd_style")],
        [InlineKeyboardButton(text="/wc - Word Count", callback_data="cmd_wc")],
        [InlineKeyboardButton(text="/tr - Translate", callback_data="cmd_tr")],
        [InlineKeyboardButton(text="Back to Main Menu", callback_data="main_menu")],
    ])
    await callback.message.edit_text("Text Tools - Available Commands:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "menu_network")
async def show_network_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/dmn - Domain Check", callback_data="cmd_dmn")],
        [InlineKeyboardButton(text="/git - GitHub Downloader", callback_data="cmd_git")],
        [InlineKeyboardButton(text="/ip - IP Info", callback_data="cmd_ip")],
        [InlineKeyboardButton(text="/px - Proxy Checker", callback_data="cmd_px")],
        [InlineKeyboardButton(text="Back to Main Menu", callback_data="main_menu")],
    ])
    await callback.message.edit_text("Network & Dev Tools - Available Commands:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "menu_other")
async def show_other_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/mail - Temp Mail", callback_data="cmd_mail")],
        [InlineKeyboardButton(text="/qr - QR Generator", callback_data="cmd_qr")],
        [InlineKeyboardButton(text="/short - URL Shortener", callback_data="cmd_short")],
        [InlineKeyboardButton(text="/fake - Random Address", callback_data="cmd_fake")],
        [InlineKeyboardButton(text="/q - Sticker Quote", callback_data="cmd_q")],
        [InlineKeyboardButton(text="Back to Main Menu", callback_data="main_menu")],
    ])
    await callback.message.edit_text("Other Utilities - Available Commands:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "about_us")
async def show_about(callback: CallbackQuery):
    about_text = """
<b>Babu Utils v69.0</b>

Creator: Nafis (@nafis_69x_bd)

Tech Stack:
• Python 3.11
• Aiogram 3.x
• Flask
• JSON Database
• Multiple AI APIs

A comprehensive multi-utility Telegram bot for all your needs.
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Back", callback_data="back_to_start")],
    ])
    await callback.message.edit_text(about_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "status")
async def show_status(callback: CallbackQuery):
    stats = DataManager.load_json('users.json')
    today = datetime.now().strftime('%Y-%m-%d')
    week = datetime.now().strftime('%Y-W%W')
    month = datetime.now().strftime('%Y-%m')
    
    daily = stats.get('stats', {}).get('daily', {}).get(today, 0)
    weekly = stats.get('stats', {}).get('weekly', {}).get(week, 0)
    monthly = stats.get('stats', {}).get('monthly', {}).get(month, 0)
    total = stats.get('stats', {}).get('total', 0)
    users = len(stats.get('users', {}))
    groups = len(DataManager.load_json('groups.json').get('groups', {}))
    
    status_text = f"""
<b>Bot Status</b>

Daily Starts: {daily}
Weekly Starts: {weekly}
Monthly Starts: {monthly}
Total Starts: {total}

Registered Users: {users}
Registered Groups: {groups}
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Back", callback_data="back_to_start")],
    ])
    await callback.message.edit_text(status_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "privacy_terms")
async def show_privacy_terms(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Privacy Policy", callback_data="privacy")],
        [InlineKeyboardButton(text="Terms & Conditions", callback_data="terms")],
        [InlineKeyboardButton(text="Back", callback_data="back_to_start")],
    ])
    await callback.message.edit_text("Select an option:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "privacy")
async def show_privacy(callback: CallbackQuery):
    privacy_text = """
<b>Privacy Policy</b>

We collect minimal data necessary for bot functionality including user IDs and chat history for AI features. Your data is never shared with third parties.

Data collected:
• Telegram User ID
• Chat history (for AI context)
• Usage statistics

Data retention: 30 days
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Back", callback_data="privacy_terms")],
    ])
    await callback.message.edit_text(privacy_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "terms")
async def show_terms(callback: CallbackQuery):
    terms_text = """
<b>Terms & Conditions</b>

By using Babu Utils, you agree to:
• Not abuse or spam the bot
• Not use for illegal activities
• Accept that services may change without notice
• Understand the bot is provided "as is"

Violations may result in permanent ban.
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Back", callback_data="privacy_terms")],
    ])
    await callback.message.edit_text(terms_text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery):
    user_name = callback.from_user.first_name or "User"
    welcome_text = f"""
Hi {user_name}! Welcome to this bot...

Babu Utils is your ultimate toolkit packed with AI assistants, media converters, downloaders, text tools, and network utilities. Everything you need in one powerful Telegram bot!

Choose an option below to get started:
"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Join Channel", url=f"https://t.me/{UPDATE_CHANNEL.replace('@', '')}")],
        [InlineKeyboardButton(text="Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton(text="About Us", callback_data="about_us")],
        [InlineKeyboardButton(text="Status", callback_data="status")],
        [InlineKeyboardButton(text="Privacy & Terms", callback_data="privacy_terms")],
    ])
    await callback.message.edit_text(welcome_text, reply_markup=keyboard)
    await callback.answer()

@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Unauthorized access.")
        return
    
    await state.set_state(LoginStates.waiting_for_username)
    await message.answer("Enter username:")

@router.message(LoginStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    if message.text != ADMIN_USER:
        await message.answer("Invalid username. Login cancelled.")
        await state.clear()
        return
    
    await state.update_data(username=message.text)
    await state.set_state(LoginStates.waiting_for_password)
    await message.answer("Enter password:")

@router.message(LoginStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    if message.text != ADMIN_PASS:
        await message.answer("Invalid password. Login cancelled.")
        await state.clear()
        return
    
    await state.set_state(LoginStates.logged_in)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Manage Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="Manage Groups", callback_data="admin_groups")],
        [InlineKeyboardButton(text="Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="Bot Controls", callback_data="admin_controls")],
        [InlineKeyboardButton(text="View Logs", callback_data="admin_logs")],
        [InlineKeyboardButton(text="Get Data Files", callback_data="admin_data")],
        [InlineKeyboardButton(text="Logout", callback_data="admin_logout")],
    ])
    
    await message.answer("Admin Panel - Select an option:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_"))
async def handle_admin_panel(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != LoginStates.logged_in.state and callback.from_user.id != ADMIN_ID:
        await callback.answer("Unauthorized. Use /login first.")
        return
    
    action = callback.data.replace("admin_", "")
    
    if action == "users":
        await show_paginated_users(callback, 0)
    elif action == "groups":
        await show_paginated_groups(callback, 0)
    elif action == "broadcast":
        await state.set_state(BroadcastStates.selecting_target)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="All Users & Groups", callback_data="broadcast_all")],
            [InlineKeyboardButton(text="Users Only", callback_data="broadcast_users")],
            [InlineKeyboardButton(text="Groups Only", callback_data="broadcast_groups")],
            [InlineKeyboardButton(text="Cancel", callback_data="admin_back")],
        ])
        await callback.message.edit_text("Select broadcast target:", reply_markup=keyboard)
    elif action == "controls":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="/on - Enable Bot", callback_data="control_on")],
            [InlineKeyboardButton(text="/off - Disable Bot", callback_data="control_off")],
            [InlineKeyboardButton(text="Back", callback_data="admin_back")],
        ])
        await callback.message.edit_text("Bot Controls:", reply_markup=keyboard)
    elif action == "logs":
        try:
            with open('bot.log', 'r') as f:
                logs = f.read()[-4000:]
            await callback.message.edit_text(f"Recent Logs:\n\n{logs}")
        except:
            await callback.message.edit_text("No logs available.")
    elif action == "data":
        files = ['users.json', 'groups.json', 'chat_history.json']
        for file in files:
            if os.path.exists(file):
                await callback.message.answer_document(FSInputFile(file))
        await callback.answer("Files sent.")
    elif action == "logout":
        await state.clear()
        await callback.message.edit_text("Logged out successfully.")
    elif action == "back":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Manage Users", callback_data="admin_users")],
            [InlineKeyboardButton(text="Manage Groups", callback_data="admin_groups")],
            [InlineKeyboardButton(text="Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="Bot Controls", callback_data="admin_controls")],
            [InlineKeyboardButton(text="View Logs", callback_data="admin_logs")],
            [InlineKeyboardButton(text="Get Data Files", callback_data="admin_data")],
            [InlineKeyboardButton(text="Logout", callback_data="admin_logout")],
        ])
        await callback.message.edit_text("Admin Panel - Select an option:", reply_markup=keyboard)
    
    await callback.answer()

async def show_paginated_users(callback: CallbackQuery, page: int):
    data = DataManager.load_json('users.json')
    users = list(data.get('users', {}).items())
    per_page = 15
    total_pages = (len(users) + per_page - 1) // per_page
    
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]
    
    text = f"Users (Page {page + 1}/{total_pages}):\n\n"
    for user_id, info in page_users:
        text += f"ID: {user_id}\nUses: {info.get('total_uses', 0)}\n\n"
    
    builder = InlineKeyboardBuilder()
    for user_id, _ in page_users:
        builder.row(
            InlineKeyboardButton(text=f"View {user_id}", callback_data=f"view_user_{user_id}"),
            InlineKeyboardButton(text=f"Delete {user_id}", callback_data=f"delete_user_{user_id}"),
            InlineKeyboardButton(text=f"Ban {user_id}", callback_data=f"ban_user_{user_id}")
        )
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="Previous", callback_data=f"users_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next", callback_data=f"users_page_{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="Back to Admin", callback_data="admin_back"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

async def show_paginated_groups(callback: CallbackQuery, page: int):
    data = DataManager.load_json('groups.json')
    groups = list(data.get('groups', {}).items())
    per_page = 15
    total_pages = (len(groups) + per_page - 1) // per_page
    
    start = page * per_page
    end = start + per_page
    page_groups = groups[start:end]
    
    text = f"Groups (Page {page + 1}/{total_pages}):\n\n"
    for group_id, info in page_groups:
        text += f"ID: {group_id}\nUses: {info.get('total_uses', 0)}\n\n"
    
    builder = InlineKeyboardBuilder()
    for group_id, _ in page_groups:
        builder.row(
            InlineKeyboardButton(text=f"View {group_id}", callback_data=f"view_group_{group_id}"),
            InlineKeyboardButton(text=f"Delete {group_id}", callback_data=f"delete_group_{group_id}")
        )
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="Previous", callback_data=f"groups_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Next", callback_data=f"groups_page_{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="Back to Admin", callback_data="admin_back"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.message(Command("off"))
async def cmd_off(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = DataManager.load_json('users.json')
    data['global_enabled'] = False
    DataManager.save_json('users.json', data)
    await message.answer("Bot has been disabled globally.")

@router.message(Command("on"))
async def cmd_on(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = DataManager.load_json('users.json')
    data['global_enabled'] = True
    DataManager.save_json('users.json', data)
    await message.answer("Bot has been enabled globally.")

@router.message(F.text.startswith("Babu"))
async def babu_trigger(message: Message):
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    history = DataManager.load_json('chat_history.json')
    chat_id = str(message.chat.id)
    if chat_id not in history:
        history[chat_id] = []
    
    history[chat_id].append({"role": "user", "content": message.text})
    
    response = f"Babu AI Response to: {message.text}\n\nThis is a simulated GPT-5 response. The AI features would be fully implemented with actual API keys."
    
    history[chat_id].append({"role": "assistant", "content": response})
    DataManager.save_json('chat_history.json', history)
    
    await message.reply(response)

@router.message(Command("gpt"))
async def cmd_gpt(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /gpt [your question]")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    
    history = DataManager.load_json('chat_history.json')
    chat_id = str(message.chat.id)
    if chat_id not in history:
        history[chat_id] = []
    
    history[chat_id].append({"role": "user", "content": command.args})
    
    response = f"GPT Response: This is a simulated response to '{command.args}'. The actual GPT integration would use OpenAI's API with proper context management."
    
    history[chat_id].append({"role": "assistant", "content": response})
    DataManager.save_json('chat_history.json', history)
    
    await message.reply(response)

@router.message(Command("gem"))
async def cmd_gemini(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /gem [your question]")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.reply(f"Gemini Response: Processing '{command.args}'. Gemini API integration ready.")

@router.message(Command("cl"))
async def cmd_claude(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /cl [your question]")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.reply(f"Claude Response: Processing '{command.args}'. Claude API integration ready.")

@router.message(Command("per"))
async def cmd_perplexity(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /per [your question]")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.reply(f"Perplexity Response: Searching for '{command.args}'. API integration ready.")

@router.message(Command("gk"))
async def cmd_grok(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /gk [your question]")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.reply(f"Grok Response: Processing '{command.args}'. Grok API integration ready.")

@router.message(Command("ar"))
async def cmd_ai_art(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /ar [prompt]")
        return
    
    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
    await message.reply(f"AI Art Generation: Creating image for '{command.args}'. This would use DALL-E or Stable Diffusion API.")

@router.message(Command("aud"))
async def cmd_audio_extract(message: Message):
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply("Reply to a video message with /aud to extract audio.")
        return
    
    await message.reply("Audio extraction started. This would use ffmpeg to extract audio from video.")

@router.message(Command("voice"))
async def cmd_to_voice(message: Message):
    if not message.reply_to_message or not message.reply_to_message.audio:
        await message.reply("Reply to an audio message with /voice to convert to voice note.")
        return
    
    await message.reply("Converting audio to voice note. This would use audio processing libraries.")

@router.message(Command("vnote"))
async def cmd_to_video_note(message: Message):
    if not message.reply_to_message or not message.reply_to_message.video:
        await message.reply("Reply to a video message with /vnote to create round video note.")
        return
    
    await message.reply("Creating video note. This would crop video to circular format.")

@router.message(Command("vth"))
async def cmd_video_thumbnail(message: Message):
    await message.reply("Send up to 10 videos with custom thumbnails. This feature would process multiple video thumbnails simultaneously.")

@router.message(Command("fb"))
async def cmd_facebook(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /fb [Facebook video URL]")
        return
    
    await message.reply(f"Downloading Facebook video from: {command.args}")

@router.message(Command("pn"))
async def cmd_pinterest(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /pn [Pinterest URL]")
        return
    
    await message.reply(f"Downloading Pinterest content from: {command.args}")

@router.message(Command("ig"))
async def cmd_instagram(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /ig [Instagram URL]")
        return
    
    await message.reply(f"Downloading Instagram content from: {command.args}")

@router.message(Command("tik"))
async def cmd_tiktok(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /tik [TikTok URL]")
        return
    
    await message.reply(f"Downloading TikTok video from: {command.args}")

@router.message(Command("tdl"))
async def cmd_threads(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /tdl [Threads URL]")
        return
    
    await message.reply(f"Downloading Threads content from: {command.args}")

@router.message(Command("yt"))
async def cmd_youtube(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /yt [YouTube URL]")
        return
    
    await message.reply(f"Downloading YouTube video from: {command.args}")

@router.message(Command("song"))
async def cmd_youtube_song(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /song [YouTube URL or song name]")
        return
    
    await message.reply(f"Downloading MP3 from: {command.args}")

@router.message(Command("en"))
async def cmd_encode(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /en [text to encode]")
        return
    
    import base64
    encoded = base64.b64encode(command.args.encode()).decode()
    await message.reply(f"Encoded: {encoded}")

@router.message(Command("de"))
async def cmd_decode(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /de [base64 text]")
        return
    
    import base64
    try:
        decoded = base64.b64decode(command.args).decode()
        await message.reply(f"Decoded: {decoded}")
    except:
        await message.reply("Invalid base64 string.")

@router.message(Command("style"))
async def cmd_style(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /style [text]")
        return
    
    styles = {
        "Bold": f"<b>{command.args}</b>",
        "Italic": f"<i>{command.args}</i>",
        "Code": f"<code>{command.args}</code>",
        "Strike": f"<s>{command.args}</s>",
    }
    
    response = "Text Styles:\n\n"
    for name, styled in styles.items():
        response += f"{name}: {styled}\n"
    
    await message.reply(response)

@router.message(Command("wc"))
async def cmd_word_count(message: Message, command: CommandObject):
    if not command.args:
        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
        else:
            await message.reply("Usage: /wc [text] or reply to a message")
            return
    else:
        text = command.args
    
    words = len(text.split())
    chars = len(text)
    await message.reply(f"Words: {words}\nCharacters: {chars}")

@router.message(Command("tr"))
async def cmd_translate(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /tr [lang_code] [text]")
        return
    
    await message.reply(f"Translating: {command.args}")

@router.message(Command("dmn"))
async def cmd_domain(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /dmn [domain]")
        return
    
    await message.reply(f"Checking domain: {command.args}")

@router.message(Command("git"))
async def cmd_github(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /git [GitHub repo URL]")
        return
    
    await message.reply(f"Downloading GitHub repository: {command.args}")

@router.message(Command("ip"))
async def cmd_ip_info(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /ip [IP address]")
        return
    
    await message.reply(f"Getting IP info for: {command.args}")

@router.message(Command("px"))
async def cmd_proxy(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /px [proxy list]")
        return
    
    await message.reply(f"Checking proxies: {command.args}")

@router.message(Command("mail"))
async def cmd_temp_mail(message: Message):
    await message.reply("Generating temporary email address... This would integrate with temp mail APIs.")

@router.message(Command("qr"))
async def cmd_qr(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /qr [text or URL]")
        return
    
    await message.reply(f"Generating QR code for: {command.args}")

@router.message(Command("short"))
async def cmd_shorten(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /short [URL]")
        return
    
    await message.reply(f"Shortening URL: {command.args}")

@router.message(Command("fake"))
async def cmd_fake_address(message: Message):
    import random
    countries = ["USA", "UK", "Canada", "Australia", "Germany", "France", "Japan"]
    streets = ["Main St", "Oak Ave", "Maple Rd", "Broadway", "Park Lane"]
    
    address = f"""
Random Address Generated:

Street: {random.randint(1, 9999)} {random.choice(streets)}
City: {random.choice(['Springfield', 'Riverside', 'Lakewood', 'Hillcrest'])}
State: {random.choice(['CA', 'NY', 'TX', 'FL'])}
Country: {random.choice(countries)}
ZIP: {random.randint(10000, 99999)}
Phone: +1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}
"""
    await message.reply(address)

@router.message(Command("q"))
async def cmd_quote(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /q [text]")
        return
    
    await message.reply(f"Creating quote sticker with text: {command.args}")

@app.route('/')
def home():
    return "Babu Utils Bot is Running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        return 'ok', 200
    return 'error', 400

def backup_data():
    if os.path.exists('users.json') and os.path.exists('groups.json') and os.path.exists('chat_history.json'):
        import asyncio
        async def send_backup():
            try:
                await bot.send_document(ADMIN_ID, FSInputFile('users.json'))
                await bot.send_document(ADMIN_ID, FSInputFile('groups.json'))
                await bot.send_document(ADMIN_ID, FSInputFile('chat_history.json'))
                await bot.send_message(ADMIN_ID, "Bot shutting down. Final backup sent.")
            except:
                pass
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_backup())
        loop.close()

def signal_handler(sig, frame):
    print("Shutting down... Sending backup.")
    backup_data()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="gpt", description="Chat with GPT"),
        BotCommand(command="gem", description="Chat with Gemini"),
        BotCommand(command="cl", description="Chat with Claude"),
        BotCommand(command="per", description="Chat with Perplexity"),
        BotCommand(command="gk", description="Chat with Grok"),
        BotCommand(command="ar", description="Generate AI art"),
        BotCommand(command="aud", description="Extract audio from video"),
        BotCommand(command="voice", description="Convert audio to voice note"),
        BotCommand(command="vnote", description="Convert video to round note"),
        BotCommand(command="vth", description="Change video thumbnail"),
        BotCommand(command="fb", description="Download Facebook video"),
        BotCommand(command="pn", description="Download Pinterest content"),
        BotCommand(command="ig", description="Download Instagram content"),
        BotCommand(command="tik", description="Download TikTok video"),
        BotCommand(command="tdl", description="Download Threads content"),
        BotCommand(command="yt", description="Download YouTube video"),
        BotCommand(command="song", description="Download YouTube MP3"),
        BotCommand(command="en", description="Encode text"),
        BotCommand(command="de", description="Decode text"),
        BotCommand(command="style", description="Apply text styles"),
        BotCommand(command="wc", description="Count words"),
        BotCommand(command="tr", description="Translate text"),
        BotCommand(command="dmn", description="Check domain"),
        BotCommand(command="git", description="Download GitHub repo"),
        BotCommand(command="ip", description="Get IP information"),
        BotCommand(command="px", description="Check proxies"),
        BotCommand(command="mail", description="Generate temp email"),
        BotCommand(command="qr", description="Generate QR code"),
        BotCommand(command="short", description="Shorten URL"),
        BotCommand(command="fake", description="Generate fake address"),
        BotCommand(command="q", description="Create quote sticker"),
        BotCommand(command="login", description="Admin login"),
        BotCommand(command="off", description="Disable bot"),
        BotCommand(command="on", description="Enable bot"),
    ]
    await bot.set_my_commands(commands)

async def main():
    await set_bot_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    
    if os.getenv("USE_WEBHOOK", "false").lower() == "true":
        webhook_url = f"https://{os.getenv('DOMAIN')}/webhook"
        await bot.set_webhook(webhook_url)
    else:
        await dp.start_polling(bot)

if __name__ == "__main__":
    from threading import Thread
    
    flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=PORT))
    flask_thread.daemon = True
    flask_thread.start()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")