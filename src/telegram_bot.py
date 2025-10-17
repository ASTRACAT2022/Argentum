import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Import our custom modules
from gemini_client import GeminiClient
from command_executor import execute_commands

# --- Configuration ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Load credentials from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    await update.message.reply_text("Привет! Я ваш AI-сисадмин. Присылайте мне задачи.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user messages, gets a command plan from Gemini, and asks for confirmation."""
    task_description = update.message.text
    logger.info(f"Received task: {task_description}")

    await update.message.reply_text(f"Получил задачу: '{task_description}'. Думаю над планом...")

    try:
        # Get command plan from Gemini
        gemini_client = context.bot_data["gemini_client"]
        command_string = gemini_client.get_commands(task_description)
        commands = [cmd for cmd in command_string.split('\n') if cmd.strip()]

        if not commands:
            await update.message.reply_text("Не удалось составить план команд для этой задачи. Попробуйте переформулировать.")
            return

        # Store commands in context to be used by the callback handler
        context.chat_data[update.message.message_id] = commands

        # Present the plan to the user for confirmation
        plan_text = "Вот план, который я предлагаю:\n\n```\n" + "\n".join(commands) + "\n```"
        keyboard = [
            [
                InlineKeyboardButton("✅ Выполнить", callback_data=f"confirm_{update.message.message_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"cancel_{update.message.message_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(plan_text, reply_markup=reply_markup, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"An error occurred in handle_message: {e}")
        await update.message.reply_text(f"Произошла ошибка: {e}")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the user's choice from the inline keyboard."""
    query = update.callback_query
    await query.answer()

    action, message_id_str = query.data.split('_')
    message_id = int(message_id_str)

    # Retrieve commands from context
    commands = context.chat_data.pop(message_id, None)

    if action == "cancel":
        await query.edit_message_text(text="План выполнения отклонен.")
        return

    if not commands:
        await query.edit_message_text(text="Не удалось найти план для выполнения. Возможно, сессия истекла.")
        return

    await query.edit_message_text(text="План принят. Выполняю команды...")

    # Execute commands and send report
    results = execute_commands(commands)

    report = "--- Отчет о выполнении ---\n\n"
    for res in results:
        report += f"Команда: `{res['command']}`\n"
        report += f"Код возврата: {res['returncode']}\n"
        if res['stdout']:
            report += f"Вывод (stdout):\n```\n{res['stdout']}\n```\n"
        if res['stderr']:
            report += f"Ошибки (stderr):\n```\n{res['stderr']}\n```\n"
        report += "---\n"

    # Telegram has a message size limit, so we might need to split the report
    if len(report) > 4096:
        report = report[:4000] + "\n... (сообщение было обрезано)"

    await query.message.reply_text(report, parse_mode='Markdown')


def main() -> None:
    """Initializes and starts the bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Environment variable TELEGRAM_BOT_TOKEN is not set.")
        return
    if not GEMINI_API_KEY:
        print("ERROR: Environment variable GEMINI_API_KEY is not set.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Store the Gemini client in bot_data for access in handlers
    application.bot_data["gemini_client"] = GeminiClient(api_key=GEMINI_API_KEY)

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(confirm|cancel)_"))

    # Run the bot
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()