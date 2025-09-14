from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('app', '<<здесь останется последняя миграция>>'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE app_course
                DROP COLUMN IF EXISTS created,
                DROP COLUMN IF EXISTS updated;
            """,
            reverse_sql="""
                ALTER TABLE app_course
                ADD COLUMN IF NOT EXISTS created timestamp with time zone NULL,
                ADD COLUMN IF NOT EXISTS updated timestamp with time zone NULL;
            """,
        ),
    ]
