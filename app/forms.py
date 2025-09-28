from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _
from .models import ContactMessage, Review

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


class CustomUserCreationForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(required=True, label=_("Email"))
    first_name = forms.CharField(max_length=30, required=True, label=_("First name"))
    last_name = forms.CharField(max_length=30, required=True, label=_("Last name"))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Плейсхолдеры + autocomplete
        self.fields["username"].widget.attrs.update({
            "placeholder": _("Create a username"),
            "autocomplete": "username",
        })
        self.fields["email"].widget.attrs.update({
            "placeholder": _("Your email"),
            "autocomplete": "email",
        })
        self.fields["first_name"].widget.attrs.update({
            "placeholder": _("Your first name"),
            "autocomplete": "given-name",
        })
        self.fields["last_name"].widget.attrs.update({
            "placeholder": _("Your last name"),
            "autocomplete": "family-name",
        })
        self.fields["password1"].widget.attrs.update({
            "placeholder": _("Create a password"),
            "autocomplete": "new-password",
        })
        self.fields["password2"].widget.attrs.update({
            "placeholder": _("Repeat the password"),
            "autocomplete": "new-password",
        })

        # Убираем шум из help_text
        for name in ("username", "password1", "password2"):
            if name in self.fields:
                self.fields[name].help_text = ""

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("A user with this email already exists."))
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class ContactForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        # Оставляю subject, раз он используется в проекте.
        fields = ["name", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Your name")}),
            "email": forms.EmailInput(attrs={"placeholder": _("Your email"), "autocomplete": "email"}),
            "subject": forms.TextInput(attrs={"placeholder": _("Subject")}),
            "message": forms.Textarea(attrs={"rows": 5, "placeholder": _("Your message")}),
        }


class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]  # если в модели поле текста называется иначе, замени "comment" на актуальное
        widgets = {
            "rating": forms.NumberInput(attrs={"min": 1, "max": 5, "placeholder": _("Rating 1–5")}),
            "comment": forms.Textarea(attrs={"rows": 4, "placeholder": _("Your review about the course")}),
        }
        labels = {
            "rating": _("Rating"),
            "comment": _("Review"),
        }
