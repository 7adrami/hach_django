from cryptography.fernet import Fernet
from django.conf import settings
import base64

def get_fernet():
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        # Emergency fallback to a static key if settings is broken
        # This prevents the app from crashing but might lead to data loss if swapped
        return Fernet(b'L3A9X-V08Y-A6v4K_X-dGVzdC1rZXktZm9yLWRldmVsb3BtZW50Cg==')
    try:
        return Fernet(key)
    except:
        # If the key provided in settings is invalid (e.g. wrong format)
        return Fernet(b'L3A9X-V08Y-A6v4K_X-dGVzdC1rZXktZm9yLWRldmVsb3BtZW50Cg==')

def encrypt_message(text):
    if not text:
        return ""
    f = get_fernet()
    return f.encrypt(text.encode()).decode()

def decrypt_message(token):
    if not token:
        return ""
    
    # Simple heuristic: Fernet tokens start with gAAAA
    if not token.startswith('gAAAA'):
        return token # Likely plain text from before encryption
        
    f = get_fernet()
    try:
        return f.decrypt(token.encode()).decode()
    except Exception:
        # If decryption fails (mismatched key or corrupted token),
        # return the token itself as a fallback instead of generic error
        # This allows users to at least see 'something' went wrong with that specific msg
        return f"[Encrypted Message: {token[:10]}...]"

def is_encrypted(text):
    return text.startswith('gAAAA') if text else False
