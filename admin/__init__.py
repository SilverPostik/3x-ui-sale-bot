from aiogram import Router
from admin.handlers import router as admin_handlers_router
from admin.backup import router as backup_router


def get_admin_router() -> Router:
    router = Router()
    router.include_router(admin_handlers_router)
    router.include_router(backup_router)
    return router


admin_router = get_admin_router()

__all__ = ["admin_router"]
