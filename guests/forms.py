from django import forms


class GuestUploadForm(forms.Form):
    selfie = forms.ImageField(
        label='Your selfie',
        help_text='Take a clear photo of your face. We use it only to find your photos.',
        widget=forms.FileInput(attrs={'accept': 'image/*', 'capture': 'user'}),
    )
    name = forms.CharField(max_length=100, required=False, label='Your name (optional)')
    phone = forms.CharField(max_length=20, required=False, label='Phone / WhatsApp (optional)')
    consent = forms.BooleanField(
        required=True,
        label='I understand that my selfie will be used only to find my photos from this event and will not be shared with third parties.',
    )
