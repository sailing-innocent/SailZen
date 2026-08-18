import React, { useMemo, useState } from 'react'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose, DialogDescription } from '@components/ui/dialog'
import { Label } from '@components/ui/label'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import DatePicker from '@components/date_picker'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@components/ui/select'
import { type AffairData, type AffairCreateProps } from '@lib/data/affair'
import { isChallengeAffair } from '@lib/data/challenge'
import { type AffairsState, useAffairsStore } from '@lib/store/affair'
import { useIsMobile } from '@/hooks/use-mobile'

export interface AddMissionDialogProps {
    ventures?: AffairData[]
}

const AddMissionDialog: React.FC<AddMissionDialogProps> = () => {
    const ventures = useAffairsStore((state: AffairsState) => state.ventures)
    const createTask = useAffairsStore((state: AffairsState) => state.createTask)
    const isMobile = useIsMobile()

    const [open, setOpen] = useState(false)
    const [name, setName] = useState<string>('')
    const [description, setDescription] = useState<string>('')
    const [parentId, setParentId] = useState<number>(0)
    const [ddl, setDdl] = useState<number>(Math.floor(Date.now() / 1000))
    const [submitting, setSubmitting] = useState<boolean>(false)

    const ventureOptions = useMemo(() => {
        return ventures
            .filter(v => !isChallengeAffair(v.title))
            .sort((a, b) => a.id - b.id)
    }, [ventures])

    const handleSubmit = async () => {
        if (!name.trim()) {
            return
        }
        const payload: AffairCreateProps = {
            title: name.trim(),
            description: description.trim(),
            parent_id: parentId > 0 ? parentId : null,
            urgency_ddl: ddl,
        }
        try {
            setSubmitting(true)
            await createTask(payload)
            setSubmitting(false)
            setOpen(false)
            setName('')
            setDescription('')
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
            <DialogContent className={isMobile ? 'max-w-[95vw] max-h-[85vh] overflow-y-auto' : ''}>
                <DialogHeader>
                    <DialogTitle>新增任务</DialogTitle>
                    <DialogDescription>选择事业并填写任务信息后创建</DialogDescription>
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
                            <Label>所属事业</Label>
                            <Select onValueChange={(v) => setParentId(parseInt(v))}>
                                <SelectTrigger className="w-56">
                                    <SelectValue placeholder="选择事业" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectGroup>
                                        <SelectLabel>事业列表</SelectLabel>
                                        {ventureOptions.map((v) => (
                                            <SelectItem key={v.id} value={v.id.toString()}>{v.title}</SelectItem>
                                        ))}
                                    </SelectGroup>
                                </SelectContent>
                            </Select>
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
                    <Button onClick={handleSubmit} disabled={submitting || !name.trim() || parentId === 0}>创建</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default AddMissionDialog
