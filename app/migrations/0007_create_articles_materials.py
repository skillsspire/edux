from django.db import migrations, models
import django.utils.timezone
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_wishlist_created_at_and_fill_kaspi'),
    ]

    operations = [
        migrations.CreateModel(
            name='Article',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('slug', models.SlugField(unique=True, db_index=True)),
                ('content', models.TextField(blank=True)),
                ('status', models.CharField(max_length=20, choices=[('draft', 'Draft'), ('published', 'Published')], default='draft')),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-published_at', '-created_at']},
        ),
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('file', models.FileField(upload_to='materials/')),
                ('is_public', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
