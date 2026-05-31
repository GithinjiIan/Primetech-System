"""
Website admin — course management with application approval workflow + CSV bulk import.
"""
import csv
import io
import secrets
import string

from django.contrib import admin, messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import path

from .models import CourseCategory, Course, Testimonial, Statistic, CourseApplication, Enrollment, NewsletterSubscriber
from .models import PartnershipApplication
from .forms import NewsletterSendForm

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
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'category', 'level', 'price', 'image', 'is_active')
        }),
        ('Description', {
            'fields': ('description',),
            'description': 'Use clear, readable prose.',
        }),
        ('Details', {
            'fields': ('duration', 'schedule', 'requirements', 'outcomes'),
            'description': 'Write each requirement/outcome on its own line, or use bullet points.',
        }),
        ('Instructor', {
            'fields': ('assigned_instructor',),
        }),
    )


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

            Enrollment.objects.get_or_create(
                student=user,
                course=application.course,
                defaults={'application': application}
            )

            application.status = 'approved'
            application.processed_by = request.user
            application.processed_at = timezone.now()
            application.save()

            if created:
                send_welcome_email.delay(user.id, temp_password)

            create_notification(
                recipient=user,
                notification_type='enrollment',
                title=f'Enrolled in {application.course.title}',
                message=f'Congratulations! You have been enrolled in "{application.course.title}". '
                        f'Please log in and start learning!',
                send_email=not created,  # welcome email already sent if new user
            )

            if application.course.assigned_instructor:
                create_notification(
                    recipient=application.course.assigned_instructor,
                    notification_type='enrollment',
                    title='New Student Enrolled',
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

        self.message_user(request, f'{count} application(s) rejected.', messages.WARNING)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'enrolled_at')
    list_filter = ('status', 'course')
    search_fields = ('student__email', 'student__first_name', 'course__title')
    raw_id_fields = ('student', 'application')
    actions = ['bulk_csv_enroll']

    def get_urls(self):
        urls = super().get_urls()
        custom = [path('csv-import/', self.admin_site.admin_view(self.csv_import_view), name='enrollment-csv-import')]
        return custom + urls

    def csv_import_view(self, request):
        """
        Handle bulk CSV learner import.
        CSV columns: full_name, email, phone_number, course_id, [nationality], [gender]
        """
        from notifications.tasks import send_welcome_email

        if request.method == 'POST' and request.FILES.get('csv_file'):
            csv_file = request.FILES['csv_file']
            decoded = csv_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))

            created_count = 0
            enrolled_count = 0
            errors = []

            for i, row in enumerate(reader, start=2):
                try:
                    full_name = row.get('full_name', '').strip()
                    email = row.get('email', '').strip().lower()
                    phone = row.get('phone_number', '').strip()
                    course_id = row.get('course_id', '').strip()


                    if not full_name or not email or not course_id:
                        errors.append(f"Row {i}: missing required fields (full_name, email, course_id).")
                        continue

                    try:
                        from website.models import Course as CourseModel
                        course = CourseModel.objects.get(pk=course_id)
                    except (CourseModel.DoesNotExist, ValueError):
                        errors.append(f"Row {i}: course_id '{course_id}' not found.")
                        continue

                    name_parts = full_name.split()
                    temp_password = _generate_temp_password()

                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            'first_name': name_parts[0],
                            'last_name': ' '.join(name_parts[1:]) or '-',
                            'role': 'student',
                            'phone_number': phone,
                            'must_change_password': True,
                            'is_active': True,
                        }
                    )
                    if created:
                        user.set_password(temp_password)
                        user.save()
                        created_count += 1
                        send_welcome_email.delay(user.id, temp_password)

                    _, enr_created = Enrollment.objects.get_or_create(
                        student=user,
                        course=course,
                    )
                    if enr_created:
                        enrolled_count += 1

                except Exception as e:
                    errors.append(f"Row {i}: unexpected error — {e}")

            msg = f"Import complete: {created_count} new account(s) created, {enrolled_count} enrollment(s) added."
            if errors:
                msg += f" {len(errors)} row(s) had errors."
                for err in errors[:5]:
                    messages.warning(request, err)
            messages.success(request, msg)
            return HttpResponseRedirect('../')

        # GET — render the upload form
        context = {
            **self.admin_site.each_context(request),
            'title': 'Bulk CSV Learner Import',
            'opts': self.model._meta,
        }
        return render(request, 'admin/csv_import.html', context)


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'user', 'is_active', 'subscribed_at')
    list_filter = ('is_active', 'subscribed_at')
    search_fields = ('email', 'first_name', 'last_name')
    change_list_template = 'admin/website/newslettersubscriber/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send-newsletter/', self.admin_site.admin_view(self.send_newsletter_view), name='website_newslettersubscriber_send_newsletter'),
        ]
        return custom_urls + urls

    def send_newsletter_view(self, request):
        if request.method == 'POST':
            form = NewsletterSendForm(request.POST)
            if form.is_valid():
                subject = form.cleaned_data['subject']
                body = form.cleaned_data['body']
                target = form.cleaned_data['target']
                create_notifications = form.cleaned_data['create_notifications']

                if target == 'subscribers':
                    subscriber_emails = NewsletterSubscriber.objects.filter(is_active=True).values_list('email', flat=True)
                    recipient_users = NewsletterSubscriber.objects.filter(is_active=True).exclude(user__isnull=True).values_list('user', flat=True)
                elif target == 'enrolled':
                    subscriber_emails = Enrollment.objects.select_related('student').filter(student__is_active=True).values_list('student__email', flat=True)
                    recipient_users = Enrollment.objects.select_related('student').filter(student__is_active=True).values_list('student', flat=True)
                elif target == 'all_users':
                    subscriber_emails = User.objects.filter(is_active=True).values_list('email', flat=True)
                    recipient_users = User.objects.filter(is_active=True).values_list('pk', flat=True)
                else:  # subscribers_and_enrolled
                    subscriber_emails = NewsletterSubscriber.objects.filter(is_active=True).values_list('email', flat=True)
                    enrolled_emails = Enrollment.objects.select_related('student').filter(student__is_active=True).values_list('student__email', flat=True)
                    subscriber_emails = list(set(list(subscriber_emails) + list(enrolled_emails)))
                    recipient_users = NewsletterSubscriber.objects.filter(is_active=True).exclude(user__isnull=True).values_list('user', flat=True)
                    enrolled_users = Enrollment.objects.filter(student__is_active=True).values_list('student', flat=True)
                    recipient_users = list(set(list(recipient_users) + list(enrolled_users)))

                recipient_emails = [email for email in set(subscriber_emails) if email]
                for email in recipient_emails:
                    from notifications.tasks import send_newsletter_email
                    send_newsletter_email.delay(email, subject, body)

                if create_notifications:
                    from notifications.utils import create_notification
                    for user_id in set(recipient_users):
                        try:
                            user = User.objects.get(pk=user_id)
                            create_notification(
                                recipient=user,
                                notification_type='system',
                                title=subject,
                                message=body,
                                send_email=False,
                            )
                        except User.DoesNotExist:
                            continue

                self.message_user(request, f'Newsletter queued for {len(recipient_emails)} recipient(s).', messages.SUCCESS)
                return HttpResponseRedirect('../')
        else:
            form = NewsletterSendForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Send Newsletter',
            'opts': self.model._meta,
            'form': form,
        }
        return render(request, 'admin/website/newslettersubscriber/send_newsletter.html', context)


@admin.register(PartnershipApplication)
class PartnershipApplicationAdmin(admin.ModelAdmin):
    list_display = ('organization_name', 'email', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('organization_name', 'email')
    readonly_fields = ('created_at',)