/**
 * seed-manager.mjs
 * Creates (or signs into) a manager Firebase Auth account and writes
 * the users/{uid} Firestore doc with role = "manager".
 *
 * Usage:
 *   node seed-manager.mjs
 *
 * Edit MANAGER_EMAIL and MANAGER_PASSWORD below before running.
 */

import { initializeApp } from 'firebase/app';
import {
  getAuth,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  updateProfile,
} from 'firebase/auth';
import { getFirestore, doc, setDoc } from 'firebase/firestore';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// ── Config ────────────────────────────────────────────────────────────────────
const MANAGER_NAME     = 'Hiring Manager';
const MANAGER_EMAIL    = 'manager@recruitsquad.com'; // change me
const MANAGER_PASSWORD = 'Change@123';               // change me
// ─────────────────────────────────────────────────────────────────────────────

const __dir = dirname(fileURLToPath(import.meta.url));
const envVars = Object.fromEntries(
  readFileSync(resolve(__dir, '.env'), 'utf8')
    .split('\n')
    .filter((l) => l.includes('=') && !l.startsWith('#'))
    .map((l) => {
      const idx = l.indexOf('=');
      return [l.slice(0, idx).trim(), l.slice(idx + 1).trim()];
    })
);

const app  = initializeApp({
  apiKey:            envVars.VITE_FIREBASE_API_KEY,
  authDomain:        envVars.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:         envVars.VITE_FIREBASE_PROJECT_ID,
  storageBucket:     envVars.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: envVars.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId:             envVars.VITE_FIREBASE_APP_ID,
});
const auth = getAuth(app);
const db   = getFirestore(app);

async function seed() {
  let uid;

  // Step 1: get or create the Auth account
  try {
    console.log(`Creating Auth account: ${MANAGER_EMAIL}`);
    const cred = await createUserWithEmailAndPassword(auth, MANAGER_EMAIL, MANAGER_PASSWORD);
    uid = cred.user.uid;
    await updateProfile(cred.user, { displayName: MANAGER_NAME });
    console.log('✓ Auth account created');
  } catch (err) {
    if (err.code === 'auth/email-already-in-use') {
      console.log('  Auth account already exists — signing in to get UID...');
      const cred = await signInWithEmailAndPassword(auth, MANAGER_EMAIL, MANAGER_PASSWORD);
      uid = cred.user.uid;
      console.log('✓ Signed in');
    } else {
      throw err;
    }
  }

  // Step 2: write Firestore doc
  console.log(`Writing Firestore users/${uid} ...`);
  const profile = {
    uid,
    email:     MANAGER_EMAIL,
    name:      MANAGER_NAME,
    role:      'manager',
    createdAt: new Date().toISOString(),
  };

  try {
    await setDoc(doc(db, 'users', uid), profile);
  } catch (err) {
    if (err.code === 5 || String(err.message).includes('NOT_FOUND')) {
      console.error('\n✗ Firestore database not found.');
      console.error('  → Go to Firebase Console → Firestore Database → Create database');
      console.error(`  → Project: ${envVars.VITE_FIREBASE_PROJECT_ID}`);
      console.error('  → Choose a region and start in production or test mode');
      console.error('  → Then re-run this script\n');
      console.error('  Your Auth account IS created. UID:', uid);
      process.exit(1);
    }
    throw err;
  }

  console.log('\n✓ Manager seeded successfully');
  console.log('─────────────────────────────────────────');
  console.log('UID:      ', uid);
  console.log('Email:    ', MANAGER_EMAIL);
  console.log('Password: ', MANAGER_PASSWORD);
  console.log('Role:      manager');
  console.log('Firestore: users/' + uid);
  console.log('─────────────────────────────────────────');
  process.exit(0);
}

seed().catch((err) => {
  console.error('\n✗ Unexpected error:', err.code ?? err.message);
  process.exit(1);
});
