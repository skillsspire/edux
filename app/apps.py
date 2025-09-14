# app/apps.py
import os
import logging
from django.apps import AppConfig
from django.conf import settings
from django.db import connection

log = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        """
        Гарантируем, что в Postgres есть колонка app_category.is_active.
        На SQLite/локалке (если не Postgres) — ничего не делаем.
        Идемпотентно (IF NOT EXISTS), безопасно при повторных запусках.
        """
        if os.environ.get('RUN_SCHEMA_ENSURE', '1') != '1':
            return

        engine = settings.DATABASES['default']['ENGINE']
        if 'postgresql' not in engine:
            return

        try:
            with connection.cursor() as cur:
                cur.execute("""
                    ALTER TABLE app_category
                    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_category_is_active_idx
                    ON app_category (is_active);
                """)
                cur.execute('ALTER TABLE app_category ADD COLUMN IF NOT EXISTS "order" integer NOT NULL DEFAULT 0;')
                cur.execute('CREATE INDEX IF NOT EXISTS app_category_order_idx ON app_category ("order");')
            log.info("Schema ensure ok: app_category.is_active ensured.")
        except Exception as e:
            log.warning("Schema ensure failed/skipped: %s", e)
