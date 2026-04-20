import json
import os
import asyncio
from threading import Lock
from config import USERS_PATH, GROUPS_PATH, CHAT_HISTORY_PATH, API_PATH

json_lock = Lock()

def read_json(path):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)
        return {}
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_json(path, data):
    with json_lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

def get_next_api():
    apis = read_json(API_PATH)
    if not apis:
        return None
    first = apis.pop(0)
    apis.append(first)
    save_json(API_PATH, apis)
    return first

def track_user(chat_id, username, first_name):
    users = read_json(USERS_PATH)
    if str(chat_id) not in users:
        from datetime import datetime
        users[str(chat_id)] = {
            "username": username or "",
            "name": first_name or "User",
            "join_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "starts": 1,
            "last_active": datetime.utcnow().isoformat()
        }
        save_json(USERS_PATH, users)
    else:
        from datetime import datetime
        users[str(chat_id)]["starts"] = users[str(chat_id)].get("starts", 0) + 1
        users[str(chat_id)]["last_active"] = datetime.utcnow().isoformat()
        save_json(USERS_PATH, users)

def track_group(chat_id, username, title):
    groups = read_json(GROUPS_PATH)
    if str(chat_id) not in groups:
        from datetime import datetime
        groups[str(chat_id)] = {
            "username": username or "",
            "name": title or "Group",
            "join_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_json(GROUPS_PATH, groups)

def get_stats():
    users = read_json(USERS_PATH)
    groups = read_json(GROUPS_PATH)
    total_users = len(users)
    total_groups = len(groups)
    today_starts = sum(1 for u in users.values() if u.get("last_active", "").startswith(__import__('datetime').datetime.utcnow().strftime("%Y-%m-%d")))
    return {
        "daily_starts": today_starts,
        "weekly_starts": 0,
        "monthly_starts": 0,
        "annual_starts": 0,
        "total_groups": total_groups,
        "users_registered": total_users
    }

def get_chat_history(chat_id):
    data = read_json(CHAT_HISTORY_PATH)
    return data.get(str(chat_id), [])

def save_chat_history(chat_id, history):
    data = read_json(CHAT_HISTORY_PATH)
    data[str(chat_id)] = history[-20:]
    save_json(CHAT_HISTORY_PATH, data)

async def backup_all_jsons(bot):
    from config import ADMIN_ID
    for path in [USERS_PATH, GROUPS_PATH, CHAT_HISTORY_PATH, API_PATH]:
        if os.path.exists(path):
            await bot.send_document(ADMIN_ID, document=path)