"""
Бэкап PostgreSQL через pg_dump внутри контейнера.
Команда /backup доступна только администраторам.
Файл отправляется в чат как документ.
"""
import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("backup"))
async def cmd_backup(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён.")
        return

    status_msg = await message.answer("⏳ Создаю бэкап базы данных...")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{settings.POSTGRES_DB}_{timestamp}.sql"
    filepath = os.path.join(tempfile.gettempdir(), filename)

    env = os.environ.copy()
    env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

    cmd = [
        "pg_dump",
        "-h", settings.POSTGRES_HOST,
        "-p", str(settings.POSTGRES_PORT),
        "-U", settings.POSTGRES_USER,
        "-d", settings.POSTGRES_DB,
        "-F", "p",          # plain SQL
        "--no-password",
        "-f", filepath,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            error = stderr.decode().strip()
            logger.error(f"pg_dump failed: {error}")
            await status_msg.edit_text(f"❌ Ошибка pg_dump:\n<code>{error[:500]}</code>", parse_mode="HTML")
            return

        file_size = os.path.getsize(filepath)
        size_kb = file_size / 1024

        await message.answer_document(
            FSInputFile(filepath, filename=filename),
            caption=(
                f"✅ <b>Бэкап БД</b>\n"
                f"📅 {datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')} UTC\n"
                f"📦 Размер: {size_kb:.1f} KB\n"
                f"🗄 База: <code>{settings.POSTGRES_DB}</code>"
            ),
            parse_mode="HTML",
        )
        await status_msg.delete()

    except asyncio.TimeoutError:
        await status_msg.edit_text("❌ Таймаут pg_dump (>120 сек).")
    except FileNotFoundError:
        await status_msg.edit_text(
            "❌ <b>pg_dump не найден.</b>\n\n"
            "Установите postgresql-client в Dockerfile:\n"
            "<code>apt-get install -y postgresql-client</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception(f"Backup error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {e}")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
