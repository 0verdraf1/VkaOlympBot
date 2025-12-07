from aiogram import Router
from .admin_reply import router_reply
from .admin_to_user import admin_to_user
from .call_organizer import call
from .get_creds import get_creds
from .registration import registration
from .search_dialog import search
from .start_admin import start_admin
from .start_broadcast import broad
from .user_to_admin import user_to_admin
from .type_call.report import user_rep
from .type_call.help import user_help
from .common import common_router


router = Router()

router.include_router(router_reply)
router.include_router(admin_to_user)
router.include_router(call)
router.include_router(get_creds)
router.include_router(registration)
router.include_router(search)
router.include_router(start_admin)
router.include_router(broad)
router.include_router(user_to_admin)
router.include_router(user_rep)
router.include_router(user_help)
router.include_router(common_router)
