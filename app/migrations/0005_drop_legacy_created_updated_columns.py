from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_course_is_popular_lessonprogress'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE app_course DROP COLUMN IF EXISTS created;
                ALTER TABLE app_course DROP COLUMN IF EXISTS updated;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
