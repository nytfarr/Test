# main.py
import asyncio
import base64
import json
import os
import random
import signal
import sys
from datetime import datetime
from threading import Thread

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from flask import Flask, request as flask_request

# ── env ────────────────────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN      = os.getenv("BOT_TOKEN")
ADMIN_ID       = int(os.getenv("ADMIN_ID"))
ADMIN_USER     = os.getenv("ADMIN_USER")
ADMIN_PASS     = os.getenv("ADMIN_PASS")
PORT           = int(os.getenv("PORT", 8080))
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "")

# ── core objects ───────────────────────────────────────────────────────────────
bot    = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp     = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)
app    = Flask(__name__)

# ── data layer ─────────────────────────────────────────────────────────────────
USERS_FILE   = "users.json"
GROUPS_FILE  = "groups.json"
HISTORY_FILE = "chat_history.json"


class DataManager:
    @staticmethod
    def load(filename: str) -> dict:
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    @staticmethod
    def save(filename: str, data: dict) -> None:
        with open(filename, "w") as f:
            json.dump(data, f, indent=2, default=str)

    # ── stats helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _bump_period(bucket: dict) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        week  = datetime.now().strftime("%Y-W%W")
        month = datetime.now().strftime("%Y-%m")
        bucket["total"]              = bucket.get("total", 0) + 1
        bucket.setdefault("daily",   {})[today]  = bucket["daily"].get(today, 0)   + 1
        bucket.setdefault("weekly",  {})[week]   = bucket["weekly"].get(week, 0)   + 1
        bucket.setdefault("monthly", {})[month]  = bucket["monthly"].get(month, 0) + 1

    @staticmethod
    def register_user(user_id: int) -> None:
        data = DataManager.load(USERS_FILE)
        data.setdefault("stats", {})
        DataManager._bump_period(data["stats"])
        users = data.setdefault("users", {})
        uid   = str(user_id)
        if uid not in users:
            users[uid] = {"first_seen": datetime.now().isoformat(), "total_uses": 0, "banned": False}
        users[uid]["total_uses"] += 1
        DataManager.save(USERS_FILE, data)

    @staticmethod
    def register_group(group_id: int) -> None:
        data = DataManager.load(GROUPS_FILE)
        groups = data.setdefault("groups", {})
        gid    = str(group_id)
        if gid not in groups:
            groups[gid] = {"first_seen": datetime.now().isoformat(), "total_uses": 0}
        groups[gid]["total_uses"] += 1
        DataManager.save(GROUPS_FILE, data)

    @staticmethod
    def is_bot_enabled() -> bool:
        return DataManager.load(USERS_FILE).get("global_enabled", True)

    @staticmethod
    def is_banned(user_id: int) -> bool:
        users = DataManager.load(USERS_FILE).get("users", {})
        return users.get(str(user_id), {}).get("banned", False)


# ── states ─────────────────────────────────────────────────────────────────────
class LoginStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_password = State()
    logged_in            = State()

class BroadcastStates(StatesGroup):
    selecting_target  = State()
    waiting_for_content = State()
    waiting_for_confirm = State()


# ── guard middleware (global enable + ban check) ────────────────────────────────
@router.message.outer_middleware()
async def global_guard(handler, event: Message, data: dict):
    # always let admin through
    if event.from_user and event.from_user.id == ADMIN_ID:
        return await handler(event, data)
    if not DataManager.is_bot_enabled():
        await event.answer("Bot is currently disabled. Try again later.")
        return
    if event.from_user and DataManager.is_banned(event.from_user.id):
        await event.answer("You are banned from using this bot.")
        return
    return await handler(event, data)


# ── keyboards ──────────────────────────────────────────────────────────────────
def start_keyboard() -> InlineKeyboardMarkup:
    channel = UPDATE_CHANNEL.replace("@", "")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel", url=f"[t.me](https://t.me/{channel})")],
        [InlineKeyboardButton(text="📋 Main Menu",    callback_data="main_menu")],
        [InlineKeyboardButton(text="ℹ️ About Us",     callback_data="about_us")],
        [InlineKeyboardButton(text="📊 Status",       callback_data="status")],
        [InlineKeyboardButton(text="🔒 Privacy & Terms", callback_data="privacy_terms")],
    ])

def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Manage Users",   callback_data="admin_users")],
        [InlineKeyboardButton(text="💬 Manage Groups",  callback_data="admin_groups")],
        [InlineKeyboardButton(text="📣 Broadcast",      callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="⚙️ Bot Controls",   callback_data="admin_controls")],
        [InlineKeyboardButton(text="📜 View Logs",      callback_data="admin_logs")],
        [InlineKeyboardButton(text="📁 Get Data Files", callback_data="admin_data")],
        [InlineKeyboardButton(text="🚪 Logout",         callback_data="admin_logout")],
    ])


# ── /start ─────────────────────────────────────────────────────────────────────
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    anim = await message.answer("⚙️ Finalizing Setup....")
    await asyncio.sleep(1.2)
    await anim.edit_text("🖥️ Preparing Server.....")
    await asyncio.sleep(1.2)
    await anim.delete()

    name = message.from_user.first_name or "User"
    text = (
        f"Hi <b>{name}</b>! Welcome to <b>Babu Utils</b> 👋\n\n"
        "Your ultimate toolkit packed with AI assistants, media converters, "
        "downloaders, text tools, and network utilities — everything you need "
        "in one powerful Telegram bot!\n\n"
        "Choose an option below to get started:"
    )
    await message.answer(text, reply_markup=start_keyboard())

    DataManager.register_user(message.from_user.id)
    if message.chat.type != "private":
        DataManager.register_group(message.chat.id)


# ── back to start ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery):
    name = callback.from_user.first_name or "User"
    text = (
        f"Hi <b>{name}</b>! Welcome to <b>Babu Utils</b> 👋\n\n"
        "Your ultimate toolkit packed with AI assistants, media converters, "
        "downloaders, text tools, and network utilities.\n\n"
        "Choose an option below to get started:"
    )
    await callback.message.edit_text(text, reply_markup=start_keyboard())
    await callback.answer()


# ── main menu ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 AI Tools",         callback_data="menu_ai")],
        [InlineKeyboardButton(text="⬇️ Downloaders",      callback_data="menu_downloaders")],
        [InlineKeyboardButton(text="🎬 Media Converters",  callback_data="menu_converters")],
        [InlineKeyboardButton(text="📝 Text Tools",        callback_data="menu_text")],
        [InlineKeyboardButton(text="🌐 Network & Dev",     callback_data="menu_network")],
        [InlineKeyboardButton(text="🧰 Other Utilities",   callback_data="menu_other")],
        [InlineKeyboardButton(text="🔙 Back",              callback_data="back_to_start")],
    ])
    await callback.message.edit_text("📋 <b>Main Menu</b> — Select a category:", reply_markup=kb)
    await callback.answer()


# ── sub-menus ──────────────────────────────────────────────────────────────────
BACK_BTN = InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")

@router.callback_query(F.data == "menu_ai")
async def show_ai_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/gpt — ChatGPT",         callback_data="noop")],
        [InlineKeyboardButton(text="/gem — Gemini",          callback_data="noop")],
        [InlineKeyboardButton(text="/cl  — Claude",          callback_data="noop")],
        [InlineKeyboardButton(text="/per — Perplexity",      callback_data="noop")],
        [InlineKeyboardButton(text="/gk  — Grok",            callback_data="noop")],
        [InlineKeyboardButton(text="/ar  — AI Art",          callback_data="noop")],
        [BACK_BTN],
    ])
    await callback.message.edit_text("🤖 <b>AI Tools</b> — Available Commands:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "menu_downloaders")
async def show_downloaders_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/fb   — Facebook",   callback_data="noop")],
        [InlineKeyboardButton(text="/pn   — Pinterest",  callback_data="noop")],
        [InlineKeyboardButton(text="/ig   — Instagram",  callback_data="noop")],
        [InlineKeyboardButton(text="/tik  — TikTok",     callback_data="noop")],
        [InlineKeyboardButton(text="/tdl  — Threads",    callback_data="noop")],
        [InlineKeyboardButton(text="/yt   — YouTube",    callback_data="noop")],
        [InlineKeyboardButton(text="/song — YouTube MP3",callback_data="noop")],
        [BACK_BTN],
    ])
    await callback.message.edit_text("⬇️ <b>Downloaders</b> — Available Commands:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "menu_converters")
async def show_converters_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/aud   — Video → Audio",      callback_data="noop")],
        [InlineKeyboardButton(text="/voice — Audio → Voice Note", callback_data="noop")],
        [InlineKeyboardButton(text="/vnote — Video → Round Note", callback_data="noop")],
        [InlineKeyboardButton(text="/vth   — Change Thumbnail",   callback_data="noop")],
        [BACK_BTN],
    ])
    await callback.message.edit_text("🎬 <b>Media Converters</b> — Available Commands:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "menu_text")
async def show_text_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/en    — Encode",      callback_data="noop")],
        [InlineKeyboardButton(text="/de    — Decode",      callback_data="noop")],
        [InlineKeyboardButton(text="/style — Font Styles", callback_data="noop")],
        [InlineKeyboardButton(text="/wc    — Word Count",  callback_data="noop")],
        [InlineKeyboardButton(text="/tr    — Translate",   callback_data="noop")],
        [BACK_BTN],
    ])
    await callback.message.edit_text("📝 <b>Text Tools</b> — Available Commands:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "menu_network")
async def show_network_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/dmn — Domain Check",      callback_data="noop")],
        [InlineKeyboardButton(text="/git — GitHub Downloader", callback_data="noop")],
        [InlineKeyboardButton(text="/ip  — IP Info",           callback_data="noop")],
        [InlineKeyboardButton(text="/px  — Proxy Checker",     callback_data="noop")],
        [BACK_BTN],
    ])
    await callback.message.edit_text("🌐 <b>Network & Dev Tools</b> — Available Commands:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "menu_other")
async def show_other_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/mail  — Temp Mail",       callback_data="noop")],
        [InlineKeyboardButton(text="/qr    — QR Generator",    callback_data="noop")],
        [InlineKeyboardButton(text="/short — URL Shortener",   callback_data="noop")],
        [InlineKeyboardButton(text="/fake  — Random Address",  callback_data="noop")],
        [InlineKeyboardButton(text="/q     — Sticker Quote",   callback_data="noop")],
        [BACK_BTN],
    ])
    await callback.message.edit_text("🧰 <b>Other Utilities</b> — Available Commands:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer("Use the command directly in chat!", show_alert=False)


# ── about / status / privacy ───────────────────────────────────────────────────
@router.callback_query(F.data == "about_us")
async def show_about(callback: CallbackQuery):
    text = (
        "<b>Babu Utils v69.0</b>\n\n"
        "Creator: Nafis (<a href='[t.me](https://t.me/nafis_69x_bd)'>@nafis_69x_bd</a>)\n\n"
        "<b>Tech Stack:</b>\n"
        "• Python 3.11\n• Aiogram 3.x\n• Flask\n• JSON Database\n• Multiple AI APIs\n\n"
        "A comprehensive multi-utility Telegram bot for all your needs."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "status")
async def show_status(callback: CallbackQuery):
    udata  = DataManager.load(USERS_FILE)
    gdata  = DataManager.load(GROUPS_FILE)
    today  = datetime.now().strftime("%Y-%m-%d")
    week   = datetime.now().strftime("%Y-W%W")
    month  = datetime.now().strftime("%Y-%m")
    s      = udata.get("stats", {})

    text = (
        "<b>📊 Bot Status</b>\n\n"
        f"Daily Starts:   {s.get('daily', {}).get(today, 0)}\n"
        f"Weekly Starts:  {s.get('weekly', {}).get(week, 0)}\n"
        f"Monthly Starts: {s.get('monthly', {}).get(month, 0)}\n"
        f"Total Starts:   {s.get('total', 0)}\n\n"
        f"Registered Users:  {len(udata.get('users', {}))}\n"
        f"Registered Groups: {len(gdata.get('groups', {}))}\n"
        f"Bot Enabled: {'✅' if DataManager.is_bot_enabled() else '❌'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_start")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "privacy_terms")
async def show_privacy_terms(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔏 Privacy Policy",    callback_data="privacy")],
        [InlineKeyboardButton(text="📄 Terms & Conditions", callback_data="terms")],
        [InlineKeyboardButton(text="🔙 Back",              callback_data="back_to_start")],
    ])
    await callback.message.edit_text("Select an option:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "privacy")
async def show_privacy(callback: CallbackQuery):
    text = (
        "<b>🔏 Privacy Policy</b>\n\n"
        "We collect minimal data necessary for bot functionality.\n\n"
        "<b>Data collected:</b>\n"
        "• Telegram User ID\n• Chat history (for AI context)\n• Usage statistics\n\n"
        "Your data is <b>never</b> shared with third parties.\n"
        "Data retention: 30 days."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="privacy_terms")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "terms")
async def show_terms(callback: CallbackQuery):
    text = (
        "<b>📄 Terms & Conditions</b>\n\n"
        "By using Babu Utils, you agree to:\n"
        "• Not abuse or spam the bot\n"
        "• Not use for illegal activities\n"
        "• Accept that services may change without notice\n"
        "• Understand the bot is provided \"as is\"\n\n"
        "Violations may result in a permanent ban."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="privacy_terms")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ── admin login ────────────────────────────────────────────────────────────────
@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Unauthorized.")
        return
    await state.set_state(LoginStates.waiting_for_username)
    await message.answer("Enter admin username:")


@router.message(LoginStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    if message.text != ADMIN_USER:
        await message.answer("❌ Wrong username. Login cancelled.")
        await state.clear()
        return
    await state.update_data(username=message.text)
    await state.set_state(LoginStates.waiting_for_password)
    await message.answer("Enter admin password:")


@router.message(LoginStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    if message.text != ADMIN_PASS:
        await message.answer("❌ Wrong password. Login cancelled.")
        await state.clear()
        return
    await state.set_state(LoginStates.logged_in)
    await message.answer("✅ Logged in successfully.", reply_markup=admin_keyboard())


# ── admin panel callbacks ──────────────────────────────────────────────────────
async def require_admin(callback: CallbackQuery, state: FSMContext) -> bool:
    """Returns True if caller is an authenticated admin."""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Unauthorized.", show_alert=True)
        return False
    cur = await state.get_state()
    if cur != LoginStates.logged_in.state:
        await callback.answer("Use /login first.", show_alert=True)
        return False
    return True


@router.callback_query(F.data.startswith("admin_"))
async def handle_admin_panel(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return

    action = callback.data[len("admin_"):]

    if action == "users":
        await show_paginated_users(callback, 0)
    elif action == "groups":
        await show_paginated_groups(callback, 0)
    elif action == "broadcast":
        await state.set_state(BroadcastStates.selecting_target)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 All Users & Groups", callback_data="broadcast_all")],
            [InlineKeyboardButton(text="👤 Users Only",         callback_data="broadcast_users")],
            [InlineKeyboardButton(text="💬 Groups Only",        callback_data="broadcast_groups")],
            [InlineKeyboardButton(text="❌ Cancel",             callback_data="admin_back")],
        ])
        await callback.message.edit_text("Select broadcast target:", reply_markup=kb)
    elif action == "controls":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Enable Bot  (/on)",  callback_data="control_on")],
            [InlineKeyboardButton(text="❌ Disable Bot (/off)", callback_data="control_off")],
            [InlineKeyboardButton(text="🔙 Back",               callback_data="admin_back")],
        ])
        await callback.message.edit_text("⚙️ Bot Controls:", reply_markup=kb)
    elif action == "logs":
        try:
            with open("bot.log", "r") as f:
                logs = f.read()[-3500:] or "Log file is empty."
        except FileNotFoundError:
            logs = "No log file found."
        await callback.message.edit_text(
            f"<pre>{logs}</pre>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
            ])
        )
    elif action == "data":
        for fname in (USERS_FILE, GROUPS_FILE, HISTORY_FILE):
            if os.path.exists(fname):
                await callback.message.answer_document(FSInputFile(fname))
        await callback.answer("📁 Files sent.")
        return
    elif action == "logout":
        await state.clear()
        await callback.message.edit_text("🚪 Logged out.")
    elif action == "back":
        await state.set_state(LoginStates.logged_in)
        await callback.message.edit_text("🛠 Admin Panel — Select an option:", reply_markup=admin_keyboard())

    await callback.answer()


# ── bot controls ───────────────────────────────────────────────────────────────
@router.callback_query(F.data.in_({"control_on", "control_off"}))
async def handle_bot_controls(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    enabled = callback.data == "control_on"
    data = DataManager.load(USERS_FILE)
    data["global_enabled"] = enabled
    DataManager.save(USERS_FILE, data)
    status = "✅ enabled" if enabled else "❌ disabled"
    await callback.message.edit_text(
        f"Bot has been {status} globally.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="admin_controls")]
        ])
    )
    await callback.answer()


@router.message(Command("on"))
async def cmd_on(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    data = DataManager.load(USERS_FILE)
    data["global_enabled"] = True
    DataManager.save(USERS_FILE, data)
    await message.answer("✅ Bot enabled globally.")


@router.message(Command("off"))
async def cmd_off(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    data = DataManager.load(USERS_FILE)
    data["global_enabled"] = False
    DataManager.save(USERS_FILE, data)
    await message.answer("❌ Bot disabled globally.")


# ── paginated users ────────────────────────────────────────────────────────────
PER_PAGE = 10

async def show_paginated_users(callback: CallbackQuery, page: int):
    data  = DataManager.load(USERS_FILE)
    users = list(data.get("users", {}).items())
    total_pages = max(1, (len(users) + PER_PAGE - 1) // PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    chunk       = users[page * PER_PAGE:(page + 1) * PER_PAGE]

    lines = [f"<b>👥 Users — Page {page+1}/{total_pages}</b>\n"]
    for uid, info in chunk:
        banned = "🚫 " if info.get("banned") else ""
        lines.append(f"{banned}ID: <code>{uid}</code> | Uses: {info.get('total_uses', 0)}")

    builder = InlineKeyboardBuilder()
    for uid, _ in chunk:
        builder.row(
            InlineKeyboardButton(text=f"👁 {uid}",  callback_data=f"view_user_{uid}"),
            InlineKeyboardButton(text=f"🚫 Ban",    callback_data=f"ban_user_{uid}"),
            InlineKeyboardButton(text=f"🗑 Delete", callback_data=f"delete_user_{uid}"),
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"users_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"users_page_{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_back"))

    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())


async def show_paginated_groups(callback: CallbackQuery, page: int):
    data   = DataManager.load(GROUPS_FILE)
    groups = list(data.get("groups", {}).items())
    total_pages = max(1, (len(groups) + PER_PAGE - 1) // PER_PAGE)
    page        = max(0, min(page, total_pages - 1))
    chunk       = groups[page * PER_PAGE:(page + 1) * PER_PAGE]

    lines = [f"<b>💬 Groups — Page {page+1}/{total_pages}</b>\n"]
    for gid, info in chunk:
        lines.append(f"ID: <code>{gid}</code> | Uses: {info.get('total_uses', 0)}")

    builder = InlineKeyboardBuilder()
    for gid, _ in chunk:
        builder.row(
            InlineKeyboardButton(text=f"👁 {gid}",  callback_data=f"view_group_{gid}"),
            InlineKeyboardButton(text=f"🗑 Delete", callback_data=f"delete_group_{gid}"),
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"groups_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶", callback_data=f"groups_page_{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="admin_back"))

    await callback.message.edit_text("\n".join(lines), reply_markup=builder.as_markup())


# ── pagination / user-action callbacks ─────────────────────────────────────────
@router.callback_query(F.data.startswith("users_page_"))
async def cb_users_page(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    page = int(callback.data.split("_")[-1])
    await show_paginated_users(callback, page)
    await callback.answer()


@router.callback_query(F.data.startswith("groups_page_"))
async def cb_groups_page(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    page = int(callback.data.split("_")[-1])
    await show_paginated_groups(callback, page)
    await callback.answer()


@router.callback_query(F.data.startswith("view_user_"))
async def cb_view_user(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    uid  = callback.data[len("view_user_"):]
    data = DataManager.load(USERS_FILE).get("users", {}).get(uid, {})
    text = (
        f"<b>User Info</b>\n\n"
        f"ID: <code>{uid}</code>\n"
        f"First seen: {data.get('first_seen', 'N/A')}\n"
        f"Total uses: {data.get('total_uses', 0)}\n"
        f"Banned: {'Yes 🚫' if data.get('banned') else 'No ✅'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_users")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("ban_user_"))
async def cb_ban_user(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    uid  = callback.data[len("ban_user_"):]
    data = DataManager.load(USERS_FILE)
    if uid in data.get("users", {}):
        data["users"][uid]["banned"] = not data["users"][uid].get("banned", False)
        DataManager.save(USERS_FILE, data)
        status = "banned 🚫" if data["users"][uid]["banned"] else "unbanned ✅"
        await callback.answer(f"User {uid} has been {status}.", show_alert=True)
    else:
        await callback.answer("User not found.", show_alert=True)


@router.callback_query(F.data.startswith("delete_user_"))
async def cb_delete_user(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    uid  = callback.data[len("delete_user_"):]
    data = DataManager.load(USERS_FILE)
    if uid in data.get("users", {}):
        del data["users"][uid]
        DataManager.save(USERS_FILE, data)
        await callback.answer(f"User {uid} deleted.", show_alert=True)
        await show_paginated_users(callback, 0)
    else:
        await callback.answer("User not found.", show_alert=True)


@router.callback_query(F.data.startswith("delete_group_"))
async def cb_delete_group(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    gid  = callback.data[len("delete_group_"):]
    data = DataManager.load(GROUPS_FILE)
    if gid in data.get("groups", {}):
        del data["groups"][gid]
        DataManager.save(GROUPS_FILE, data)
        await callback.answer(f"Group {gid} deleted.", show_alert=True)
        await show_paginated_groups(callback, 0)
    else:
        await callback.answer("Group not found.", show_alert=True)


@router.callback_query(F.data.startswith("view_group_"))
async def cb_view_group(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    gid  = callback.data[len("view_group_"):]
    data = DataManager.load(GROUPS_FILE).get("groups", {}).get(gid, {})
    text = (
        f"<b>Group Info</b>\n\n"
        f"ID: <code>{gid}</code>\n"
        f"First seen: {data.get('first_seen', 'N/A')}\n"
        f"Total uses: {data.get('total_uses', 0)}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_groups")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ── broadcast ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("broadcast_"))
async def cb_broadcast_target(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    target = callback.data[len("broadcast_"):]   # all | users | groups
    await state.update_data(broadcast_target=target)
    await state.set_state(BroadcastStates.waiting_for_content)
    await callback.message.edit_text(
        f"📣 Broadcast to: <b>{target}</b>\n\nNow send the message you want to broadcast:"
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_for_content)
async def cb_broadcast_content(message: Message, state: FSMContext):
    data   = await state.get_data()
    target = data.get("broadcast_target", "all")
    await state.update_data(broadcast_text=message.text)
    await state.set_state(BroadcastStates.waiting_for_confirm)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Cancel",  callback_data="broadcast_cancel")],
    ])
    await message.answer(
        f"Preview:\n\n{message.text}\n\n<b>Target:</b> {target}\n\nConfirm broadcast?",
        reply_markup=kb
    )


@router.callback_query(F.data == "broadcast_confirm")
async def cb_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if not await require_admin(callback, state):
        return
    data   = await state.get_data()
    text   = data.get("broadcast_text", "")
    target = data.get("broadcast_target", "all")

    sent = failed = 0
    ids: list[int] = []

    if target in ("all", "users"):
        udata = DataManager.load(USERS_FILE)
        ids += [int(uid) for uid in udata.get("users", {})]
    if target in ("all", "groups"):
        gdata = DataManager.load(GROUPS_FILE)
        ids += [int(gid) for gid in gdata.get("groups", {})]

    await callback.message.edit_text(f"📣 Broadcasting to {len(ids)} chats...")
    for cid in ids:
        try:
            await bot.send_message(cid, text)
            sent += 1
            await asyncio.sleep(0.05)   # respect Telegram rate limits
        except Exception:
            failed += 1

    await state.set_state(LoginStates.logged_in)
    await callback.message.answer(
        f"✅ Broadcast done.\nSent: {sent} | Failed: {failed}",
        reply_markup=admin_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def cb_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LoginStates.logged_in)
    await callback.message.edit_text("❌ Broadcast cancelled.", reply_markup=admin_keyboard())
    await callback.answer()


# ── "Babu" trigger ─────────────────────────────────────────────────────────────
@router.message(F.text.startswith("Babu"))
async def babu_trigger(message: Message):
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    history = DataManager.load(HISTORY_FILE)
    cid     = str(message.chat.id)
    history.setdefault(cid, []).append({"role": "user", "content": message.text})
    response = (
        f"Babu AI here! 🤖\n\n"
        f"You said: <i>{message.text}</i>\n\n"
        "AI response would go here once the API is connected."
    )
    history[cid].append({"role": "assistant", "content": response})
    DataManager.save(HISTORY_FILE, history)
    await message.reply(response)


# ── AI commands ────────────────────────────────────────────────────────────────
async def _ai_reply(message: Message, command: CommandObject, name: str):
    if not command.args:
        await message.reply(f"Usage: /{command.command} [your question]")
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    history = DataManager.load(HISTORY_FILE)
    cid     = str(message.chat.id)
    history.setdefault(cid, []).append({"role": "user", "content": command.args})
    response = f"<b>{name}</b>: This is a simulated response to «{command.args}». API integration pending."
    history[cid].append({"role": "assistant", "content": response})
    DataManager.save(HISTORY_FILE, history)
    await message.reply(response)

@router.message(Command("gpt"))
async def cmd_gpt(message: Message, command: CommandObject):
    await _ai_reply(message, command, "ChatGPT")

@router.message(Command("gem"))
async def cmd_gemini(message: Message, command: CommandObject):
    await _ai_reply(message, command, "Gemini")

@router.message(Command("cl"))
async def cmd_claude(message: Message, command: CommandObject):
    await _ai_reply(message, command, "Claude")

@router.message(Command("per"))
async def cmd_perplexity(message: Message, command: CommandObject):
    await _ai_reply(message, command, "Perplexity")

@router.message(Command("gk"))
async def cmd_grok(message: Message, command: CommandObject):
    await _ai_reply(message, command, "Grok")

@router.message(Command("ar"))
async def cmd_ai_art(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /ar [prompt]")
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
    await message.reply(f"🎨 AI Art for «{command.args}» — DALL-E/SD API integration pending.")


# ── media converter commands ───────────────────────────────────────────────────
@router.message(Command("aud"))
async def cmd_audio_extract(message: Message):
    if not (message.reply_to_message and message.reply_to_message.video):
        await message.reply("Reply to a video with /aud to extract audio.")
        return
    await message.reply("🎵 Audio extraction started. (ffmpeg integration pending)")

@router.message(Command("voice"))
async def cmd_to_voice(message: Message):
    if not (message.reply_to_message and message.reply_to_message.audio):
        await message.reply("Reply to an audio message with /voice.")
        return
    await message.reply("🎤 Converting to voice note… (pending)")

@router.message(Command("vnote"))
async def cmd_to_video_note(message: Message):
    if not (message.reply_to_message and message.reply_to_message.video):
        await message.reply("Reply to a video with /vnote.")
        return
    await message.reply("🎥 Creating round video note… (pending)")

@router.message(Command("vth"))
async def cmd_video_thumbnail(message: Message):
    await message.reply("📸 Send a video and thumbnail. (pending)")


# ── downloader commands ────────────────────────────────────────────────────────
def _dl_handler(platform: str):
    async def handler(message: Message, command: CommandObject):
        if not command.args:
            await message.reply(f"Usage: /{command.command} [URL]")
            return
        await message.reply(f"⬇️ Downloading {platform} content from:\n<code>{command.args}</code>")
    return handler

router.message(Command("fb"))  (  _dl_handler("Facebook")  )
router.message(Command("pn"))  (  _dl_handler("Pinterest")  )
router.message(Command("ig"))  (  _dl_handler("Instagram")  )
router.message(Command("tik")) (  _dl_handler("TikTok")     )
router.message(Command("tdl")) (  _dl_handler("Threads")    )
router.message(Command("yt"))  (  _dl_handler("YouTube")    )

@router.message(Command("song"))
async def cmd_youtube_song(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /song [YouTube URL or song name]")
        return
    await message.reply(f"🎵 Downloading MP3 for: <code>{command.args}</code>")


# ── text tools ─────────────────────────────────────────────────────────────────
@router.message(Command("en"))
async def cmd_encode(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /en [text]")
        return
    encoded = base64.b64encode(command.args.encode()).decode()
    await message.reply(f"🔒 Encoded:\n<code>{encoded}</code>")

@router.message(Command("de"))
async def cmd_decode(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /de [base64 text]")
        return
    try:
        decoded = base64.b64decode(command.args.encode()).decode()
        await message.reply(f"🔓 Decoded:\n<code>{decoded}</code>")
    except Exception:
        await message.reply("❌ Invalid base64 string.")

@router.message(Command("style"))
async def cmd_style(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /style [text]")
        return
    t = command.args
    response = (
        "✨ <b>Text Styles</b>\n\n"
        f"Bold:   <b>{t}</b>\n"
        f"Italic: <i>{t}</i>\n"
        f"Code:   <code>{t}</code>\n"
        f"Strike: <s>{t}</s>\n"
        f"Under:  <u>{t}</u>"
    )
    await message.reply(response)

@router.message(Command("wc"))
async def cmd_word_count(message: Message, command: CommandObject):
    if command.args:
        text = command.args
    elif message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text
    else:
        await message.reply("Usage: /wc [text] or reply to a message.")
        return
    await message.reply(
        f"📊 Words: <b>{len(text.split())}</b>\n"
        f"Characters: <b>{len(text)}</b>\n"
        f"Lines: <b>{text.count(chr(10)) + 1}</b>"
    )

@router.message(Command("tr"))
async def cmd_translate(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /tr [lang_code] [text]\nExample: /tr en Bonjour")
        return
    await message.reply(f"🌐 Translating: <i>{command.args}</i>\n(Translation API pending)")


# ── network & dev tools ────────────────────────────────────────────────────────
@router.message(Command("dmn"))
async def cmd_domain(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /dmn [domain.com]")
        return
    await message.reply(f"🌐 Checking domain: <code>{command.args}</code>\n(WHOIS API pending)")

@router.message(Command("git"))
async def cmd_github(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /git [GitHub repo URL]")
        return
    await message.reply(f"📦 Downloading repo: <code>{command.args}</code>\n(API pending)")

@router.message(Command("ip"))
async def cmd_ip_info(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /ip [IP address]")
        return
    await message.reply(f"🌍 IP info for: <code>{command.args}</code>\n(IP API pending)")

@router.message(Command("px"))
async def cmd_proxy(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /px [proxy:port ...]")
        return
    await message.reply(f"🔍 Checking proxies…\n(Checker pending)")


# ── other utilities ────────────────────────────────────────────────────────────
@router.message(Command("mail"))
async def cmd_temp_mail(message: Message):
    await message.reply("📧 Generating temp email… (Temp Mail API pending)")

@router.message(Command("qr"))
async def cmd_qr(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /qr [text or URL]")
        return
    await message.reply(f"📷 Generating QR for: <code>{command.args}</code>\n(qrcode lib pending)")

@router.message(Command("short"))
async def cmd_shorten(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /short [URL]")
        return
    await message.reply(f"🔗 Shortening: <code>{command.args}</code>\n(URL shortener API pending)")

@router.message(Command("fake"))
async def cmd_fake_address(message: Message):
    streets  = ["Main St", "Oak Ave", "Maple Rd", "Broadway", "Park Lane"]
    cities   = ["Springfield", "Riverside", "Lakewood", "Hillcrest"]
    states   = ["CA", "NY", "TX", "FL"]
    countries= ["USA", "UK", "Canada", "Australia", "Germany"]
    text = (
        "🏠 <b>Random Address</b>\n\n"
        f"Street:  {random.randint(1, 9999)} {random.choice(streets)}\n"
        f"City:    {random.choice(cities)}\n"
        f"State:   {random.choice(states)}\n"
        f"Country: {random.choice(countries)}\n"
        f"ZIP:     {random.randint(10000, 99999)}\n"
        f"Phone:   +1-{random.randint(200,999)}-{random.randint(200,999)}-{random.randint(1000,9999)}"
    )
    await message.reply(text)

@router.message(Command("q"))
async def cmd_quote(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Usage: /q [text]")
        return
    await message.reply(f"💬 Creating quote sticker for: <i>{command.args}</i>\n(Sticker API pending)")


# ── Flask routes ───────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return "Babu Utils Bot is Running! ✅"

@app.route("/webhook", methods=["POST"])
def webhook():
    if flask_request.content_type == "application/json":
        return "ok", 200
    return "error", 400


# ── graceful shutdown with backup ──────────────────────────────────────────────
async def send_backup():
    for fname in (USERS_FILE, GROUPS_FILE, HISTORY_FILE):
        if os.path.exists(fname):
            try:
                await bot.send_document(ADMIN_ID, FSInputFile(fname))
            except Exception:
                pass
    try:
        await bot.send_message(ADMIN_ID, "🛑 Bot shutting down. Final backup sent.")
    except Exception:
        pass


def signal_handler(sig, frame):
    print("Shutting down… sending backup.")
    loop = asyncio.new_event_loop()
    loop.run_until_complete(send_backup())
    loop.close()
    sys.exit(0)

signal.signal(signal.SIGINT,  signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ── bot commands list ──────────────────────────────────────────────────────────
async def set_bot_commands():
    commands = [
        BotCommand(command="start",  description="Start the bot"),
        BotCommand(command="gpt",    description="Chat with ChatGPT"),
        BotCommand(command="gem",    description="Chat with Gemini"),
        BotCommand(command="cl",     description="Chat with Claude"),
        BotCommand(command="per",    description="Chat with Perplexity"),
        BotCommand(command="gk",     description="Chat with Grok"),
        BotCommand(command="ar",     description="Generate AI art"),
        BotCommand(command="aud",    description="Extract audio from video"),
        BotCommand(command="voice",  description="Convert audio to voice note"),
        BotCommand(command="vnote",  description="Convert video to round note"),
        BotCommand(command="vth",    description="Change video thumbnail"),
        BotCommand(command="fb",     description="Download Facebook video"),
        BotCommand(command="pn",     description="Download Pinterest content"),
        BotCommand(command="ig",     description="Download Instagram content"),
        BotCommand(command="tik",    description="Download TikTok video"),
        BotCommand(command="tdl",    description="Download Threads content"),
        BotCommand(command="yt",     description="Download YouTube video"),
        BotCommand(command="song",   description="Download YouTube MP3"),
        BotCommand(command="en",     description="Base64 encode text"),
        BotCommand(command="de",     description="Base64 decode text"),
        BotCommand(command="style",  description="Apply text styles"),
        BotCommand(command="wc",     description="Count words & chars"),
        BotCommand(command="tr",     description="Translate text"),
        BotCommand(command="dmn",    description="Check domain info"),
        BotCommand(command="git",    description="Download GitHub repo"),
        BotCommand(command="ip",     description="Get IP information"),
        BotCommand(command="px",     description="Check proxies"),
        BotCommand(command="mail",   description="Generate temp email"),
        BotCommand(command="qr",     description="Generate QR code"),
        BotCommand(command="short",  description="Shorten URL"),
        BotCommand(command="fake",   description="Generate random address"),
        BotCommand(command="q",      description="Create quote sticker"),
        BotCommand(command="login",  description="Admin login"),
        BotCommand(command="on",     description="Enable bot (admin)"),
        BotCommand(command="off",    description="Disable bot (admin)"),
    ]
    await bot.set_my_commands(commands)


# ── entry point ────────────────────────────────────────────────────────────────
async def main():
    await set_bot_commands()
    await bot.delete_webhook(drop_pending_updates=True)

    use_webhook = os.getenv("USE_WEBHOOK", "false").lower() == "true"
    if use_webhook:
        domain = os.getenv("DOMAIN", "")
        await bot.set_webhook(f"[{domain}](https://{domain}/webhook)")
        print(f"Webhook set to [{domain}](https://{domain}/webhook)")
    else:
        print("Starting polling…")
        await dp.start_polling(bot)


if __name__ == "__main__":
    flask_thread = Thread(
        target=lambda: app.run(host="0.0.0.0", port=PORT, use_reloader=False),
        daemon=True
    )
    flask_thread.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
