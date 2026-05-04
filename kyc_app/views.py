from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from .forms import CustomUserCreationForm, KYCDocumentForm, FaceVerificationForm
from .models import KYCDocument, FaceVerification
from .utils import DocumentProcessor, FaceProcessor
import json
import base64
from io import BytesIO
from PIL import Image
import uuid

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})

@login_required
def dashboard(request):
    documents = KYCDocument.objects.filter(user=request.user)
    face_verifications = FaceVerification.objects.filter(user=request.user)
    return render(request, 'dashboard.html', {
        'documents': documents,
        'face_verifications': face_verifications
    })

@login_required
def kyc_upload(request):
    if request.method == 'POST':
        form = KYCDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.user = request.user

            # Handle camera captured image
            if 'camera_data' in request.POST:
                try:
                    # Decode base64 image data
                    image_data = request.POST['camera_data']
                    format, imgstr = image_data.split(';base64,')
                    ext = format.split('/')[-1]
                    
                    # Create file from base64 data
                    img_file = ContentFile(
                        base64.b64decode(imgstr),
                        name=f'document_{uuid.uuid4().hex}.{ext}'
                    )
                    doc.document_image = img_file
                except Exception as e:
                    messages.error(request, f'Error processing camera image: {str(e)}')
                    return render(request, 'kyc_upload.html', {'form': form})
            else:
                # Regular file upload
                doc.document_image = request.FILES['document_image']

            doc.save()  # Save to get file path

            processor = DocumentProcessor()

            # Check clarity
            is_clear = processor.is_image_clear(doc.document_image.path)

            # Extract text
            extracted_text = processor.extract_text(doc.document_image.path)

            # Validate document type
            is_valid_type = processor.validate_document_type(
                extracted_text, doc.document_type
            )

            # Process results
            if not is_clear:
                messages.error(request, '📷 Document image is unclear. Please retake the photo with better lighting.')
                doc.delete()  # remove invalid file
            elif not is_valid_type:
                messages.error(request, f'📄 Document type mismatch. Expected {doc.get_document_type_display()}, please upload correct document.')
                doc.delete()  # remove invalid file
            else:
                doc.is_clear = True
                doc.extracted_text = extracted_text
                doc.is_valid_type = True
                doc.save()
                messages.success(request, '✅ Document uploaded successfully and is under review.')
                return redirect('face_verification')

    else:
        form = KYCDocumentForm()
    
    return render(request, 'kyc_upload.html', {'form': form})

@login_required
def face_verification(request):
    if request.method == 'POST':
        form = FaceVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            face_ver = form.save(commit=False)
            face_ver.user = request.user
            
            # Handle camera captured image
            if 'camera_data' in request.POST:
                try:
                    # Decode base64 image data
                    image_data = request.POST['camera_data']
                    format, imgstr = image_data.split(';base64,')
                    ext = format.split('/')[-1]
                    
                    # Create file from base64 data
                    img_file = ContentFile(
                        base64.b64decode(imgstr),
                        name=f'face_{uuid.uuid4().hex}.{ext}'
                    )
                    face_ver.face_image = img_file
                except Exception as e:
                    messages.error(request, f'Error processing camera image: {str(e)}')
                    return render(request, 'verification.html', {'form': form})
            else:
                # Regular file upload
                face_ver.face_image = request.FILES['face_image']
            
            face_ver.save()  # Save to get file path
            
            # Process face
            processor = FaceProcessor()
            
            # Check if face is detected
            if not processor.detect_face(face_ver.face_image.path):
                messages.error(request, '👤 No face detected. Please retake the photo ensuring your face is clearly visible.')
                face_ver.delete()
            else:
                # Liveness check
                face_ver.is_live = processor.liveness_check(face_ver.face_image.path)
                face_ver.confidence_score = 0.8 if face_ver.is_live else 0.3
                face_ver.save()
                
                if face_ver.is_live:
                    messages.success(request, '✅ Face verification completed successfully! Your submission is under review.')
                    return redirect('dashboard')
                else:
                    messages.warning(request, '⚠️ Liveness check failed. Please ensure good lighting and look directly at camera.')
                    # Don't delete, allow manual review
    else:
        form = FaceVerificationForm()
    
    return render(request, 'verification.html', {'form': form})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def upload_camera_image(request):
    """API endpoint to handle camera captured images"""
    try:
        data = json.loads(request.body)
        image_data = data.get('image_data')
        upload_type = data.get('type')  # 'document' or 'face'
        
        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image data provided'})
        
        # Decode base64 image
        format, imgstr = image_data.split(';base64,')
        ext = format.split('/')[-1]
        
        # Generate unique filename
        filename = f'{upload_type}_{request.user.id}_{uuid.uuid4().hex}.{ext}'
        
        # Create file from base64 data
        img_file = ContentFile(
            base64.b64decode(imgstr),
            name=filename
        )
        
        # Save temporarily and return path
        file_path = default_storage.save(f'temp/{filename}', img_file)
        
        return JsonResponse({
            'success': True,
            'file_path': file_path,
            'filename': filename
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Error processing image: {str(e)}'
        })

from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render
from django.db.models import Max
from django.contrib.auth.models import User
@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/login/')


def admin_panel(request):
    # Handle status updates
    if request.method == 'POST':
        action = request.POST.get('action')   # verified / rejected
        item_type = request.POST.get('type') # document / face
        item_id = request.POST.get('id')
        
        if item_type == 'document':
            doc = KYCDocument.objects.get(id=item_id)
            doc.status = action
            doc.save()
            messages.success(request, f'{doc.get_document_type_display()} {action} successfully.')

            # ✅ Send email to user
            subject = f"KYC Update: {doc.get_document_type_display()} {action.title()}"
            message = f"Dear {doc.user.get_full_name() or doc.user.username},\n\n" \
                      f"Your {doc.get_document_type_display()} has been {action}.\n\n" \
                      f"Regards,\nKYC Verification Team"
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,   # from email
                [doc.user.email],              # to user
                fail_silently=True,
            )

        elif item_type == 'face':
            face = FaceVerification.objects.get(id=item_id)
            face.status = action
            face.save()
            messages.success(request, f'Face verification {action} successfully.')

            # ✅ Send email to user
            subject = f"KYC Update: Face Verification {action.title()}"
            message = f"Dear {face.user.get_full_name() or face.user.username},\n\n" \
                      f"Your Face Verification has been {action}.\n\n" \
                      f"Regards,\nKYC Verification Team"
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [face.user.email],
                fail_silently=True,
            )

    # Get unique users with submissions
    user_ids_with_docs = KYCDocument.objects.values_list('user_id', flat=True).distinct()
    user_ids_with_faces = FaceVerification.objects.values_list('user_id', flat=True).distinct()
    all_user_ids = set(list(user_ids_with_docs) + list(user_ids_with_faces))
    
    users_with_submissions = User.objects.filter(id__in=all_user_ids)
    
    # Organize data by user
    user_submissions = []
    for user in users_with_submissions:
        documents = KYCDocument.objects.filter(user=user).order_by('-created_at')
        face_verifications = FaceVerification.objects.filter(user=user).order_by('-created_at')
        
        pending_docs = documents.filter(status='pending').count()
        verified_docs = documents.filter(status='verified').count()
        rejected_docs = documents.filter(status='rejected').count()
        
        pending_faces = face_verifications.filter(status='pending').count()
        verified_faces = face_verifications.filter(status='verified').count()
        rejected_faces = face_verifications.filter(status='rejected').count()
        
        user_data = {
            'user': user,
            'documents': documents,
            'face_verifications': face_verifications,
            'stats': {
                'total_documents': documents.count(),
                'total_faces': face_verifications.count(),
                'pending_documents': pending_docs,
                'pending_faces': pending_faces,
                'verified_documents': verified_docs,
                'verified_faces': verified_faces,
                'rejected_documents': rejected_docs,
                'rejected_faces': rejected_faces,
            },
            'latest_submission': max(
                documents.aggregate(latest=Max('created_at'))['latest'] or user.date_joined,
                face_verifications.aggregate(latest=Max('created_at'))['latest'] or user.date_joined
            )
        }
        user_submissions.append(user_data)
    
    # Sort by latest submission
    user_submissions.sort(key=lambda x: x['latest_submission'], reverse=True)
    
    # Overall statistics
    total_stats = {
        'total_users': len(user_submissions),
        'total_documents': KYCDocument.objects.count(),
        'total_faces': FaceVerification.objects.count(),
        'pending_documents': KYCDocument.objects.filter(status='pending').count(),
        'pending_faces': FaceVerification.objects.filter(status='pending').count(),
        'verified_documents': KYCDocument.objects.filter(status='verified').count(),
        'verified_faces': FaceVerification.objects.filter(status='verified').count(),
    }
    
    return render(request, 'admin_panel.html', {
        'user_submissions': user_submissions,
        'total_stats': total_stats
    })

@csrf_exempt
@require_http_methods(["POST"])
def voice_instruction(request):
    """API endpoint for voice instructions"""
    try:
        data = json.loads(request.body)
        language = data.get('language', 'english')
        step = data.get('step', 'welcome')
        
        instructions = {
            'english': {
                'welcome': 'Welcome to KYC verification system. Please follow the instructions carefully for successful verification.',
                'document_upload': 'Please take a clear photo of your document. Ensure all text is visible, the document is well-lit, and there are no shadows or blur.',
                'face_capture': 'Please look directly at the camera for face verification. Ensure good lighting on your face and remove any glasses or hats if possible.',
                'success': 'Verification completed successfully. Thank you for using our KYC system.',
                'retry': 'Please try again with better lighting and positioning.',
                'camera_permission': 'Please allow camera access to take photos for verification.',
                'processing': 'Processing your verification. Please wait a moment.'
            },
            'hindi': {
                'welcome': 'केवाईसी सत्यापन प्रणाली में आपका स्वागत है। सफल सत्यापन के लिए कृपया निर्देशों का ध्यानपूर्वक पालन करें।',
                'document_upload': 'कृपया अपने दस्तावेज़ की स्पष्ट फोटो लें। सुनिश्चित करें कि सभी टेक्स्ट दिखाई दे, दस्तावेज़ अच्छी तरह से रोशन हो और कोई छाया या धुंधलाहट न हो।',
                'face_capture': 'चेहरे की पहचान के लिए कृपया सीधे कैमरे की ओर देखें। अपने चेहरे पर अच्छी रोशनी सुनिश्चित करें और यदि संभव हो तो चश्मा या टोपी हटा दें।',
                'success': 'सत्यापन सफलतापूर्वक पूरा हुआ। हमारी केवाईसी प्रणाली का उपयोग करने के लिए धन्यवाद।',
                'retry': 'कृपया बेहतर रोशनी और स्थिति के साथ फिर से कोशिश करें।',
                'camera_permission': 'सत्यापन के लिए फोटो लेने हेतु कृपया कैमरा एक्सेस की अनुमति दें।',
                'processing': 'आपका सत्यापन प्रक्रिया में है। कृपया एक पल प्रतीक्षा करें।'
            },
            'tamil': {
                'welcome': 'KYC சரிபார்ப்பு அமைப்பிற்கு வரவேற்கிறோम். வெற்றிகரமான சரிபார்ப்பிற்காக தயவுசெய்து வழிமுறைகளை கவனமாக பின்பற்றவும்.',
                'document_upload': 'தயவுசெய்து உங்கள் ஆவணத்தின் தெளிவான புகைப்படம் எடுக்கவும். அனைத்து உரையும் தெரியும், ஆவணம் நன்றாக ஒளிர்ந்திருக்கும் மற்றும் நிழல் அல்லது மங்கலானது இல்லை என்பதை உறுதிப்படuத்தவும்.',
                'face_capture': 'முக சரிபார்ப்பிற்காக தயவுசெய்து கேமராவை நேராக பாருங்கள். உங்கள் முகத்தில் நல்ல ஒளி இருப்பதை உறுதிப்படுத்தி, முடிந்தால் கண்ணாடி அல்லது தொப்பியை அகற்றவும்.',
                'success': 'சரிபார்ப்பு வெற்றிகரமாக நிறைவேற்றப்பட்டது. எங்கள் KYC அமைப்பைப் பயன்படுத்தியதற்கு நன்றி.',
                'retry': 'தயவுசெய்து சிறந்த ஒளி மற்றும் நிலைப்படுத்தலுடன் மீண்டும் முயற்சிக்கவும்.',
                'camera_permission': 'சரிபார்ப்பிற்கான புகைப்படங்களை எடுக்க தயவுசெய்து கேமரா அணுகலை அனுமதிக்கவும்.',
                'processing': 'உங்கள் சரிபார்ப்பு செயலாக்கப்படுகிறது. தயவுசெய்து சிறிது காத்திருக்கவும்.'
            }
        }
        
        message = instructions.get(language, instructions['english']).get(step, '')
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt 
@require_http_methods(["POST"])
def check_camera_support(request):
    """Check if browser supports camera features"""
    return JsonResponse({
        'success': True,
        'supported': True,  # Assume support, let frontend handle detection
        'message': 'Camera support check completed'
    })

