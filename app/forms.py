from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import ContactMessage, Review, UserProfile, CorporateOrder

# reCAPTCHA
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox

User = get_user_model()


# Универсально навешиваем Bootstrap-классы на все поля формы
class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                base = "form-select"
            elif isinstance(widget, forms.CheckboxInput):
                base = "form-check-input"
            else:
                base = "form-control"
            widget.attrs["class"] = f"{existing} {base}".strip()


# --------------------------
# LOGIN FORM
# --------------------------
class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(
        label=_("Email or Username"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Enter your email or username"),
            "autocomplete": "username",
        })
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            "placeholder": _("Enter your password"),
            "autocomplete": "current-password",
        })
    )


# --------------------------
# REGISTRATION FORM (+ reCAPTCHA)
# --------------------------
class CustomUserCreationForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(max_length=30, required=True, label="Имя")
    last_name = forms.CharField(max_length=30, required=True, label="Фамилия")
    phone = forms.CharField(max_length=20, required=True, label="Телефон")
    company = forms.CharField(max_length=100, required=False, label="Организация")
    position = forms.CharField(max_length=100, required=False, label="Должность")

    accept_offer = forms.BooleanField(
        required=True,
        label="Я принимаю условия Публичной оферты SkillsSpire",
        error_messages={"required": "Для регистрации необходимо принять Публичную оферту."},
    )
    accept_privacy = forms.BooleanField(
        required=True,
        label="Я даю согласие на сбор и обработку персональных данных",
        error_messages={"required": "Для регистрации необходимо дать согласие на обработку персональных данных."},
    )

    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox())

    OFFER_VERSION = "2026-10"
    PRIVACY_VERSION = "2026-10"

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "company",
            "position",
            "password1",
            "password2",
            "accept_offer",
            "accept_privacy",
            "captcha",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].widget.attrs.update({
            "placeholder": "Создайте имя пользователя",
            "autocomplete": "username",
        })
        self.fields["email"].widget.attrs.update({
            "placeholder": "you@example.com",
            "autocomplete": "email",
        })
        self.fields["first_name"].widget.attrs.update({
            "placeholder": "Имя",
            "autocomplete": "given-name",
        })
        self.fields["last_name"].widget.attrs.update({
            "placeholder": "Фамилия",
            "autocomplete": "family-name",
        })
        self.fields["phone"].widget.attrs.update({
            "placeholder": "+7 700 000 00 00",
            "autocomplete": "tel",
        })
        self.fields["company"].widget.attrs.update({
            "placeholder": "Организация / вуз (необязательно)",
            "autocomplete": "organization",
        })
        self.fields["position"].widget.attrs.update({
            "placeholder": "Должность (необязательно)",
            "autocomplete": "organization-title",
        })
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Создайте пароль",
            "autocomplete": "new-password",
        })
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Повторите пароль",
            "autocomplete": "new-password",
        })

        for name in ("username", "password1", "password2"):
            if name in self.fields:
                self.fields[name].help_text = ""

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже зарегистрирован.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            now = timezone.now()
            profile.phone = self.cleaned_data.get("phone", "").strip()
            profile.company = self.cleaned_data.get("company", "").strip()
            profile.position = self.cleaned_data.get("position", "").strip()
            profile.offer_accepted_at = now
            profile.privacy_accepted_at = now
            profile.offer_version = self.OFFER_VERSION
            profile.privacy_version = self.PRIVACY_VERSION
            profile.save(update_fields=[
                "phone",
                "company",
                "position",
                "offer_accepted_at",
                "privacy_accepted_at",
                "offer_version",
                "privacy_version",
                "updated_at",
            ])
        return user


# --------------------------
# CONTACT FORM
# --------------------------
class ContactForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Your name")}),
            "email": forms.EmailInput(attrs={"placeholder": _("Your email"), "autocomplete": "email"}),
            "subject": forms.TextInput(attrs={"placeholder": _("Subject")}),
            "message": forms.Textarea(attrs={"rows": 5, "placeholder": _("Your message")}),
        }


# --------------------------
# REVIEW FORM
# --------------------------
class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.NumberInput(attrs={"min": 1, "max": 5, "placeholder": _("Rating 1–5")}),
            "comment": forms.Textarea(attrs={"rows": 4, "placeholder": _("Your review about the course")}),
        }
        labels = {
            "rating": _("Rating"),
            "comment": _("Review"),
        }


# --------------------------
# CORPORATE CLIENTS
# --------------------------
class CorporateOrderRequestForm(BootstrapFormMixin, forms.Form):
    organization_name = forms.CharField(max_length=255, label="Наименование организации")
    bin = forms.CharField(max_length=20, label="БИН")
    legal_address = forms.CharField(max_length=500, required=False, label="Юридический адрес")
    contact_name = forms.CharField(max_length=255, label="Контактное лицо")
    contact_email = forms.EmailField(label="Email контактного лица")
    contact_phone = forms.CharField(max_length=30, label="Телефон контактного лица")
    seats = forms.IntegerField(min_value=1, max_value=1000, label="Количество слушателей")
    note = forms.CharField(
        required=False,
        label="Комментарий",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Например: нужен договор и счёт на оплату"}),
    )

    def clean_bin(self):
        value = (self.cleaned_data.get("bin") or "").strip().replace(" ", "")
        if not value:
            raise forms.ValidationError("Укажите БИН организации.")
        return value


class CorporateParticipantsForm(BootstrapFormMixin, forms.Form):
    participants = forms.CharField(
        label="Список слушателей",
        widget=forms.Textarea(attrs={
            "rows": 8,
            "placeholder": "Иванов; Иван; ivanov@example.kz\nСадыкова; Анна; sadykova@example.kz",
        }),
        help_text="Каждый участник — с новой строки: Фамилия; Имя; email.",
    )

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

    def clean_participants(self):
        raw = self.cleaned_data.get("participants", "")
        participants = []
        seen = set()

        for line_number, raw_line in enumerate(raw.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue

            delimiter = ";" if ";" in line else ","
            parts = [part.strip() for part in line.split(delimiter)]
            if len(parts) != 3:
                raise forms.ValidationError(
                    f"Строка {line_number}: используйте формат «Фамилия; Имя; email»."
                )

            last_name, first_name, email = parts
            email = email.lower()
            if not last_name or not first_name or not email:
                raise forms.ValidationError(f"Строка {line_number}: заполнены не все данные.")

            try:
                forms.EmailField().clean(email)
            except forms.ValidationError:
                raise forms.ValidationError(f"Строка {line_number}: некорректный email.")

            if email in seen:
                raise forms.ValidationError(f"Email {email} повторяется в списке.")
            seen.add(email)
            participants.append({
                "last_name": last_name,
                "first_name": first_name,
                "email": email,
            })

        if not participants:
            raise forms.ValidationError("Добавьте хотя бы одного слушателя.")

        if self.order:
            remaining = self.order.remaining_seats
            if len(participants) > remaining:
                raise forms.ValidationError(
                    f"Доступно мест: {remaining}. В списке указано: {len(participants)}."
                )

            existing_emails = set(
                self.order.invitations.exclude(status="revoked")
                .values_list("email", flat=True)
            )
            duplicate = next((p["email"] for p in participants if p["email"] in existing_emails), None)
            if duplicate:
                raise forms.ValidationError(
                    f"Для {duplicate} приглашение уже существует в этом заказе."
                )

        return participants
