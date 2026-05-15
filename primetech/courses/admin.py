"""
Admin registration for courses app — full CRUD for staff and admins.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import CourseMaterial, ClassSession, Assignment, Submission, Grade, MaterialProgress


@admin.register(CourseMaterial)
class CourseMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'material_type', 'order', 'is_published', 'created_at')
    list_filter = ('material_type', 'is_published', 'course')
    search_fields = ('title', 'course__title')
    list_editable = ('order', 'is_published')
    ordering = ('course', 'order')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Info', {'fields': ('course', 'title', 'material_type', 'description', 'order', 'is_published')}),
        ('Content', {
            'fields': ('content', 'file', 'url'),
            'description': 'Fill in the field that matches your material type.'
        }),
        ('Meta', {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'session_date', 'start_time', 'end_time', 'mode', 'is_upcoming')
    list_filter = ('mode', 'course', 'session_date')
    search_fields = ('title', 'course__title')
    readonly_fields = ('created_at',)
    date_hierarchy = 'session_date'

    def is_upcoming(self, obj):
        if obj.is_upcoming:
            return format_html('<span style="color:green;">✔ Upcoming</span>')
        return format_html('<span style="color:grey;">Past</span>')
    is_upcoming.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class GradeInline(admin.StackedInline):
    model = Grade
    extra = 0
    readonly_fields = ('graded_at', 'updated_at')


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'due_date', 'max_score', 'is_published', 'submissions_count')
    list_filter = ('is_published', 'course')
    search_fields = ('title', 'course__title')
    readonly_fields = ('created_at', 'updated_at')

    def submissions_count(self, obj):
        return obj.submissions.count()
    submissions_count.short_description = '# Submissions'

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'status', 'submitted_at', 'has_grade')
    list_filter = ('status', 'assignment__course')
    search_fields = ('student__email', 'student__first_name', 'assignment__title')
    readonly_fields = ('submitted_at', 'updated_at')
    inlines = [GradeInline]

    def has_grade(self, obj):
        has = hasattr(obj, 'grade')
        return format_html('<span style="color:{};">●</span> {}', 'green' if has else 'red', 'Graded' if has else 'Pending')
    has_grade.short_description = 'Grade Status'


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('submission', 'score', 'percentage', 'letter_grade', 'graded_by', 'graded_at')
    readonly_fields = ('graded_at', 'updated_at', 'percentage', 'letter_grade')
    search_fields = ('submission__student__email', 'submission__assignment__title')

    def percentage(self, obj):
        return f"{obj.percentage}%"
    percentage.short_description = 'Score %'

    def letter_grade(self, obj):
        return obj.letter_grade
    letter_grade.short_description = 'Letter Grade'
