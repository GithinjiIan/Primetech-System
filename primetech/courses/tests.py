from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from courses.forms import CourseMaterialForm


class CourseMaterialFormTests(TestCase):
    def test_content_field_uses_ckeditor_widget(self):
        form = CourseMaterialForm()
        self.assertEqual(form.fields['content'].widget.attrs['class'], 'ckeditor-field form-control')
        self.assertEqual(form.fields['content'].widget.attrs['id'], 'materialContentEditor')

    def test_text_material_clears_url_and_file_pre_save(self):
        form = CourseMaterialForm(data={
            'title': 'Course notes',
            'material_type': 'text',
            'description': 'Instructor notes',
            'content': '<p>Welcome students</p>',
            'url': ' https://example.com ',
            'order': 1,
            'is_published': True,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['url'], '')
        self.assertIsNone(form.cleaned_data['file'])

    def test_video_material_rejects_invalid_url(self):
        form = CourseMaterialForm(data={
            'title': 'Course video',
            'material_type': 'video',
            'description': 'A sample video',
            'url': 'https://example.com/not-a-video',
            'order': 1,
            'is_published': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('url', form.errors)
        self.assertEqual(form.errors['url'], ['Enter a valid YouTube or Vimeo URL (including Shorts).'])

    def test_video_material_accepts_youtube_url(self):
        form = CourseMaterialForm(data={
            'title': 'Course video',
            'material_type': 'video',
            'description': 'A sample video',
            'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'order': 1,
            'is_published': True,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['content'], '')

    def test_pdf_material_requires_file_upload(self):
        form = CourseMaterialForm(data={
            'title': 'Lecture slides',
            'material_type': 'pdf',
            'description': 'Downloadable PDF',
            'order': 1,
            'is_published': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)
        self.assertEqual(form.errors['file'], ['Please upload a file for this material type.'])

    def test_pdf_material_rejects_unsupported_file_types(self):
        uploaded = SimpleUploadedFile('notes.txt', b'Hello world', content_type='text/plain')
        form = CourseMaterialForm(
            data={
                'title': 'Lecture notes',
                'material_type': 'pdf',
                'description': 'Text file upload',
                'order': 1,
                'is_published': True,
            },
            files={'file': uploaded}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)
        self.assertEqual(form.errors['file'], ['Upload a PDF, Word, PowerPoint, Excel, or ZIP document only.'])

    def test_pdf_material_accepts_supported_file_types(self):
        uploaded = SimpleUploadedFile('slides.pdf', b'%PDF-1.4 sample', content_type='application/pdf')
        form = CourseMaterialForm(
            data={
                'title': 'Lecture slides',
                'material_type': 'pdf',
                'description': 'Downloadable slides',
                'order': 1,
                'is_published': True,
            },
            files={'file': uploaded}
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['url'], '')
        self.assertEqual(form.cleaned_data['content'], '')
        self.assertTrue(form.cleaned_data['file'].name.endswith('slides.pdf'))
