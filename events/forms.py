from django import forms
from .models import Event

_fc = {'class': 'form-control'}


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'event_date', 'description', 'watch_folder']
        widgets = {
            'name': forms.TextInput(attrs=_fc),
            'event_date': forms.DateInput(attrs={**_fc, 'type': 'date'}),
            'description': forms.Textarea(attrs={**_fc, 'rows': 3}),
            'watch_folder': forms.TextInput(attrs={**_fc, 'placeholder': 'e.g. C:\\Wedding Photos'}),
        }
        labels = {'watch_folder': 'Watch Folder Path (optional)'}
        help_texts = {'watch_folder': 'Folder path on the agent PC for auto sync'}
