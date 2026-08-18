import React, { useState } from 'react'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DialogClose, DialogDescription } from '@components/ui/dialog'
import { Label } from '@components/ui/label'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import { type AffairCreateProps } from '@lib/data/affair'
import { type AffairsState, useAffairsStore } from '@lib/store/affair'
import { useIsMobile } from '@/hooks/use-mobile'
import { Calendar } from '@components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@components/ui/popover'
import { CalendarIcon } from 'lucide-react'
import { format } from 'date-fns'
import { cn } from '@lib/utils'

const AddProjectDialog: React.FC = () => {
    const createVenture = useAffairsStore((state: AffairsState) => state.createVenture)
    const isMobile = useIsMobile()
    const [open, setOpen] = useState(false)
    const [name, setName] = useState<string>('')
    const [description, setDescription] = useState<string>('')
    const [targetDate, setTargetDate] = useState<Date | undefined>(undefined)
    const [submitting, setSubmitting] = useState<boolean>(false)

    const handleSubmit = async () => {
        if (!name.trim()) {
            return
        }
        const payload: AffairCreateProps = {
            title: name.trim(),
            description: description.trim(),
            kind_meta: targetDate ? { target_date: targetDate.toISOString().split('T')[0] } : {},
        }
        try {
            setSubmitting(true)
            await createVenture(payload)
            setSubmitting(false)
            setOpen(false)
            setName('')
            setDescription('')
            setTargetDate(undefined)
        } catch (e) {
            setSubmitting(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline">Add Project</Button>
            </DialogTrigger>
            <DialogContent className={isMobile ? 'max-w-[95vw] max-h-[85vh] overflow-y-auto' : ''}>
                <DialogHeader>
                    <DialogTitle>新增事业</DialogTitle>
                    <DialogDescription>输入长期事业信息后创建</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-2">
                    <div className="flex flex-col gap-2">
                        <Label htmlFor="project-name">事业名称</Label>
                        <Input id="project-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="请输入事业名称" />
                    </div>
                    <div className="flex flex-col gap-2">
                        <Label htmlFor="project-desc">事业描述</Label>
                        <Input id="project-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="请输入事业描述" />
                    </div>
                    <div className="flex flex-col gap-2">
                        <Label>目标日（可选）</Label>
                        <Popover>
                            <PopoverTrigger asChild>
                                <Button
                                    variant="outline"
                                    className={cn(
                                        'w-full justify-start text-left font-normal',
                                        !targetDate && 'text-muted-foreground'
                                    )}
                                >
                                    <CalendarIcon className="mr-2 h-4 w-4" />
                                    {targetDate ? (
                                        format(targetDate, 'yyyy年MM月dd日')
                                    ) : (
                                        <span>选择目标日</span>
                                    )}
                                </Button>
                            </PopoverTrigger>
                            <PopoverContent className="w-auto p-0" align="start">
                                <Calendar
                                    mode="single"
                                    selected={targetDate}
                                    onSelect={(date) => setTargetDate(date)}
                                    disabled={(date) => date < new Date(new Date().setHours(0, 0, 0, 0))}
                                />
                            </PopoverContent>
                        </Popover>
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
