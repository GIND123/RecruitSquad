import { RouterProvider } from 'react-router';
import { AuthProvider } from './contexts/AuthContext';
import { JobProvider } from './contexts/JobContext';
import { router } from './routes';

export default function App() {
  return (
    <AuthProvider>
      <JobProvider>
        <RouterProvider router={router} />
      </JobProvider>
    </AuthProvider>
  );
}
