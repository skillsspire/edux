from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("app", "0002_add_is_active_manual"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE app_category
                ADD COLUMN IF NOT EXISTS "order" integer NOT NULL DEFAULT 0;
                CREATE INDEX IF NOT EXISTS app_category_order_idx ON app_category ("order");
            """,
            reverse_sql="",
        ),
    ]
