import os
import logging
import sqlite3
import asyncio
import html
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from telegram.error import Forbidden, BadRequest

# --- 1. الإعدادات (CONFIG) ---
TOKEN = "8570263566:AAFspvrukYqTQ498U5FbhEVaUgYCmcv4pxE"  # ⚠️ توكن البوت
ADMIN_ID = 7818816235            # ⚠️ الآيدي الخاص بك
DB_NAME = "bot_ultimate_v7.db"   

if not TOKEN:
    raise ValueError("Bot token is missing!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- States (حالات المحادثة) ---
(
    MAIN_MENU, 
    AWAIT_MSG_TARGET, AWAIT_MSG_CONTENT,   # Direct Message
    AWAIT_WHISPER_CONTENT,                 # 🆕 Whisper Message (Deep Link)
    SETTINGS_BLOCK_INPUT,                  # Manual Block
    SETTINGS_REPORT_INPUT, SETTINGS_REPORT_REASON, # Manual Report
    ADMIN_PANEL, ADMIN_ADD_CHANNEL, ADMIN_ADD_ADMIN, ADMIN_BROADCAST, ADMIN_WARN_USER 
) = range(12)

# --- القاموس (اللغات) ---
TRANS = {
    'ar': {
        'welcome': "👋 **أهلاً بك في بوت تواصل لولوش!**\n\nاختر ما تريد:",
        'send_msg': "📩 إرسال رسالة",
        'get_link': "همسه",
        'donate_btn': "💎 دعم البوت ",
        'settings': "⚙️ الإعدادات",
        'admin_panel': "🔐 لوحة الأدمن",
        'banned': "🚫 **أنت محظور من استخدام هذا البوت.**",
        'must_join': "⚠️ **عذراً، يجب الاشتراك في القنوات التالية:**",
        'joined_btn': "✅ تم الاشتراك (تحقق)",
        'lang_btn': "🇺🇸 English",
        'block_user': "🚫 حظر مستخدم (يدوي)",
        'report_user': "🚨 إبلاغ عن مستخدم",
        'back': "رجوع",
        'user_not_found': "❌ المستخدم غير موجود في البوت.",
        'blocked_success': "✅ تم حظر المستخدم بنجاح.",
        'report_sent': "✅ تم إرسال البلاغ للإدارة.",
        'settings_title': "⚙️ **الإعدادات:**",
        'vis_show': "الوضع: 👁️ ظاهر (الاسم واليوزر)",
        'vis_hide': "الوضع: 👻 مخفي (مجهول)",
        'toggle_vis': "تغيير الحالة 🔄",
        'my_blocks': "🚫 قائمة المحظورين",
        'ask_target': "👤 **لمن تريد إرسال الرسالة؟**\nأرسل اليوزر أو الآيدي.",
        'cancel': "إلغاء ❌",
        'write_msg': "📝 **أرسل رسالتك الآن (نص، صور، فيديو، ملفات...):**",
        'sent_ok': "✅ **تم الإرسال بنجاح!**",
        'target_blocked': "🚫 عذراً، هذا المستخدم قام بحظرك.",
        'cant_self': "🤔 لا يمكنك مراسلة نفسك.",
        'my_link_msg': "🔗 **هذا هو رابطك الخاص:**\n\n`{link}`\n\nانشره ليستطيع الناس مراسلتك دون معرفة هويتهم!",
        'whisper_start': "👋 **مرحباً!**\nأنت الآن تقوم بمراسلة: **{name}**\n\n📝 أرسل رسالتك الآن (نص، فيديو، صوت...) وستصله فوراً.",
        'donate_title': "💎 **قائمة التبرع ودعم البوت:**\nاختر عدد النجوم التي تريد التبرع بها:",
        'donate_thanks': "🙏 شكراً لك! دعمك يساعدنا على الاستمرار."
    },
    'en': {
        'welcome': "👋 **Welcome to Lelouch Bot!**\n\nChoose an option:",
        'send_msg': "📩 Send Msg",
        'get_link': "Whisper",
        'donate_btn': "💎 Donate ",
        'settings': "⚙️ Settings",
        'admin_panel': "🔐 Admin Panel",
        'banned': "🚫 **You are banned.**",
        'must_join': "⚠️ **You must join these channels first:**",
        'joined_btn': "✅ I Joined",
        'lang_btn': "🇸🇦 العربية",
        'block_user': "🚫 Block User",
        'report_user': "🚨 Report User",
        'back': "Back",
        'user_not_found': "❌ User not found.",
        'blocked_success': "✅ User blocked.",
        'report_sent': "✅ Report sent.",
        'settings_title': "⚙️ **Settings:**",
        'vis_show': "Status: 👁️ Visible",
        'vis_hide': "Status: 👻 Hidden",
        'toggle_vis': "Toggle Visibility 🔄",
        'my_blocks': "🚫 Blocked Users",
        'ask_target': "👤 **Send Username or ID:**",
        'cancel': "Cancel ❌",
        'write_msg': "📝 **Send your message now:**",
        'sent_ok': "✅ **Sent successfully!**",
        'target_blocked': "🚫 User blocked you.",
        'cant_self': "🤔 Cannot message yourself.",
        'my_link_msg': "🔗 **Here is your link:**\n\n`{link}`\n\nShare it to receive anonymous messages!",
        'whisper_start': "👋 **Hello!**\nYou are messaging: **{name}**\n\n📝 Send your message now (Text, Media...)",
        'donate_title': "💎 **Donation Menu:**\nChoose how many stars to donate:",
        'donate_thanks': "🙏 Thank you for your support!"
    }
}

# --- 2. قاعدة البيانات (DATABASE) ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  is_banned INTEGER DEFAULT 0, is_show_id INTEGER DEFAULT 1, language TEXT DEFAULT 'ar')''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ar'")
    except: pass

    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, username TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (channel_id INTEGER, channel_link TEXT, channel_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS blocks (blocker_id INTEGER, blocked_id INTEGER, PRIMARY KEY(blocker_id, blocked_id))''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- 3. دوال مساعدة (HELPERS) ---

def is_admin(user_id):
    if user_id == ADMIN_ID: return True
    conn = get_db()
    res = conn.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return bool(res)

def get_lang(user_id):
    conn = get_db()
    res = conn.execute("SELECT language FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return res['language'] if res else 'ar'

def t(user_id, key):
    lang = get_lang(user_id)
    return TRANS.get(lang, TRANS['ar']).get(key, key)

async def check_subscription(user_id, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(user_id): return []
    conn = get_db()
    channels = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    not_joined = []
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=ch['channel_id'], user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_joined.append(ch)
        except Exception: pass 
    return not_joined

# --- 4. البداية والقائمة الرئيسية (START & MENU) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    
    # تسجيل المستخدم
    exist = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user.id,)).fetchone()
    if not exist:
        conn.execute("INSERT INTO users (user_id, username, language) VALUES (?, ?, 'ar')", (user.id, user.username))
        conn.commit()
        try:
            await context.bot.send_message(ADMIN_ID, f"🔔 مستخدم جديد:\n👤 {user.first_name} (@{user.username})\n🆔 {user.id}")
        except: pass
    else:
        conn.execute("UPDATE users SET username=? WHERE user_id=?", (user.username, user.id))
        conn.commit()
    
    # 🆕 التحقق من الرابط الخاص (Deep Linking)
    args = context.args
    if args and len(args) > 0:
        target_payload = args[0]
        if target_payload.isdigit() and int(target_payload) != user.id:
            target_id = int(target_payload)
            target_user = conn.execute("SELECT username FROM users WHERE user_id=?", (target_id,)).fetchone()
            
            # التحقق من الحظر
            blocked = conn.execute("SELECT 1 FROM blocks WHERE blocker_id=? AND blocked_id=?", (target_id, user.id)).fetchone()
            conn.close()

            if blocked:
                await update.message.reply_text(t(user.id, 'target_blocked'))
                return ConversationHandler.END
            
            if target_user:
                # حفظ الهدف وتغيير الحالة لإرسال الرسالة
                context.user_data['msg_target_id'] = target_id
                target_name = target_user['username'] or str(target_id)
                
                await update.message.reply_text(
                    t(user.id, 'whisper_start').format(name=target_name),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user.id, 'cancel'), callback_data='cancel_to_main')]])
                )
                return AWAIT_WHISPER_CONTENT # حالة جديدة خاصة بالرابط
            else:
                await update.message.reply_text(t(user.id, 'user_not_found'))
                return await main_menu_display(update, context)

    conn.close()
    return await main_menu_display(update, context)

async def main_menu_display(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    u_data = conn.execute("SELECT is_banned FROM users WHERE user_id=?", (user.id,)).fetchone()
    conn.close()
    
    if u_data and u_data['is_banned']:
        if update.callback_query: await update.callback_query.answer()
        await context.bot.send_message(user.id, t(user.id, 'banned'))
        return ConversationHandler.END

    not_joined = await check_subscription(user.id, context)
    if not_joined:
        buttons = []
        for ch in not_joined:
            buttons.append([InlineKeyboardButton(f"{ch['channel_name']}", url=ch['channel_link'])])
        buttons.append([InlineKeyboardButton(t(user.id, 'joined_btn'), callback_data='check_subs')])
        text = t(user.id, 'must_join')
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return MAIN_MENU

    text = t(user.id, 'welcome')
    btns = [
        [InlineKeyboardButton(t(user.id, 'get_link'), callback_data='get_my_link')],  # 🆕 زر الرابط
        [InlineKeyboardButton(t(user.id, 'send_msg'), callback_data='btn_send'),
         InlineKeyboardButton(t(user.id, 'donate_btn'), callback_data='btn_donate')], # 🆕 زر التبرع
        [InlineKeyboardButton(t(user.id, 'settings'), callback_data='btn_settings')]
    ]
    if is_admin(user.id):
        btns.append([InlineKeyboardButton(t(user.id, 'admin_panel'), callback_data='admin_home')])
    
    markup = InlineKeyboardMarkup(btns)
    
    if update.callback_query:
        if update.callback_query.data == 'check_subs':
            await update.callback_query.answer("✅")
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        except BadRequest:
             await update.callback_query.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return MAIN_MENU

# --- 5. ميزة الرابط الخاص (WHISPER) والإرسال ---

# عرض الرابط للمستخدم
async def show_my_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = context.bot.username
    link = f"https://t.me/{bot_username}?start={user.id}"
    
    await update.callback_query.edit_message_text(
        t(user.id, 'my_link_msg').format(link=link),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user.id, 'back'), callback_data='cancel_to_main')]]),
        parse_mode='Markdown'
    )
    return MAIN_MENU

# معالجة رسالة الرابط الخاص (الشكل الجديد)
async def process_whisper_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    target_id = context.user_data.get('msg_target_id')
    
    # 🆕 إعداد الوقت والتاريخ
    now = datetime.now()
    # التنسيق: YYYY/MM/DD - HH:MM:SS AM/PM
    time_str = now.strftime('%Y/%m/%d - %I:%M:%S %p')
    
    # 🆕 التنسيق المطلوب بالضبط
    header = (
        f"⁣💌 وصلتك رسالة جديدة\n"
        f"⏱ وقت الرسالة: {time_str}\n"
        f"----\n"
    )
    footer = "\n----"
    
    btns = [
        [InlineKeyboardButton("رد ↩️", callback_data=f"reply_{sender.id}"),
         InlineKeyboardButton("حظر 🚫", callback_data=f"block_{sender.id}")],
        [InlineKeyboardButton("🚨 إبلاغ", callback_data=f"report_{sender.id}")]
    ]
    
    try:
        if update.message.text:
            text_body = f"{header}رسالته هنا:\n{update.message.text}{footer}"
            await context.bot.send_message(target_id, text_body, reply_markup=InlineKeyboardMarkup(btns))
        else:
            # للوسائط، نضع النص في الكابشن
            original_cap = update.message.caption or "محتوى ميديا (صورة/فيديو)"
            caption_body = f"{header}رسالته هنا:\n{original_cap}{footer}"
            
            # في حال كان الكابشن طويلاً جداً قد يعطي خطأ، لذا نرسل الهيدر كرسالة ثم الميديا (اختياري)، 
            # لكن سنستخدم copy للتسهيل مع كابشن معدل
            await update.message.copy(
                chat_id=target_id, 
                caption=caption_body, 
                reply_markup=InlineKeyboardMarkup(btns)
            )

        await update.message.reply_text(t(sender.id, 'sent_ok'))
    except Forbidden:
        await update.message.reply_text("🚫 المستخدم قام بحظر البوت.")
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")
        
    return await main_menu_display(update, context)

# الإرسال اليدوي (بالبحث عن المعرف) - بقيت كما هي مع تعديل بسيط
async def ask_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.callback_query.edit_message_text(
        t(user_id, 'ask_target'),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, 'cancel'), callback_data='cancel_to_main')]])
    )
    return AWAIT_MSG_TARGET

async def receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace('@', '').replace('https://t.me/', '')
    user = update.effective_user
    conn = get_db()
    
    target = None
    if text.isdigit():
        target = conn.execute("SELECT * FROM users WHERE user_id=?", (int(text),)).fetchone()
    else:
        target = conn.execute("SELECT * FROM users WHERE username=?", (text,)).fetchone()
    
    if not target:
        conn.close()
        await update.message.reply_text(t(user.id, 'user_not_found'))
        return AWAIT_MSG_TARGET
    
    target_id = target['user_id']
    if target_id == user.id:
        conn.close()
        await update.message.reply_text(t(user.id, 'cant_self'))
        return AWAIT_MSG_TARGET
        
    blocked = conn.execute("SELECT 1 FROM blocks WHERE blocker_id=? AND blocked_id=?", (target_id, user.id)).fetchone()
    conn.close()
    
    if blocked:
        await update.message.reply_text(t(user.id, 'target_blocked'))
        return MAIN_MENU 
        
    context.user_data['msg_target_id'] = target_id
    await update.message.reply_text(
        t(user.id, 'write_msg'),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user.id, 'cancel'), callback_data='cancel_to_main')]])
    )
    return AWAIT_MSG_CONTENT

async def process_manual_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # استخدام نفس المنطق القديم للرسائل اليدوية (بدون فورمات صارم مثل الرابط، أو يمكن توحيدها)
    # هنا سأتركها بسيطة كما كانت للحفاظ على الفرق بين "الهمسة" والرسالة العادية
    # أو يمكننا استخدام نفس دالة process_whisper_content إذا أردت توحيد الشكل.
    return await process_whisper_content(update, context)

# --- 6. ميزة التبرع (DONATION - Telegram Stars) ---

async def donate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = t(user_id, 'donate_title')
    
    # أزرار التبرع (XTR = Stars)
    # القيمة 1 = 1 Star
    kb = [
        [InlineKeyboardButton("⭐️ 50 Stars", callback_data='pay_50'), InlineKeyboardButton("⭐️ 100 Stars", callback_data='pay_100')],
        [InlineKeyboardButton("⭐️ 250 Stars", callback_data='pay_250'), InlineKeyboardButton("⭐️ 500 Stars", callback_data='pay_500')],
        [InlineKeyboardButton(t(user_id, 'back'), callback_data='cancel_to_main')]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return MAIN_MENU

async def process_donation_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    amount = int(query.data.split('_')[1]) # استخراج الرقم 50, 100...
    
    title = "دعم البوت"
    description = f"تبرع بـ {amount} نجمة لدعم تطوير البوت"
    payload = "Custom-Payload"
    currency = "XTR" # عملة Stars
    prices = [LabeledPrice("Donation", amount)] # المبلغ بالنجوم (لا يحتاج ضرب في 100 مثل الدولار)

    # ملاحظة: لإرسال فاتورة Stars، لا تحتاج provider_token، اتركه فارغاً ""
    try:
        await context.bot.send_invoice(
            chat_id=query.from_user.id,
            title=title,
            description=description,
            payload=payload,
            provider_token="", 
            currency=currency,
            prices=prices,
            start_parameter="donation-bot"
        )
        await query.answer("🚀 تم إنشاء الفاتورة")
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # الموافقة على الدفع قبل الخصم
    query = update.pre_checkout_query
    if query.invoice_payload != 'Custom-Payload':
        await query.answer(ok=False, error_message="Something went wrong...")
    else:
        await query.answer(ok=True)

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # بعد اكتمال الدفع
    await update.message.reply_text(t(update.effective_user.id, 'donate_thanks'))

# --- 7. الإعدادات، الحظر، الردود ---

async def user_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    u = conn.execute("SELECT is_show_id, language FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    
    is_vis = u['is_show_id'] == 1
    status_txt = t(user_id, 'vis_show') if is_vis else t(user_id, 'vis_hide')
    
    text = f"{t(user_id, 'settings_title')}\n\n{status_txt}"
    kb = [
        [InlineKeyboardButton(t(user_id, 'toggle_vis'), callback_data='toggle_vis')],
        [InlineKeyboardButton(t(user_id, 'lang_btn'), callback_data='switch_lang')],
        [InlineKeyboardButton(t(user_id, 'block_user'), callback_data='manual_block')],
        [InlineKeyboardButton(t(user_id, 'report_user'), callback_data='manual_report')],
        [InlineKeyboardButton(t(user_id, 'my_blocks'), callback_data='my_blocks')],
        [InlineKeyboardButton(t(user_id, 'back'), callback_data='cancel_to_main')]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return MAIN_MENU

async def switch_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    curr = conn.execute("SELECT language FROM users WHERE user_id=?", (user_id,)).fetchone()['language']
    new_lang = 'en' if curr == 'ar' else 'ar'
    conn.execute("UPDATE users SET language=? WHERE user_id=?", (new_lang, user_id))
    conn.commit()
    conn.close()
    await update.callback_query.answer("Language Changed / تم تغيير اللغة")
    return await user_settings(update, context)

async def toggle_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    curr = conn.execute("SELECT is_show_id FROM users WHERE user_id=?", (user_id,)).fetchone()['is_show_id']
    new_val = 0 if curr else 1
    conn.execute("UPDATE users SET is_show_id=? WHERE user_id=?", (new_val, user_id))
    conn.commit()
    conn.close()
    return await user_settings(update, context)

# --- الحظر اليدوي ---
async def manual_block_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.callback_query.edit_message_text(
        t(user_id, 'enter_block'),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, 'cancel'), callback_data='btn_settings')]])
    )
    return SETTINGS_BLOCK_INPUT

async def manual_block_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace('@', '')
    user_id = update.effective_user.id
    conn = get_db()
    
    target = None
    if text.isdigit():
        target = conn.execute("SELECT user_id FROM users WHERE user_id=?", (int(text),)).fetchone()
    else:
        target = conn.execute("SELECT user_id FROM users WHERE username=?", (text,)).fetchone()
        
    if not target:
        conn.close()
        await update.message.reply_text(t(user_id, 'user_not_found'))
        return SETTINGS_BLOCK_INPUT
    
    target_id = target['user_id']
    conn.execute("INSERT OR IGNORE INTO blocks VALUES (?, ?)", (user_id, target_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(t(user_id, 'blocked_success'))
    return await main_menu_display(update, context)

# --- الإبلاغ اليدوي ---
async def manual_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.callback_query.edit_message_text(
        t(user_id, 'enter_report'),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, 'cancel'), callback_data='btn_settings')]])
    )
    return SETTINGS_REPORT_INPUT

async def manual_report_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace('@', '')
    user_id = update.effective_user.id
    conn = get_db()
    target = None
    if text.isdigit(): target = conn.execute("SELECT * FROM users WHERE user_id=?", (int(text),)).fetchone()
    else: target = conn.execute("SELECT * FROM users WHERE username=?", (text,)).fetchone()
    conn.close()
    if not target:
        await update.message.reply_text(t(user_id, 'user_not_found'))
        return SETTINGS_REPORT_INPUT
    context.user_data['report_target_id'] = target['user_id']
    context.user_data['report_target_name'] = target['username']
    await update.message.reply_text(
        t(user_id, 'enter_reason'),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t(user_id, 'cancel'), callback_data='btn_settings')]])
    )
    return SETTINGS_REPORT_REASON

async def manual_report_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = context.user_data['report_target_id']
    target_name = html.escape(str(context.user_data.get('report_target_name', 'Unknown')))
    reporter = update.effective_user
    
    admin_header = f"🚨 <b>بلاغ يدوي!</b>\n👮 من: {reporter.id}\n👤 ضد: {target_id} (@{target_name})"
    btns = [[InlineKeyboardButton("🔨 حظر", callback_data=f"adm_ban_{target_id}"), InlineKeyboardButton("👁️ تجاهل", callback_data="adm_ignore")]]
    
    await context.bot.send_message(ADMIN_ID, admin_header, parse_mode='HTML')
    if update.message.text:
        await context.bot.send_message(ADMIN_ID, f"📝 السبب: {update.message.text}", reply_markup=InlineKeyboardMarkup(btns))
    else:
        await update.message.copy(ADMIN_ID, reply_markup=InlineKeyboardMarkup(btns))
    
    await update.message.reply_text(t(reporter.id, 'report_sent'))
    return await main_menu_display(update, context)

async def my_blocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    blocks = conn.execute("SELECT blocked_id FROM blocks WHERE blocker_id=?", (user_id,)).fetchall()
    conn.close()
    kb = []
    for b in blocks:
        kb.append([InlineKeyboardButton(f"🔓 {b['blocked_id']}", callback_data=f"unblock_me_{b['blocked_id']}")])
    kb.append([InlineKeyboardButton(t(user_id, 'back'), callback_data='btn_settings')])
    await update.callback_query.edit_message_text(t(user_id, 'my_blocks'), reply_markup=InlineKeyboardMarkup(kb))
    return MAIN_MENU

async def unblock_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = int(update.callback_query.data.split('_')[2])
    conn = get_db()
    conn.execute("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?", (update.effective_user.id, tid))
    conn.commit()
    conn.close()
    await update.callback_query.answer("✅")
    return await my_blocks(update, context)

async def handle_reply_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split('_')[1])
    context.user_data['msg_target_id'] = target_id
    await query.message.reply_text(
        "↩️",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌", callback_data='cancel_to_main')]])
    )
    return AWAIT_MSG_CONTENT

async def handle_block_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    target_id = int(query.data.split('_')[1])
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO blocks VALUES (?, ?)", (query.from_user.id, target_id))
    conn.commit()
    conn.close()
    await query.answer("🚫", show_alert=True)

async def handle_report_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🚨 تم الإبلاغ")
    sender_id = int(query.data.split('_')[1])
    await context.bot.send_message(ADMIN_ID, f"🚨 بلاغ عن رسالة من: {sender_id}")

# --- 8. لوحة الأدمن (ADMIN) ---

async def admin_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return await main_menu_display(update, context)
    text = "🔐 **Admin Panel**"
    kb = [
        [InlineKeyboardButton("📢 قنوات", callback_data='adm_channels'), InlineKeyboardButton("👥 أدمنز", callback_data='adm_admins')],
        [InlineKeyboardButton("📊 إحصائيات", callback_data='adm_stats'), InlineKeyboardButton("📡 إذاعة", callback_data='adm_broadcast')],
        [InlineKeyboardButton("🏠 خروج", callback_data='cancel_to_main')]
    ]
    if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_PANEL

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    u_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    b_count = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
    conn.close()
    await update.callback_query.edit_message_text(f"📊 Users: {u_count} | Banned: {b_count}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data='admin_home')]]))
    return ADMIN_PANEL

async def admin_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    chans = conn.execute("SELECT * FROM channels").fetchall()
    conn.close()
    text = "📢 **القنوات:**\n"
    kb = []
    for c in chans:
        text += f"- {c['channel_name']}\n"
        kb.append([InlineKeyboardButton(f"🗑 {c['channel_name']}", callback_data=f"adm_del_ch_{c['channel_id']}")])
    kb.append([InlineKeyboardButton("➕ قناة", callback_data='adm_add_ch_req')])
    kb.append([InlineKeyboardButton("🔙", callback_data='admin_home')])
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_PANEL

async def req_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("➕ أرسل معرف القناة أو الرابط:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء", callback_data='admin_home')]]))
    return ADMIN_ADD_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        txt = update.message.text.strip()
        identifier = txt if "t.me/" not in txt else "@" + txt.split("t.me/")[-1].split("/")[0]
        chat = await context.bot.get_chat(identifier)
        conn = get_db()
        conn.execute("INSERT INTO channels VALUES (?, ?, ?)", (chat.id, chat.invite_link or txt, chat.title))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ تم")
    except: await update.message.reply_text("❌ خطأ، تأكد أن البوت أدمن.")
    return await admin_home(update, context)

async def del_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch_id = update.callback_query.data.split('_')[3]
    conn = get_db()
    conn.execute("DELETE FROM channels WHERE channel_id=?", (ch_id,))
    conn.commit()
    conn.close()
    await update.callback_query.answer("✅")
    return await admin_channels(update, context)

async def req_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("📡 أرسل الإذاعة:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء", callback_data='admin_home')]]))
    return ADMIN_BROADCAST

async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    await msg.reply_text("⏳...")
    conn = get_db()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    for u in users:
        try:
            if msg.text: await context.bot.send_message(u['user_id'], f"📢 **إدارة:**\n{msg.text}")
            else: await msg.copy(u['user_id'], caption=f"📢 **إدارة:**\n{msg.caption or ''}")
            await asyncio.sleep(0.05)
        except: pass
    await msg.reply_text("✅ تم")
    return await admin_home(update, context)

async def admin_manage_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    admins = conn.execute("SELECT * FROM admins").fetchall()
    conn.close()
    text = "🔐 **الأدمنز:**\n"
    kb = []
    for a in admins:
        text += f"- {a['username'] or a['user_id']}\n"
        kb.append([InlineKeyboardButton(f"🗑 {a['user_id']}", callback_data=f"adm_del_adm_{a['user_id']}")])
    kb.append([InlineKeyboardButton("➕ أدمن", callback_data='adm_add_adm_req')])
    kb.append([InlineKeyboardButton("🔙", callback_data='admin_home')])
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_PANEL

async def req_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("➕ أرسل الآيدي:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء", callback_data='admin_home')]]))
    return ADMIN_ADD_ADMIN

async def save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.isdigit():
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (int(txt),))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅")
    else: await update.message.reply_text("❌ أرسل آيدي رقمي فقط")
    return await admin_home(update, context)

async def del_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.callback_query.data.split('_')[3]
    conn = get_db()
    conn.execute("DELETE FROM admins WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    await update.callback_query.answer("✅")
    return await admin_manage_list(update, context)

async def admin_action_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = int(update.callback_query.data.split('_')[2])
    conn = get_db()
    conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    await update.callback_query.answer("🔨 تم الحظر")

async def admin_action_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['warn_target'] = int(update.callback_query.data.split('_')[2])
    await update.callback_query.message.reply_text("⚠️ أرسل التحذير:")
    return ADMIN_WARN_USER

async def send_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(context.user_data['warn_target'], f"👮 **تنبيه:**\n{update.message.text}")
        await update.message.reply_text("✅ وصل")
    except: await update.message.reply_text("❌ فشل")
    return ADMIN_PANEL

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: await update.callback_query.answer()
    return await main_menu_display(update, context)

# --- التشغيل ---
def main():
    print("🚀 Bot is starting...")

    init_db()

    application = ApplicationBuilder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(show_my_link, pattern='^get_my_link$'), # 🆕
                CallbackQueryHandler(donate_menu, pattern='^btn_donate$'),   # 🆕
                CallbackQueryHandler(process_donation_click, pattern='^pay_'), # 🆕
                CallbackQueryHandler(ask_target, pattern='^btn_send$'),
                CallbackQueryHandler(user_settings, pattern='^btn_settings$'),
                CallbackQueryHandler(toggle_visibility, pattern='^toggle_vis$'),
                CallbackQueryHandler(switch_language, pattern='^switch_lang$'),
                CallbackQueryHandler(manual_block_start, pattern='^manual_block$'),
                CallbackQueryHandler(manual_report_start, pattern='^manual_report$'),
                CallbackQueryHandler(my_blocks, pattern='^my_blocks$'),
                CallbackQueryHandler(unblock_me, pattern='^unblock_me_'),
                CallbackQueryHandler(admin_home, pattern='^admin_home$'),
                CallbackQueryHandler(handle_reply_btn, pattern='^reply_'),
                CallbackQueryHandler(handle_block_btn, pattern='^block_'),
                CallbackQueryHandler(handle_report_btn, pattern='^report_'),
                CallbackQueryHandler(main_menu_display, pattern='^check_subs$'),
            ],
            # الحالة الجديدة للهمسة
            AWAIT_WHISPER_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, process_whisper_content), CallbackQueryHandler(cancel_handler, pattern='^cancel')],
            
            AWAIT_MSG_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_target), CallbackQueryHandler(cancel_handler, pattern='^cancel')],
            AWAIT_MSG_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, process_manual_msg), CallbackQueryHandler(cancel_handler, pattern='^cancel')],
            SETTINGS_BLOCK_INPUT: [MessageHandler(filters.TEXT, manual_block_process), CallbackQueryHandler(user_settings, pattern='^btn_settings')],
            SETTINGS_REPORT_INPUT: [MessageHandler(filters.TEXT, manual_report_target), CallbackQueryHandler(user_settings, pattern='^btn_settings')],
            SETTINGS_REPORT_REASON: [MessageHandler(filters.ALL & ~filters.COMMAND, manual_report_submit), CallbackQueryHandler(user_settings, pattern='^btn_settings')],

            ADMIN_PANEL: [
                CallbackQueryHandler(admin_stats, pattern='^adm_stats$'),
                CallbackQueryHandler(admin_channels, pattern='^adm_channels$'),
                CallbackQueryHandler(req_add_channel, pattern='^adm_add_ch_req$'),
                CallbackQueryHandler(del_channel, pattern='^adm_del_ch_'),
                CallbackQueryHandler(admin_manage_list, pattern='^adm_admins$'),
                CallbackQueryHandler(req_add_admin, pattern='^adm_add_adm_req$'),
                CallbackQueryHandler(del_admin, pattern='^adm_del_adm_'),
                CallbackQueryHandler(req_broadcast, pattern='^adm_broadcast$'),
                CallbackQueryHandler(cancel_handler, pattern='^cancel'),
                CallbackQueryHandler(admin_home, pattern='^admin_home$'),
            ],
            ADMIN_ADD_CHANNEL: [MessageHandler(filters.TEXT, save_channel), CallbackQueryHandler(admin_home, pattern='^admin_home')],
            ADMIN_ADD_ADMIN: [MessageHandler(filters.TEXT, save_admin), CallbackQueryHandler(admin_home, pattern='^admin_home')],
            ADMIN_BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND, do_broadcast), CallbackQueryHandler(admin_home, pattern='^admin_home')],
            ADMIN_WARN_USER: [MessageHandler(filters.TEXT, send_warning)]
        },
        fallbacks=[CommandHandler('start', start), CallbackQueryHandler(cancel_handler, pattern='^cancel')]
    )

    application.add_handler(CallbackQueryHandler(admin_action_ban, pattern='^adm_ban_'))
    application.add_handler(CallbackQueryHandler(admin_action_warn, pattern='^adm_warn_'))
    application.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.answer(), pattern='^adm_ignore$'))
    
    # 🆕 هاندلر الدفع (Stars)
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    warn_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_action_warn, pattern='^adm_warn_')],
        states={ADMIN_WARN_USER: [MessageHandler(filters.TEXT, send_warning)]},
        fallbacks=[CommandHandler('start', start)]
    )
    application.add_handler(warn_conv)
    application.add_handler(conv)

    print("✅ Handlers loaded")

    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
