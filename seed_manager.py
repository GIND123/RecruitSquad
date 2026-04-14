"""
One-shot script to write the manager Firestore profile using the Admin SDK.
Run with: backend/.venv/bin/python seed_manager.py
"""
import firebase_admin
from firebase_admin import credentials, firestore, auth as admin_auth

SERVICE_ACCOUNT = "recruit-squad-7d8e1-firebase-adminsdk-fbsvc-d833df39c6.json"
MANAGER_EMAIL   = "manager@recruitsquad.com"

cred = credentials.Certificate(SERVICE_ACCOUNT)
firebase_admin.initialize_app(cred)

db = firestore.client()

# Look up the UID from Firebase Auth
user = admin_auth.get_user_by_email(MANAGER_EMAIL)
uid  = user.uid

profile = {
    "uid":       uid,
    "email":     MANAGER_EMAIL,
    "name":      user.display_name or "Hiring Manager",
    "role":      "manager",
    "createdAt": user.user_metadata.creation_timestamp and
                 __import__("datetime").datetime.utcfromtimestamp(
                     user.user_metadata.creation_timestamp / 1000
                 ).isoformat() + "Z",
}

db.collection("users").document(uid).set(profile)
print(f"✓ Written users/{uid}")
print(f"  email: {MANAGER_EMAIL}")
print(f"  role:  manager")
