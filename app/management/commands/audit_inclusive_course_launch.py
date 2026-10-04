from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from app.models import Course, Lesson, LessonBlock, Quiz


COURSE_SLUG = "inclusive-higher-education"


class Command(BaseCommand):
    help = "Проверяет готовность курса SkillsSpire к безопасной публикации."

    def handle(self, *args, **options):
        errors = []

        try:
            course = Course.objects.get(slug=COURSE_SLUG)
        except Course.DoesNotExist as exc:
            raise CommandError(
                "Курс inclusive-higher-education не найден. Сначала выполните seed_inclusive_course."
            ) from exc

        if int(course.duration_hours or 0) != 72:
            errors.append("Трудоёмкость курса должна быть ровно 72 академических часа.")

        if not course.certificate:
            errors.append("Для курса должна быть включена выдача сертификата.")

        if Decimal(course.price or 0) <= 0:
            errors.append(
                "Цена курса не настроена. Платный курс нельзя публиковать с ценой 0."
            )

        modules = course.modules.filter(is_deleted=False, is_active=True)
        if modules.count() != 4:
            errors.append(f"Ожидалось 4 активных модуля, найдено {modules.count()}.")

        lessons = Lesson.objects.filter(
            module__course=course,
            module__is_deleted=False,
            is_deleted=False,
            is_active=True,
        )
        if lessons.count() != 16:
            errors.append(f"Ожидалось 16 активных тем, найдено {lessons.count()}.")

        quizzes = Quiz.objects.filter(
            lesson__module__course=course,
            lesson__is_deleted=False,
            is_active=True,
        ).distinct()
        if quizzes.count() != 16:
            errors.append(f"Ожидалось 16 тематических тестов, найдено {quizzes.count()}.")

        question_count = sum(quiz.questions.count() for quiz in quizzes)
        if question_count != 80:
            errors.append(f"Ожидалось 80 тестовых вопросов, найдено {question_count}.")

        invalid_quizzes = [
            quiz.title
            for quiz in quizzes
            if quiz.passing_score != 80
            or not getattr(quiz, "unlimited_attempts", False)
            or quiz.questions.count() != 5
        ]
        if invalid_quizzes:
            errors.append(
                "Все 16 тестов должны содержать по 5 вопросов, проходной балл 80% "
                "и неограниченные попытки."
            )

        lessons_with_required_practice = (
            lessons.filter(
                blocks__block_type="assignment",
                blocks__is_required=True,
                blocks__is_deleted=False,
            )
            .distinct()
            .count()
        )
        if lessons_with_required_practice != 16:
            errors.append(
                "В каждой из 16 тем должно быть хотя бы одно обязательное практическое задание."
            )

        optional_cases = LessonBlock.objects.filter(
            lesson__module__course=course,
            lesson__is_deleted=False,
            block_type="assignment",
            is_required=False,
            is_deleted=False,
            title__startswith="Дополнительный кейс",
        ).count()
        if optional_cases != 24:
            errors.append(f"Ожидалось 24 дополнительных кейса, найдено {optional_cases}.")

        certificate_settings = {
            "CERTIFICATE_REGISTRY_ENDPOINT": getattr(
                settings, "CERTIFICATE_REGISTRY_ENDPOINT", ""
            ),
            "CERTIFICATE_REGISTRY_TOKEN": getattr(
                settings, "CERTIFICATE_REGISTRY_TOKEN", ""
            ),
            "CERTIFICATE_CALLBACK_URL": getattr(
                settings, "CERTIFICATE_CALLBACK_URL", ""
            ),
        }
        missing = [name for name, value in certificate_settings.items() if not str(value).strip()]
        if missing:
            errors.append(
                "Не настроена интеграция сертификатов: " + ", ".join(missing) + "."
            )

        if errors:
            raise CommandError(
                "Предпусковая проверка курса не пройдена:\n- " + "\n- ".join(errors)
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Предпусковая проверка пройдена: 4 модуля, 16 тем, "
                "80 вопросов, 24 кейса, платная цена и сертификатная интеграция настроены."
            )
        )
