from datetime import datetime, timezone
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from bot import Bot
from config import ADMINS, UPI_ID, UPI_QR_IMAGE, ADMIN_CONTACT
from database.database import (
    create_payment_request, get_payment_request, approve_premium,
    reject_payment, get_premium,
)

PLANS = {
    "p1": (1, 10),
    "p2": (2, 20),
    "p3": (3, 30),
    "p7": (7, 49),
    "p30": (30, 99),
}


def premium_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 Day — ₹10", callback_data="plan_p1"), InlineKeyboardButton("2 Days — ₹20", callback_data="plan_p2")],
        [InlineKeyboardButton("3 Days — ₹30", callback_data="plan_p3"), InlineKeyboardButton("7 Days — ₹49", callback_data="plan_p7")],
        [InlineKeyboardButton("30 Days — ₹99", callback_data="plan_p30")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")],
    ])


@Bot.on_callback_query(filters.regex(r"^premium_menu$"))
async def show_premium_menu(client: Bot, query: CallbackQuery):
    await query.message.edit_text(
        "👑 <b>PREMIUM MEMBERSHIP</b>\n\n"
        "Premium plan ಆಯ್ಕೆಮಾಡಿ. ಪಾವತಿ ಮಾಡಿದ ನಂತರ <b>I HAVE PAID</b> ಒತ್ತಿ. "
        "Admin ಪಾವತಿಯನ್ನು ಪರಿಶೀಲಿಸಿ ಅನುಮೋದಿಸಿದ ಮೇಲೆ ಮಾತ್ರ Premium ಸಕ್ರಿಯವಾಗುತ್ತದೆ.",
        reply_markup=premium_keyboard(),
    )
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^plan_(p1|p2|p3|p7|p30)$"))
async def select_plan(client: Bot, query: CallbackQuery):
    key = query.data.split("_", 1)[1]
    days, amount = PLANS[key]
    await create_payment_request(query.from_user.id, days, amount)
    text = (
        f"👑 <b>Premium — {days} day(s)</b>\n"
        f"💰 Amount: <b>₹{amount}</b>\n\n"
        f"UPI ID: <code>{UPI_ID}</code>\n\n"
        "UPI ಮೂಲಕ ಪಾವತಿ ಮಾಡಿ. ನಂತರ ಕೆಳಗಿನ <b>I HAVE PAID</b> ಒತ್ತಿ. "
        "ಇದು payment confirmation ಮಾತ್ರ; Admin ಪರಿಶೀಲನೆ ನಂತರವೇ Premium ಸಕ್ರಿಯವಾಗುತ್ತದೆ."
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I HAVE PAID", callback_data=f"paid_{key}")],
        [InlineKeyboardButton("⬅️ Plans", callback_data="premium_menu")],
        [InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{ADMIN_CONTACT.lstrip('@')}")],
    ])
    if UPI_QR_IMAGE:
        await query.message.reply_photo(UPI_QR_IMAGE, caption=text, reply_markup=markup)
        await query.message.delete()
    else:
        await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^paid_(p1|p2|p3|p7|p30)$"))
async def paid_notice(client: Bot, query: CallbackQuery):
    key = query.data.split("_", 1)[1]
    days, amount = PLANS[key]
    request = await get_payment_request(query.from_user.id)
    if not request:
        await query.answer("ಮೊದಲು ಒಂದು Premium plan ಆಯ್ಕೆಮಾಡಿ.", show_alert=True)
        return
    admin_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"premapprove_{query.from_user.id}_{days}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"premreject_{query.from_user.id}")]
    ])
    user = query.from_user
    username = f"@{user.username}" if user.username else "No username"
    notice = (
        "🔔 <b>Premium payment request</b>\n"
        f"User: {user.mention} (<code>{user.id}</code>)\n"
        f"Username: {username}\nPlan: {days} day(s)\nAmount: ₹{amount}\n\n"
        "ಪಾವತಿ ಪರಿಶೀಲಿಸಿ; ಸರಿ ಇದ್ದರೆ Approve ಒತ್ತಿ."
    )
    delivered = 0
    for admin_id in ADMINS:
        try:
            await client.send_message(admin_id, notice, reply_markup=admin_markup)
            delivered += 1
        except Exception:
            pass
    await query.message.edit_text(
        "✅ ನಿಮ್ಮ payment request Admin‌ಗೆ ಕಳುಹಿಸಲಾಗಿದೆ.\n"
        "ಪಾವತಿ ಪರಿಶೀಲನೆಯ ನಂತರ ನಿಮಗೆ ತಿಳಿಸಲಾಗುತ್ತದೆ."
    )
    await query.answer("Request ಕಳುಹಿಸಲಾಗಿದೆ.")
    if delivered == 0:
        await client.send_message(query.from_user.id, "Admin‌ಗೆ notification ಕಳುಹಿಸಲು ಆಗಲಿಲ್ಲ. Admin ಬಾಟ್‌ಗೆ ಮೊದಲು /start ಕಳುಹಿಸಿರುವುದನ್ನು ಖಚಿತಪಡಿಸಿ.")


@Bot.on_callback_query(filters.regex(r"^premapprove_\d+_\d+$") & filters.user(ADMINS))
async def approve_request(client: Bot, query: CallbackQuery):
    _, user_id, days = query.data.split("_")
    user_id, days = int(user_id), int(days)
    request = await get_payment_request(user_id)
    if not request:
        await query.answer("Pending request ಸಿಗಲಿಲ್ಲ ಅಥವಾ ಈಗಾಗಲೇ ನಿರ್ವಹಿಸಲಾಗಿದೆ.", show_alert=True)
        return
    expires_at = await approve_premium(user_id, days)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.message.reply_text(f"✅ User <code>{user_id}</code> ಗೆ {days} ದಿನಗಳ Premium ಅನುಮೋದಿಸಲಾಗಿದೆ.")
    try:
        await client.send_message(user_id, f"🎉 ನಿಮ್ಮ Premium membership ಅನುಮೋದಿಸಲಾಗಿದೆ!\nExpiry: <code>{expires_at:%Y-%m-%d %H:%M UTC}</code>")
    except Exception:
        pass
    await query.answer("Premium activated")


@Bot.on_callback_query(filters.regex(r"^premreject_\d+$") & filters.user(ADMINS))
async def reject_request(client: Bot, query: CallbackQuery):
    user_id = int(query.data.split("_")[1])
    await reject_payment(user_id)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.message.reply_text(f"❌ User <code>{user_id}</code> payment request rejected.")
    try:
        await client.send_message(user_id, "❌ ನಿಮ್ಮ payment request ಅನ್ನು Admin ಅನುಮೋದಿಸಿಲ್ಲ. ವಿವರಗಳಿಗಾಗಿ Admin ಸಂಪರ್ಕಿಸಿ.")
    except Exception:
        pass
    await query.answer("Request rejected")


@Bot.on_callback_query(filters.regex(r"^download_free$"))
async def free_download_info(client: Bot, query: CallbackQuery):
    await query.answer()
    await query.message.reply_text(
        "📥 <b>FREE DOWNLOAD</b>\n\n"
        "ಫೈಲ್ ಪಡೆಯಲು ಚಾನೆಲ್‌ನಲ್ಲಿ ನೀಡಿರುವ file link ಅನ್ನು ತೆರೆಯಿರಿ."
    )


@Bot.on_callback_query(filters.regex(r"^menu_back$"))
async def back_to_menu(client: Bot, query: CallbackQuery):
    await query.message.edit_text(
        "🎬 <b>RUDRA MOVIES</b>\n\nನಿಮಗೆ ಬೇಕಾದ ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 DOWNLOAD — FREE", callback_data="download_free")],
            [InlineKeyboardButton("👑 PREMIUM MEMBERSHIP", callback_data="premium_menu")],
            [InlineKeyboardButton("📚 DOWNLOAD TUTORIAL", url="https://t.me/RudraMovies4")],
        ])
    )
    await query.answer()


@Bot.on_message(filters.command("premiumstatus") & filters.private)
async def premium_status(client: Bot, message):
    premium = await get_premium(message.from_user.id)
    if not premium:
        await message.reply_text("ನಿಮ್ಮ Premium membership ಸಕ್ರಿಯವಾಗಿಲ್ಲ.")
        return
    expires_at = premium["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    await message.reply_text(f"👑 Premium active\nExpiry: <code>{expires_at:%Y-%m-%d %H:%M UTC}</code>")
