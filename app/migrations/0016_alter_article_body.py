from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_squashed_0015_remove_subscription_user_alter_article_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='article',
            name='body',
            field=models.TextField(verbose_name='Текст', default="Текст появится позже"),
            preserve_default=False,
        ),
    ]
