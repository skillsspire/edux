from django.db import migrations

SQL = r"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_course' AND column_name='created') THEN
        ALTER TABLE app_course DROP COLUMN created;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_course' AND column_name='updated') THEN
        ALTER TABLE app_course DROP COLUMN updated;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_module' AND column_name='created') THEN
        ALTER TABLE app_module DROP COLUMN created;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_module' AND column_name='updated') THEN
        ALTER TABLE app_module DROP COLUMN updated;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_lesson' AND column_name='created') THEN
        ALTER TABLE app_lesson DROP COLUMN created;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_lesson' AND column_name='updated') THEN
        ALTER TABLE app_lesson DROP COLUMN updated;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_enrollment' AND column_name='created') THEN
        ALTER TABLE app_enrollment DROP COLUMN created;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='app_enrollment' AND column_name='updated') THEN
        ALTER TABLE app_enrollment DROP COLUMN updated;
    END IF;
END $$;
"""

REVERSE = r"""
DO $$
BEGIN
    ALTER TABLE app_course ADD COLUMN IF NOT EXISTS created timestamp with time zone NULL;
    ALTER TABLE app_course ADD COLUMN IF NOT EXISTS updated timestamp with time zone NULL;

    ALTER TABLE app_module ADD COLUMN IF NOT EXISTS created timestamp with time zone NULL;
    ALTER TABLE app_module ADD COLUMN IF NOT EXISTS updated timestamp with time zone NULL;

    ALTER TABLE app_lesson ADD COLUMN IF NOT EXISTS created timestamp with time zone NULL;
    ALTER TABLE app_lesson ADD COLUMN IF NOT EXISTS updated timestamp with time zone NULL;

    ALTER TABLE app_enrollment ADD COLUMN IF NOT EXISTS created timestamp with time zone NULL;
    ALTER TABLE app_enrollment ADD COLUMN IF NOT EXISTS updated timestamp with time zone NULL;
END $$;
"""

class Migration(migrations.Migration):

    dependencies = [
        ("app", "0005_drop_legacy_created_updated_columns"),
    ]

    operations = [
        migrations.RunSQL(SQL, reverse_sql=REVERSE),
    ]
