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
        Самовосстановление схемы БД для продакшена на Postgres.
        Идемпотентно (IF NOT EXISTS), безопасно для повторных запусков.
        Отключить можно переменной окружения RUN_SCHEMA_ENSURE=0.
        """
        if os.environ.get('RUN_SCHEMA_ENSURE', '1') != '1':
            return

        engine = settings.DATABASES['default']['ENGINE']
        if 'postgresql' not in engine:
            # На SQLite/локали ничего не делаем — миграции покрывают всё.
            return

        def get_col_type(table: str, column: str = 'id', default_type: str = 'bigint') -> str:
            """
            Возвращает фактический тип колонки (например, 'bigint' или 'integer'),
            чтобы FK/колонки совпадали по типам.
            """
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT format_type(a.atttypid, a.atttypmod)
                    FROM pg_attribute a
                    WHERE a.attrelid = %s::regclass
                      AND a.attname  = %s
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                    """,
                    [f'public.{table}', column],
                )
                row = cur.fetchone()
                return (row[0] if row else default_type).lower()

        try:
            # 1) app_category.is_active
            with connection.cursor() as cur:
                cur.execute("""
                    ALTER TABLE app_category
                    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_category_is_active_idx
                    ON app_category (is_active);
                """)

            # 2) app_category."order"
            with connection.cursor() as cur:
                cur.execute("""
                    ALTER TABLE app_category
                    ADD COLUMN IF NOT EXISTS "order" integer NOT NULL DEFAULT 0;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_category_order_idx
                    ON app_category ("order");
                """)

            # 3) many-to-many таблица студентов: app_course_students
            course_pk_type = get_col_type('app_course', 'id', 'bigint')
            user_pk_type   = get_col_type('auth_user', 'id',  'bigint')

            with connection.cursor() as cur:
                # сама таблица (если ранее не была создана миграциями)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS app_course_students (
                        id bigserial PRIMARY KEY,
                        course_id {course_pk_type} NOT NULL,
                        user_id   {user_pk_type}   NOT NULL
                    );
                """)
                # уникальность пары (course, user)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint c
                            JOIN pg_class t ON t.oid = c.conrelid
                            WHERE c.conname = 'app_course_students_course_user_uniq'
                        ) THEN
                            ALTER TABLE app_course_students
                            ADD CONSTRAINT app_course_students_course_user_uniq
                            UNIQUE (course_id, user_id);
                        END IF;
                    END$$;
                """)
                # индексы
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_course_students_course_idx
                    ON app_course_students (course_id);
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_course_students_user_idx
                    ON app_course_students (user_id);
                """)
                # внешние ключи
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'app_course_students_course_fk'
                        ) THEN
                            ALTER TABLE app_course_students
                            ADD CONSTRAINT app_course_students_course_fk
                            FOREIGN KEY (course_id)
                            REFERENCES app_course(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'app_course_students_user_fk'
                        ) THEN
                            ALTER TABLE app_course_students
                            ADD CONSTRAINT app_course_students_user_fk
                            FOREIGN KEY (user_id)
                            REFERENCES auth_user(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                    END$$;
                """)

            # 4) FK на преподавателя у курса: app_course.instructor_id -> auth_user.id
            with connection.cursor() as cur:
                cur.execute(f"""
                    ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS instructor_id {user_pk_type} NULL;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_course_instructor_id_idx
                    ON app_course (instructor_id);
                """)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'app_course_instructor_id_fk'
                        ) THEN
                            ALTER TABLE app_course
                            ADD CONSTRAINT app_course_instructor_id_fk
                            FOREIGN KEY (instructor_id)
                            REFERENCES auth_user(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                    END$$;
                """)

            log.info("Schema ensure OK: categories + m2m + instructor_id готовы.")

        except Exception as e:
            # Не валим приложение: просто логируем, чтобы сайт продолжал работать.
            log.warning("Schema ensure failed/skipped: %s", e)
