from django import forms
from .models import Event

_fc = {'class': 'form-control'}


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'event_date', 'description']
        widgets = {
            'name': forms.TextInput(attrs=_fc),
            'event_date': forms.DateInput(attrs={**_fc, 'type': 'date'}),
            'description': forms.Textarea(attrs={**_fc, 'rows': 3}),
        }
