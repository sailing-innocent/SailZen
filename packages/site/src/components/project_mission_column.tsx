import type { ProjectData, MissionData } from '@lib/data/project'
import { isMissionActive } from '@lib/data/project'
import React from 'react'
import { QBWDate } from '@lib/utils/qbw_date'
import { useIsMobile } from '@/hooks/use-mobile'
import { Badge } from '@/components/ui/badge'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion'
import { CheckCircle2 } from 'lucide-react'
import MissionCard from './mission_card'

export interface ProjectMissionColumnProps {
    project: ProjectData
    missions: MissionData[] // a sorted list of missions belong to this project
}

interface ProjectDisplayData extends ProjectData {
    start_time_qbw: QBWDate,
    end_time_qbw: QBWDate
}

const ProjectMissionColumn: React.FC<ProjectMissionColumnProps> = ({ project, missions }) => {
    const isMobile = useIsMobile()
    const projectDisplayData: ProjectDisplayData = {
        ...project,
        start_time_qbw: QBWDate.from_int(project.start_time),
        end_time_qbw: QBWDate.from_int(project.end_time)
    }

    // Count active missions
    const activeMissions = missions.filter((m) => isMissionActive(m.state))
    const completedMissions = missions.filter((m) => !isMissionActive(m.state))

    return (
        <div className={`flex flex-col ${
            isMobile 
                ? 'w-full p-3 border rounded-lg mb-3' 
                : 'min-w-[300px] max-w-[350px] border rounded-lg p-4'
        }`}>
            {/* Project Header */}
            <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                    <h2 className={`font-bold ${isMobile ? 'text-base' : 'text-lg'}`}>
                        {projectDisplayData.name}
                    </h2>
                    <Badge variant="outline" className="text-xs">
                        {activeMissions.length}/{missions.length}
                    </Badge>
                </div>
                <p className={`text-muted-foreground ${isMobile ? 'text-xs' : 'text-sm'}`}>
                    {projectDisplayData.description}
                </p>
                <p className={`text-muted-foreground ${isMobile ? 'text-xs' : 'text-sm'}`}>
                    {projectDisplayData.start_time_qbw.get_fmt_string()} - {projectDisplayData.end_time_qbw.get_fmt_string()}
                </p>
            </div>

            {/* Mission List */}
            <div className="flex flex-col gap-2">
                {missions.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                        暂无任务
                    </p>
                ) : (
                    <>
                        {/* Active missions first */}
                        {activeMissions.map((mission) => (
                            <MissionCard
                                key={mission.id}
                                mission={mission}
                                compact
                            />
                        ))}
                        
                        {/* Completed missions (collapsed) */}
                        {completedMissions.length > 0 && (
                            <Accordion type="single" collapsible className="mt-2">
                                <AccordionItem value="completed" className="border-none">
                                    <AccordionTrigger className="py-2 text-xs text-muted-foreground hover:text-foreground hover:no-underline">
                                        <span className="flex items-center gap-1">
                                            <CheckCircle2 className="h-3 w-3" />
                                            已完成 ({completedMissions.length})
                                        </span>
                                    </AccordionTrigger>
                                    <AccordionContent className="pb-0">
                                        <div className="space-y-2">
                                            {completedMissions.map((mission) => (
                                                <MissionCard
                                                    key={mission.id}
                                                    mission={mission}
                                                    compact
                                                />
                                            ))}
                                        </div>
                                    </AccordionContent>
                                </AccordionItem>
                            </Accordion>
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

export default ProjectMissionColumn