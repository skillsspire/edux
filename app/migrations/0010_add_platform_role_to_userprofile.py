from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0009_remove_article_author_alter_material_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='platform_role',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('student', 'Студент'),
                    ('support', 'Поддержка'),
                    ('content', 'Контент-менеджер'),
                    ('platform_admin', 'Администратор платформы'),
                ],
                default='student',
                help_text='Глобальная роль на платформе',
            ),
        ),
    ]
