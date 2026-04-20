from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import requests
from utils.json_io import get_next_api, get_chat_history, save_chat_history

router = Router()

async def fetch_ai_response(prompt, history, model):
    api = get_next_api()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api}",
        "User-Agent": "BabuUtilsBot/1.0"
    }
    messages = history + [{"role": "user", "content": prompt}]
    payload = {"model": model, "messages": messages, "max_tokens": 1024}
    res = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=30)
    if res.status_code == 200:
        reply = res.json()["choices"][0]["message"]["content"]
        return reply
    return "API Error: Please try again later."

@router.message(Command("gpt"))
async def cmd_gpt(message: Message):
    prompt = message.text.split(" ", 1)[1] if len(message.text.split(" ")) > 1 else message.reply_to_message.text if message.reply_to_message else None
    if not prompt:
        await message.answer("Please provide a prompt.")
        return
    hist = get_chat_history(message.chat.id)
    reply = await fetch_ai_response(prompt, hist, "gpt-4")
    new_hist = hist + [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}]
    save_chat_history(message.chat.id, new_hist)
    await message.answer(reply)

@router.message(F.text.lower().startswith("babu "))
async def cmd_babu_trigger(message: Message):
    prompt = message.text[5:].strip()
    if not prompt:
        return
    hist = get_chat_history(message.chat.id)
    reply = await fetch_ai_response(prompt, hist, "gpt-4")
    new_hist = hist + [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}]
    save_chat_history(message.chat.id, new_hist)
    await message.answer(reply)

@router.message(Command("gem", "cl", "per", "gk"))
async def cmd_alt_ai(message: Message):
    await message.answer("AI module integrated. Add your specific API endpoints in utils/ai.py for these models.")
