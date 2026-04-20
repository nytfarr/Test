from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.json_io import read_json, USERS_PATH, GROUPS_PATH

router = Router()
PAGE_SIZE = 15

@router.callback_query(F.data.startswith("adm_"))
async def cb_admin_panel(call: CallbackQuery):
    action = call.data.split("_")[1]
    page = int(call.data.split("_")[-1]) if call.data.endswith("_") else 0
    kb = InlineKeyboardBuilder()
    if action == "users":
        users = read_json(USERS_PATH)
        items = list(users.items())
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = items[start:end]
        for uid, u in page_items:
            kb.row(InlineKeyboardButton(text=f"{u['name']} ({uid})", callback_data=f"adm_user_view_{uid}"))
        nav = []
        if page > 0: nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"adm_users_{page-1}"))
        if end < len(items): nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"adm_users_{page+1}"))
        kb.row(*nav)
    elif action == "groups":
        groups = read_json(GROUPS_PATH)
        items = list(groups.items())
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = items[start:end]
        for gid, g in page_items:
            kb.row(InlineKeyboardButton(text=f"{g['name']} ({gid})", callback_data=f"adm_group_view_{gid}"))
        nav = []
        if page > 0: nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"adm_groups_{page-1}"))
        if end < len(items): nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"adm_groups_{page+1}"))
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="🔙 Back", callback_data="start"))
    await call.message.edit_text(f"Admin Panel - {action.upper()}", reply_markup=kb.as_markup())