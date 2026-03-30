import { Building2, MapPin, Briefcase, Clock, Bookmark } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  type: string;
  level: string;
  postedDate: string;
  applicants: number;
  description: string;
  logo?: string;
  promoted?: boolean;
}

interface JobCardProps {
  job: Job;
  onClick: () => void;
  isActive: boolean;
}

export function JobCard({ job, onClick, isActive }: JobCardProps) {
  return (
    <div
      onClick={onClick}
      className={`p-4 border-b cursor-pointer hover:bg-gray-50 transition-colors ${
        isActive ? "bg-blue-50 border-l-4 border-l-blue-600" : ""
      }`}
    >
      <div className="flex gap-3">
        <div className="flex-shrink-0">
          <div className="w-14 h-14 bg-gray-200 rounded flex items-center justify-center">
            {job.logo ? (
              <img src={job.logo} alt={job.company} className="w-full h-full rounded object-cover" />
            ) : (
              <Building2 className="w-6 h-6 text-gray-500" />
            )}
          </div>
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-blue-700 hover:underline">
                {job.title}
              </h3>
              <p className="text-gray-900 mt-1">{job.company}</p>
            </div>
            <Button variant="ghost" size="icon" className="flex-shrink-0">
              <Bookmark className="w-5 h-5" />
            </Button>
          </div>
          
          <div className="flex flex-wrap items-center gap-2 mt-2 text-sm text-gray-600">
            <div className="flex items-center gap-1">
              <MapPin className="w-4 h-4" />
              <span>{job.location}</span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1">
              <Briefcase className="w-4 h-4" />
              <span>{job.type}</span>
            </div>
            <span>•</span>
            <span>{job.level}</span>
          </div>
          
          {job.promoted && (
            <Badge variant="secondary" className="mt-2">
              Promoted
            </Badge>
          )}
          
          <div className="flex items-center gap-2 mt-3 text-xs text-gray-500">
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>{job.postedDate}</span>
            </div>
            <span>•</span>
            <span>{job.applicants} applicants</span>
          </div>
        </div>
      </div>
    </div>
  );
}
