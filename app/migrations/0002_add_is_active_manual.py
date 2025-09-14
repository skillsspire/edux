from django.db import migrations, models

def add_is_active_if_missing(apps, schema_editor):
    """
    Безопасно добавляет колонку category.is_active, если её нет.
    Работает на SQLite/Postgres/MySQL без IF EXISTS.
    """
    connection = schema_editor.connection
    table_name = 'app_category'

    # Получаем список колонок таблицы
    try:
        cursor = connection.cursor()
        description = connection.introspection.get_table_description(cursor, table_name)
        existing_columns = {col.name for col in description}
    except Exception:
        existing_columns = set()

    if 'is_active' not in existing_columns:
        Category = apps.get_model('app', 'Category')
        field = models.BooleanField(default=True, verbose_name='Активна')
        field.set_attributes_from_name('is_active')
        # Добавляем поле через schema_editor (кросс-БД)
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
