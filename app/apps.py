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
        Самовосстановление схемы БД на Postgres.
        - Идемпотентно (IF NOT EXISTS), безопасно при повторных запусках.
        - Отключается RUN_SCHEMA_ENSURE=0.
        На SQLite/локали — ничего не делаем.
        """
        if os.environ.get('RUN_SCHEMA_ENSURE', '1') != '1':
            return

        engine = settings.DATABASES['default'].get('ENGINE', '')
        if 'postgresql' not in engine:
            return

        def get_col_type(table: str, column: str = 'id', default_type: str = 'bigint') -> str:
            """Вернуть реальный тип колонки (bigint/integer), чтобы FK совпадали по типам."""
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
            # 1) Категории: is_active + order
            with connection.cursor() as cur:
                cur.execute("""
                    ALTER TABLE app_category
                    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_category_is_active_idx
                    ON app_category (is_active);
                """)
                cur.execute("""
                    ALTER TABLE app_category
                    ADD COLUMN IF NOT EXISTS "order" integer NOT NULL DEFAULT 0;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_category_order_idx
                    ON app_category ("order");
                """)

            # 2) M2M студентов: app_course_students (для Course.students)
            course_pk_type = get_col_type('app_course', 'id', 'bigint')
            user_pk_type   = get_col_type('auth_user', 'id',  'bigint')

            with connection.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS app_course_students (
                        id bigserial PRIMARY KEY,
                        course_id {course_pk_type} NOT NULL,
                        user_id   {user_pk_type}   NOT NULL
                    );
                """)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'app_course_students_course_user_uniq'
                        ) THEN
                            ALTER TABLE app_course_students
                            ADD CONSTRAINT app_course_students_course_user_uniq
                            UNIQUE (course_id, user_id);
                        END IF;
                    END$$;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_course_students_course_idx
                    ON app_course_students (course_id);
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS app_course_students_user_idx
                    ON app_course_students (user_id);
                """)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'app_course_students_course_fk') THEN
                            ALTER TABLE app_course_students
                            ADD CONSTRAINT app_course_students_course_fk
                            FOREIGN KEY (course_id)
                            REFERENCES app_course(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'app_course_students_user_fk') THEN
                            ALTER TABLE app_course_students
                            ADD CONSTRAINT app_course_students_user_fk
                            FOREIGN KEY (user_id)
                            REFERENCES auth_user(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                    END$$;
                """)

            # 3) FK на преподавателя: app_course.instructor_id -> auth_user.id
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
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'app_course_instructor_id_fk') THEN
                            ALTER TABLE app_course
                            ADD CONSTRAINT app_course_instructor_id_fk
                            FOREIGN KEY (instructor_id)
                            REFERENCES auth_user(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                    END$$;
                """)

            # 4) Все недостающие поля Course (чтобы ORM не падал на SELECT *)
            with connection.cursor() as cur:
                # тексты/числа
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS short_description text NOT NULL DEFAULT '';
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS description text NOT NULL DEFAULT '';
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS price numeric(10,2) NOT NULL DEFAULT 0;
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS discount_price numeric(10,2) NULL;
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS duration varchar(50) NOT NULL DEFAULT '';
                """)
                # файлы (пути к изображениям)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS image varchar(100) NULL;
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS thumbnail varchar(100) NULL;
                """)
                # статусы/флаги
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS level varchar(20) NOT NULL DEFAULT 'beginner';
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS status varchar(20) NOT NULL DEFAULT 'draft';
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS is_featured boolean NOT NULL DEFAULT false;
                """)
                # доп. поля
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS requirements text NOT NULL DEFAULT '';
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS what_you_learn text NOT NULL DEFAULT '';
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS language varchar(50) NOT NULL DEFAULT 'Русский';
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS certificate boolean NOT NULL DEFAULT true;
                """)
                # таймстемпы (на случай отсутствия)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
                """)
                cur.execute("""ALTER TABLE app_course
                    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
                """)

            log.info("Schema ensure OK: categories, m2m, instructor_id, all course columns.")

        except Exception as e:
            # Не валим приложение, просто логируем.
            log.warning("Schema ensure failed/skipped: %s", e)
