from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("app", "0007_create_articles_materials"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS app_material_slug_c087ef9f_like;",
            reverse_sql="",
        ),
    ]
