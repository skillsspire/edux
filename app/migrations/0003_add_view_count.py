from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0002_assignment_faq_plan_article_view_count_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='view_count',
            field=models.IntegerField(default=0),
        ),
    ]
