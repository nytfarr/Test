from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from config import ADMIN_ID
from utils.json_io import read_json, save_json, USERS_PATH, GROUPS_PATH, backup_all_jsons
import os

router = Router()
bot_states = {"paused": set()}

@router.message(Command("off"))
async def cmd_off(message: Message):
    if message.from_user.id != ADMIN_ID: return
    bot_states["paused"].add(message.chat.id)
    await message.answer("Bot responses paused for this chat.")

@router.message(Command("on"))
async def cmd_on(message: Message):
    if message.from_user.id != ADMIN_ID: return
    bot_states["paused"].discard(message.chat.id)
    await message.answer("Bot responses enabled.")

@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id != ADMIN_ID: return
    target = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else None
    if not target: return
    users = read_json(USERS_PATH)
    users[str(target)] = users.get(str(target), {})
    users[str(target)]["banned"] = True
    save_json(USERS_PATH, users)
    await message.answer(f"{target} banned.")

@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.from_user.id != ADMIN_ID: return
    target = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else None
    if not target: return
    users = read_json(USERS_PATH)
    if str(target) in users and users[str(target)].get("banned"):
        del users[str(target)]["banned"]
        save_json(USERS_PATH, users)
        await message.answer(f"{target} unbanned.")

@router.message(Command("data"))
async def cmd_data(message: Message):
    if message.from_user.id != ADMIN_ID: return
    for f in [USERS_PATH, GROUPS_PATH, "chat_history.json", "allapi.json"]:
        if os.path.exists(f):
            await message.answer_document(f)

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    if message.from_user.id != ADMIN_ID: return
    save_json(USERS_PATH, {})
    save_json(GROUPS_PATH, {})
    await message.answer("All JSON data cleared.")

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Use /status in menu for live stats.")