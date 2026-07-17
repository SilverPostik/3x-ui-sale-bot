"""
Восстановление БД бота из панели 3x-ui после потери Postgres.

Что восстанавливается:
- users        — по паттерну email клиента "tg<user_id>" (так бот всегда называет
                 клиентов), username/full_name бот сам подтянет при следующем
                 обращении пользователя (см. bot/middlewares/user_middleware.py)
- subscriptions — expires_at, xui_client_id, xui_inbound_id, xui_sub_id,
                  subscription_url, is_active — восстанавливаются из данных клиента
                  в панели. Клиенты с одним UUID, встреченные в нескольких
                  inbound'ах, схлопываются в одну подписку (мультиinbound).

Что НЕ восстанавливается (в панели этого не было и быть не может):
- payments (история платежей/доход) — если платежи шли через Platega,
  историю транзакций можно выгрузить в личном кабинете Platega отдельно,
  но в БД бота она сама не попадёт.
- promocodes / promocode_activations — история промокодов.
- plan_months — сколько месяцев/дней было куплено изначально (в панели этого
  нет, есть только текущий expiryTime) — ставится 0 ("неизвестно").
- notified_7d/3d/1d — флаги уведомлений об истечении, ставятся в False
  (в худшем случае кто-то получит одно лишнее уведомление, не критично).

Скрипт идемпотентен: повторный запуск не создаёт дублей — если подписка
с данным xui_client_id уже есть в БД, она пропускается.

ИСПОЛЬЗОВАНИЕ (миграции применяются автоматически, отдельный шаг не нужен):
    # Просмотреть, что будет восстановлено, ничего не меняя в БД:
    docker compose run --rm bot python scripts/recover_from_panel.py

    # Реально записать в БД:
    docker compose run --rm bot python scripts/recover_from_panel.py --apply
"""
import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from database.engine import AsyncSessionLocal
from database.models.user import User
from database.models.subscription import Subscription
from bot.services.xui_client import xui_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("recover")

EMAIL_RE = re.compile(r"^tg(\d+)$")


def ensure_schema() -> None:
    """
    Применяет alembic-миграции (upgrade head) синхронно, до старта async-кода.
    Скрипт может запускаться до первого старта бота — не полагаемся на то,
    что main.py уже успел это сделать. Без этого шага таблицы users/subscriptions
    могут просто отсутствовать (именно так выглядела ошибка
    "relation subscriptions does not exist"). Безопасно вызывать повторно:
    если схема уже актуальна, alembic ничего не делает.
    """
    from alembic.config import Config
    from alembic import command

    project_root = Path(__file__).resolve().parent.parent
    logger.info("Применяю alembic-миграции (upgrade head)...")
    cfg = Config(str(project_root / "migrations" / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "migrations"))
    try:
        command.upgrade(cfg, "head")
        # См. main.py::run_migrations — fileConfig() из alembic.ini отключает
        # (.disabled=True) все уже существующие логгеры, не только root.
        for _name in list(logging.Logger.manager.loggerDict.keys()):
            logging.getLogger(_name).disabled = False
        logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s", force=True)
        logger.info("Миграции применены (или уже были актуальны) ✓")
    except Exception as e:
        logger.error(f"Не удалось применить миграции: {e}")
        logger.error(
            "Проверьте, что контейнер db поднят и доступен "
            "(POSTGRES_HOST/POSTGRES_PORT/POSTGRES_PASSWORD в .env верны)."
        )
        raise


async def collect_clients() -> dict[str, dict]:
    """
    Обходит ВСЕ inbound'ы в панели (не только перечисленные сейчас в
    REALITY_INBOUND_ID — конфиг мог измениться с момента создания клиентов)
    и группирует клиентов по UUID.
    Возвращает {uuid: {"email", "expiryTime", "subId", "enable", "limitIp", "inbound_ids": set}}
    """
    groups: dict[str, dict] = {}

    inbounds = await xui_client.get_inbounds()
    if not inbounds:
        logger.error("Панель вернула пустой список inbound'ов — проверь THREEXUI_URL/логин/пароль в .env")
        return groups

    logger.info(f"Найдено inbound'ов в панели: {len(inbounds)}")

    for inbound in inbounds:
        iid = inbound.get("id")
        raw = inbound.get("settings")
        if not raw:
            continue
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.error(f"Не удалось распарсить settings inbound #{iid}: {e}")
            continue

        clients = parsed.get("clients") or []
        logger.info(f"Inbound #{iid} ({inbound.get('remark', '—')}): найдено {len(clients)} клиентов")

        for c in clients:
            uuid = c.get("id")
            if not uuid:
                continue
            g = groups.setdefault(uuid, {
                "email": c.get("email", ""),
                "expiryTime": c.get("expiryTime", 0),
                "subId": c.get("subId", ""),
                "enable": c.get("enable", True),
                "limitIp": c.get("limitIp", 1),
                "inbound_ids": set(),
            })
            g["inbound_ids"].add(iid)
            # На случай расхождений между копиями в разных inbound'ах — берём
            # максимальный expiry и subId/email первого непустого значения.
            if c.get("expiryTime", 0) > g["expiryTime"]:
                g["expiryTime"] = c.get("expiryTime", 0)
            if not g["subId"] and c.get("subId"):
                g["subId"] = c.get("subId")

    return groups


async def main(apply: bool) -> None:
    logger.info(f"Режим: {'ЗАПИСЬ В БД' if apply else 'DRY-RUN (просмотр, без изменений)'}")

    groups = await collect_clients()
    logger.info(f"Всего уникальных клиентов (по UUID) в панели: {len(groups)}")

    now = datetime.now(timezone.utc)
    restored, skipped_existing, skipped_unmatched = 0, 0, 0

    async with AsyncSessionLocal() as session:
        for uuid, g in groups.items():
            email = g["email"]
            m = EMAIL_RE.match(email)
            if not m:
                logger.warning(f"Пропускаю: email='{email}' не похож на клиента бота (uuid={uuid})")
                skipped_unmatched += 1
                continue

            user_id = int(m.group(1))

            existing = await session.execute(
                select(Subscription).where(Subscription.xui_client_id == uuid)
            )
            if existing.scalar_one_or_none():
                logger.info(f"user_id={user_id}: подписка с xui_client_id={uuid} уже есть в БД, пропускаю")
                skipped_existing += 1
                continue

            expiry_ms = g["expiryTime"]
            if expiry_ms and expiry_ms > 0:
                expires_at = datetime.fromtimestamp(expiry_ms / 1000, tz=timezone.utc)
            else:
                # expiryTime=0 в 3x-ui означает "без ограничения срока" — такого
                # в обычном платном/промо-флоу этого бота не бывает, но на всякий
                # случай не роняем восстановление, а ставим далёкую дату и подсвечиваем.
                expires_at = now.replace(year=now.year + 5)
                logger.warning(f"user_id={user_id}: expiryTime=0 (без срока), ставлю +5 лет — проверьте вручную")

            is_active = bool(g["enable"]) and expires_at > now
            inbound_ids = sorted(g["inbound_ids"])
            sub_id = g["subId"]
            sub_url = xui_client.build_subscription_url(sub_id) if sub_id else None

            logger.info(
                f"user_id={user_id}: expires_at={expires_at.isoformat()} "
                f"active={is_active} inbounds={inbound_ids} sub_id={sub_id}"
            )

            if not apply:
                restored += 1
                continue

            user = await session.get(User, user_id)
            if not user:
                user = User(id=user_id)
                session.add(user)

            sub = Subscription(
                user_id=user_id,
                plan_months=0,  # неизвестно, в панели этой информации нет
                expires_at=expires_at,
                is_active=is_active,
                xui_client_id=uuid,
                xui_inbound_id=Subscription.format_inbound_ids(inbound_ids),
                xui_sub_id=sub_id,
                subscription_url=sub_url,
                devices=g["limitIp"] or 1,
                inbound_type="vless_reality",
            )
            session.add(sub)
            restored += 1

        if apply:
            await session.commit()

    logger.info("─" * 50)
    logger.info(f"Восстановлено: {restored}")
    logger.info(f"Уже были в БД (пропущены): {skipped_existing}")
    logger.info(f"Не похожи на клиентов бота (пропущены): {skipped_unmatched}")
    if not apply:
        logger.info("Это был DRY-RUN — ничего не записано. Запустите с флагом --apply.")


if __name__ == "__main__":
    ensure_schema()
    apply_flag = "--apply" in sys.argv
    asyncio.run(main(apply_flag))
