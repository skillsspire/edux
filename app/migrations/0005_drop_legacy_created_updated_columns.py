from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("app", "0004_course_is_popular_lessonprogress"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # COURSE
                migrations.RunSQL(
                    "ALTER TABLE app_course DROP COLUMN IF EXISTS created;",
                    reverse_sql="ALTER TABLE app_course ADD COLUMN created timestamp with time zone NULL;"
                ),
                migrations.RunSQL(
                    "ALTER TABLE app_course DROP COLUMN IF EXISTS updated;",
                    reverse_sql="ALTER TABLE app_course ADD COLUMN updated timestamp with time zone NULL;"
                ),

                # MODULE
                migrations.RunSQL(
                    "ALTER TABLE app_module DROP COLUMN IF EXISTS created;",
                    reverse_sql="ALTER TABLE app_module ADD COLUMN created timestamp with time zone NULL;"
                ),
                migrations.RunSQL(
                    "ALTER TABLE app_module DROP COLUMN IF EXISTS updated;",
                    reverse_sql="ALTER TABLE app_module ADD COLUMN updated timestamp with time zone NULL;"
                ),

                # LESSON
                migrations.RunSQL(
                    "ALTER TABLE app_lesson DROP COLUMN IF EXISTS created;",
                    reverse_sql="ALTER TABLE app_lesson ADD COLUMN created timestamp with time zone NULL;"
                ),
                migrations.RunSQL(
                    "ALTER TABLE app_lesson DROP COLUMN IF EXISTS updated;",
                    reverse_sql="ALTER TABLE app_lesson ADD COLUMN updated timestamp with time zone NULL;"
                ),

                # ENROLLMENT (на всякий случай, если были)
                migrations.RunSQL(
                    "ALTER TABLE app_enrollment DROP COLUMN IF EXISTS created;",
                    reverse_sql="ALTER TABLE app_enrollment ADD COLUMN created timestamp with time zone NULL;"
                ),
                migrations.RunSQL(
                    "ALTER TABLE app_enrollment DROP COLUMN IF EXISTS updated;",
                    reverse_sql="ALTER TABLE app_enrollment ADD COLUMN updated timestamp with time zone NULL;"
                ),
            ],
            state_operations=[],
        ),
    ]
