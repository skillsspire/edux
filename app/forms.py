from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import ContactMessage, Review
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Email or Username"),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter your email or username'),
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter your password'),
            'autocomplete': 'current-password'
        })
    )

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})

        # Добавьте placeholder для лучшего UX
        self.fields['username'].widget.attrs['placeholder'] = 'Придумайте имя пользователя'
        self.fields['email'].widget.attrs['placeholder'] = 'Ваш email'
        self.fields['first_name'].widget.attrs['placeholder'] = 'Ваше имя'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Ваша фамилия'
        self.fields['password1'].widget.attrs['placeholder'] = 'Придумайте пароль'
        self.fields['password2'].widget.attrs['placeholder'] = 'Повторите пароль'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


# Остальные существующие формы...
class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ваше имя'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ваш email'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Тема сообщения'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ваше сообщение', 'rows': 5}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 5,
                'placeholder': 'Оценка от 1 до 5'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Ваш отзыв о курсе',
                'rows': 4
            }),
        }