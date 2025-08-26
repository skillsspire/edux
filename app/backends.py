# app/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Пытаемся найти пользователя по email или username
            user = User.objects.get(
                Q(email__iexact=username) | Q(username__iexact=username)
            )
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Если найдено несколько пользователей с одинаковым email
            return None