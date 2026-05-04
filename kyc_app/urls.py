from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),  # POST only
    path('register/', views.register_view, name='register'),
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('kyc-upload/', views.kyc_upload, name='kyc_upload'),
    path('face-verification/', views.face_verification, name='face_verification'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('voice-instruction/', views.voice_instruction, name='voice_instruction'),
    path('upload-camera-image/', views.upload_camera_image, name='upload_camera_image'),
    path('check-camera-support/', views.check_camera_support, name='check_camera_support'),
    
]
