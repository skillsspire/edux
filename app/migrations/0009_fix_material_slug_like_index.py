# app/migrations/0009_fix_material_slug_like_index.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("app", "0007_create_articles_materials"),
    ]

    operations = [
        migrations.RunSQL(
            # оставляем только безопасный DROP — без CREATE, чтобы не требовалась колонка заранее
            sql="DROP INDEX IF EXISTS app_material_slug_c087ef9f_like;",
            reverse_sql="",  # no-op
        ),
    ]
