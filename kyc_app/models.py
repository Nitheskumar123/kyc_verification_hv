from django.db import models
from django.contrib.auth.models import User

class KYCDocument(models.Model):
    DOCUMENT_TYPES = [
        ('aadhaar', 'Aadhaar Card'),
        ('pan', 'PAN Card'),
        ('driving_license', 'Driving License'),
        ('voter_id', 'Voter ID'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    document_image = models.ImageField(upload_to='documents/')
    extracted_text = models.TextField(blank=True)
    is_clear = models.BooleanField(default=False)
    is_valid_type = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.document_type}"

class FaceVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    face_image = models.ImageField(upload_to='faces/')
    is_live = models.BooleanField(default=False)
    confidence_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - Face Verification"