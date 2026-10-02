from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import Category, Course, Module, Lesson, LessonBlock, Quiz


COURSE_SLUG = "inclusive-higher-education"

MODULES = [
    (
        "Основы инклюзивного обучения в высшей школе",
        [
            ("1.1 Инклюзивное обучение и современная высшая школа", "inclusive-learning-modern-university", 4),
            ("1.2 Разнообразие образовательных потребностей студентов", "diverse-learning-needs", 4),
            ("1.3 Барьеры в образовательном процессе", "educational-barriers", 5),
            ("1.4 Этика взаимодействия, коммуникация и профессиональные границы преподавателя", "ethics-communication-boundaries", 5),
        ],
    ),
    (
        "Проектирование доступного образовательного процесса",
        [
            ("2.1 Универсальный дизайн обучения", "universal-design-for-learning", 4),
            ("2.2 Проектирование доступного занятия", "accessible-lesson-design", 4),
            ("2.3 Доступные учебные материалы", "accessible-learning-materials", 5),
            ("2.4 Цифровая образовательная среда и онлайн-обучение", "digital-accessible-learning", 5),
        ],
    ),
    (
        "Технологии преподавания, взаимодействия и оценивания",
        [
            ("3.1 Инклюзивные методы преподавания", "inclusive-teaching-methods", 4),
            ("3.2 Организация групповой работы и взаимодействия", "group-work-interaction", 4),
            ("3.3 Инклюзивное оценивание", "inclusive-assessment", 5),
            ("3.4 Обратная связь, поддержка самостоятельности и сопровождение студента", "feedback-autonomy-support", 5),
        ],
    ),
    (
        "Практика инклюзивного преподавания: ситуации и профессиональные решения",
        [
            ("4.1 Анализ комплексных педагогических ситуаций", "complex-teaching-cases", 4),
            ("4.2 Адаптация учебных заданий без снижения академических требований", "assignment-adaptation-standards", 4),
            ("4.3 Проектирование собственного инклюзивного занятия", "design-inclusive-lesson", 5),
            ("4.4 Комплексные профессиональные решения", "integrated-professional-decisions", 5),
        ],
    ),
]


class Command(BaseCommand):
    help = "Создаёт каркас 72-часового курса SkillsSpire без публикации."

    @transaction.atomic
    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(
            slug="professional-development",
            defaults={
                "name": "Повышение квалификации",
                "is_active": True,
            },
        )

        course, created = Course.objects.update_or_create(
            slug=COURSE_SLUG,
            defaults={
                "title": "Инклюзивное обучение в высшей школе: технологии и практики преподавания",
                "category": category,
                "short_description": (
                    "Практический курс для преподавателей организаций высшего и послевузовского образования."
                ),
                "description": (
                    "72-часовой курс по проектированию доступного образовательного процесса, "
                    "инклюзивным методам преподавания, оцениванию и профессиональным решениям."
                ),
                "duration_hours": 72,
                "language": "Русский",
                "certificate": True,
                "status": Course.DRAFT,
                "requirements": "Для преподавателей организаций высшего и послевузовского образования.",
                "what_you_learn": (
                    "Выявлять образовательные барьеры; проектировать доступные занятия и материалы; "
                    "применять инклюзивные методы преподавания и оценивания; принимать профессиональные "
                    "решения без снижения академических требований."
                ),
            },
        )

        expected_hours = sum(hours for _, lessons in MODULES for _, _, hours in lessons)
        if expected_hours != 72:
            raise RuntimeError(f"Ошибка структуры курса: {expected_hours} ч. вместо 72 ч.")

        lesson_count = 0
        for module_order, (module_title, lessons) in enumerate(MODULES, start=1):
            module, _ = Module.objects.update_or_create(
                course=course,
                order=module_order,
                defaults={
                    "title": module_title,
                    "is_active": True,
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )

            for lesson_order, (title, slug, academic_hours) in enumerate(lessons, start=1):
                lesson, _ = Lesson.objects.update_or_create(
                    module=module,
                    slug=slug,
                    defaults={
                        "title": title,
                        "order": lesson_order,
                        "duration_minutes": academic_hours * 45,
                        "description": f"{academic_hours} академических часа" if academic_hours == 4 else f"{academic_hours} академических часов",
                        "is_active": True,
                        "is_free": False,
                        "is_deleted": False,
                        "deleted_at": None,
                    },
                )

                quiz, _ = Quiz.objects.update_or_create(
                    lesson=lesson,
                    title=f"Тест по теме {title.split(' ', 1)[0]}",
                    defaults={
                        "passing_score": 80,
                        "attempts_allowed": 1,
                        "unlimited_attempts": True,
                        "is_active": True,
                        "description": "5 вопросов. Для прохождения необходимо набрать не менее 80%.",
                        "instructions": "Количество попыток не ограничено. Сохраняется лучший результат.",
                    },
                )

                LessonBlock.objects.update_or_create(
                    lesson=lesson,
                    block_type="quiz",
                    order=90,
                    defaults={
                        "title": "Проверка знаний",
                        "description": "Тематический тест из 5 вопросов.",
                        "quiz": quiz,
                        "is_required": True,
                        "estimated_minutes": 30,
                        "is_free_preview": False,
                        "is_deleted": False,
                        "deleted_at": None,
                    },
                )
                lesson_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Создан' if created else 'Обновлён'} курс: {course.title}. "
                f"4 модуля, {lesson_count} тем, 72 академических часа. Статус: черновик."
            )
        )
