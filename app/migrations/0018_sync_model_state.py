from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0017_corporate_orders"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="corporateinvitation",
            old_name="app_corpor_order_i_2c1f33_idx",
            new_name="app_corpora_order_i_484511_idx",
        ),
        migrations.RenameIndex(
            model_name="corporateinvitation",
            old_name="app_corpor_email_12417c_idx",
            new_name="app_corpora_email_d70793_idx",
        ),
        migrations.RenameIndex(
            model_name="corporateorder",
            old_name="app_corpor_status_d5f9a9_idx",
            new_name="app_corpora_status_ac8c05_idx",
        ),
        migrations.RenameIndex(
            model_name="corporateorder",
            old_name="app_corpor_organiz_04c9a3_idx",
            new_name="app_corpora_organiz_da2354_idx",
        ),
        migrations.RenameIndex(
            model_name="quizattempt",
            old_name="app_quizatt_user_id_72f4cb_idx",
            new_name="app_quizatt_user_id_bf28dd_idx",
        ),
        migrations.RenameIndex(
            model_name="quizattempt",
            old_name="app_quizatt_quiz_id_d68487_idx",
            new_name="app_quizatt_quiz_id_65ab8a_idx",
        ),
        migrations.AlterField(
            model_name="quizattempt",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, verbose_name="Создано"),
        ),
        migrations.AlterField(
            model_name="quizattempt",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, verbose_name="Обновлено"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Удалён"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="is_deleted",
            field=models.BooleanField(default=False, verbose_name="Удалён"),
        ),
    ]
