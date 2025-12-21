from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0011_alter_userprofile_platform_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='deleted_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
