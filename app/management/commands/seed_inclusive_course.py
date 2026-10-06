import html
import json
from pathlib import Path
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from app.models import (
    Answer,
    Category,
    Course,
    Lesson,
    LessonBlock,
    Module,
    Question,
    Quiz,
)


COURSE_SLUG = "inclusive-higher-education"
DATA_FILE = Path(__file__).resolve().parents[2] / "course_data" / "inclusive_course.json"

MODULE_TITLES = {
    1: "Основы инклюзивного обучения в высшей школе",
    2: "Проектирование доступного образовательного процесса",
    3: "Технологии преподавания, взаимодействия и оценивания",
    4: "Практика инклюзивного преподавания: ситуации и профессиональные решения",
}


def paragraphs_to_html(paragraphs):
    return "\n".join(f"<p>{html.escape(text)}</p>" for text in paragraphs if text)


def section_text(paragraphs):
    return "\n\n".join(text for text in paragraphs if text)


class Command(BaseCommand):
    help = (
        "Создаёт/обновляет полный черновик 72-часового курса SkillsSpire: "
        "4 модуля, 16 тем, учебные тексты, практику, 80 вопросов и 24 кейса."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        with DATA_FILE.open("r", encoding="utf-8") as source:
            data = json.load(source)

        topics = data["topics"]
        cases = data["cases"]

        if len(topics) != 16:
            raise RuntimeError(f"Ожидалось 16 тем, найдено {len(topics)}.")
        if sum(len(topic["questions"]) for topic in topics) != 80:
            raise RuntimeError("Банк тестов должен содержать ровно 80 вопросов.")
        if len(cases) != 24:
            raise RuntimeError(f"Банк практики должен содержать 24 кейса, найдено {len(cases)}.")
        if sum(int(topic["hours"]) for topic in topics) != 72:
            raise RuntimeError("Суммарная трудоёмкость тем должна составлять 72 академических часа.")

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
                "title": data["course"]["title"],
                "category": category,
                "short_description": (
                    "Практический курс для преподавателей организаций высшего "
                    "и послевузовского образования."
                ),
                "description": (
                    "Курс помогает проектировать доступный образовательный процесс, "
                    "выявлять барьеры, применять универсальный дизайн обучения, "
                    "инклюзивные методы преподавания и оценивания без снижения "
                    "академических требований."
                ),
                "duration_hours": 72,
                "price": Decimal("15000.00"),
                "discount_price": None,
                "language": "Русский",
                "certificate": True,
                "status": Course.DRAFT,
                "requirements": (
                    "Для преподавателей организаций высшего и послевузовского образования."
                ),
                "what_you_learn": (
                    "Выявлять образовательные барьеры; проектировать доступные занятия "
                    "и материалы; применять инклюзивные методы преподавания и оценивания; "
                    "принимать профессиональные решения без снижения академических требований."
                ),
            },
        )

        lessons_by_module = {}

        for topic in topics:
            code = topic["code"]
            module_number = int(code.split(".")[0])
            lesson_order = int(code.split(".")[1])
            module, _ = Module.objects.update_or_create(
                course=course,
                order=module_number,
                defaults={
                    "title": MODULE_TITLES[module_number],
                    "is_active": True,
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )

            slug = {
                "1.1": "inclusive-learning-modern-university",
                "1.2": "diverse-learning-needs",
                "1.3": "educational-barriers",
                "1.4": "ethics-communication-boundaries",
                "2.1": "universal-design-for-learning",
                "2.2": "accessible-lesson-design",
                "2.3": "accessible-learning-materials",
                "2.4": "digital-accessible-learning",
                "3.1": "inclusive-teaching-methods",
                "3.2": "group-work-interaction",
                "3.3": "inclusive-assessment",
                "3.4": "feedback-autonomy-support",
                "4.1": "complex-teaching-cases",
                "4.2": "assignment-adaptation-standards",
                "4.3": "design-inclusive-lesson",
                "4.4": "integrated-professional-decisions",
            }[code]

            lesson, _ = Lesson.objects.update_or_create(
                module=module,
                slug=slug,
                defaults={
                    "title": f"{code}. {topic['title']}",
                    "order": lesson_order,
                    "duration_minutes": int(topic["hours"]) * 45,
                    "description": f"{topic['hours']} академических часов",
                    "is_active": True,
                    "is_free": False,
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )
            lessons_by_module.setdefault(module_number, []).append(lesson)

            LessonBlock.objects.update_or_create(
                lesson=lesson,
                order=10,
                defaults={
                    "block_type": "text",
                    "title": "Учебный материал",
                    "content": paragraphs_to_html(topic["lecture"]),
                    "description": "",
                    "is_required": True,
                    "estimated_minutes": max(45, int(topic["hours"]) * 30),
                    "is_free_preview": False,
                    "is_deleted": False,
                    "deleted_at": None,
                    "quiz": None,
                    "assignment": None,
                },
            )

            for section_number, section in enumerate(topic["sections"], start=1):
                LessonBlock.objects.update_or_create(
                    lesson=lesson,
                    order=10 + section_number * 10,
                    defaults={
                        "block_type": "assignment",
                        "title": section["title"],
                        "description": section_text(section["paragraphs"]),
                        "content": "",
                        "is_required": True,
                        "estimated_minutes": 30,
                        "is_free_preview": False,
                        "is_deleted": False,
                        "deleted_at": None,
                        "quiz": None,
                        "assignment": None,
                    },
                )

            quiz, _ = Quiz.objects.update_or_create(
                lesson=lesson,
                title=f"Тест по теме {code}",
                defaults={
                    "passing_score": 80,
                    "attempts_allowed": 1,
                    "unlimited_attempts": True,
                    "is_active": True,
                    "description": "5 вопросов. Для прохождения необходимо набрать не менее 80%.",
                    "instructions": (
                        "Количество попыток не ограничено. Сохраняется лучший результат."
                    ),
                },
            )

            quiz.questions.all().delete()
            for question_order, item in enumerate(topic["questions"], start=1):
                question = Question.objects.create(
                    quiz=quiz,
                    text=item["text"],
                    question_type="single",
                    order=question_order,
                    points=1,
                    explanation=item["explanation"],
                )
                for answer_order, option in enumerate(item["options"], start=1):
                    Answer.objects.create(
                        question=question,
                        text=option["text"],
                        is_correct=option["letter"] == item["correct"],
                        order=answer_order,
                    )

            LessonBlock.objects.update_or_create(
                lesson=lesson,
                order=90,
                defaults={
                    "block_type": "quiz",
                    "title": "Проверка знаний",
                    "description": "Тематический тест из 5 вопросов.",
                    "quiz": quiz,
                    "assignment": None,
                    "content": "",
                    "is_required": True,
                    "estimated_minutes": 30,
                    "is_free_preview": False,
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )

        # 24 дополнительных кейса распределяются по темам своего модуля.
        # Они являются практикой для закрепления и не блокируют сертификат.
        for case in cases:
            module_lessons = sorted(
                lessons_by_module[int(case["module"])],
                key=lambda lesson: lesson.order,
            )
            target_lesson = module_lessons[(int(case["number"]) - 1) % 4]
            case_text = (
                f"{case['scenario']}\n\n"
                f"Задание. {case['task']}\n\n"
                f"Рекомендуемый разбор. {case['recommended_analysis']}\n\n"
                f"Методический комментарий. {case['methodological_comment']}"
            )
            LessonBlock.objects.update_or_create(
                lesson=target_lesson,
                order=100 + int(case["number"]),
                defaults={
                    "block_type": "assignment",
                    "title": f"Дополнительный кейс {case['number']}. {case['title']}",
                    "description": case_text,
                    "content": "",
                    "is_required": False,
                    "estimated_minutes": 20,
                    "is_free_preview": False,
                    "is_deleted": False,
                    "deleted_at": None,
                    "quiz": None,
                    "assignment": None,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Создан' if created else 'Обновлён'} черновик курса: {course.title}. "
                "4 модуля, 16 тем, 80 вопросов, 24 дополнительных кейса, 72 академических часа."
            )
        )
