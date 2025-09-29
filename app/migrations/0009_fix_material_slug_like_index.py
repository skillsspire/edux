from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("app", "0008_add_excerpt_slug"),
    ]

    operations = [
        # Удаляем лишний *_like индекс, если он вдруг есть; если нет — просто ничего не делаем
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS app_material_slug_c087ef9f_like;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
