# core/middleware.py

from sales.models import DatabaseMode
from core.db_router import set_current_db

# Global variable to cache the current DB name
CURRENT_DB_NAME = None


def get_current_db_name():
    global CURRENT_DB_NAME
    if CURRENT_DB_NAME is None:
        try:
            config = DatabaseMode.get_solo()
            CURRENT_DB_NAME = 'demo' if config.demo_data else 'default'
        except Exception:
            CURRENT_DB_NAME = 'default'
    return CURRENT_DB_NAME


def set_current_db_name(demo_data):
    global CURRENT_DB_NAME
    CURRENT_DB_NAME = 'demo' if demo_data else 'default'


class ModelBasedDBSwitchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        db_name = get_current_db_name()
        set_current_db(db_name)
        return self.get_response(request)
