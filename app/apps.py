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
        Самолечащаяся схема БД для продакшена на Postgres.
        - Безопасно и идемпотентно (IF NOT EXISTS).
        - Отключается переменной окружения RUN_SCHEMA_ENSURE=0.
        """
        if os.environ.get('RUN_SCHEMA_ENSURE', '1') != '1':
            return

        engine = settings.DATABASES['default']['ENGINE']
        if 'postgresql' not in engine:
            # На SQLite/локалке полагаемся на миграции.
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
            # ------------------------------------------------------
            # 1) Категории: is_active + order (+ индексы)
            # ------------------------------------------------------
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

            # ------------------------------------------------------
            # 2) Курсы: гарантируем недостающие колонки
            # ------------------------------------------------------
            with connection.cursor() as cur:
                # Базовые поля
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS short_description text NOT NULL DEFAULT '';""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS description       text NOT NULL DEFAULT '';""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS price             numeric(10,2) NOT NULL DEFAULT 0;""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS discount_price    numeric(10,2) NULL;""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS duration          varchar(50) NOT NULL DEFAULT '';""")
                # Файлы/картинки как текстовый путь (совместимо с ImageField/FileField)
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS image             text NULL;""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS thumbnail         text NULL;""")
                # Прочие флаги/статусы
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS level             varchar(20) NOT NULL DEFAULT 'beginner';""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS status            varchar(20) NOT NULL DEFAULT 'draft';""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS is_featured       boolean NOT NULL DEFAULT false;""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS requirements      text NOT NULL DEFAULT '';""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS what_you_learn    text NOT NULL DEFAULT '';""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS language          varchar(50) NOT NULL DEFAULT 'Русский';""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS certificate       boolean NOT NULL DEFAULT true;""")
                # Таймстемпы
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS created_at        timestamptz NOT NULL DEFAULT now();""")
                cur.execute("""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS updated_at        timestamptz NOT NULL DEFAULT now();""")

            # ------------------------------------------------------
            # 3) M2M студентов (если нет): app_course_students
            # ------------------------------------------------------
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
                cur.execute("""CREATE INDEX IF NOT EXISTS app_course_students_course_idx ON app_course_students (course_id);""")
                cur.execute("""CREATE INDEX IF NOT EXISTS app_course_students_user_idx   ON app_course_students (user_id);""")
                cur.execute(f"""
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

            # ------------------------------------------------------
            # 4) FK на преподавателя: app_course.instructor_id -> auth_user.id
            # ------------------------------------------------------
            with connection.cursor() as cur:
                cur.execute(f"""ALTER TABLE app_course ADD COLUMN IF NOT EXISTS instructor_id {user_pk_type} NULL;""")
                cur.execute("""CREATE INDEX IF NOT EXISTS app_course_instructor_id_idx ON app_course (instructor_id);""")
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

            # ------------------------------------------------------
            # 5) Отзывы: app_review (для Course.reviews/average_rating)
            # ------------------------------------------------------
            with connection.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS app_review (
                        id bigserial PRIMARY KEY,
                        course_id {course_pk_type} NOT NULL,
                        user_id   {user_pk_type}   NOT NULL,
                        rating integer NOT NULL CHECK (rating >= 1 AND rating <= 5),
                        comment text NOT NULL,
                        is_active boolean NOT NULL DEFAULT true,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        updated_at timestamptz NOT NULL DEFAULT now()
                    );
                """)
                cur.execute("""CREATE INDEX IF NOT EXISTS app_review_course_idx ON app_review (course_id);""")
                cur.execute("""CREATE INDEX IF NOT EXISTS app_review_user_idx   ON app_review (user_id);""")
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'app_review_course_user_uniq'
                        ) THEN
                            ALTER TABLE app_review
                            ADD CONSTRAINT app_review_course_user_uniq
                            UNIQUE (course_id, user_id);
                        END IF;

                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'app_review_course_fk'
                        ) THEN
                            ALTER TABLE app_review
                            ADD CONSTRAINT app_review_course_fk
                            FOREIGN KEY (course_id)
                            REFERENCES app_course(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;

                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'app_review_user_fk'
                        ) THEN
                            ALTER TABLE app_review
                            ADD CONSTRAINT app_review_user_fk
                            FOREIGN KEY (user_id)
                            REFERENCES auth_user(id)
                            ON DELETE CASCADE
                            DEFERRABLE INITIALLY DEFERRED;
                        END IF;
                    END$$;
                """)

            log.info("Schema ensure OK: categories, course columns, m2m students, instructor FK, reviews — готовы.")

        except Exception as e:
            # Не валим приложение: просто логируем, чтобы сайт продолжал работать.
            log.warning("Schema ensure failed/skipped: %s", e)
