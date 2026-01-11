import logging
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
SESSION_STRING = "1ApWapzMBu7tofZMURMSzo89mVMr9xLotyNvtPCmERdQUHiz6JYT"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    logger.info("✅ Userbot ishlayapti")
    logger.info(f"👤 Foydalanuvchi: {me.first_name} | @{me.username} | ID: {me.id}")

    @client.on(events.NewMessage())
    async def handler(event):
        chat = await event.get_chat()
        if getattr(chat, 'title', None):
            logger.info(f"📢 Guruh: {chat.title} | Xabar: {event.raw_text}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
