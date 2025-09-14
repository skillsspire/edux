from django.db import migrations, models

def add_is_active_if_missing(apps, schema_editor):
    """
    Кросс-БД добавление app_category.is_active, только если колонки ещё нет.
    Без IF EXISTS, работает на SQLite/Postgres/MySQL.
    """
    connection = schema_editor.connection
    table_name = 'app_category'

    # Узнаём, какие колонки уже есть у таблицы
    try:
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(cursor, table_name)
        existing_columns = {col.name for col in description}
    except Exception:
        existing_columns = set()

    if 'is_active' not in existing_columns:
        Category = apps.get_model('app', 'Category')
        field = models.BooleanField(default=True, verbose_name='Активна')
        field.set_attributes_from_name('is_active')
        schema_editor.add_field(Category, field)

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_is_active_if_missing, reverse_code=migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='category',
                    name='is_active',
                    field=models.BooleanField(default=True, verbose_name='Активна'),
                ),
            ],
        ),
    ]
