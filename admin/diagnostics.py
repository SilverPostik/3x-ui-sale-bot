"""
Команды диагностики для администраторов.
/ping  — проверить соединение с 3x-ui
/xui   — показать список inbound'ов
"""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.xui_client import xui_client
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    msg = await message.answer("⏳ Проверяю соединение с 3x-ui...")

    if not await xui_client.ping():
        await msg.edit_text(
            f"❌ <b>Ошибка авторизации 3x-ui</b>\n\n"
            f"URL: <code>{settings.THREEXUI_URL}</code>\n"
            f"Проверьте THREEXUI_URL, THREEXUI_USERNAME, THREEXUI_PASSWORD или THREEXUI_API_TOKEN в .env",
            parse_mode="HTML",
        )
        return

    inbounds = await xui_client.get_inbounds()
    found = {i.get("id"): i for i in inbounds if i.get("id") in settings.REALITY_INBOUND_ID}
    missing = [iid for iid in settings.REALITY_INBOUND_ID if iid not in found]

    if found and not missing:
        status = "✅"
    elif found:
        status = "⚠️"
    else:
        status = "❌"

    lines = []
    for iid in settings.REALITY_INBOUND_ID:
        inb = found.get(iid)
        if inb:
            lines.append(f"✅ #{iid}: <b>{inb.get('remark', '—')}</b> port={inb.get('port')}")
        else:
            lines.append(f"⚠️ #{iid}: НЕ найден")
    inbound_info = "\n".join(lines)
    if missing:
        inbound_info += f"\n\nДоступные inbound ID: {[i.get('id') for i in inbounds]}"

    await msg.edit_text(
        f"{status} <b>3x-ui соединение</b>\n\n"
        f"URL: <code>{settings.THREEXUI_URL}</code>\n"
        f"Авторизация: ✅\n"
        f"Inbound'ы:\n{inbound_info}\n\n"
        f"Всего inbound'ов в панели: {len(inbounds)}",
        parse_mode="HTML",
    )


@router.message(Command("xui"))
async def cmd_xui(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    msg = await message.answer("⏳ Получаю список inbound'ов...")
    inbounds = await xui_client.get_inbounds()
    if not inbounds:
        await msg.edit_text("❌ Нет inbound'ов или ошибка соединения.")
        return

    lines = [f"📋 <b>Inbound'ы 3x-ui ({len(inbounds)})</b>\n"]
    for inb in inbounds:
        enabled = "✅" if inb.get("enable") else "❌"
        lines.append(
            f"{enabled} ID={inb.get('id')} | {inb.get('protocol')} | "
            f"port={inb.get('port')} | <b>{inb.get('remark', '—')}</b>"
        )
    await msg.edit_text("\n".join(lines), parse_mode="HTML")
