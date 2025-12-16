import React, { useMemo, useState } from 'react'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose, DialogDescription } from '@components/ui/dialog'
import { Label } from '@components/ui/label'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import DatePicker from '@components/date_picker'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@components/ui/select'
import { type ProjectData, type MissionCreateProps } from '@lib/data/project'
import { type ProjectsState, useProjectsStore, type MissionsState, useMissionsStore } from '@lib/store/project'

export interface AddMissionDialogProps {
    projects?: ProjectData[]
}

const AddMissionDialog: React.FC<AddMissionDialogProps> = () => {
    const projects = useProjectsStore((state: ProjectsState) => state.projects)
    const createMission = useMissionsStore((state: MissionsState) => state.createMission)

    const [open, setOpen] = useState(false)
    const [name, setName] = useState<string>('')
    const [description, setDescription] = useState<string>('')
    const [projectId, setProjectId] = useState<number>(0)
    const [parentId, setParentId] = useState<number>(0)
    const [ddl, setDdl] = useState<number>(Math.floor(Date.now() / 1000))
    const [submitting, setSubmitting] = useState<boolean>(false)

    const projectOptions = useMemo(() => projects.sort((a, b) => a.id - b.id), [projects])

    const handleSubmit = async () => {
        if (!name.trim()) {
            return
        }
        const payload: MissionCreateProps = {
            name: name.trim(),
            description: description.trim(),
            parent_id: parentId,
            project_id: projectId,
            ddl: ddl,
        }
        try {
            setSubmitting(true)
            await createMission(payload)
            setSubmitting(false)
            setOpen(false)
            setName('')
            setDescription('')
            setProjectId(0)
            setParentId(0)
        } catch (e) {
            setSubmitting(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline">Add Mission</Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>新增任务</DialogTitle>
                    <DialogDescription>选择项目并填写任务信息后创建</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-2">
                    <div className="flex flex-col gap-2">
                        <Label htmlFor="mission-name">任务名称</Label>
                        <Input id="mission-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="请输入任务名称" />
                    </div>
                    <div className="flex flex-col gap-2">
                        <Label htmlFor="mission-desc">任务描述</Label>
                        <Input id="mission-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="请输入任务描述" />
                    </div>
                    <div className="flex flex-row gap-6">
                        <div className="flex flex-col gap-2">
                            <Label>所属项目</Label>
                            <Select onValueChange={(v) => setProjectId(parseInt(v))}>
                                <SelectTrigger className="w-56">
                                    <SelectValue placeholder="选择项目" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectGroup>
                                        <SelectLabel>项目列表</SelectLabel>
                                        {projectOptions.map((p) => (
                                            <SelectItem key={p.id} value={p.id.toString()}>{p.name}</SelectItem>
                                        ))}
                                    </SelectGroup>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="flex flex-col gap-2">
                            <Label>父任务ID（可选）</Label>
                            <Input type="number" placeholder="父任务ID" value={parentId} onChange={(e) => setParentId(parseInt(e.target.value || '0'))} className="w-56" />
                        </div>
                    </div>
                    <div className="flex flex-row gap-6">
                        <DatePicker label="截止日期" onChange={(d: Date) => setDdl(Math.floor(d.getTime() / 1000))} />
                    </div>
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="ghost">取消</Button>
                    </DialogClose>
                    <Button onClick={handleSubmit} disabled={submitting || !name.trim() || projectId === 0}>创建</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default AddMissionDialog


