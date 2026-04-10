import { createBrowserRouter, Navigate } from 'react-router';
import { Home } from './pages/Home';
import { Jobs } from './pages/Jobs';
import { JobDetails } from './pages/JobDetails';
import { Apply } from './pages/Apply';
import { Profile } from './pages/Profile';
import { Login } from './pages/Login';
import { ManagerDashboard } from './pages/ManagerDashboard';
import { CreateJob } from './pages/CreateJob';
import { JobAdvertisements } from './pages/JobAdvertisements';
import { Layout } from './components/Layout';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'jobs', element: <Jobs /> },
      { path: 'jobs/:id', element: <JobDetails /> },
      { path: 'jobs/:id/apply', element: <Apply /> },
      { path: 'job-advertisements', element: <JobAdvertisements /> },
      { path: 'profile', element: <Profile /> },
      { path: 'login', element: <Login /> },
      { path: 'manager', element: <ManagerDashboard /> },
      { path: 'manager/create-job', element: <CreateJob /> },
      { path: '*', element: <Navigate to="/" replace /> }
    ]
  }
]);
