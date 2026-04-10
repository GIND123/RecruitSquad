import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Search, Briefcase, Users, TrendingUp, ArrowRight } from 'lucide-react';

export const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Build Your Career at Google
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Join a team of passionate innovators working to organize the world's information and make it universally accessible and useful.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button size="lg" onClick={() => navigate('/jobs')} className="text-lg px-8">
            <Search className="w-5 h-5 mr-2" />
            Explore Jobs
          </Button>
          <Button size="lg" variant="outline" onClick={() => navigate('/login')} className="text-lg px-8">
            Manager Login
          </Button>
        </div>
      </section>

      {/* Stats Section */}
      <section className="container mx-auto px-4 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <Card className="p-8 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Briefcase className="w-8 h-8 text-blue-600" />
            </div>
            <h3 className="text-3xl font-bold mb-2">500+</h3>
            <p className="text-gray-600">Open Positions</p>
          </Card>
          
          <Card className="p-8 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Users className="w-8 h-8 text-purple-600" />
            </div>
            <h3 className="text-3xl font-bold mb-2">150,000+</h3>
            <p className="text-gray-600">Employees Worldwide</p>
          </Card>
          
          <Card className="p-8 text-center hover:shadow-lg transition-shadow">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <TrendingUp className="w-8 h-8 text-green-600" />
            </div>
            <h3 className="text-3xl font-bold mb-2">40+</h3>
            <p className="text-gray-600">Countries</p>
          </Card>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="container mx-auto px-4 py-16">
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">
          Why Work at Google?
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {benefits.map((benefit, index) => (
            <Card key={index} className="p-6 hover:shadow-lg transition-shadow">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
                  <benefit.icon className="w-6 h-6 text-blue-600" />
                </div>
                <div>
                  <h3 className="font-semibold mb-2">{benefit.title}</h3>
                  <p className="text-sm text-gray-600">{benefit.description}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <Card className="p-12 bg-gradient-to-r from-blue-600 to-purple-600 text-white">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready to Make an Impact?
          </h2>
          <p className="text-lg mb-8 opacity-90">
            Browse our open positions and find your perfect role
          </p>
          <Button 
            size="lg" 
            variant="secondary" 
            onClick={() => navigate('/jobs')}
            className="text-lg px-8"
          >
            View All Jobs
            <ArrowRight className="w-5 h-5 ml-2" />
          </Button>
        </Card>
      </section>
    </div>
  );
};

const benefits = [
  {
    icon: Briefcase,
    title: 'Competitive Compensation',
    description: 'Industry-leading salaries and equity packages for all employees.'
  },
  {
    icon: Users,
    title: 'Health & Wellness',
    description: 'Comprehensive health insurance and wellness programs for you and your family.'
  },
  {
    icon: TrendingUp,
    title: 'Career Growth',
    description: 'Continuous learning opportunities and clear career progression paths.'
  },
  {
    icon: Briefcase,
    title: 'Work-Life Balance',
    description: 'Flexible work arrangements and generous time off policies.'
  },
  {
    icon: Users,
    title: 'Collaborative Culture',
    description: 'Work with brilliant minds in an inclusive and diverse environment.'
  },
  {
    icon: TrendingUp,
    title: 'Innovation',
    description: 'Access to cutting-edge technology and resources to bring your ideas to life.'
  }
];
