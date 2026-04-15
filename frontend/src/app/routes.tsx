import { createBrowserRouter, Navigate } from 'react-router';
import { Home } from './pages/Home';
import { Jobs } from './pages/Jobs';
import { JobDetails } from './pages/JobDetails';
import { Apply } from './pages/Apply';
import { Profile } from './pages/Profile';
import { Login } from './pages/Login';
import { ManagerDashboard } from './pages/ManagerDashboard';
import { CreateJob } from './pages/CreateJob';
import { JobCandidates } from './pages/JobCandidates';
import { BehavioralChat } from './pages/BehavioralChat';
import { OnlineAssessment } from './pages/OnlineAssessment';
import { InterviewSchedule } from './pages/InterviewSchedule';
import { JobAdvertisements } from './pages/JobAdvertisements';
import { EmployerLanding } from './pages/EmployerLanding';
import { OrgSignup } from './pages/OrgSignup';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: 'jobs', element: <Jobs /> },
      { path: 'jobs/:id', element: <JobDetails /> },
      { path: 'jobs/:id/apply', element: <Apply /> },
      { path: 'oa/:token', element: <OnlineAssessment /> },
      { path: 'schedule/:candidateId', element: <InterviewSchedule /> },
      { path: 'oa/:token/chat', element: <BehavioralChat /> },
      { path: 'job-advertisements', element: <JobAdvertisements /> },
      { path: 'login', element: <Login /> },
      { path: 'employer', element: <EmployerLanding /> },
      { path: 'employer/new', element: <OrgSignup /> },
      {
        path: 'profile',
        element: (
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        ),
      },
      {
        path: 'manager',
        element: (
          <ProtectedRoute requireManager>
            <ManagerDashboard />
          </ProtectedRoute>
        ),
      },
      {
        path: 'manager/create-job',
        element: (
          <ProtectedRoute requireManager>
            <CreateJob />
          </ProtectedRoute>
        ),
      },
      {
        path: 'manager/jobs/:jobId',
        element: (
          <ProtectedRoute requireManager>
            <JobCandidates />
          </ProtectedRoute>
        ),
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
