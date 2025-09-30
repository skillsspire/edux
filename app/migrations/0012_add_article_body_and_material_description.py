from django.db import migrations

SQL_UP = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='app_article' AND column_name='body'
    ) THEN
        ALTER TABLE app_article ADD COLUMN body text NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='app_material' AND column_name='description'
    ) THEN
        ALTER TABLE app_material ADD COLUMN description text NULL;
    END IF;
END
$$;
"""

SQL_DOWN = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='app_article' AND column_name='body'
    ) THEN
        ALTER TABLE app_article DROP COLUMN body;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='app_material' AND column_name='description'
    ) THEN
        ALTER TABLE app_material DROP COLUMN description;
    END IF;
END
$$;
"""

class Migration(migrations.Migration):

    dependencies = [
        ("app", "0010_merge_20250929_2243"),
    ]

    operations = [
        migrations.RunSQL(SQL_UP, SQL_DOWN),
    ]
