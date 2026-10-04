from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from app.models import (
    Category,
    CertificateRequest,
    BlockProgress,
    CorporateInvitation,
    CorporateOrder,
    Course,
    Enrollment,
    Lesson,
    LessonBlock,
    Module,
    Organization,
    Payment,
    PracticalResponse,
    Quiz,
    QuizAttempt,
)

from app.views import _check_course_completion


User = get_user_model()


class PublicPageSmokeTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Smoke category",
            slug="smoke-category",
        )
        self.course = Course.objects.create(
            title="Smoke course",
            slug="smoke-course",
            category=self.category,
            short_description="Проверка публичной страницы курса.",
            duration_hours=72,
            price=Decimal("15000.00"),
            status=Course.PUBLISHED,
        )
        module = Module.objects.create(
            course=self.course,
            title="Модуль 1",
            order=1,
        )
        Lesson.objects.create(
            module=module,
            title="Тема 1",
            slug="smoke-topic",
            order=1,
            duration_minutes=180,
        )

    def test_core_public_pages_render(self):
        for url in (
            "/",
            "/courses/",
            f"/courses/{self.course.slug}/",
            f"/courses/{self.course.slug}/corporate/",
            "/signup/",
            "/terms/",
            "/privacy/",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    def test_checkout_renders_and_reuses_pending_payment(self):
        user = User.objects.create_user(
            username="checkout-user",
            email="checkout@example.kz",
            password="test-password",
        )
        self.client.force_login(user)

        url = f"/checkout/{self.course.slug}/"
        first = self.client.get(url)
        second = self.client.get(url)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            Payment.objects.filter(
                user=user,
                course=self.course,
                status=Payment.PENDING,
            ).count(),
            1,
        )

    def test_successful_payment_creates_access_and_status_endpoint_reports_it(self):
        user = User.objects.create_user(
            username="paid-user",
            email="paid@example.kz",
            password="test-password",
        )
        self.client.force_login(user)
        self.client.get(f"/checkout/{self.course.slug}/")
        payment = Payment.objects.get(user=user, course=self.course)

        payment.status = Payment.SUCCESS
        payment.save()

        self.assertTrue(
            Enrollment.objects.filter(user=user, course=self.course).exists()
        )
        response = self.client.get(f"/api/payments/{payment.id}/status/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["paid"])
        self.assertTrue(payload["has_access"])
        self.assertTrue(payload["learn_url"])


class CorporateAccessTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Повышение квалификации",
            slug="professional-development-tests",
        )
        self.course = Course.objects.create(
            title="Тестовый курс",
            slug="corporate-test-course",
            category=self.category,
            duration_hours=72,
            price=Decimal("15000.00"),
            status=Course.PUBLISHED,
        )
        self.organization = Organization.objects.create(
            name="Тестовый университет",
            bin="123456789012",
            contact_name="Контакт",
            contact_email="corp@example.kz",
            contact_phone="+77000000000",
        )

    def create_order(self, seats=10, status=CorporateOrder.PAID):
        return CorporateOrder.objects.create(
            organization=self.organization,
            course=self.course,
            seats_purchased=seats,
            base_unit_price=self.course.final_price,
            unit_price=self.course.final_price,
            total_amount=Decimal("0.00"),
            status=status,
        )

    def test_corporate_discount_for_ten_seats(self):
        order = self.create_order(seats=10)
        self.assertEqual(order.discount_percent, Decimal("7.00"))
        self.assertEqual(order.unit_price, Decimal("13950.00"))
        self.assertEqual(order.total_amount, Decimal("139500.00"))
        self.assertEqual(order.remaining_seats, 10)

    def test_order_price_snapshot_does_not_change_when_course_price_changes(self):
        order = self.create_order(seats=10)
        self.course.price = Decimal("30000.00")
        self.course.save(update_fields=["price", "updated_at"])

        order.notes = "Повторное сохранение"
        order.save()

        self.assertEqual(order.base_unit_price, Decimal("15000.00"))
        self.assertEqual(order.unit_price, Decimal("13950.00"))
        self.assertEqual(order.total_amount, Decimal("139500.00"))

    def test_paid_seat_activates_only_for_matching_email(self):
        order = self.create_order(seats=2)
        invitation = CorporateInvitation.objects.create(
            order=order,
            email="teacher@example.kz",
            first_name="Анна",
            last_name="Иванова",
        )
        wrong_user = User.objects.create_user(
            username="wrong",
            email="wrong@example.kz",
            password="test-password",
        )
        with self.assertRaises(ValidationError):
            invitation.activate_for(wrong_user)

        user = User.objects.create_user(
            username="teacher",
            email="teacher@example.kz",
            password="test-password",
        )
        enrollment = invitation.activate_for(user)

        invitation.refresh_from_db()
        enrollment.refresh_from_db()
        self.assertEqual(invitation.status, CorporateInvitation.ACTIVATED)
        self.assertEqual(invitation.user, user)
        self.assertEqual(enrollment.corporate_invitation, invitation)
        self.assertEqual(order.activated_seats, 1)
        self.assertEqual(order.remaining_seats, 1)

    def test_cannot_allocate_more_than_purchased_seats(self):
        order = self.create_order(seats=1)
        CorporateInvitation.objects.create(
            order=order,
            email="one@example.kz",
            first_name="Первый",
            last_name="Слушатель",
        )
        with self.assertRaises(ValidationError):
            CorporateInvitation.objects.create(
                order=order,
                email="two@example.kz",
                first_name="Второй",
                last_name="Слушатель",
            )


class CertificatePeriodTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            title="72 часа",
            slug="certificate-test-course",
            duration_hours=72,
            price=Decimal("0.00"),
        )
        self.user = User.objects.create_user(
            username="certificate-user",
            email="certificate@example.kz",
            password="test-password",
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            completed=True,
            completed_at=timezone.now(),
        )

    def test_72_hours_requires_nine_calendar_days_for_period(self):
        self.assertEqual(
            CertificateRequest(
                enrollment=self.enrollment,
                user=self.user,
                course=self.course,
                period_mode=CertificateRequest.WITHOUT_PERIOD,
            ).minimum_training_days,
            9,
        )

    def test_without_period_is_available_immediately_after_completion(self):
        request = CertificateRequest.objects.create(
            enrollment=self.enrollment,
            user=self.user,
            course=self.course,
            period_mode=CertificateRequest.WITHOUT_PERIOD,
        )
        self.assertIsNone(request.period_start)
        self.assertIsNone(request.period_end)

    def test_with_period_waits_until_ninth_calendar_day(self):
        now = timezone.now()
        Enrollment.objects.filter(pk=self.enrollment.pk).update(
            enrolled_at=now - timedelta(days=3),
            completed_at=now,
        )
        self.enrollment.refresh_from_db()

        request = CertificateRequest(
            enrollment=self.enrollment,
            user=self.user,
            course=self.course,
            period_mode=CertificateRequest.WITH_PERIOD,
        )
        with self.assertRaises(ValidationError):
            request.save()

        Enrollment.objects.filter(pk=self.enrollment.pk).update(
            enrolled_at=now - timedelta(days=8),
            completed_at=now - timedelta(days=5),
        )
        self.enrollment.refresh_from_db()
        request.enrollment = self.enrollment
        request.save()

        self.assertEqual(request.period_start, self.enrollment.enrolled_at.date())
        self.assertEqual(
            request.period_end,
            self.enrollment.enrolled_at.date() + timedelta(days=8),
        )


class QuizAttemptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quiz-user",
            email="quiz@example.kz",
            password="test-password",
        )
        self.course = Course.objects.create(
            title="Quiz course",
            slug="quiz-course",
        )
        self.module = Module.objects.create(course=self.course, title="Модуль 1", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module,
            title="Тема 1",
            slug="topic-1",
            order=1,
        )
        self.quiz = Quiz.objects.create(
            lesson=self.lesson,
            title="Тест",
            passing_score=80,
            unlimited_attempts=True,
        )

    def test_attempt_passes_at_80_and_fails_at_79(self):
        passed = QuizAttempt.objects.create(
            user=self.user,
            quiz=self.quiz,
            attempt_number=1,
            score_percent=80,
        )
        failed = QuizAttempt.objects.create(
            user=self.user,
            quiz=self.quiz,
            attempt_number=2,
            score_percent=79,
        )
        self.assertTrue(passed.passed)
        self.assertFalse(failed.passed)


class PracticalResponseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="practice-user",
            email="practice@example.kz",
            password="test-password",
        )
        self.course = Course.objects.create(
            title="Practice course",
            slug="practice-course",
        )
        Enrollment.objects.create(user=self.user, course=self.course)
        module = Module.objects.create(course=self.course, title="Модуль", order=1)
        lesson = Lesson.objects.create(
            module=module,
            title="Практика",
            slug="practice-topic",
            order=1,
        )
        self.block = LessonBlock.objects.create(
            lesson=lesson,
            block_type="assignment",
            order=10,
            title="Практическое задание",
            is_required=True,
        )
        self.client.force_login(self.user)

    def test_required_assignment_cannot_be_completed_without_response(self):
        response = self.client.post(f"/api/blocks/{self.block.id}/complete/")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            BlockProgress.objects.filter(
                user=self.user,
                block=self.block,
                is_completed=True,
            ).exists()
        )

    def test_practical_response_marks_required_assignment_complete(self):
        response = self.client.post(
            f"/api/blocks/{self.block.id}/practical-response/",
            {"text": "Анализирую барьер и предлагаю доступный способ выполнения задания."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PracticalResponse.objects.filter(
                user=self.user,
                block=self.block,
            ).exists()
        )
        self.assertTrue(
            BlockProgress.objects.get(
                user=self.user,
                block=self.block,
            ).is_completed
        )


class CourseCompletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="completion-user",
            email="completion@example.kz",
            password="test-password",
        )
        self.course = Course.objects.create(
            title="Completion course",
            slug="completion-course",
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
        )
        self.module = Module.objects.create(
            course=self.course,
            title="Модуль",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title="Тема",
            slug="completion-topic",
            order=1,
        )
        self.text_block = LessonBlock.objects.create(
            lesson=self.lesson,
            block_type="text",
            order=10,
            title="Материал",
            is_required=True,
        )
        self.quiz = Quiz.objects.create(
            lesson=self.lesson,
            title="Тест",
            passing_score=70,
            unlimited_attempts=True,
        )
        self.quiz_block = LessonBlock.objects.create(
            lesson=self.lesson,
            block_type="quiz",
            order=90,
            title="Тест",
            quiz=self.quiz,
            is_required=True,
        )
        for block in (self.text_block, self.quiz_block):
            BlockProgress.objects.create(
                user=self.user,
                block=block,
                is_completed=True,
                progress_percent=100,
                completed_at=timezone.now(),
            )

    def test_cumulative_score_below_80_blocks_completion(self):
        QuizAttempt.objects.create(
            user=self.user,
            quiz=self.quiz,
            attempt_number=1,
            score_percent=75,
        )
        status = _check_course_completion(self.user, self.course)
        self.enrollment.refresh_from_db()

        self.assertFalse(status["cumulative_passed"])
        self.assertFalse(self.enrollment.completed)

    def test_best_score_at_80_allows_completion(self):
        QuizAttempt.objects.create(
            user=self.user,
            quiz=self.quiz,
            attempt_number=1,
            score_percent=75,
        )
        QuizAttempt.objects.create(
            user=self.user,
            quiz=self.quiz,
            attempt_number=2,
            score_percent=80,
        )
        status = _check_course_completion(self.user, self.course)
        self.enrollment.refresh_from_db()

        self.assertEqual(status["cumulative_score"], 80)
        self.assertTrue(status["eligible_for_completion"])
        self.assertTrue(self.enrollment.completed)
        self.assertIsNotNone(self.enrollment.completed_at)


class InclusiveCourseSeedTests(TestCase):
    def test_seed_command_creates_complete_course_structure(self):
        call_command("seed_inclusive_course", verbosity=0)

        course = Course.objects.get(slug="inclusive-higher-education")
        self.assertEqual(course.status, Course.DRAFT)
        self.assertEqual(course.duration_hours, 72)
        self.assertEqual(course.modules.count(), 4)
        self.assertEqual(
            Lesson.objects.filter(module__course=course, is_deleted=False).count(),
            16,
        )
        self.assertEqual(
            Quiz.objects.filter(lesson__module__course=course).count(),
            16,
        )
        self.assertEqual(
            sum(
                quiz.questions.count()
                for quiz in Quiz.objects.filter(lesson__module__course=course)
            ),
            80,
        )
        self.assertEqual(
            course.modules.filter(
                lessons__blocks__block_type="assignment",
                lessons__blocks__is_required=False,
                lessons__blocks__title__startswith="Дополнительный кейс",
            ).distinct().count(),
            4,
        )
        self.assertEqual(
            sum(
                lesson.blocks.filter(
                    block_type="assignment",
                    is_required=False,
                    title__startswith="Дополнительный кейс",
                ).count()
                for lesson in Lesson.objects.filter(module__course=course)
            ),
            24,
        )
