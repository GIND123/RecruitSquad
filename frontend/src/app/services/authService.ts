import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  sendPasswordResetEmail,
  updateProfile,
} from 'firebase/auth';
import { doc, getDoc, setDoc } from 'firebase/firestore';
import { auth, db, googleProvider } from './firebase';

export type UserRole = 'candidate' | 'manager';

export interface UserProfile {
  uid: string;
  email: string;
  name: string;
  role: UserRole;
  createdAt: string;
}

export async function getUserProfile(uid: string): Promise<UserProfile | null> {
  const snap = await getDoc(doc(db, 'users', uid));
  return snap.exists() ? (snap.data() as UserProfile) : null;
}

export async function createUserProfile(
  uid: string,
  data: Omit<UserProfile, 'uid'>
): Promise<void> {
  await setDoc(doc(db, 'users', uid), { uid, ...data });
}

export async function loginWithEmail(email: string, password: string) {
  return signInWithEmailAndPassword(auth, email, password);
}

export async function signupWithEmail(email: string, password: string, name: string) {
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  await updateProfile(cred.user, { displayName: name });
  await createUserProfile(cred.user.uid, {
    email,
    name,
    role: 'candidate',
    createdAt: new Date().toISOString(),
  });
  return cred;
}

export async function loginWithGoogle() {
  const cred = await signInWithPopup(auth, googleProvider);
  const existing = await getUserProfile(cred.user.uid);
  if (!existing) {
    await createUserProfile(cred.user.uid, {
      email: cred.user.email!,
      name: cred.user.displayName || cred.user.email!.split('@')[0],
      role: 'candidate',
      createdAt: new Date().toISOString(),
    });
  }
  return cred;
}

export async function logoutUser() {
  return signOut(auth);
}

export async function resetPassword(email: string) {
  return sendPasswordResetEmail(auth, email);
}

/** Map Firebase auth error codes to user-friendly messages */
export function firebaseAuthError(code: string): string {
  const map: Record<string, string> = {
    'auth/user-not-found': 'No account found with this email.',
    'auth/wrong-password': 'Incorrect password.',
    'auth/invalid-credential': 'Invalid email or password.',
    'auth/email-already-in-use': 'An account with this email already exists.',
    'auth/weak-password': 'Password must be at least 6 characters.',
    'auth/invalid-email': 'Please enter a valid email address.',
    'auth/popup-closed-by-user': 'Sign-in popup was closed. Please try again.',
    'auth/too-many-requests': 'Too many attempts. Please try again later.',
    'auth/network-request-failed': 'Network error. Check your connection.',
  };
  return map[code] ?? 'Something went wrong. Please try again.';
}
