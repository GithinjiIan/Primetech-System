
from django.db import models
from django.conf import settings
from django.utils.text import slugify


class CourseCategory(models.Model):
    """Category for grouping courses (Technology, Business, Creative, etc.)"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Course Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Course(models.Model):
    """Individual course offered by PrimeTech Foundation"""
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    category = models.ForeignKey(
        CourseCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='courses'
    )
    short_description = models.CharField(max_length=255, blank=True,
                                         help_text="Brief teaser shown on course cards")
    description = models.TextField(help_text="Full course description")
    duration = models.CharField(max_length=100, help_text="e.g., '8 Weeks (Part-time)'")
    schedule = models.CharField(max_length=200, help_text="e.g., 'Once per week, 2 hours per session'")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')

    # Keep the CharField for display, add FK for assignment
    instructor = models.CharField(max_length=100, blank=True,
                                  help_text="Display name (auto-filled from assigned instructor)")
    assigned_instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'staff'},
        related_name='assigned_courses',
        help_text="Staff member assigned to teach this course"
    )

    price = models.CharField(max_length=50, default="Ksh 0")
    image = models.ImageField(upload_to='courses/', blank=True, null=True)
    requirements = models.TextField(
        default=list,
        blank=True,
        help_text="List of requirements, e.g., ['Basic computer literacy', 'Internet access']"
    )
    outcomes = models.TextField(
        default=list,
        blank=True,
        help_text="List of learning outcomes"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__name', 'title']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        # Auto-fill instructor name from assigned instructor
        if self.assigned_instructor:
            self.instructor = self.assigned_instructor.get_full_name()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Testimonial(models.Model):
    """Student testimonials displayed on the courses page"""
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, help_text="e.g., 'Data Science Student'")
    content = models.TextField()
    photo = models.ImageField(upload_to='testimonials/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.role}"
    

class Statistic(models.Model):
    title = models.CharField(max_length=100, help_text="e.g., 'Total Applications'")
    value = models.PositiveIntegerField(help_text="The number to display (e.g., 1200)")
    icon = models.CharField(
        max_length=50, blank=True,
        help_text="Font Awesome class, e.g. 'fas fa-users'"
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.title}: {self.value}"


# ─── LMS Models ─────────────────────────────────────────────────

class CourseApplication(models.Model):
    """Application from a prospective student for a course."""

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    nationality = models.CharField(max_length=100, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female')],
        blank=True,
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='applications'
    )
    motivation = models.TextField(
        blank=True,
        help_text="Why the applicant wants to take this course"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='processed_applications',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Course Application'
        verbose_name_plural = 'Course Applications'

    def __str__(self):
        return f"{self.full_name} → {self.course.title} ({self.status})"


class Enrollment(models.Model):
    """Tracks student enrollment in courses."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('withdrawn', 'Withdrawn'),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='enrollments'
    )
    application = models.OneToOneField(
        CourseApplication,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='enrollment',
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        ordering = ['-enrolled_at']
        unique_together = ['student', 'course']
        verbose_name = 'Enrollment'
        verbose_name_plural = 'Enrollments'

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.course.title}"
    
    
    #Patnership Applicatoin Form─────────────────────────────────────────────────
class PartnershipApplication(models.Model):
    """Application from a prospective partner organization."""

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    PARTNERSHIP_CHOICES = [
        ('financial_support', 'Financial Support'),
        ('in_kind_donations', 'In-Kind Donations'),
        ('volunteer_program', 'Volunteer Program'),
        ('corporate_sponsorship', 'Corporate Sponsorship'),
    ]
    
    INTERESTED_IN = [
        ('education', 'Education'),
        ('technology_access', 'Technology Access'),
        ('youth_empowerment', 'Youth Empowerment'),
        ('community_development', 'Community Development'),
    ]


    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    organization_name = models.CharField(max_length=200)
    position = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    company_website = models.URLField(blank=True)
    partnership_type = models.CharField(
        max_length=100,
        choices=PARTNERSHIP_CHOICES,
        help_text="Type of partnership"
    )
    
    interested_in = models.CharField(max_length= 200,
                                    choices=INTERESTED_IN,
                                    blank=True ,
                                    help_text="Areas of interest for partnership")
    
    about_proposal = models.TextField(
        blank=True,
        help_text="Why the organization wants to partner with PrimeTech Foundation"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='processed_partnerships',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Partnership Application'
        verbose_name_plural = 'Partnership Applications'

    def __str__(self):
        return f"{self.organization_name} ({self.full_name}) — {self.partnership_type} ({self.status})"