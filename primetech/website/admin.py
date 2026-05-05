"""
Website admin — course management with application approval workflow.
"""
import secrets
import string

from django.contrib import admin, messages
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import CourseCategory, Course, Testimonial, Statistic, CourseApplication, Enrollment

User = get_user_model()


def _generate_temp_password(length=10):
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'assigned_instructor', 'level', 'price', 'is_active')
    list_filter = ('category', 'level', 'is_active')
    search_fields = ('title', 'instructor')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('assigned_instructor',)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'is_active', 'created_at')
    list_filter = ('is_active',)


@admin.register(Statistic)
class StatisticAdmin(admin.ModelAdmin):
    list_display = ('title', 'value', 'order')
    ordering = ('order',)


@admin.register(CourseApplication)
class CourseApplicationAdmin(admin.ModelAdmin):
    """Admin for reviewing and approving course applications."""

    list_display = ('full_name', 'email', 'course', 'status', 'created_at')
    list_filter = ('status', 'course', 'created_at')
    search_fields = ('full_name', 'email')
    readonly_fields = ('created_at',)
    actions = ['approve_and_enroll', 'reject_applications']

    fieldsets = (
        ('Applicant Info', {'fields': ('full_name', 'email', 'phone_number', 'nationality', 'gender')}),
        ('Application', {'fields': ('course', 'motivation', 'status', 'admin_notes')}),
        ('Processing', {'fields': ('processed_by', 'processed_at', 'created_at')}),
    )

    @admin.action(description='✅ Approve selected & enroll students')
    def approve_and_enroll(self, request, queryset):
        """Approve applications, create student accounts, enroll, and send emails."""
        from notifications.utils import create_notification
        from notifications.tasks import send_welcome_email

        approved = 0
        for application in queryset.filter(status='pending'):
            # 1. Create or get the student user account
            temp_password = _generate_temp_password()
            user, created = User.objects.get_or_create(
                email=application.email,
                defaults={
                    'first_name': application.full_name.split()[0],
                    'last_name': ' '.join(application.full_name.split()[1:]) or '-',
                    'role': 'student',
                    'phone_number': application.phone_number,
                    'nationality': application.nationality,
                    'gender': application.gender,
                    'must_change_password': True,
                    'is_active': True,
                }
            )
            if created:
                user.set_password(temp_password)
                user.save()

            # 2. Create enrollment (skip if already enrolled)
            enrollment, enr_created = Enrollment.objects.get_or_create(
                student=user,
                course=application.course,
                defaults={'application': application}
            )

            # 3. Update application status
            application.status = 'approved'
            application.processed_by = request.user
            application.processed_at = timezone.now()
            application.save()

            # 4. Send congratulatory email with credentials
            if created:
                send_welcome_email.delay(user.id, temp_password)

            # 5. In-app notifications
            create_notification(
                recipient=user,
                notification_type='enrollment',
                title=f'Enrolled in {application.course.title}',
                message=f'Congratulations! You have been enrolled in "{application.course.title}". '
                        f'Please log in and start learning!',
                send_email=False,  # Welcome email already sent
            )

            # Notify the instructor if assigned
            if application.course.assigned_instructor:
                create_notification(
                    recipient=application.course.assigned_instructor,
                    notification_type='enrollment',
                    title=f'New Student Enrolled',
                    message=f'{user.get_full_name()} has been enrolled in your course '
                            f'"{application.course.title}".',
                )

            approved += 1

        self.message_user(
            request,
            f'{approved} application(s) approved and enrolled successfully.',
            messages.SUCCESS,
        )

    @admin.action(description='❌ Reject selected applications')
    def reject_applications(self, request, queryset):
        """Reject selected applications and notify applicants."""
        from notifications.tasks import send_application_status_email

        count = 0
        for application in queryset.filter(status='pending'):
            application.status = 'rejected'
            application.processed_by = request.user
            application.processed_at = timezone.now()
            application.save()
            send_application_status_email.delay(application.id, 'rejected')
            count += 1

        self.message_user(
            request,
            f'{count} application(s) rejected.',
            messages.WARNING,
        )


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'enrolled_at')
    list_filter = ('status', 'course')
    search_fields = ('student__email', 'student__first_name', 'course__title')
    raw_id_fields = ('student', 'application')