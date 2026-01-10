import logging
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== SOZLAMALAR ====================
TOKEN = "8332172370:AAHpj0H_6sss-bMoGizp1ulUFQkmkEdC_PA"
SUPER_ADMIN_ID = 7740552653
PHONE = "+998931317231"
API_ID = 36799342
API_HASH = "fcdf748b56fb519c6900d02e25ae2d62"
SESSION_STRING = "1ApWapzMBu7tofZMURMSzo89mVMr9xLotyNvtPCmERdQUHiz6JYT-4lRg2Q9BIXhZ4vQKg91VtU5AuCcz6mA7Okorwah803VPKW9G_uJ2T6wbhW3_UARwiT0xQO-NmNzhYV3Y65AeH4qAhYPEZ8ytw7FbrEO0r9h4cVB7z2gfUsS6bd7a8xuwNpt5Glwb3VOB-RXFMd1Mhv5EF3pV-rnejmRPGr27VhZml9ATMiCwUJwd4OqAA5ygn-fs8C6HH_UriS6K2T5ASR6ACLXSU8WeGCjBloyJM632L0coc1ik4ZduUxmnX3tQGRo8MCu26-QfwKG6Uqi2_lI6rHcTQYjE-G-DDC3qHcs="
DB_PATH = "bot_data.db"

userbot_client = None
bot_app = None

# ==================== DATABASE ====================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, username TEXT, added_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS keywords (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER NOT NULL, keyword TEXT NOT NULL, created_date TEXT, FOREIGN KEY(admin_id) REFERENCES admins(user_id) ON DELETE CASCADE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS private_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER UNIQUE NOT NULL, group_id INTEGER NOT NULL, added_date TEXT, FOREIGN KEY(admin_id) REFERENCES admins(user_id) ON DELETE CASCADE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS search_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER NOT NULL, group_id INTEGER NOT NULL, group_name TEXT, added_date TEXT, FOREIGN KEY(admin_id) REFERENCES admins(user_id) ON DELETE CASCADE)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_keywords_admin ON keywords(admin_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_search_groups_admin ON search_groups(admin_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_search_groups_group ON search_groups(group_id)')
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

def is_super_admin(user_id):
    return user_id == SUPER_ADMIN_ID

def is_admin(user_id):
    if is_super_admin(user_id):
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def add_admin(user_id, username):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO admins (user_id, username, added_date) VALUES (?, ?, ?)", (user_id, username, datetime.now().isoformat()))
        conn.commit()
        success = c.rowcount > 0
    except Exception as e:
        logger.error(f"Admin qo'shishda xato: {e}")
        success = False
    conn.close()
    return success

def remove_admin(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM keywords WHERE admin_id = ?", (user_id,))
    c.execute("DELETE FROM private_groups WHERE admin_id = ?", (user_id,))
    c.execute("DELETE FROM search_groups WHERE admin_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

def get_all_admins():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username FROM admins")
    admins = [(r['user_id'], r['username']) for r in c.fetchall()]
    conn.close()
    return admins

def add_keyword(admin_id, keyword):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO keywords (admin_id, keyword, created_date) VALUES (?, ?, ?)", (admin_id, keyword, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_keywords(admin_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, keyword FROM keywords WHERE admin_id = ?", (admin_id,))
    keywords = [(r['id'], r['keyword']) for r in c.fetchall()]
    conn.close()
    return keywords

def remove_keyword(keyword_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
    conn.commit()
    conn.close()
    return True

def add_private_group(admin_id, group_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO private_groups (admin_id, group_id, added_date) VALUES (?, ?, ?)", (admin_id, group_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_private_group(admin_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT group_id FROM private_groups WHERE admin_id = ?", (admin_id,))
    result = c.fetchone()
    conn.close()
    return result['group_id'] if result else None

def remove_private_group(admin_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM private_groups WHERE admin_id = ?", (admin_id,))
    conn.commit()
    conn.close()
    return True

def add_search_group(admin_id, group_id, group_name):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS cnt FROM search_groups WHERE admin_id = ?", (admin_id,))
    count = c.fetchone()['cnt']
    if count >= 100:
        conn.close()
        return False
    c.execute("INSERT INTO search_groups (admin_id, group_id, group_name, added_date) VALUES (?, ?, ?, ?)", (admin_id, group_id, group_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_search_groups(admin_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, group_id, group_name FROM search_groups WHERE admin_id = ?", (admin_id,))
    groups = [(r['id'], r['group_id'], r['group_name']) for r in c.fetchall()]
    conn.close()
    return groups

def remove_search_group(row_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM search_groups WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
    return True

def check_keywords_in_message(group_id, message_text):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT DISTINCT k.admin_id, k.keyword, pg.group_id AS private_group_id FROM keywords k JOIN search_groups sg ON k.admin_id = sg.admin_id JOIN private_groups pg ON k.admin_id = pg.admin_id WHERE sg.group_id = ?""", (group_id,))
    results = c.fetchall()
    conn.close()
    matches = []
    msg_lower = (message_text or "").lower()
    for r in results:
        if (r['keyword'] or "").lower() in msg_lower:
            matches.append({'admin_id': r['admin_id'], 'keyword': r['keyword'], 'private_group_id': r['private_group_id']})
    return matches

def super_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Yangi admin qo'shish", callback_data='add_admin')],
        [InlineKeyboardButton("📋 Adminlar ro'yxati", callback_data='list_admins')],
        [InlineKeyboardButton("🗑 Admin o'chirish", callback_data='remove_admin')],
        [InlineKeyboardButton("🚪 Admin xonasiga o'tish", callback_data='enter_admin_room')]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kalit so'z", callback_data='add_keyword'), InlineKeyboardButton("📋 Ko'rish", callback_data='view_keywords')],
        [InlineKeyboardButton("🗑 So'z o'chirish", callback_data='delete_keyword')],
        [InlineKeyboardButton("➕ Shaxsiy guruh", callback_data='add_private_group')],
        [InlineKeyboardButton("👁 Ko'rish", callback_data='view_private_group'), InlineKeyboardButton("🗑 O'chirish", callback_data='delete_private_group')],
        [InlineKeyboardButton("➕ Izlovchi guruh", callback_data='add_search_group')],
        [InlineKeyboardButton("📋 Ko'rish", callback_data='view_search_groups'), InlineKeyboardButton("🗑 O'chirish", callback_data='delete_search_group')]
    ])

def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Ortga", callback_data='back_to_main')]])

# ==================== USERBOT ====================
async def init_userbot():
    global userbot_client
    try:
        userbot_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await userbot_client.start(phone=PHONE)
        logger.info("✅ Userbot ishga tushdi")
        
        @userbot_client.on(events.NewMessage())
        async def userbot_message_handler(event):
            try:
                if not event.message or not event.message.text:
                    return
                chat = await event.get_chat()
                if not getattr(chat, 'megagroup', False):
                    return
                group_id = event.chat_id
                msg_text = event.message.text
                sender = await event.get_sender()
                user_id = sender.id
                username = sender.username or getattr(sender, 'first_name', None) or "Unknown"
                group_name = getattr(chat, 'title', 'Unknown group')
                matches = check_keywords_in_message(group_id, msg_text)
                for match in matches:
                    try:
                        await bot_app.bot.send_message(
                            chat_id=match['private_group_id'],
                            text=f"🔍 Kalit so'z topildi! (Userbot)\n\n📢 Guruh: {group_name}\n👤 Foydalanuvchi: {username}\n🆔 User ID: {user_id}\n🔑 Kalit so'z: {match['keyword']}\n\n💬 Xabar:\n{msg_text}",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👤 Profil", url=f"tg://user?id={user_id}")]])
                        )
                    except Exception as e:
                        logger.error(f"Userbot xabar yuborishda xato: {e}")
            except Exception as e:
                logger.error(f"Userbot handler xatosi: {e}")
    except Exception as e:
        logger.error(f"Userbot ishga tushirishda xato: {e}")

# ==================== BOT HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    if is_super_admin(user_id):
        await update.message.reply_text(
            "🔐 Assalomu alaykum, Super Admin!\n\nMenyudan kerakli bo'limni tanlang:",
            reply_markup=super_admin_keyboard()
        )
    elif is_admin(user_id):
        await update.message.reply_text(
            f"👋 Assalomu alaykum, {username}!\n\n🏠 Shaxsiy xonangizga xush kelibsiz:",
            reply_markup=admin_keyboard()
        )
    else:
        keyboard = [[InlineKeyboardButton("👤 Adminga bog'lanish", url=f"tg://user?id={SUPER_ADMIN_ID}")]]
        await update.message.reply_text(
            f"👋 Assalomu alaykum, {username}!\n\n⚠️ Botdan faqat adminlar foydalana oladi!\nBotdan foydalanish uchun adminga murojaat qiling!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"📊 Bu guruh ID: {chat_id}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == 'add_admin' and is_super_admin(user_id):
        context.user_data['waiting'] = 'admin_id'
        await query.edit_message_text("📝 Yangi admin ID raqamini yuboring:", reply_markup=back_button())
    
    elif data == 'list_admins' and is_super_admin(user_id):
        admins = get_all_admins()
        if admins:
            keyboard = [[InlineKeyboardButton(f"👤 {u} (ID: {i})", url=f"tg://user?id={i}")] for i, u in admins]
            keyboard.append([InlineKeyboardButton("⬅️ Ortga", callback_data='back_to_main')])
            await query.edit_message_text(f"📋 Adminlar ro'yxati ({len(admins)} ta):", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("ℹ️ Adminlar yo'q.", reply_markup=back_button())
    
    elif data == 'remove_admin' and is_super_admin(user_id):
        admins = get_all_admins()
        if admins:
            keyboard = [[InlineKeyboardButton(f"🗑 {u}", callback_data=f'rmadm_{i}')] for i, u in admins]
            keyboard.append([InlineKeyboardButton("⬅️ Ortga", callback_data='back_to_main')])
            await query.edit_message_text("🗑 O'chirish uchun adminni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("ℹ️ Adminlar yo'q.", reply_markup=back_button())
    
    elif data.startswith('rmadm_') and is_super_admin(user_id):
        admin_id = int(data.split('_')[1])
        remove_admin(admin_id)
        await query.edit_message_text("✅ Admin o'chirildi!", reply_markup=back_button())
    
    elif data == 'enter_admin_room' and is_super_admin(user_id):
        admins = get_all_admins()
        if admins:
            keyboard = [[InlineKeyboardButton(f"🚪 {u}", callback_data=f'enter_{i}')] for i, u in admins]
            keyboard.append([InlineKeyboardButton("⬅️ Ortga", callback_data='back_to_main')])
            await query.edit_message_text("🚪 Adminni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("ℹ️ Adminlar yo'q.", reply_markup=back_button())
    
    elif data.startswith('enter_') and is_super_admin(user_id):
        admin_id = int(data.split('_')[1])
        context.user_data['viewing_admin'] = admin_id
        await query.edit_message_text(f"🏠 Admin xonasi (ID: {admin_id}):", reply_markup=admin_keyboard())
    
    elif data == 'add_keyword':
        context.user_data['waiting'] = 'keyword'
        await query.edit_message_text("📝 Kalit so'zni kiriting:", reply_markup=back_button())
    
    elif data == 'view_keywords':
        admin_id = context.user_data.get('viewing_admin', user_id)
        kws = get_keywords(admin_id)
        if kws:
            text = "📋 Kalit so'zlar:\n\n" + "\n".join([f"{i}. {k}" for i, (_, k) in enumerate(kws, 1)]) + f"\n\n💾 Jami: {len(kws)} ta"
            await query.edit_message_text(text, reply_markup=back_button())
        else:
            await query.edit_message_text("ℹ️ Kalit so'zlar yo'q.", reply_markup=back_button())
    
    elif data == 'delete_keyword':
        admin_id = context.user_data.get('viewing_admin', user_id)
        kws = get_keywords(admin_id)
        if kws:
            keyboard = [[InlineKeyboardButton(f"🗑 {k}", callback_data=f'delkw_{i}')] for i, k in kws]
            keyboard.append([InlineKeyboardButton("⬅️ Ortga", callback_data='back_to_main')])
            await query.edit_message_text("🗑 O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("ℹ️ Kalit so'zlar yo'q.", reply_markup=back_button())
    
    elif data.startswith('delkw_'):
        kid = int(data.split('_')[1])
        remove_keyword(kid)
        await query.edit_message_text("✅ Kalit so'z o'chirildi!", reply_markup=back_button())
    
    elif data == 'add_private_group':
        context.user_data['waiting'] = 'private_group'
        await query.edit_message_text("📝 Shaxsiy guruh ID ni yuboring:\n\n💡 ID olish:\n1. Botni guruhga admin qiling\n2. Guruhda /id yuboring\n3. ID ni bu yerga yuboring", reply_markup=back_button())
    
    elif data == 'view_private_group':
        admin_id = context.user_data.get('viewing_admin', user_id)
        gid = get_private_group(admin_id)
        if gid:
            await query.edit_message_text(f"📢 Shaxsiy guruh ID: {gid}", reply_markup=back_button())
        else:
            await query.edit_message_text("ℹ️ Shaxsiy guruh yo'q.", reply_markup=back_button())
    
    elif data == 'delete_private_group':
        admin_id = context.user_data.get('viewing_admin', user_id)
        remove_private_group(admin_id)
        await query.edit_message_text("✅ Shaxsiy guruh o'chirildi!", reply_markup=back_button())
    
    elif data == 'add_search_group':
        admin_id = context.user_data.get('viewing_admin', user_id)
        grps = get_search_groups(admin_id)
        context.user_data['waiting'] = 'search_group'
        await query.edit_message_text(f"📝 Izlovchi guruh ID ni yuboring:\n\n📊 Hozirda: {len(grps)}/100 ta\n\n💡 ID olish:\n1. Botni guruhga admin qiling\n2. Guruhda /id yuboring\n3. ID ni bu yerga yuboring", reply_markup=back_button())
    
    elif data == 'view_search_groups':
        admin_id = context.user_data.get('viewing_admin', user_id)
        grps = get_search_groups(admin_id)
        if grps:
            text = "📋 Izlovchi guruhlar:\n\n"
            for i, (_, gid, gname) in enumerate(grps, 1):
                text += f"{i}. {gname}\n   ID: {gid}\n\n"
            text += f"💾 Jami: {len(grps)}/100 ta"
            await query.edit_message_text(text, reply_markup=back_button())
        else:
            await query.edit_message_text("ℹ️ Izlovchi guruhlar yo'q.", reply_markup=back_button())
    
    elif data == 'delete_search_group':
        admin_id = context.user_data.get('viewing_admin', user_id)
        grps = get_search_groups(admin_id)
        if grps:
            keyboard = [[InlineKeyboardButton(f"🗑 {n}", callback_data=f'delgrp_{i}')] for i, _, n in grps]
            keyboard.append([InlineKeyboardButton("⬅️ Ortga", callback_data='back_to_main')])
            await query.edit_message_text("🗑 O'chirish uchun tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("ℹ️ Izlovchi guruhlar yo'q.", reply_markup=back_button())
    
    elif data.startswith('delgrp_'):
        gid_row = int(data.split('_')[1])
        remove_search_group(gid_row)
        await query.edit_message_text("✅ Izlovchi guruh o'chirildi!", reply_markup=back_button())
    
    elif data == 'back_to_main':
        context.user_data.pop('waiting', None)
        if is_super_admin(user_id):
            context.user_data.pop('viewing_admin', None)
            await query.edit_message_text("🔐 Super Admin menyusi:", reply_markup=super_admin_keyboard())
        elif is_admin(user_id):
            await query.edit_message_text("🏠 Admin menyusi:", reply_markup=admin_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not is_admin(user_id):
        return
    waiting = context.user_data.get('waiting')
    
    if waiting == 'admin_id' and is_super_admin(user_id):
        try:
            new_id = int(text)
            try:
                chat = await context.bot.get_chat(new_id)
                uname = chat.username or chat.first_name or f"User_{new_id}"
            except Exception:
                uname = f"User_{new_id}"
            if add_admin(new_id, uname):
                await update.message.reply_text(f"✅ Admin qo'shildi!\n\n👤 {uname}\n🆔 {new_id}", reply_markup=back_button())
            else:
                await update.message.reply_text("ℹ️ Bu admin mavjud!", reply_markup=back_button())
        except Exception:
            await update.message.reply_text("❌ Noto'g'ri ID!", reply_markup=back_button())
        context.user_data.pop('waiting', None)
    
    elif waiting == 'keyword':
        admin_id = context.user_data.get('viewing_admin', user_id)
        add_keyword(admin_id, text)
        await update.message.reply_text(f"✅ Kalit so'z qo'shildi: {text}", reply_markup=back_button())
        context.user_data.pop('waiting', None)
    
    elif waiting == 'private_group':
        try:
            gid = int(text)
            admin_id = context.user_data.get('viewing_admin', user_id)
            add_private_group(admin_id, gid)
            await update.message.reply_text(f"✅ Shaxsiy guruh qo'shildi: {gid}", reply_markup=back_button())
        except Exception:
            await update.message.reply_text("❌ Noto'g'ri ID!", reply_markup=back_button())
        context.user_data.pop('waiting', None)
    
    elif waiting == 'search_group':
        try:
            gid = int(text)
            admin_id = context.user_data.get('viewing_admin', user_id)
            try:
                chat = await context.bot.get_chat(gid)
                gname = chat.title or f"Guruh {gid}"
            except Exception:
                gname = f"Guruh {gid}"
            if add_search_group(admin_id, gid, gname):
                await update.message.reply_text(f"✅ Izlovchi guruh qo'shildi: {gname}", reply_markup=back_button())
            else:
                await update.message.reply_text("❌ Maksimal 100 ta guruh!", reply_markup=back_button())
        except Exception:
            await update.message.reply_text("❌ Noto'g'ri ID!", reply_markup=back_button())
        context.user_data.pop('waiting', None)

async def check_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.message.chat.type not in ['group', 'supergroup']:
        return
    msg_text = update.message.text
    group_id = update.message.chat.id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    group_name = update.message.chat.title
    matches = check_keywords_in_message(group_id, msg_text)
    for match in matches:
        try:
            keyboard = [[InlineKeyboardButton("👤 Profil", url=f"tg://user?id={user_id}")]]
            await context.bot.send_message(
                chat_id=match['private_group_id'],
                text=f"🔍 Kalit so'z topildi! (Bot)\n\n📢 Guruh: {group_name}\n👤 Foydalanuvchi: {username}\n🔑 Kalit so'z: {match['keyword']}\n\n💬 Xabar:\n{msg_text}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Xabar yuborishda xato: {e}")

# ==================== MAIN ====================
async def main():
    global bot_app
    
    init_db()
    
    bot_app = Application.builder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("id", get_chat_id))
    bot_app.add_handler(CallbackQueryHandler(button_callback))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text))
    bot_app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, check_group_message))
    
    logger.info("🚀 Bot ishga tushmoqda...")
    
    await init_userbot()
    
    logger.info("✅ Bot va Userbot ishga tayyor!")
    
    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        if userbot_client:
            await userbot_client.run_until_disconnected()
        else:
            await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
