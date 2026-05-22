// static/js/main.js — Common scripts for all pages
document.addEventListener('DOMContentLoaded', function () {
    // Initialize AOS
    if (typeof AOS !== 'undefined') {
        AOS.init({ duration: 800, once: true });
    }

    // Back to Top button
    const backToTopBtn = document.getElementById('backToTop');
    if (backToTopBtn) {
        window.addEventListener('scroll', function () {
            const scrolled = document.body.scrollTop > 200 ||
            document.documentElement.scrollTop > 200;
            backToTopBtn.style.display = scrolled ? 'block' : 'none';
        });
        backToTopBtn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // WhatsApp redirect helper
    window.redirectToWhatsApp = function () {
        const phone = '254725023365';
        const text = encodeURIComponent('Hello, I would like to know more about PrimeTech Foundation courses.');
        const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
        const url = isMobile
        ? `https://wa.me/${phone}?text=${text}`
        : `https://web.whatsapp.com/send?phone=${phone}&text=${text}`;
        window.open(url, '_blank');
    };
});


// Animate counters when they become visible
function animateCounters() {
    const counters = document.querySelectorAll('.counter');
    
    counters.forEach(counter => {
        const target = +counter.getAttribute('data-target');
        if (isNaN(target)) return;
        
        let count = 0;
        const speed = target / 100; // slower for larger numbers
        
        const updateCount = () => {
            const increment = Math.ceil(target / 100);
            if (count < target) {
                count += increment;
                counter.innerText = count + '+';
                requestAnimationFrame(updateCount);
            } else {
                counter.innerText = target + '+';
            }
        };
        
        // Use IntersectionObserver to start animation when visible
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    updateCount();
                    observer.unobserve(counter);
                }
            });
        }, { threshold: 0.5 });
        
        observer.observe(counter);
    });
}

// Call after DOM loaded
document.addEventListener('DOMContentLoaded', animateCounters);

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