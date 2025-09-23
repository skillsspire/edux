from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("app", "0004_course_is_popular_lessonprogress"),
    ]
    # На SQLite ничего не делаем; на Postgres эту очистку мы когда-нибудь проведём отдельно.
    operations = []
