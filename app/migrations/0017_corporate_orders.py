from decimal import Decimal
import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("app", "0016_userprofile_consents"),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("name", models.CharField(max_length=255, verbose_name="Наименование организации")),
                ("bin", models.CharField(max_length=20, unique=True, verbose_name="БИН")),
                ("legal_address", models.CharField(blank=True, max_length=500, verbose_name="Юридический адрес")),
                ("contact_name", models.CharField(max_length=255, verbose_name="Контактное лицо")),
                ("contact_email", models.EmailField(max_length=254, verbose_name="Email контактного лица")),
                ("contact_phone", models.CharField(max_length=30, verbose_name="Телефон контактного лица")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
            ],
            options={
                "verbose_name": "Организация",
                "verbose_name_plural": "Организации",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CorporateOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("seats_purchased", models.PositiveIntegerField(verbose_name="Количество мест")),
                ("base_unit_price", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Базовая цена за место")),
                ("discount_percent", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5, verbose_name="Корпоративная скидка, %")),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Цена за место после скидки")),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Сумма заказа")),
                ("status", models.CharField(choices=[("requested", "Заявка получена"), ("invoiced", "Счёт выставлен"), ("paid", "Оплачен"), ("cancelled", "Отменён")], default="requested", max_length=20, verbose_name="Статус")),
                ("order_number", models.CharField(blank=True, max_length=40, unique=True, verbose_name="Номер заказа")),
                ("manage_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Токен кабинета заказчика")),
                ("paid_at", models.DateTimeField(blank=True, null=True, verbose_name="Оплачен")),
                ("notes", models.TextField(blank=True, verbose_name="Комментарий")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="corporate_orders", to="app.course", verbose_name="Курс")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="app.organization", verbose_name="Организация")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="corporate_orders_requested", to=settings.AUTH_USER_MODEL, verbose_name="Создал заявку")),
            ],
            options={
                "verbose_name": "Корпоративный заказ",
                "verbose_name_plural": "Корпоративные заказы",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CorporateInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("email", models.EmailField(max_length=254, verbose_name="Email слушателя")),
                ("first_name", models.CharField(max_length=100, verbose_name="Имя")),
                ("last_name", models.CharField(max_length=100, verbose_name="Фамилия")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Токен приглашения")),
                ("status", models.CharField(choices=[("pending", "Приглашён"), ("activated", "Доступ активирован"), ("revoked", "Приглашение отозвано")], default="pending", max_length=20, verbose_name="Статус")),
                ("activated_at", models.DateTimeField(blank=True, null=True, verbose_name="Активировано")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invitations", to="app.corporateorder", verbose_name="Корпоративный заказ")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="corporate_invitations", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={
                "verbose_name": "Корпоративное приглашение",
                "verbose_name_plural": "Корпоративные приглашения",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddField(
            model_name="enrollment",
            name="corporate_invitation",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="enrollment", to="app.corporateinvitation", verbose_name="Корпоративное место"),
        ),
        migrations.AddIndex(
            model_name="corporateorder",
            index=models.Index(fields=["status", "created_at"], name="app_corpor_status_d5f9a9_idx"),
        ),
        migrations.AddIndex(
            model_name="corporateorder",
            index=models.Index(fields=["organization", "course"], name="app_corpor_organiz_04c9a3_idx"),
        ),
        migrations.AddIndex(
            model_name="corporateinvitation",
            index=models.Index(fields=["order", "status"], name="app_corpor_order_i_2c1f33_idx"),
        ),
        migrations.AddIndex(
            model_name="corporateinvitation",
            index=models.Index(fields=["email", "status"], name="app_corpor_email_12417c_idx"),
        ),
        migrations.AddConstraint(
            model_name="corporateinvitation",
            constraint=models.UniqueConstraint(fields=("order", "email"), name="uniq_corporate_order_invite_email"),
        ),
    ]
