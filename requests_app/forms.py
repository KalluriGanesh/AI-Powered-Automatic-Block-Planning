from django import forms
from .models import MaintenanceRequest
from core.models import Asset


class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = ['asset', 'description', 'duration_hours', 'priority', 'deadline_day']
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the maintenance work required...',
            }),
            'duration_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 8,
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 5,
            }),
            'deadline_day': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 6,
            }),
        }
        labels = {
            'asset': 'Target Asset',
            'description': 'Work Description',
            'duration_hours': 'Duration (hours, 1–8)',
            'priority': 'Priority (1 = Low, 5 = Critical)',
            'deadline_day': 'Deadline Day (0–6)',
        }
        help_texts = {
            'duration_hours': 'How many consecutive hours the maintenance block requires (1–8).',
            'priority': 'Higher priority requests are scheduled first by the engine.',
            'deadline_day': 'Latest day (0 = today, 6 = end of week) the work must be completed.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset'].queryset = Asset.objects.select_related('section').all()

    def clean_duration_hours(self):
        val = self.cleaned_data['duration_hours']
        if val < 1 or val > 8:
            raise forms.ValidationError('Duration must be between 1 and 8 hours.')
        return val

    def clean_priority(self):
        val = self.cleaned_data['priority']
        if val < 1 or val > 5:
            raise forms.ValidationError('Priority must be between 1 and 5.')
        return val

    def clean_deadline_day(self):
        val = self.cleaned_data['deadline_day']
        if val < 0 or val > 6:
            raise forms.ValidationError('Deadline day must be between 0 and 6.')
        return val
