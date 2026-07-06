from aiogram import Router
from bot.handlers import start, profile, connect, instruction, support, promo, payment, legal


def get_main_router() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(profile.router)
    router.include_router(connect.router)
    router.include_router(instruction.router)
    router.include_router(support.router)
    router.include_router(legal.router)
    router.include_router(promo.router)
    router.include_router(payment.router)
    return router
