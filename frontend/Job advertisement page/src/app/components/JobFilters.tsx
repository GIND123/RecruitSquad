import { X } from "lucide-react";
import { Button } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import { Label } from "./ui/label";
import { Separator } from "./ui/separator";

interface JobFiltersProps {
  onClose?: () => void;
}

export function JobFilters({ onClose }: JobFiltersProps) {
  return (
    <div className="bg-white border-r h-full overflow-y-auto">
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">All filters</h2>
          {onClose && (
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          )}
        </div>

        <div className="space-y-6">
          {/* Date Posted */}
          <div>
            <h3 className="text-sm font-semibold mb-3">Date posted</h3>
            <div className="space-y-2">
              {["Any time", "Past month", "Past week", "Past 24 hours"].map((option) => (
                <div key={option} className="flex items-center space-x-2">
                  <Checkbox id={`date-${option}`} />
                  <Label
                    htmlFor={`date-${option}`}
                    className="text-sm font-normal cursor-pointer"
                  >
                    {option}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Job Type */}
          <div>
            <h3 className="text-sm font-semibold mb-3">Job type</h3>
            <div className="space-y-2">
              {["Full-time", "Part-time", "Contract", "Temporary", "Internship"].map((type) => (
                <div key={type} className="flex items-center space-x-2">
                  <Checkbox id={`type-${type}`} />
                  <Label
                    htmlFor={`type-${type}`}
                    className="text-sm font-normal cursor-pointer"
                  >
                    {type}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Experience Level */}
          <div>
            <h3 className="text-sm font-semibold mb-3">Experience level</h3>
            <div className="space-y-2">
              {["Entry level", "Associate", "Mid-Senior level", "Director", "Executive"].map(
                (level) => (
                  <div key={level} className="flex items-center space-x-2">
                    <Checkbox id={`level-${level}`} />
                    <Label
                      htmlFor={`level-${level}`}
                      className="text-sm font-normal cursor-pointer"
                    >
                      {level}
                    </Label>
                  </div>
                )
              )}
            </div>
          </div>

          <Separator />

          {/* On-site/Remote */}
          <div>
            <h3 className="text-sm font-semibold mb-3">On-site/remote</h3>
            <div className="space-y-2">
              {["On-site", "Remote", "Hybrid"].map((mode) => (
                <div key={mode} className="flex items-center space-x-2">
                  <Checkbox id={`mode-${mode}`} />
                  <Label
                    htmlFor={`mode-${mode}`}
                    className="text-sm font-normal cursor-pointer"
                  >
                    {mode}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Company */}
          <div>
            <h3 className="text-sm font-semibold mb-3">Company</h3>
            <div className="space-y-2">
              {["Google", "Microsoft", "Apple", "Amazon", "Meta"].map((company) => (
                <div key={company} className="flex items-center space-x-2">
                  <Checkbox id={`company-${company}`} />
                  <Label
                    htmlFor={`company-${company}`}
                    className="text-sm font-normal cursor-pointer"
                  >
                    {company}
                  </Label>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6 flex gap-2">
          <Button variant="outline" className="flex-1">
            Clear all
          </Button>
          <Button className="flex-1 bg-blue-600 hover:bg-blue-700">
            Show results
          </Button>
        </div>
      </div>
    </div>
  );
}
