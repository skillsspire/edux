# app/migrations/0011_add_material_slug_like_index.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("app", "0010_merge_20250929_2243"),  # было ("app", "0008_add_excerpt_slug")
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS app_material_slug_c087ef9f_like
            ON app_material (slug text_pattern_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS app_material_slug_c087ef9f_like;",
        ),
    ]
