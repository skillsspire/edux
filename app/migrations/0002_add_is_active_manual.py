from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE app_category
                ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
                CREATE INDEX IF NOT EXISTS app_category_is_active_idx ON app_category (is_active);
            """,
            reverse_sql="""
                -- no-op
            """,
        ),
    ]
