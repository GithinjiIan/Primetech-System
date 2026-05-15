from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'courses'
    verbose_name = 'LMS — Courses & Content'

    def ready(self):
        pass  # Reserved for future signal registration
