"""
Setup script for PrimeTech LMS.
Run this ONCE to clean old data and set up the new database.

Usage: python setup_lms.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'primetech.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()


def cleanup():
    """Remove old database and migration files."""
    print("=" * 50)
    print("  PrimeTech LMS Setup")
    print("=" * 50)

    # Remove old database
    db_file = 'db.sqlite3'
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✓ Removed {db_file}")
    else:
        print(f"  {db_file} not found (OK)")

    # Remove old migration files
    migration_dirs = [
        'accounts/migrations',
        'notifications/migrations',
        'website/migrations',
    ]
    for mdir in migration_dirs:
        if os.path.exists(mdir):
            for f in os.listdir(mdir):
                if f.startswith('0') and f.endswith('.py'):
                    filepath = os.path.join(mdir, f)
                    os.remove(filepath)
                    print(f"✓ Removed {filepath}")
                # Also remove .pyc files in __pycache__
                pycache = os.path.join(mdir, '__pycache__')
                if os.path.exists(pycache):
                    for pf in os.listdir(pycache):
                        if pf.startswith('0'):
                            os.remove(os.path.join(pycache, pf))

    # Remove old calery.py (typo)
    calery_file = os.path.join('primetech', 'calery.py')
    if os.path.exists(calery_file):
        os.remove(calery_file)
        print(f"✓ Removed {calery_file} (typo)")

    print()


def run_migrations():
    """Run Django makemigrations and migrate."""
    from django.core.management import call_command

    print("Running makemigrations...")
    call_command('makemigrations', 'accounts')
    call_command('makemigrations', 'notifications')
    call_command('makemigrations', 'website')
    print("✓ Migrations created\n")

    print("Running migrate...")
    call_command('migrate')
    print("✓ Database migrated\n")


def create_superuser():
    """Create a superuser account."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    email = 'admin@primetechfoundation.org'
    if not User.objects.filter(email=email).exists():
        User.objects.create_superuser(
            email=email,
            password='admin123',
            first_name='Super',
            last_name='Admin',
        )
        print(f"✓ Superuser created:")
        print(f"  Email:    {email}")
        print(f"  Password: admin123")
        print(f"   Change this password in production!")
    else:
        print(f"  Superuser {email} already exists")
    print()


if __name__ == '__main__':
    cleanup()
    run_migrations()
    create_superuser()
    print("=" * 50)
    print("  Setup complete! Run: python manage.py runserver")
    print("=" * 50)
