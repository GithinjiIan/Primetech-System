// static/js/courses.js — Course filtering, details, testimonials slider
document.addEventListener('DOMContentLoaded', function () {
    // ===== Category Filtering =====
    const categoryBtns = document.querySelectorAll('#categoryFilters button');
    const courseWrappers = document.querySelectorAll('.course-item-wrapper');

    categoryBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            categoryBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const category = this.dataset.category;

            courseWrappers.forEach(wrapper => {
                if (category === 'all' || wrapper.dataset.category === category) {
                    wrapper.style.display = '';
                } else {
                    wrapper.style.display = 'none';
                }
            });
        });
    });

    // ===== Course Detail Population =====
    const viewBtns = document.querySelectorAll('.view-course-btn');
    const detailTitle = document.getElementById('detailCourseTitle');
    const detailContent = document.getElementById('courseDetailsContent');
    const selectedCourseInput = document.getElementById('selectedCourse');
    const detailsSection = document.getElementById('courseDetailsSection');

    viewBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const courseId = this.dataset.courseId;
            const course = coursesData[courseId];

            if (!course) return;

            // Update form field
            if (selectedCourseInput) {
                selectedCourseInput.value = course.title;
            }

            // Scroll to details
            detailsSection.scrollIntoView({ behavior: 'smooth' });

            // Update detail view
            detailTitle.textContent = course.title;
            detailContent.innerHTML = `
            <div class="mb-3">
            <h3 class="h5 fw-bold text-brand-dark">${course.title}</h3>
            <p class="text-muted">${course.description}</p>
        </div>
        <div class="mb-3">
        <h4 class="h6 fw-bold"><i class="fas fa-info-circle text-brand-orange me-2"></i>Course Details</h4>
        <p class="mb-1"><strong>Duration:</strong> ${course.duration}</p>
        <p class="mb-1"><strong>Schedule:</strong> ${course.schedule}</p>
        <p class="mb-1"><strong>Instructor:</strong> ${course.instructor}</p>
        <p class="mb-1"><strong>Course Fee:</strong> ${course.price}</p>
    </div>
    <div class="mb-3">
    <h4 class="h6 fw-bold"><i class="fas fa-clipboard-check text-brand-orange me-2"></i>Requirements</h4>
    <ul>${course.requirements.map(r => `<li>${r}</li>`).join('')}</ul>
</div>
<div class="mb-3">
<h4 class="h6 fw-bold"><i class="fas fa-star text-brand-orange me-2"></i>Learning Outcomes</h4>
<ul>${course.outcomes.map(o => `<li>${o}</li>`).join('')}</ul>
</div>
<a href="#course-application" class="btn btn-orange rounded-pill px-4">Apply Now</a>
`;
});
});

// ===== Testimonials Slider =====
const track = document.getElementById('testimonialsTrack');
const slides = track.querySelectorAll('.testimonial-slide');
const leftArrow = document.querySelector('.testimonial-arrow.left');
const rightArrow = document.querySelector('.testimonial-arrow.right');
let currentSlide = 0;
let autoSlideInterval;
let isPaused = false;

function showSlide(index) {
    if (slides.length === 0) return;
    currentSlide = (index + slides.length) % slides.length;
    track.style.transform = `translateX(-${currentSlide * 100}%)`;
}

function nextSlide() { showSlide(currentSlide + 1); }
function prevSlide() { showSlide(currentSlide - 1); }

if (leftArrow && rightArrow && slides.length > 1) {
    rightArrow.addEventListener('click', nextSlide);
    leftArrow.addEventListener('click', prevSlide);

    track.addEventListener('mouseenter', () => { isPaused = true; });
    track.addEventListener('mouseleave', () => { isPaused = false; });

    autoSlideInterval = setInterval(() => {
        if (!isPaused) nextSlide();
    }, 4000);

    showSlide(0);
}

// ===== Application Form =====
const form = document.getElementById('courseApplicationForm');
if (form) {
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        // In production, send via fetch() to Django backend
        alert('Application submitted! Our team will contact you within 3 business days.');
        form.reset();
    });
}

// Set minimum date for start date field
const startDateInput = document.getElementById('startDate');
if (startDateInput) {
    const today = new Date().toISOString().split('T')[0];
    startDateInput.setAttribute('min', today);
}
});