import asyncio
import signal
from flask import Flask, request
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_PATH
from utils.handler import router as handler_router
from utils.ai import router as ai_router
from admin.login import router as login_router
from admin.dashboard import router as dashboard_router
from admin.commands import router as admin_router
from utils.json_io import backup_all_jsons

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(handler_router)
dp.include_router(ai_router)
dp.include_router(login_router)
dp.include_router(dashboard_router)
dp.include_router(admin_router)

@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    update = await dp.feed_webhook_update(bot, request.json)
    return web.json_response({"status": "ok"})

async def on_shutdown():
    await backup_all_jsons(bot)
    await bot.session.close()

async def main():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(on_shutdown()))
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())