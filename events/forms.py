from django import forms


class EventForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        label='Event Name',
        widget=forms.TextInput(attrs={'placeholder': 'Wedding, Birthday, Conference…'}),
    )
    event_date = forms.DateField(
        label='Event Date',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    description = forms.CharField(
        required=False,
        label='Description',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional notes…'}),
    )
