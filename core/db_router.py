# core/db_router.py

import threading

DB_CONTEXT = threading.local()


def set_current_db(db_name):
    DB_CONTEXT.db = db_name


def get_current_db():
    return getattr(DB_CONTEXT, 'db', 'default')  # fallback


class DynamicDBRouter:
    def db_for_read(self, model, **hints):
        return get_current_db()

    def db_for_write(self, model, **hints):
        return get_current_db()

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True  # Allow for both
