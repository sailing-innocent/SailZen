import React, { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogClose,
  DialogDescription,
} from '@components/ui/dialog'
import { Label } from '@components/ui/label'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import { type HistoryEventData, type HistoryEventUpdateProps } from '@lib/data/history'
import { type HistoryEventsState, useHistoryEventsStore } from '@lib/store/history'

interface EditHistoryEventDialogProps {
  event: HistoryEventData
  open: boolean
  onOpenChange: (open: boolean) => void
}

const EditHistoryEventDialog: React.FC<EditHistoryEventDialogProps> = ({ event, open, onOpenChange }) => {
  const updateEvent = useHistoryEventsStore((state: HistoryEventsState) => state.updateEvent)
  const [title, setTitle] = useState<string>('')
  const [description, setDescription] = useState<string>('')
  const [rarTags, setRarTags] = useState<string>('')
  const [tags, setTags] = useState<string>('')
  const [startTime, setStartTime] = useState<string>('')
  const [endTime, setEndTime] = useState<string>('')
  const [parentEvent, setParentEvent] = useState<string>('')
  const [relatedEvents, setRelatedEvents] = useState<string>('')
  const [details, setDetails] = useState<string>('')
  const [submitting, setSubmitting] = useState<boolean>(false)
  const [error, setError] = useState<string>('')

  // Initialize form with event data
  useEffect(() => {
    if (event) {
      setTitle(event.title || '')
      setDescription(event.description || '')
      setRarTags(event.rar_tags?.join(', ') || '')
      setTags(event.tags?.join(', ') || '')
      setStartTime(event.start_time ? formatDateTimeLocal(event.start_time) : '')
      setEndTime(event.end_time ? formatDateTimeLocal(event.end_time) : '')
      setParentEvent(event.parent_event !== undefined ? String(event.parent_event) : '')
      setRelatedEvents(event.related_events?.join(', ') || '')
      setDetails(event.details ? JSON.stringify(event.details, null, 2) : '')
      setError('')
    }
  }, [event])

  // Format ISO datetime to datetime-local input format
  const formatDateTimeLocal = (isoString: string): string => {
    try {
      const date = new Date(isoString)
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      return `${year}-${month}-${day}T${hours}:${minutes}`
    } catch {
      return ''
    }
  }

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) {
      setError('标题和描述为必填项')
      return
    }

    const payload: HistoryEventUpdateProps = {
      title: title.trim(),
      description: description.trim(),
    }

    // Parse optional fields
    if (rarTags.trim()) {
      payload.rar_tags = rarTags.split(',').map((tag) => tag.trim()).filter((tag) => tag)
    }
    if (tags.trim()) {
      payload.tags = tags.split(',').map((tag) => tag.trim()).filter((tag) => tag)
    }
    if (startTime.trim()) {
      payload.start_time = startTime.trim()
    }
    if (endTime.trim()) {
      payload.end_time = endTime.trim()
    }
    if (parentEvent.trim()) {
      const parentId = parseInt(parentEvent.trim())
      if (!isNaN(parentId)) {
        payload.parent_event = parentId
      }
    }
    if (relatedEvents.trim()) {
      payload.related_events = relatedEvents
        .split(',')
        .map((id) => parseInt(id.trim()))
        .filter((id) => !isNaN(id))
    }
    if (details.trim()) {
      try {
        payload.details = JSON.parse(details.trim())
      } catch (e) {
        setError('详情字段必须是有效的 JSON 格式')
        return
      }
    }

    try {
      setSubmitting(true)
      setError('')
      await updateEvent(event.id, payload)
      setSubmitting(false)
      onOpenChange(false)
    } catch (e) {
      setSubmitting(false)
      setError('更新失败，请检查输入或稍后重试')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑历史事件</DialogTitle>
          <DialogDescription>修改事件信息。标题和描述为必填项。</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          {error && <div className="text-red-500 text-sm">{error}</div>}

          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-event-title">
              标题 <span className="text-red-500">*</span>
            </Label>
            <Input
              id="edit-event-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="请输入事件标题"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-event-description">
              描述 <span className="text-red-500">*</span>
            </Label>
            <textarea
              id="edit-event-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="请输入事件描述"
              className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-event-rar-tags">手动标签</Label>
            <Input
              id="edit-event-rar-tags"
              value={rarTags}
              onChange={(e) => setRarTags(e.target.value)}
              placeholder="多个标签用逗号分隔，如：政治,经济,中美关系"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-event-tags">机器标签</Label>
            <Input
              id="edit-event-tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="多个标签用逗号分隔，如：trade,economy,politics"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-event-start-time">开始时间</Label>
              <Input
                id="edit-event-start-time"
                type="datetime-local"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-event-end-time">结束时间</Label>
              <Input
                id="edit-event-end-time"
                type="datetime-local"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-event-parent">父事件 ID</Label>
            <Input
              id="edit-event-parent"
              type="number"
              value={parentEvent}
              onChange={(e) => setParentEvent(e.target.value)}
              placeholder="如果有父事件，请输入父事件的 ID"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-event-related">关联事件 IDs</Label>
            <Input
              id="edit-event-related"
              value={relatedEvents}
              onChange={(e) => setRelatedEvents(e.target.value)}
              placeholder="多个 ID 用逗号分隔，如：1,2,3"
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="edit-event-details">详细信息 (JSON)</Label>
            <textarea
              id="edit-event-details"
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              placeholder='可选，输入 JSON 格式，如：{"participants": ["张三", "李四"]}'
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 font-mono"
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">取消</Button>
          </DialogClose>
          <Button onClick={handleSubmit} disabled={submitting || !title.trim() || !description.trim()}>
            {submitting ? '更新中...' : '更新'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default EditHistoryEventDialog

