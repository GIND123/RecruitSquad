import { Building2, MapPin, Briefcase, Clock, Users, Share2, Flag } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Separator } from "./ui/separator";
import type { Job } from "./JobCard";

interface JobDetailProps {
  job: Job;
}

export function JobDetail({ job }: JobDetailProps) {
  return (
    <div className="h-full overflow-y-auto bg-white">
      <div className="p-6">
        {/* Header */}
        <div className="flex gap-4 mb-6">
          <div className="flex-shrink-0">
            <div className="w-16 h-16 bg-gray-200 rounded flex items-center justify-center">
              {job.logo ? (
                <img src={job.logo} alt={job.company} className="w-full h-full rounded object-cover" />
              ) : (
                <Building2 className="w-8 h-8 text-gray-500" />
              )}
            </div>
          </div>
          
          <div className="flex-1">
            <h1 className="text-2xl mb-1">{job.title}</h1>
            <p className="text-lg text-gray-700 mb-2">{job.company}</p>
            
            <div className="flex flex-wrap items-center gap-2 text-sm text-gray-600 mb-3">
              <div className="flex items-center gap-1">
                <MapPin className="w-4 h-4" />
                <span>{job.location}</span>
              </div>
              <span>•</span>
              <div className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                <span>{job.postedDate}</span>
              </div>
              <span>•</span>
              <div className="flex items-center gap-1">
                <Users className="w-4 h-4" />
                <span>{job.applicants} applicants</span>
              </div>
            </div>
            
            <div className="flex gap-2 mb-3">
              <Badge variant="secondary">{job.type}</Badge>
              <Badge variant="secondary">{job.level}</Badge>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 mb-6">
          <Button className="flex-1 bg-blue-600 hover:bg-blue-700">
            Apply
          </Button>
          <Button variant="outline">
            <Share2 className="w-4 h-4 mr-2" />
            Share
          </Button>
          <Button variant="outline" size="icon">
            <Flag className="w-4 h-4" />
          </Button>
        </div>

        <Separator className="my-6" />

        {/* Job Description */}
        <div className="space-y-4">
          <div>
            <h2 className="text-lg mb-3">About the job</h2>
            <div className="text-gray-700 space-y-3">
              <p>{job.description}</p>
              
              <p>
                We are looking for a talented professional to join our dynamic team. 
                This role offers an exciting opportunity to work on challenging projects 
                and make a significant impact on our organization's success.
              </p>

              <h3 className="font-semibold mt-4">Responsibilities</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Collaborate with cross-functional teams to deliver high-quality solutions</li>
                <li>Contribute to strategic planning and execution of key initiatives</li>
                <li>Mentor junior team members and promote best practices</li>
                <li>Stay current with industry trends and emerging technologies</li>
                <li>Participate in code reviews and technical discussions</li>
              </ul>

              <h3 className="font-semibold mt-4">Qualifications</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Bachelor's degree in relevant field or equivalent experience</li>
                <li>Proven track record of successful project delivery</li>
                <li>Strong problem-solving and analytical skills</li>
                <li>Excellent communication and teamwork abilities</li>
                <li>Passion for continuous learning and improvement</li>
              </ul>

              <h3 className="font-semibold mt-4">Benefits</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Competitive salary and equity package</li>
                <li>Comprehensive health, dental, and vision insurance</li>
                <li>Flexible work arrangements</li>
                <li>Professional development opportunities</li>
                <li>Collaborative and inclusive work environment</li>
              </ul>
            </div>
          </div>
        </div>

        <Separator className="my-6" />

        {/* Company Info */}
        <div>
          <h2 className="text-lg mb-3">About the company</h2>
          <div className="flex gap-3 mb-4">
            <div className="w-12 h-12 bg-gray-200 rounded flex items-center justify-center">
              <Building2 className="w-6 h-6 text-gray-500" />
            </div>
            <div>
              <p className="font-semibold">{job.company}</p>
              <p className="text-sm text-gray-600">Technology • 1,000+ employees</p>
            </div>
          </div>
          <p className="text-gray-700">
            We're a leading company in our industry, committed to innovation and 
            excellence. Our mission is to create meaningful solutions that make a 
            difference in people's lives.
          </p>
        </div>
      </div>
    </div>
  );
}
