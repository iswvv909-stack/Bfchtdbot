import logging
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes,
)
from dotenv import load_dotenv

from services.openai_service import get_level_test_question, get_lesson_content
from services.tts_service import text_to_speech
from utils.constants import CHOOSING, LEVEL_TEST, LESSON, EXERCISE, LEVELS, LEVEL_TEST_QUESTIONS, LESSON_TOPICS
from utils.database import (
    init_db, save_user, get_user, update_level,
    save_progress, get_user_stats, save_level_test,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def send_voice(update: Update, text: str, voice: str = "en"):
    try:
        voice_path = await text_to_speech(text, voice)
        with open(voice_path, "rb") as f:
            await update.effective_message.reply_audio(audio=f)
        os.unlink(voice_path)
    except Exception as e:
        logger.error(f"TTS error: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    save_user(user.id, user.username or "", user.first_name or "")
    context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("📝 اختبار تحديد المستوى", callback_data="test_level")],
        [InlineKeyboardButton("🎯 اختيار المستوى يدوياً", callback_data="choose_level")],
        [InlineKeyboardButton("📊 عرض تقدمي", callback_data="show_progress")],
    ]
    await update.message.reply_text(
        f"مرحباً {user.first_name}! 👋\nأنا بوت تعليم اللغة الإنجليزية.\nاختر ما تريد:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING


async def choose_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🟢 مبتدئ", callback_data="set_level_beginner")],
        [InlineKeyboardButton("🟡 متوسط", callback_data="set_level_intermediate")],
        [InlineKeyboardButton("🔴 متقدم", callback_data="set_level_advanced")],
    ]
    await query.edit_message_text("اختر مستواك:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING


async def set_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    level_key = query.data.replace("set_level_", "")
    context.user_data["level"] = level_key
    context.user_data["lesson_count"] = 0
    update_level(query.from_user.id, level_key)
    await query.edit_message_text(f"✅ مستواك: {LEVELS[level_key]}\nلنبدأ الدرس الأول!")
    return await start_lesson(update, context)


async def start_level_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["test_question_number"] = 1
    context.user_data["test_score"] = 0
    await query.edit_message_text("📝 سؤال 1 من 7...")
    return await ask_test_question(update, context)


async def ask_test_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q_num = context.user_data.get("test_question_number", 1)
    if q_num > LEVEL_TEST_QUESTIONS:
        return await assign_level(update, context)

    try:
        q_data = await get_level_test_question(q_num)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.effective_message.reply_text("حدث خطأ، حاول مجددًا.")
        return LEVEL_TEST

    context.user_data["current_test_question"] = q_data
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"test_ans_{i}")] for i, opt in enumerate(q_data["options"])]
    text = f"📝 سؤال {q_num} من 7:\n\n{q_data['question']}"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return LEVEL_TEST


async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected = int(query.data.replace("test_ans_", ""))
    q_data = context.user_data.get("current_test_question")
    if not q_data:
        return LEVEL_TEST

    if selected == q_data["correct_index"]:
        context.user_data["test_score"] = context.user_data.get("test_score", 0) + 1
        feedback = "✅ إجابة صحيحة!"
    else:
        feedback = f"❌ إجابة خاطئة. الصحيح: {q_data['options'][q_data['correct_index']]}"

    await query.edit_message_text(feedback)
    context.user_data["test_question_number"] = context.user_data.get("test_question_number", 1) + 1
    return await ask_test_question(update, context)


async def assign_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    score = context.user_data.get("test_score", 0)
    if score <= 2:
        level = "beginner"
    elif score <= 4:
        level = "intermediate"
    else:
        level = "advanced"

    context.user_data["level"] = level
    context.user_data["lesson_count"] = 0
    user_id = update.effective_user.id
    update_level(user_id, level)
    save_level_test(user_id, score, level)

    await update.effective_message.reply_text(
        f"🎉 انتهى الاختبار!\nنتيجتك: {score}/{LEVEL_TEST_QUESTIONS}\nمستواك: {LEVELS[level]}\n\nلنبدأ الدرس الأول!"
    )
    return await start_lesson(update, context)


async def start_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    level = context.user_data.get("level", "beginner")
    topic = random.choice(LESSON_TOPICS.get(level, LESSON_TOPICS["beginner"]))
    context.user_data["current_topic"] = topic

    try:
        data = await get_lesson_content(level, topic)
    except Exception as e:
        logger.error(f"Lesson error: {e}")
        await update.effective_message.reply_text("تعذر تحميل الدرس، حاول مجددًا.")
        return LESSON

    context.user_data["lesson_data"] = data

    message = (
        f"📚 *درس: {topic}*\n\n"
        f"{data['lesson_explanation']}\n\n"
        f"*مثال:*\n`{data['example']}`\n\n"
        f"*تمرين:*\n{data['exercise_question']}"
    )

    keyboard = [[InlineKeyboardButton(opt, callback_data=f"lesson_ans_{i}")] for i, opt in enumerate(data["exercise_options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    await send_voice(update, data["example"])
    return EXERCISE


async def handle_lesson_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected = int(query.data.replace("lesson_ans_", ""))
    data = context.user_data.get("lesson_data")
    if not data:
        return EXERCISE

    is_correct = selected == data["correct_index"]
    if is_correct:
        feedback = "✅ إجابة صحيحة! أحسنت."
        score = 1
    else:
        feedback = f"❌ إجابة خاطئة. الصحيح: {data['exercise_options'][data['correct_index']]}"
        score = 0

    await query.edit_message_text(feedback)

    user_id = query.from_user.id
    topic = context.user_data.get("current_topic", "unknown")
    level = context.user_data.get("level", "beginner")
    save_progress(user_id, topic, level, score)

    context.user_data["lesson_count"] = context.user_data.get("lesson_count", 0) + 1
    count = context.user_data["lesson_count"]

    if count % 3 == 0:
        keyboard = [
            [InlineKeyboardButton("📖 متابعة الدروس", callback_data="continue_lessons")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")],
        ]
        await update.effective_message.reply_text(
            f"🎊 أكملت {count} دروس!",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return CHOOSING

    await update.effective_message.reply_text("➡️ لننتقل إلى الدرس التالي.")
    return await start_lesson(update, context)


async def continue_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("حسنًا، لنكمل!")
    return await start_lesson(update, context)


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    stats = get_user_stats(query.from_user.id)
    if not stats:
        await query.edit_message_text("لا توجد بيانات بعد. ابدأ التعلم أولاً!")
        return CHOOSING

    user = stats["user"]
    msg = f"📊 *تقدمك يا {user['first_name']}:*\n\n"
    msg += f"🎯 المستوى: {LEVELS.get(user['level'], user['level'])}\n"
    msg += f"📚 الدروس المكتملة: {user['current_lesson']}\n"
    msg += f"⭐ مجموع النقاط: {user['total_score']}\n"

    await query.edit_message_text(msg, parse_mode="Markdown")
    return CHOOSING


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await start(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("تم الإلغاء. استخدم /start للبدء من جديد.")
    return ConversationHandler.END


def main() -> None:
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(start_level_test, pattern="^test_level$"),
                CallbackQueryHandler(choose_level, pattern="^choose_level$"),
                CallbackQueryHandler(set_level, pattern="^set_level_"),
                CallbackQueryHandler(show_progress, pattern="^show_progress$"),
                CallbackQueryHandler(continue_lessons, pattern="^continue_lessons$"),
                CallbackQueryHandler(main_menu, pattern="^main_menu$"),
            ],
            LEVEL_TEST: [CallbackQueryHandler(handle_test_answer, pattern="^test_ans_")],
            LESSON: [CallbackQueryHandler(handle_lesson_answer, pattern="^lesson_ans_")],
            EXERCISE: [CallbackQueryHandler(handle_lesson_answer, pattern="^lesson_ans_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    logger.info("🤖 البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
