import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Import our custom modules
from gemini_client import GeminiClient
from command_executor import execute_commands
import database as db

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
    """Sends a welcome message and instructions."""
    welcome_text = (
        "Привет! Я ваш AI-сисадмин. Я могу выполнять задачи в рамках проектов.\n\n"
        "Доступные команды:\n"
        "/new_project <название> - Создать новый проект.\n"
        "/list_projects - Показать все проекты.\n"
        "/select_project <ID> - Выбрать проект для работы.\n"
        "/help - Показать это сообщение.\n\n"
        "Сначала выберите или создайте проект."
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the help message."""
    await start(update, context)

async def new_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Creates a new project."""
    project_name = " ".join(context.args)
    if not project_name:
        await update.message.reply_text("Пожалуйста, укажите название проекта. Пример: /new_project Установка веб-сервера")
        return

    project_id = db.create_project(project_name)
    if project_id:
        await update.message.reply_text(f"Проект '{project_name}' создан с ID {project_id}.")
        context.user_data['selected_project_id'] = project_id
        await update.message.reply_text(f"Проект '{project_name}' (ID: {project_id}) выбран для дальнейшей работы.")
    else:
        await update.message.reply_text(f"Не удалось создать проект '{project_name}'. Возможно, он уже существует.")

async def list_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all available projects."""
    projects = db.list_projects()
    if not projects:
        await update.message.reply_text("Проектов пока нет. Создайте новый с помощью /new_project.")
        return

    message = "Доступные проекты:\n"
    for proj in projects:
        message += f"- ID: {proj['id']}, Название: {proj['name']}\n"
    message += "\nЧтобы выбрать проект, используйте /select_project <ID>."
    await update.message.reply_text(message)

async def select_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Selects a project to work on."""
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите ID проекта. Пример: /select_project 1")
        return

    try:
        project_id = int(context.args[0])
        projects = db.list_projects()
        project_ids = [p['id'] for p in projects]

        if project_id not in project_ids:
            await update.message.reply_text("Проект с таким ID не найден.")
            return

        context.user_data['selected_project_id'] = project_id
        project_name = next((p['name'] for p in projects if p['id'] == project_id), "")
        await update.message.reply_text(f"Выбран проект: '{project_name}' (ID: {project_id}). Теперь вы можете присылать мне задачи.")
    except (ValueError, IndexError):
        await update.message.reply_text("Неверный формат ID. Укажите число.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user tasks, but only if a project is selected."""
    project_id = context.user_data.get('selected_project_id')
    if not project_id:
        await update.message.reply_text("Пожалуйста, сначала выберите проект с помощью /select_project <ID> или создайте новый с /new_project.")
        return

    task_description = update.message.text
    logger.info(f"Received task for project {project_id}: {task_description}")
    await update.message.reply_text(f"Получил задачу: '{task_description}'. Думаю над планом...")

    try:
        # Get project history
        history = db.get_project_history(project_id)

        gemini_client = context.bot_data["gemini_client"]
        command_string = gemini_client.get_commands(task_description, history)
        commands = [cmd for cmd in command_string.split('\n') if cmd.strip()]

        if not commands:
            await update.message.reply_text("Не удалось составить план команд. Попробуйте переформулировать.")
            return

        # Create a new task in the database and store its ID
        plan_str = "\n".join(commands)
        task_id = db.create_task(project_id, task_description, plan_str)
        if not task_id:
            await update.message.reply_text("Не удалось сохранить задачу в базе данных.")
            return

        # Use the task_id for the callback data
        context.chat_data[task_id] = commands

        plan_text = "Вот план, который я предлагаю:\n\n```\n" + plan_str + "\n```"
        keyboard = [
            [
                InlineKeyboardButton("✅ Выполнить", callback_data=f"confirm_{task_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"cancel_{task_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(plan_text, reply_markup=reply_markup, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"An error occurred in handle_message: {e}")
        await update.message.reply_text(f"Произошла ошибка: {e}")


async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the user's choice and executes commands."""
    query = update.callback_query
    await query.answer()

    action, task_id_str = query.data.split('_')
    task_id = int(task_id_str)

    commands = context.chat_data.pop(task_id, None)

    if action == "cancel":
        # TODO: Update task status to 'cancelled' in the database
        await query.edit_message_text(text="План выполнения отклонен.")
        return

    if not commands:
        await query.edit_message_text(text="Не удалось найти план. Возможно, сессия истекла.")
        return

    await query.edit_message_text(text="План принят. Выполняю команды...")

    results = execute_commands(commands)
    log_json = json.dumps(results, indent=2)

    # Save execution log to the database
    db.update_task_log(task_id, log_json)

    report = "--- Отчет о выполнении ---\n\n"
    for res in results:
        report += f"Команда: `{res['command']}`\n"
        report += f"Код возврата: {res['returncode']}\n"
        if res['stdout']:
            report += f"Вывод (stdout):\n```\n{res['stdout']}\n```\n"
        if res['stderr']:
            report += f"Ошибки (stderr):\n```\n{res['stderr']}\n```\n"
        report += "---\n"

    if len(report) > 4096:
        report = report[:4000] + "\n... (отчет был обрезан)"

    await query.message.reply_text(report, parse_mode='Markdown')


def main() -> None:
    """Initializes and starts the bot."""
    # --- Critical Setup ---
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("FATAL: Environment variable TELEGRAM_BOT_TOKEN is not set.")
        return
    if not GEMINI_API_KEY:
        logger.critical("FATAL: Environment variable GEMINI_API_KEY is not set.")
        return

    # Initialize the database
    db.initialize_database()

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Store the Gemini client in bot_data
    application.bot_data["gemini_client"] = GeminiClient(api_key=GEMINI_API_KEY)

    # --- Add Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new_project", new_project))
    application.add_handler(CommandHandler("list_projects", list_projects))
    application.add_handler(CommandHandler("select_project", select_project))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(confirm|cancel)_"))

    # Run the bot
    logger.info("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()