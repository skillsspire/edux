from django.db import migrations
from django.contrib.auth import get_user_model

def create_admin_user(apps, schema_editor):
    User = get_user_model()
    User.objects.create_superuser(
        username='admin_new',
        email='admin@example.com',
        password='NewSecurePassword123!'
    )

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_admin_user),
    ]