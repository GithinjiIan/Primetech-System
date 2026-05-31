# PrimeTech Foundation LMS

A comprehensive Learning Management System (LMS) and community platform built for the PrimeTech Foundation. This application facilitates course management, student applications, automated notifications, and interactive learning experiences.

## Features

### For Students
- **Course Discovery**: Browse and search through various course categories.
- **Applications**: Apply for courses directly through the platform.
- **Student Dashboard**: Track course progress, upcoming sessions, and assignments.
- **Learning Materials**: Access rich-text articles, video embeds, and downloadable resources.
- **Assignments & Submissions**: Submit work and receive grades and feedback from instructors.
- **Notifications**: Stay updated with real-time alerts for new materials, graded assignments, and upcoming classes.

### For Staff / Instructors
- **Course Management**: Set up syllabus, learning modules, and course materials.
- **Class Scheduling**: Manage virtual and physical class sessions.
- **Grading System**: Review student submissions and provide detailed feedback.
- **Student Oversight**: Monitor applications and enrollments.

### For Administrators
- **User Management**: Role-based access control (Student, Staff, SuperAdmin).
- **Application Processing**: Review and approve student and partnership applications.
- **Analytics**: Track platform statistics and engagement.
- **Newsletter**: Manage subscribers and community outreach.

---

## Tech Stack

- **Framework**: [Django 6.0](https://www.djangoproject.com/)
- **API**: [Django REST Framework](https://www.django-rest-framework.org/)
- **Database**: [PostgreSQL](https://www.postgresql.org/)
- **Task Queue**: [Celery](https://docs.celeryq.dev/) with [Redis](https://redis.io/)
- **Frontend Styling**: [Tailwind CSS](https://tailwindcss.com/) & [Bootstrap 5](https://getbootstrap.com/)
- **Rich Text Editor**: [CKEditor 5](https://ckeditor.com/ckeditor-5/)
- **Admin Interface**: [Jazzmin](https://github.com/farridav/django-jazzmin)

---

## Project Structure

```text
├── accounts/          # Custom User model & authentication logic
├── website/           # Public site, course catalog, applications, and enrollments
├── courses/           # Core LMS logic: syllabus, materials, assignments, grading
├── staff/             # Instructor-specific views and dashboards
├── students/          # Student-specific views and dashboards
├── notifications/      # Centralized notification system
├── primetech/         # Project configuration (settings, urls, wsgi/asgi)
└── templates/         # Global HTML templates
```

---

## Local Development Setup

### 1. Prerequisites
- Python 3.10+
- PostgreSQL
- Redis (for Celery)

### 2. Installation
```bash
# Clone the repository
git clone <repository-url>
cd primetech

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory and populate it with your local settings (refer to `primetech/settings.py` for required keys):
```env
DEBUG=True
SECRET_KEY=your-secret-key
DB_NAME=primetech
DB_USER=your-user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
```

### 4. Database Initialization
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Running the Application
```bash
# Start the Django development server
python manage.py runserver

# In a separate terminal, start the Celery worker
celery -A primetech worker -l info
```

---

## Email & Notifications
The project is configured to use Gmail SMTP for emails. In development, `CELERY_TASK_ALWAYS_EAGER=True` is enabled by default in `settings.py` to run tasks synchronously without requiring a running worker.

---

## Contributing
1. Create a new branch for your feature.
2. Follow Django coding standards and PEP 8.
3. Ensure all changes are documented and tested.
