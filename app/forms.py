from django import forms
from .models import Course, Lesson

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'category', 'price', 'duration', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'content', 'order', 'video_url']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 6}),
        }