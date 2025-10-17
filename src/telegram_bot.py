import asyncio
import logging
import os
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Import our custom modules
from gemini_client import GeminiClient
from command_executor import execute_command, execute_commands
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
        mode_status = "✅" if proj.get('programmer_mode') else "❌"
        message += f"- ID: {proj['id']}, Название: {proj['name']} (Режим программиста: {mode_status})\n"
    message += "\nЧтобы выбрать проект, используйте /select_project <ID>."
    message += "\nЧтобы изменить режим, выберите проект и используйте /programmer_mode <on|off>."
    await update.message.reply_text(message)

async def programmer_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles programmer mode for the selected project."""
    project_id = context.user_data.get('selected_project_id')
    if not project_id:
        await update.message.reply_text("Пожалуйста, сначала выберите проект.")
        return

    if not context.args or context.args[0].lower() not in ['on', 'off']:
        await update.message.reply_text("Используйте: /programmer_mode <on|off>")
        return

    enabled = context.args[0].lower() == 'on'
    db.set_programmer_mode(project_id, enabled)
    status = "включен" if enabled else "выключен"
    await update.message.reply_text(f"Режим программиста {status} для текущего проекта.")


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
        project = next((p for p in projects if p['id'] == project_id), None)
        project_name = project['name']

        message = f"Выбран проект: '{project_name}' (ID: {project_id}).\n"

        programmer_mode_enabled = project.get('programmer_mode', 0)
        if programmer_mode_enabled:
            message += "✅ Режим программиста активен. Я буду работать автономно.\n"
        else:
            message += "❌ Режим программиста неактивен. Я буду запрашивать подтверждение для каждого шага.\n"

        message += "Теперь вы можете присылать мне задачи."
        await update.message.reply_text(message)
    except (ValueError, IndexError):
        await update.message.reply_text("Неверный формат ID. Укажите число.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user tasks based on the selected project and its mode."""
    project_id = context.user_data.get('selected_project_id')
    if not project_id:
        await update.message.reply_text("Пожалуйста, сначала выберите проект.")
        return

    task_description = update.message.text
    logger.info(f"Received task for project {project_id}: {task_description}")

    if db.is_programmer_mode_enabled(project_id):
        await update.message.reply_text(f"Получил задачу: '{task_description}'.\n✅ Режим программиста активен. Начинаю автономную работу...")
        asyncio.create_task(run_programmer_mode_session(project_id, task_description, update, context))
    else:
        await update.message.reply_text(f"Получил задачу: '{task_description}'.\nДумаю над планом...")
        await handle_standard_mode(project_id, task_description, update, context)

async def handle_standard_mode(project_id: int, task_description: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles task in standard mode with user confirmation."""
    try:
        history = db.get_project_history(project_id)
        gemini_client = context.bot_data["gemini_client"]

        command_string = gemini_client.get_commands(task_description, history, is_programmer_mode=False)
        commands = [cmd for cmd in command_string.split('\n') if cmd.strip()]

        if not commands:
            await update.message.reply_text("Не удалось составить план. Попробуйте переформулировать.")
            return

        plan_str = "\n".join(commands)
        task_id = db.create_task(project_id, task_description, plan_str)
        context.chat_data[task_id] = commands

        plan_text = "Вот план, который я предлагаю:\n\n```\n" + plan_str + "\n```"
        keyboard = [[
            InlineKeyboardButton("✅ Выполнить", callback_data=f"confirm_{task_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"cancel_{task_id}"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(plan_text, reply_markup=reply_markup, parse_mode='MarkdownV2')

    except Exception as e:
        logger.error(f"An error occurred in handle_standard_mode: {e}")
        await update.message.reply_text(f"Произошла ошибка: {e}")


async def run_programmer_mode_session(project_id: int, task_description: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs a task autonomously in programmer mode."""
    gemini_client = context.bot_data["gemini_client"]
    history = db.get_project_history(project_id)
    task_id = db.create_task(project_id, task_description, "Autonomous session")

    last_command_output = None
    full_log = []
    max_steps = 20 # Safety break

    for i in range(max_steps):
        await update.message.reply_text(f"Шаг {i+1}/{max_steps}. Думаю над следующей командой...")

        command_to_execute = gemini_client.get_commands(
            task_description, history, is_programmer_mode=True, last_command_output=last_command_output
        )

        if not command_to_execute or command_to_execute.strip().upper() == "TASK_COMPLETE":
            await update.message.reply_text("✅ Задача выполнена.")
            db.update_task_log(task_id, json.dumps(full_log, indent=2))
            return

        await update.message.reply_text(f"Выполняю команду:\n```\n{command_to_execute}\n```", parse_mode='MarkdownV2')
        result = execute_command(command_to_execute)

        # Format output for the next AI prompt and for the user
        last_command_output = (
            f"Command: {result['command']}\n"
            f"Return Code: {result['returncode']}\n"
            f"STDOUT:\n{result['stdout']}\n"
            f"STDERR:\n{result['stderr']}\n"
        )
        full_log.append(result)

        report_message = f"Отчет по шагу {i+1}:\n" + f"```\n{last_command_output}\n```"
        if len(report_message) > 4096:
            report_message = report_message[:4000] + "\n... (отчет был обрезан)"
        await update.message.reply_text(report_message, parse_mode='MarkdownV2')

        # Update history for the next iteration
        history.append({
            "description": f"Step {i+1} of '{task_description}'",
            "plan": command_to_execute,
            "execution_log": json.dumps(result),
            "status": "completed"
        })

    await update.message.reply_text("⚠️ Достигнуто максимальное количество шагов. Сессия завершена.")
    db.update_task_log(task_id, json.dumps(full_log, indent=2))


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
    application.add_handler(CommandHandler("programmer_mode", programmer_mode))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(confirm|cancel)_"))

    # Run the bot
    logger.info("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()