from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import KYCDocument, FaceVerification

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

class KYCDocumentForm(forms.ModelForm):
    class Meta:
        model = KYCDocument
        fields = ['document_type', 'document_image']
        widgets = {
            'document_image': forms.FileInput(attrs={'accept': 'image/*', 'capture': 'camera'})
        }

class FaceVerificationForm(forms.ModelForm):
    class Meta:
        model = FaceVerification
        fields = ['face_image']
        widgets = {
            'face_image': forms.FileInput(attrs={'accept': 'image/*', 'capture': 'user'})
        }