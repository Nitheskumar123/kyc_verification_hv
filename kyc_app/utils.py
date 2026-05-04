import cv2
import numpy as np
import pytesseract
import face_recognition
from PIL import Image
import re
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

class DocumentProcessor:
    @staticmethod
    def is_image_clear(image_path, threshold=100):
        """Check if image is clear using Laplacian variance"""
        image = cv2.imread(str(image_path))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        return variance > threshold

    @staticmethod
    def extract_text(image_path):
        """Extract text from image using pytesseract with cleanup"""
        try:
            text = pytesseract.image_to_string(Image.open(image_path))

            # Normalize text
            text = text.lower()
            text = re.sub(r'\s+', ' ', text)  # remove newlines, multiple spaces
            text = text.strip()

            # Fix common OCR mistakes
            replacements = {
                "licence": "license",   # unify spelling
                "licencc": "license",
                "licenec": "license"
            }
            for wrong, correct in replacements.items():
                text = text.replace(wrong, correct)

            return text
        except Exception as e:
            print(f"OCR extraction failed: {e}")
            return ""


    @staticmethod
    def validate_document_type(text, expected_type):
        """Validate if document matches expected type with flexible keywords"""
        text_lower = text.lower()

        patterns = {
            'aadhaar': ['aadhaar', 'aadhar', 'unique identification'],
            'pan': ['income tax', 'pan', 'permanent account'],
            'driving_license': [
                'driving licence',   # British spelling (common in India)
                'driving license',   # American spelling
                'licence number',
                'transport department',
                'union driving licence'
            ],
            'voter_id': ['election commission', 'voter', 'electoral']
        }

        if expected_type in patterns:
            return any(re.search(pattern, text_lower) for pattern in patterns[expected_type])
        return False


class FaceProcessor:
    @staticmethod
    def detect_face(image_path):
        """Detect if face is present in image"""
        try:
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image)
            return len(face_locations) > 0
        except:
            return False

    @staticmethod
    def liveness_check(image_path):
        """Simple liveness check - detect if eyes are open"""
        try:
            image = cv2.imread(str(image_path))
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Load eye cascade
            eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
            eyes = eye_cascade.detectMultiScale(gray, 1.1, 4)
            
            return len(eyes) >= 2  # At least 2 eyes detected
        except:
            return False

    @staticmethod
    def compare_faces(image1_path, image2_path, tolerance=0.6):
        """Compare two face images"""
        try:
            image1 = face_recognition.load_image_file(image1_path)
            image2 = face_recognition.load_image_file(image2_path)
            
            encoding1 = face_recognition.face_encodings(image1)
            encoding2 = face_recognition.face_encodings(image2)
            
            if len(encoding1) > 0 and len(encoding2) > 0:
                distance = face_recognition.face_distance([encoding1[0]], encoding2[0])
                return distance[0] < tolerance, 1 - distance[0]
            return False, 0.0
        except:
            return False, 0.0