# telegram_bot.py
import logging

import psycopg2
import psycopg2.extras  # ← ЭТО ОБЯЗАТЕЛЬНО!
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, \
    PreCheckoutQueryHandler

load_dotenv()  # Загружает пере     менные из .env
# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7710403201:AAEPwYZ7SBuVkQg330d0-qSj0Wf5U7hTJEA"
DATABASE_URL = "postgresql://occultong_db_user:OCAxevVLpQCBQrm8TJGtH5MwCMGKgNz5@dpg-d3dnm8a4d50c739lkh6g-a.oregon-postgres.render.com/occultong_db"


# Подключение к базе данных
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) начал взаимодействие")

    if context.args and context.args[0] == 'payment':
        await send_payment_menu(update, context)
    else:
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот для оплаты подписки Guru на OccultoNG Web.\n"
            "Чтобы начать, отправьте мне ваш email, привязанный к аккаунту на сайте."
        )


async def send_payment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет меню оплаты"""
    keyboard = [
        [InlineKeyboardButton("Оплатить Guru план (5 Stars)", callback_data='pay_guru')],
        [InlineKeyboardButton("Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Вы выбрали оплату Guru плана.\n\n"
        "❗️Внимание: перед оплатой убедитесь, что вы вошли на сайт OccultoNG Web под тем же email, который вы "
        "собираетесь указать здесь.\n\n"
        "Нажмите кнопку ниже, чтобы продолжить.",
        reply_markup=reply_markup
    )


async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        user_row = cur.fetchone()
        cur.close()
        conn.close()

        if not user_row:
            await update.message.reply_text(
                "❌ Не удалось найти пользователя с таким email.\n\n"
                "Пожалуйста, убедитесь, что вы зарегистрировались на сайте OccultoNG Web под этим email адресом."
            )
            return

        context.user_data['email'] = email
        context.user_data['user_id'] = user_row['id']

        # ✅ Отправляем сообщение с кнопкой "Оплатить Guru план"
        keyboard = [
            [InlineKeyboardButton("Оплатить Guru план (5 Stars)", callback_data='pay_guru')],
            [InlineKeyboardButton("Отмена", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"✅ Email {email} успешно найден!\n\n"
            "Теперь нажмите кнопку ниже, чтобы начать оплату Guru плана за 5 Stars.",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке email: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при проверке email. Попробуйте позже или свяжитесь с поддержкой."
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопок"""
    query = update.callback_query
    await query.answer()

    if query.data == 'pay_guru':
        # Запуск процесса оплаты через Stars
        await query.edit_message_text(
            "⏳ Готовим оплату...\n\n"
            "Пожалуйста, подтвердите оплату 5 Stars в открывшемся окне."
        )
        # Используем встроенный механизм Telegram Stars
        await query.message.reply_invoice(
            title="OccultoNG Web - Guru Plan",
            description="Безлимитные операции стеганографии",
            payload="guru_plan_payment",
            provider_token="",  # Пустой токен для Stars
            currency="XTR",  # Код валюты для Telegram Stars
            prices=[{"label": "Guru Plan", "amount": 500}],  # 5 Stars = 500
            need_email=True,
            is_flexible=False
        )
    elif query.data == 'cancel':
        await query.edit_message_text("Оплата отменена.")


async def pre_checkout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка предварительной проверки платежа"""
    query = update.pre_checkout_query
    # Принимаем все платежи (можно добавить дополнительную логику)
    await query.answer(ok=True)


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка успешного платежа"""
    user_id = update.effective_user.id
    email = context.user_data.get('email')
    db_user_id = context.user_data.get('user_id')

    if not email or not db_user_id:
        await update.message.reply_text("❌ Ошибка: не удалось найти информацию о пользователе.")
        return

    # Обновляем статус подписки в базе данных
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET subscription_status = 'guru',
            last_payment_date = NOW()
        WHERE id = %s
    """, (db_user_id,))
    conn.commit()
    cur.close()
    conn.close()

    # Отправляем подтверждение пользователю
    await update.message.reply_text(
        "🎉 Поздравляем! Ваша подписка Guru активирована.\n\n"
        "Теперь вы можете выполнять неограниченное количество операций на сайте OccultoNG Web.\n\n"
        "Зайдите на сайт и обновите страницу, чтобы увидеть обновленный статус."
    )

    # Отправляем уведомление на сайт (если возможно)
    # Можно использовать webhook или другую систему уведомлений


def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(None, handle_email))  # Обрабатываем любой текст как email
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    application.add_handler(MessageHandler(None, successful_payment_callback))

    logger.info("Бот запущен")
    application.run_polling()


if __name__ == '__main__':
    main()
