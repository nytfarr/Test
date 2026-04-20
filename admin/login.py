from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_ID, ADMIN_USERNAME, ADMIN_PASSWORD

router = Router()
admin_sessions = {}

@router.message(Command("login"))
async def cmd_login(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if message.chat.type == "private":
        await message.answer("Enter Admin Username:")
        admin_sessions[message.from_user.id] = {"step": "username"}
    else:
        await message.answer("Login only available in private chat.")

@router.message(F.chat.type == "private")
async def handle_login_input(message: Message):
    uid = message.from_user.id
    if uid not in admin_sessions:
        return
    step = admin_sessions[uid].get("step")
    if step == "username":
        if message.text == ADMIN_USERNAME:
            admin_sessions[uid]["step"] = "password"
            await message.answer("Enter Admin Password:")
        else:
            await message.answer("Invalid username. Try again.")
    elif step == "password":
        if message.text == ADMIN_PASSWORD:
            admin_sessions[uid]["logged_in"] = True
            kb = InlineKeyboardBuilder()
            kb.row(InlineKeyboardButton(text="Manage Users", callback_data="adm_users"))
            kb.row(InlineKeyboardButton(text="Manage Groups", callback_data="adm_groups"))
            kb.row(InlineKeyboardButton(text="Broadcast", callback_data="adm_bc"))
            kb.row(InlineKeyboardButton(text="Settings", callback_data="adm_settings"))
            await message.answer("✅ Admin Login Successful!", reply_markup=kb.as_markup())
            del admin_sessions[uid]
        else:
            await message.answer("Invalid password.")
            del admin_sessions[uid]
