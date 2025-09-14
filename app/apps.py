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
        if os.environ.get('RUN_SCHEMA_ENSURE', '1') != '1':
            return

        engine = settings.DATABASES['default']['ENGINE']
        if 'postgresql' not in engine:
            return

        try:
            with connection.cursor() as cur:
                # 1) Категории: is_active
                cur.execute("""
                    ALTER TABLE app_category
                    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_category_is_active_idx
                    ON app_category (is_active);
                """)

                # 2) Категории: "order" (нужны кавычки)
                cur.execute('ALTER TABLE app_category ADD COLUMN IF NOT EXISTS "order" integer NOT NULL DEFAULT 0;')
                cur.execute('CREATE INDEX IF NOT EXISTS app_category_order_idx ON app_category ("order");')

                # 3) M2M: Course.students -> app_course_students
                # Таблица (id BigInt PK, course_id -> app_course.id (bigint), user_id -> auth_user.id (int))
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS app_course_students (
                        id BIGSERIAL PRIMARY KEY,
                        course_id bigint NOT NULL REFERENCES app_course(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
                        user_id integer NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
                    );
                """)
                # Уникальность пары (как в Django-модели)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'app_course_students_course_id_user_id_key'
                        ) THEN
                            ALTER TABLE app_course_students
                            ADD CONSTRAINT app_course_students_course_id_user_id_key
                            UNIQUE (course_id, user_id);
                        END IF;
                    END$$;
                """)
                # Индексы для джойнов/Count()
                cur.execute("""CREATE INDEX IF NOT EXISTS app_course_students_course_id_idx ON app_course_students (course_id);""")
                cur.execute("""CREATE INDEX IF NOT EXISTS app_course_students_user_id_idx   ON app_course_students (user_id);""")

            log.info("Schema ensure ok: category columns & app_course_students ensured.")
        except Exception as e:
            log.warning("Schema ensure failed/skipped: %s", e)
