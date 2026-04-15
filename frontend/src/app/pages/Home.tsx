import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Search, Briefcase, Users, Zap, ArrowRight } from 'lucide-react';

export const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Hero Section */}
      <section className="container mx-auto px-4 py-24 text-center">
        <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Hiring, Made Smarter
        </h1>
        <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto">
          RecruitSquad connects talented candidates with the right opportunities — and gives organizations the tools to hire with confidence.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button size="lg" onClick={() => navigate('/jobs')} className="text-lg px-8">
            <Search className="w-5 h-5 mr-2" />
            Explore Jobs
          </Button>
          <Button
            size="lg"
            variant="outline"
            onClick={() => navigate('/employer')}
            className="text-lg px-8"
          >
            For Employers
          </Button>
        </div>
      </section>

      {/* How It Works */}
      <section className="container mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold text-center mb-12 text-gray-800">
          How It Works
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <Card className="p-8 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Search className="w-8 h-8 text-blue-600" />
            </div>
            <h3 className="text-xl font-semibold mb-2">Browse Openings</h3>
            <p className="text-gray-600 text-sm">
              Explore roles across industries and find positions that match your skills and goals.
            </p>
          </Card>

          <Card className="p-8 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Briefcase className="w-8 h-8 text-purple-600" />
            </div>
            <h3 className="text-xl font-semibold mb-2">Apply with Ease</h3>
            <p className="text-gray-600 text-sm">
              Submit your application in minutes. Track your status every step of the way.
            </p>
          </Card>

          <Card className="p-8 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Zap className="w-8 h-8 text-green-600" />
            </div>
            <h3 className="text-xl font-semibold mb-2">Get Hired Faster</h3>
            <p className="text-gray-600 text-sm">
              AI-assisted screening helps great candidates surface quickly and move through the process faster.
            </p>
          </Card>
        </div>
      </section>

      {/* For Organizations */}
      <section className="container mx-auto px-4 py-16">
        <Card className="p-12 bg-gradient-to-r from-blue-600 to-purple-600 text-white text-center">
          <div className="flex justify-center mb-4">
            <Users className="w-12 h-12 opacity-90" />
          </div>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Are You Hiring?
          </h2>
          <p className="text-lg mb-8 opacity-90 max-w-xl mx-auto">
            Register your organization to post jobs, manage candidates, and streamline your recruitment pipeline.
          </p>
          <Button
            size="lg"
            variant="secondary"
            onClick={() => navigate('/employer/new')}
            className="text-lg px-8"
          >
            Get Started
            <ArrowRight className="w-5 h-5 ml-2" />
          </Button>
        </Card>
      </section>
    </div>
  );
};
