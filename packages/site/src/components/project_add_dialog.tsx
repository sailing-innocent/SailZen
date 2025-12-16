import React, { useState } from 'react'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose, DialogDescription } from '@components/ui/dialog'
import { Label } from '@components/ui/label'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { QBWDate } from '@lib/utils/qbw_date'
import { type ProjectCreateProps } from '@lib/data/project'
import { type ProjectsState, useProjectsStore } from '@lib/store/project'

const AddProjectDialog: React.FC = () => {
    const createProject = useProjectsStore((state: ProjectsState) => state.createProject)
    const [open, setOpen] = useState(false)
    const [name, setName] = useState<string>('')
    const [description, setDescription] = useState<string>('')
    const now = new Date()
    const initialYear = now.getFullYear()
    const initialQuarter = Math.floor(now.getMonth() / 3) + 1
    const [startYear, setStartYear] = useState<number>(initialYear)
    const [startQuarter, setStartQuarter] = useState<number>(initialQuarter)
    const [startIndex, setStartIndex] = useState<number>(1)
    const [endYear, setEndYear] = useState<number>(initialYear)
    const [endQuarter, setEndQuarter] = useState<number>(initialQuarter)
    const [endIndex, setEndIndex] = useState<number>(1)
    const [submitting, setSubmitting] = useState<boolean>(false)

    const handleSubmit = async () => {
        if (!name.trim()) {
            return
        }
        const start_time = new QBWDate(startYear, startQuarter, startIndex).to_int()
        const end_time = new QBWDate(endYear, endQuarter, endIndex).to_int()
        if (end_time < start_time) {
            return
        }
        const payload: ProjectCreateProps = {
            name: name.trim(),
            description: description.trim(),
            start_time,
            end_time,
        }
        try {
            setSubmitting(true)
            await createProject(payload)
            setSubmitting(false)
            setOpen(false)
            setName('')
            setDescription('')
        } catch (e) {
            setSubmitting(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline">Add Project</Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>新增项目</DialogTitle>
                    <DialogDescription>输入项目信息后创建</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-2">
                    <div className="flex flex-col gap-2">
                        <Label htmlFor="project-name">项目名称</Label>
                        <Input id="project-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="请输入项目名称" />
                    </div>
                    <div className="flex flex-col gap-2">
                        <Label htmlFor="project-desc">项目描述</Label>
                        <Input id="project-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="请输入项目描述" />
                    </div>
                    <div className="flex flex-col gap-3">
                        <span className="text-sm text-muted-foreground">开始时间（季度/双周）</span>
                        <div className="flex flex-row gap-4 items-center">
                            <Select value={String(startYear)} onValueChange={(v) => setStartYear(parseInt(v))}>
                                <SelectTrigger className="w-28">
                                    <SelectValue placeholder="年份" />
                                </SelectTrigger>
                                <SelectContent>
                                    {Array.from({ length: 21 }).map((_, idx) => {
                                        const y = initialYear - 10 + idx
                                        return (
                                            <SelectItem key={y} value={String(y)}>{y} 年</SelectItem>
                                        )
                                    })}
                                </SelectContent>
                            </Select>
                            <Select value={String(startQuarter)} onValueChange={(v) => setStartQuarter(parseInt(v))}>
                                <SelectTrigger className="w-28">
                                    <SelectValue placeholder="季度" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1">第 1 季度</SelectItem>
                                    <SelectItem value="2">第 2 季度</SelectItem>
                                    <SelectItem value="3">第 3 季度</SelectItem>
                                    <SelectItem value="4">第 4 季度</SelectItem>
                                </SelectContent>
                            </Select>
                            <Select value={String(startIndex)} onValueChange={(v) => setStartIndex(parseInt(v))}>
                                <SelectTrigger className="w-32">
                                    <SelectValue placeholder="双周序号" />
                                </SelectTrigger>
                                <SelectContent>
                                    {Array.from({ length: 6 }).map((_, idx) => (
                                        <SelectItem key={idx + 1} value={String(idx + 1)}>双周 {idx + 1}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <div className="flex flex-col gap-3">
                        <span className="text-sm text-muted-foreground">结束时间（季度/双周）</span>
                        <div className="flex flex-row gap-4 items-center">
                            <Select value={String(endYear)} onValueChange={(v) => setEndYear(parseInt(v))}>
                                <SelectTrigger className="w-28">
                                    <SelectValue placeholder="年份" />
                                </SelectTrigger>
                                <SelectContent>
                                    {Array.from({ length: 21 }).map((_, idx) => {
                                        const y = initialYear - 10 + idx
                                        return (
                                            <SelectItem key={y} value={String(y)}>{y} 年</SelectItem>
                                        )
                                    })}
                                </SelectContent>
                            </Select>
                            <Select value={String(endQuarter)} onValueChange={(v) => setEndQuarter(parseInt(v))}>
                                <SelectTrigger className="w-28">
                                    <SelectValue placeholder="季度" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="1">第 1 季度</SelectItem>
                                    <SelectItem value="2">第 2 季度</SelectItem>
                                    <SelectItem value="3">第 3 季度</SelectItem>
                                    <SelectItem value="4">第 4 季度</SelectItem>
                                </SelectContent>
                            </Select>
                            <Select value={String(endIndex)} onValueChange={(v) => setEndIndex(parseInt(v))}>
                                <SelectTrigger className="w-32">
                                    <SelectValue placeholder="双周序号" />
                                </SelectTrigger>
                                <SelectContent>
                                    {Array.from({ length: 6 }).map((_, idx) => (
                                        <SelectItem key={idx + 1} value={String(idx + 1)}>双周 {idx + 1}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="ghost">取消</Button>
                    </DialogClose>
                <Button onClick={handleSubmit} disabled={submitting || !name.trim()}>创建</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default AddProjectDialog


