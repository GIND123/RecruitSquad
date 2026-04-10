import React, { createContext, useContext, useState, useEffect } from 'react';

export interface Job {
  id: string;
  title: string;
  department: string;
  location: string;
  type: 'Full-time' | 'Part-time' | 'Contract' | 'Internship';
  description: string;
  requirements: string[];
  responsibilities: string[];
  salary?: string;
  postedDate: string;
  status: 'active' | 'closed';
}

export interface Application {
  id: string;
  jobId: string;
  jobTitle: string;
  candidateName: string;
  candidateEmail: string;
  resumeFile: string; // Base64 encoded or file name
  resumeName: string;
  appliedDate: string;
  status: 'pending' | 'reviewed' | 'rejected' | 'accepted';
}

interface JobContextType {
  jobs: Job[];
  applications: Application[];
  addJob: (job: Omit<Job, 'id' | 'postedDate' | 'status'>) => void;
  updateJob: (id: string, job: Partial<Job>) => void;
  deleteJob: (id: string) => void;
  applyToJob: (application: Omit<Application, 'id' | 'appliedDate' | 'status'>) => void;
  getUserApplications: (email: string) => Application[];
}

const JobContext = createContext<JobContextType | undefined>(undefined);

// Mock initial jobs
const initialJobs: Job[] = [
  {
    id: '1',
    title: 'Senior Software Engineer',
    department: 'Engineering',
    location: 'Mountain View, CA',
    type: 'Full-time',
    description: 'We are looking for a talented Senior Software Engineer to join our team and help build the next generation of products that will impact billions of users.',
    requirements: [
      'BS/MS degree in Computer Science or equivalent practical experience',
      '5+ years of software development experience',
      'Experience with modern web technologies (React, TypeScript, Node.js)',
      'Strong problem-solving skills and attention to detail'
    ],
    responsibilities: [
      'Design and implement scalable backend services',
      'Collaborate with cross-functional teams',
      'Mentor junior engineers',
      'Write clean, maintainable code with comprehensive tests'
    ],
    salary: '$150,000 - $200,000',
    postedDate: '2026-03-15',
    status: 'active'
  },
  {
    id: '2',
    title: 'Product Manager',
    department: 'Product',
    location: 'San Francisco, CA',
    type: 'Full-time',
    description: 'Join our product team to drive the vision and strategy for innovative products used by millions worldwide.',
    requirements: [
      '3+ years of product management experience',
      'Strong analytical and data-driven decision making skills',
      'Excellent communication and stakeholder management',
      'Experience shipping consumer-facing products'
    ],
    responsibilities: [
      'Define product roadmap and strategy',
      'Work closely with engineering and design teams',
      'Analyze user metrics and feedback',
      'Drive product launches from conception to delivery'
    ],
    salary: '$130,000 - $180,000',
    postedDate: '2026-03-20',
    status: 'active'
  },
  {
    id: '3',
    title: 'UX Designer',
    department: 'Design',
    location: 'New York, NY',
    type: 'Full-time',
    description: 'We are seeking a creative UX Designer to craft beautiful and intuitive user experiences for our products.',
    requirements: [
      'Portfolio demonstrating UX design skills',
      '4+ years of UX design experience',
      'Proficiency in Figma, Sketch, or similar tools',
      'Strong understanding of design principles and user-centered design'
    ],
    responsibilities: [
      'Create wireframes, prototypes, and high-fidelity designs',
      'Conduct user research and usability testing',
      'Collaborate with product and engineering teams',
      'Maintain and evolve design systems'
    ],
    salary: '$120,000 - $160,000',
    postedDate: '2026-03-18',
    status: 'active'
  }
];

export const JobProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);

  useEffect(() => {
    // Load jobs from localStorage or use initial jobs
    const savedJobs = localStorage.getItem('jobs');
    if (savedJobs) {
      setJobs(JSON.parse(savedJobs));
    } else {
      setJobs(initialJobs);
      localStorage.setItem('jobs', JSON.stringify(initialJobs));
    }

    // Load applications from localStorage
    const savedApplications = localStorage.getItem('applications');
    if (savedApplications) {
      setApplications(JSON.parse(savedApplications));
    }
  }, []);

  const addJob = (job: Omit<Job, 'id' | 'postedDate' | 'status'>) => {
    const newJob: Job = {
      ...job,
      id: `job-${Date.now()}`,
      postedDate: new Date().toISOString().split('T')[0],
      status: 'active'
    };
    const updatedJobs = [...jobs, newJob];
    setJobs(updatedJobs);
    localStorage.setItem('jobs', JSON.stringify(updatedJobs));
  };

  const updateJob = (id: string, updatedJob: Partial<Job>) => {
    const updatedJobs = jobs.map(job => 
      job.id === id ? { ...job, ...updatedJob } : job
    );
    setJobs(updatedJobs);
    localStorage.setItem('jobs', JSON.stringify(updatedJobs));
  };

  const deleteJob = (id: string) => {
    const updatedJobs = jobs.filter(job => job.id !== id);
    setJobs(updatedJobs);
    localStorage.setItem('jobs', JSON.stringify(updatedJobs));
  };

  const applyToJob = (application: Omit<Application, 'id' | 'appliedDate' | 'status'>) => {
    const newApplication: Application = {
      ...application,
      id: `app-${Date.now()}`,
      appliedDate: new Date().toISOString().split('T')[0],
      status: 'pending'
    };
    const updatedApplications = [...applications, newApplication];
    setApplications(updatedApplications);
    localStorage.setItem('applications', JSON.stringify(updatedApplications));
  };

  const getUserApplications = (email: string): Application[] => {
    return applications.filter(app => app.candidateEmail === email);
  };

  return (
    <JobContext.Provider value={{
      jobs,
      applications,
      addJob,
      updateJob,
      deleteJob,
      applyToJob,
      getUserApplications
    }}>
      {children}
    </JobContext.Provider>
  );
};

export const useJobs = () => {
  const context = useContext(JobContext);
  if (context === undefined) {
    throw new Error('useJobs must be used within a JobProvider');
  }
  return context;
};
