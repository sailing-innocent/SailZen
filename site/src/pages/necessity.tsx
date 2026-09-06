/**
 * @file necessity.tsx
 * @brief Necessity (生活物资) Management Page
 * @author sailing-innocent
 * @date 2026-02-01
 */

import { useEffect, useState, useCallback } from 'react'
import PageLayout from '@components/page_layout'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { Badge } from '@components/ui/badge'
import { Skeleton } from '@components/ui/skeleton'
import { Checkbox } from '@components/ui/checkbox'
import { Textarea } from '@components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@components/ui/alert-dialog'
import { Input } from '@components/ui/input'
import { Label } from '@components/ui/label'
import { ScrollArea } from '@components/ui/scroll-area'
import { Separator } from '@components/ui/separator'

import {
  useResidenceStore,
  useCategoryStore,
  useItemsStore,
  useInventoryStore,
  useJourneyStore,
} from '@lib/store/necessity'

import {
  ResidenceType,
  ResidenceTypeLabels,
  ItemType,
  ItemTypeLabels,
  ItemState,
  ItemStateLabels,
  JourneyStatus,
  JourneyStatusLabels,
  type ResidenceData,
  type ItemData,
  type InventoryData,
} from '@lib/data/necessity'

// ============ Add Residence Dialog ============

const AddResidenceDialog = ({ onResidenceAdded }: { onResidenceAdded?: () => void }) => {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [type, setType] = useState<ResidenceType>(ResidenceType.LIVING)
  const [address, setAddress] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { createResidence } = useResidenceStore()

  const handleSubmit = async () => {
    if (!name.trim()) return
    
    setIsSubmitting(true)
    try {
      await createResidence({
        name: name.trim(),
        code: code.trim() || undefined,
        type,
        address: address.trim() || undefined,
        description: description.trim() || undefined,
        is_portable: type === ResidenceType.PORTABLE,
        priority,
      })
      setOpen(false)
      resetForm()
      onResidenceAdded?.()
    } catch (error) {
      console.error('Failed to create residence:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const resetForm = () => {
    setName('')
    setCode('')
    setType(ResidenceType.LIVING)
    setAddress('')
    setDescription('')
    setPriority(1)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="w-full">
          + 新建住所
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建住所</DialogTitle>
          <DialogDescription>
            创建一个新的物资存放住所
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="res-name">名称 *</Label>
            <Input
              id="res-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="如：上海住所"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="res-code">代码</Label>
              <Input
                id="res-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="如：SH"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="res-type">类型</Label>
              <Select value={type.toString()} onValueChange={(v) => setType(parseInt(v))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(ResidenceTypeLabels).map(([key, label]) => (
                    <SelectItem key={key} value={key}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="res-address">地址</Label>
            <Input
              id="res-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="详细地址"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="res-desc">描述</Label>
            <Textarea
              id="res-desc"
              value={description}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)}
              placeholder="住所描述"
              rows={2}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="res-priority">补货优先级 (数字越小越优先)</Label>
            <Select value={priority.toString()} onValueChange={(v) => setPriority(parseInt(v))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((n) => (
                  <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !name.trim()}>
            {isSubmitting ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ============ Residence Card Component ============

const ResidenceCard = ({ residence, isSelected, onSelect }: {
  residence: ResidenceData
  isSelected: boolean
  onSelect: () => void
}) => {
  return (
    <Card 
      className={`cursor-pointer transition-colors ${isSelected ? 'border-primary bg-primary/5' : 'hover:border-muted-foreground/50'}`}
      onClick={onSelect}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{residence.name}</CardTitle>
          <Badge variant={residence.is_portable ? 'default' : 'secondary'}>
            {ResidenceTypeLabels[residence.type as ResidenceType]}
          </Badge>
        </div>
        {residence.code && (
          <CardDescription className="text-xs">{residence.code}</CardDescription>
        )}
      </CardHeader>
      {residence.description && (
        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground">{residence.description}</p>
        </CardContent>
      )}
    </Card>
  )
}

// ============ Residence Selector Component ============

const ResidenceSelector = () => {
  const { residences, currentResidence, isLoading, fetchResidences, setCurrentResidence } = useResidenceStore()
  const { fetchInventoriesByResidence, fetchLowStock, fetchStats } = useInventoryStore()

  useEffect(() => {
    fetchResidences()
  }, [fetchResidences])

  const handleSelectResidence = (residence: ResidenceData) => {
    setCurrentResidence(residence)
    fetchInventoriesByResidence(residence.id)
    fetchLowStock(residence.id)
    fetchStats(residence.id)
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium">选择住所</h3>
      </div>
      {residences.map((residence) => (
        <ResidenceCard
          key={residence.id}
          residence={residence}
          isSelected={currentResidence?.id === residence.id}
          onSelect={() => handleSelectResidence(residence)}
        />
      ))}
      <AddResidenceDialog onResidenceAdded={() => fetchResidences()} />
    </div>
  )
}

// ============ Add Item Dialog ============

const AddItemDialog = ({ onItemAdded }: { onItemAdded?: () => void }) => {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [type, setType] = useState<ItemType>(ItemType.UNIQUE)
  const [brand, setBrand] = useState('')
  const [model, setModel] = useState('')
  const [description, setDescription] = useState('')
  const [importance, setImportance] = useState(3)
  const [portability, setPortability] = useState(3)
  const [state, setState] = useState<ItemState>(ItemState.ACTIVE)
  const [tags, setTags] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { createItem } = useItemsStore()

  const handleSubmit = async () => {
    if (!name.trim()) return
    
    setIsSubmitting(true)
    try {
      await createItem({
        name: name.trim(),
        type,
        brand,
        model,
        description,
        importance,
        portability,
        state,
        tags,
      })
      setOpen(false)
      resetForm()
      onItemAdded?.()
    } catch (error) {
      console.error('Failed to create item:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const resetForm = () => {
    setName('')
    setBrand('')
    setModel('')
    setDescription('')
    setType(ItemType.UNIQUE)
    setImportance(3)
    setPortability(3)
    setState(ItemState.ACTIVE)
    setTags('')
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>添加物资</Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>添加新物资</DialogTitle>
          <DialogDescription>
            填写物资信息，创建后可在库存中添加位置
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh]">
          <div className="grid gap-4 py-4 px-1">
            <div className="grid gap-2">
              <Label htmlFor="name">名称 *</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="物资名称"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="type">类型</Label>
                <Select value={type.toString()} onValueChange={(v) => setType(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">{ItemTypeLabels[ItemType.UNIQUE]}</SelectItem>
                    <SelectItem value="1">{ItemTypeLabels[ItemType.BULK]}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="state">状态</Label>
                <Select value={state.toString()} onValueChange={(v) => setState(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ItemStateLabels).map(([key, label]) => (
                      <SelectItem key={key} value={key}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="brand">品牌</Label>
                <Input
                  id="brand"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="品牌名称"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="model">型号</Label>
                <Input
                  id="model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="型号规格"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">描述</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)}
                placeholder="物资描述"
                rows={2}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tags">标签 (逗号分隔)</Label>
              <Input
                id="tags"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="如：常用,电子产品"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>重要程度 (1-5)</Label>
                <Select value={importance.toString()} onValueChange={(v) => setImportance(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>便携性 (1-5)</Label>
                <Select value={portability.toString()} onValueChange={(v) => setPortability(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !name.trim()}>
            {isSubmitting ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ============ Edit Item Dialog ============

const EditItemDialog = ({ item, open, onOpenChange, onItemUpdated }: {
  item: ItemData
  open: boolean
  onOpenChange: (open: boolean) => void
  onItemUpdated?: () => void
}) => {
  const [name, setName] = useState(item.name)
  const [type, setType] = useState<ItemType>(item.type)
  const [brand, setBrand] = useState(item.brand)
  const [model, setModel] = useState(item.model)
  const [description, setDescription] = useState(item.description)
  const [importance, setImportance] = useState(item.importance)
  const [portability, setPortability] = useState(item.portability)
  const [state, setState] = useState<ItemState>(item.state)
  const [tags, setTags] = useState(item.tags)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { updateItem } = useItemsStore()

  useEffect(() => {
    setName(item.name)
    setType(item.type)
    setBrand(item.brand)
    setModel(item.model)
    setDescription(item.description)
    setImportance(item.importance)
    setPortability(item.portability)
    setState(item.state)
    setTags(item.tags)
  }, [item])

  const handleSubmit = async () => {
    if (!name.trim()) return
    
    setIsSubmitting(true)
    try {
      await updateItem(item.id, {
        name: name.trim(),
        type,
        brand,
        model,
        description,
        importance,
        portability,
        state,
        tags,
      })
      onOpenChange(false)
      onItemUpdated?.()
    } catch (error) {
      console.error('Failed to update item:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>编辑物资</DialogTitle>
          <DialogDescription>
            修改物资信息和状态
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh]">
          <div className="grid gap-4 py-4 px-1">
            <div className="grid gap-2">
              <Label htmlFor="edit-name">名称 *</Label>
              <Input
                id="edit-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="物资名称"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-type">类型</Label>
                <Select value={type.toString()} onValueChange={(v) => setType(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0">{ItemTypeLabels[ItemType.UNIQUE]}</SelectItem>
                    <SelectItem value="1">{ItemTypeLabels[ItemType.BULK]}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-state">状态</Label>
                <Select value={state.toString()} onValueChange={(v) => setState(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ItemStateLabels).map(([key, label]) => (
                      <SelectItem key={key} value={key}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="edit-brand">品牌</Label>
                <Input
                  id="edit-brand"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="品牌名称"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-model">型号</Label>
                <Input
                  id="edit-model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="型号规格"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-description">描述</Label>
              <Textarea
                id="edit-description"
                value={description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setDescription(e.target.value)}
                placeholder="物资描述"
                rows={2}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-tags">标签 (逗号分隔)</Label>
              <Input
                id="edit-tags"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="如：常用,电子产品"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>重要程度 (1-5)</Label>
                <Select value={importance.toString()} onValueChange={(v) => setImportance(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>便携性 (1-5)</Label>
                <Select value={portability.toString()} onValueChange={(v) => setPortability(parseInt(v))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </ScrollArea>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !name.trim()}>
            {isSubmitting ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ============ Items Table Component ============

const ItemsTable = () => {
  const { items, isLoading, fetchItems, deleteItem } = useItemsStore()
  const [editingItem, setEditingItem] = useState<ItemData | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [stateFilter, setStateFilter] = useState<string>('all')

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  const filteredItems = items.filter((item) => {
    const matchesSearch = searchKeyword === '' || 
      item.name.toLowerCase().includes(searchKeyword.toLowerCase()) ||
      item.brand?.toLowerCase().includes(searchKeyword.toLowerCase()) ||
      item.tags?.toLowerCase().includes(searchKeyword.toLowerCase())
    
    const matchesState = stateFilter === 'all' || item.state.toString() === stateFilter

    return matchesSearch && matchesState
  })

  const handleDelete = async (item: ItemData) => {
    try {
      await deleteItem(item.id)
    } catch (error) {
      console.error('Failed to delete item:', error)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 搜索和筛选 */}
      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="搜索物资名称、品牌、标签..."
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          className="max-w-xs"
        />
        <Select value={stateFilter} onValueChange={setStateFilter}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="状态筛选" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            {Object.entries(ItemStateLabels).map(([key, label]) => (
              <SelectItem key={key} value={key}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {filteredItems.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          {items.length === 0 ? '暂无物资，点击"添加物资"创建第一个物资' : '没有匹配的物资'}
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名称</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>品牌/型号</TableHead>
              <TableHead>重要性</TableHead>
              <TableHead>便携性</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredItems.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="font-medium">
                  {item.name}
                  {item.tags && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {item.tags.split(',').filter(Boolean).map((tag, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {tag.trim()}
                        </Badge>
                      ))}
                    </div>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {ItemTypeLabels[item.type as ItemType]}
                  </Badge>
                </TableCell>
                <TableCell>
                  {item.brand || '-'}
                  {item.model && <span className="text-muted-foreground text-xs ml-1">({item.model})</span>}
                </TableCell>
                <TableCell>
                  <span className="text-yellow-500">{'★'.repeat(item.importance)}</span>
                  <span className="text-muted-foreground">{'☆'.repeat(5 - item.importance)}</span>
                </TableCell>
                <TableCell>
                  <span className="text-blue-500">{'●'.repeat(item.portability)}</span>
                  <span className="text-muted-foreground">{'○'.repeat(5 - item.portability)}</span>
                </TableCell>
                <TableCell>
                  <Badge 
                    variant={item.state === ItemState.ACTIVE ? 'default' : 
                             item.state === ItemState.LOST || item.state === ItemState.DISPOSED ? 'destructive' : 
                             'secondary'}
                  >
                    {ItemStateLabels[item.state as ItemState]}
                  </Badge>
                </TableCell>
                <TableCell className="text-right space-x-1">
                  <Button variant="ghost" size="sm" onClick={() => setEditingItem(item)}>
                    编辑
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive">
                        删除
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>确认删除</AlertDialogTitle>
                        <AlertDialogDescription>
                          确定要删除物资「{item.name}」吗？此操作不可撤销。
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>取消</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleDelete(item)}>
                          删除
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* 编辑物资对话框 */}
      {editingItem && (
        <EditItemDialog
          item={editingItem}
          open={!!editingItem}
          onOpenChange={(open) => !open && setEditingItem(null)}
          onItemUpdated={() => fetchItems()}
        />
      )}
    </div>
  )
}

// ============ Inventory Table Component ============

const InventoryTable = () => {
  const { inventories, isLoading, lowStockItems, deleteInventory, fetchInventoriesByResidence, fetchLowStock, fetchStats } = useInventoryStore()
  const { currentResidence } = useResidenceStore()

  const refreshData = useCallback(() => {
    if (currentResidence) {
      fetchInventoriesByResidence(currentResidence.id)
      fetchLowStock(currentResidence.id)
      fetchStats(currentResidence.id)
    }
  }, [currentResidence, fetchInventoriesByResidence, fetchLowStock, fetchStats])

  if (!currentResidence) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        请先选择一个住所查看库存
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (inventories.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        该住所暂无库存记录
      </div>
    )
  }

  const isLowStock = (inv: InventoryData) => {
    return lowStockItems.some((l) => l.id === inv.id)
  }

  const formatCheckTime = (timestamp: number | null) => {
    if (!timestamp) return '从未'
    const date = new Date(timestamp)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return '今天'
    if (diffDays === 1) return '昨天'
    if (diffDays < 7) return `${diffDays}天前`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
    return date.toLocaleDateString()
  }

  const handleDelete = async (inv: InventoryData) => {
    try {
      await deleteInventory(inv.id)
      refreshData()
    } catch (error) {
      console.error('Failed to delete inventory:', error)
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>物资名称</TableHead>
          <TableHead>数量</TableHead>
          <TableHead>单位</TableHead>
          <TableHead>容器</TableHead>
          <TableHead>最后清点</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {inventories.map((inv) => (
          <TableRow key={inv.id}>
            <TableCell className="font-medium">
              {inv.item_name || `物资#${inv.item_id}`}
              {inv.notes && (
                <p className="text-xs text-muted-foreground mt-0.5">{inv.notes}</p>
              )}
            </TableCell>
            <TableCell>
              <span className={isLowStock(inv) ? 'text-destructive font-medium' : ''}>
                {inv.quantity}
              </span>
              {isLowStock(inv) && (
                <Badge variant="destructive" className="ml-2">低库存</Badge>
              )}
              {parseFloat(inv.min_quantity) > 0 && (
                <span className="text-xs text-muted-foreground ml-2">
                  (≥{inv.min_quantity})
                </span>
              )}
            </TableCell>
            <TableCell>{inv.unit}</TableCell>
            <TableCell>{inv.container_name || '-'}</TableCell>
            <TableCell>
              <span className={!inv.last_check_time ? 'text-muted-foreground' : ''}>
                {formatCheckTime(inv.last_check_time)}
              </span>
            </TableCell>
            <TableCell className="text-right space-x-1">
              <InventoryCheckDialog inventory={inv} onChecked={refreshData} />
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive">
                    删除
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>确认删除</AlertDialogTitle>
                    <AlertDialogDescription>
                      确定要删除「{inv.item_name}」的库存记录吗？此操作不可撤销。
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>取消</AlertDialogCancel>
                    <AlertDialogAction onClick={() => handleDelete(inv)}>
                      删除
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// ============ Stats Card Component ============

const StatsCard = () => {
  const { stats, lowStockItems } = useInventoryStore()
  const { currentResidence } = useResidenceStore()

  if (!currentResidence || !stats) {
    return null
  }

  return (
    <div className="grid grid-cols-3 gap-4 mb-4">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>物资种类</CardDescription>
          <CardTitle className="text-2xl">{stats.total_items}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>总数量</CardDescription>
          <CardTitle className="text-2xl">{stats.total_quantity}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>低库存</CardDescription>
          <CardTitle className={`text-2xl ${lowStockItems.length > 0 ? 'text-destructive' : ''}`}>
            {lowStockItems.length}
          </CardTitle>
        </CardHeader>
      </Card>
    </div>
  )
}

// ============ Portable Items View Component ============

const PortableItemsView = () => {
  const { fetchPortableResidence, portableResidence } = useResidenceStore()
  const { fetchInventoriesByResidence, inventories, isLoading, updateInventory } = useInventoryStore()
  const [checkedItems, setCheckedItems] = useState<Set<number>>(new Set())
  const [isCheckMode, setIsCheckMode] = useState(false)
  const [checkNotes, setCheckNotes] = useState('')

  useEffect(() => {
    fetchPortableResidence()
  }, [fetchPortableResidence])

  useEffect(() => {
    if (portableResidence) {
      fetchInventoriesByResidence(portableResidence.id)
    }
  }, [portableResidence, fetchInventoriesByResidence])

  const handleToggleCheck = (invId: number) => {
    setCheckedItems((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(invId)) {
        newSet.delete(invId)
      } else {
        newSet.add(invId)
      }
      return newSet
    })
  }

  const handleCheckAll = () => {
    if (checkedItems.size === inventories.length) {
      setCheckedItems(new Set())
    } else {
      setCheckedItems(new Set(inventories.map((inv) => inv.id)))
    }
  }

  const handleCompleteCheck = async () => {
    const now = Date.now()
    try {
      // 更新所有已勾选物资的清点时间
      for (const invId of checkedItems) {
        const inv = inventories.find((i) => i.id === invId)
        if (inv) {
          await updateInventory(invId, {
            item_id: inv.item_id,
            residence_id: inv.residence_id,
            last_check_time: now,
            notes: checkNotes || inv.notes,
          })
        }
      }
      setIsCheckMode(false)
      setCheckedItems(new Set())
      setCheckNotes('')
      // 刷新数据
      if (portableResidence) {
        fetchInventoriesByResidence(portableResidence.id)
      }
    } catch (error) {
      console.error('Failed to complete check:', error)
    }
  }

  const formatCheckTime = (timestamp: number | null) => {
    if (!timestamp) return '从未清点'
    const date = new Date(timestamp)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return '今天'
    if (diffDays === 1) return '昨天'
    if (diffDays < 7) return `${diffDays}天前`
    return date.toLocaleDateString()
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!portableResidence) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        未找到随身携带住所，请先创建一个类型为"随身携带"的住所
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-base px-3 py-1">
            {portableResidence.name}
          </Badge>
          <span className="text-sm text-muted-foreground">
            共 {inventories.length} 项物资
          </span>
        </div>
        <div className="flex gap-2">
          {isCheckMode ? (
            <>
              <Button variant="outline" size="sm" onClick={() => {
                setIsCheckMode(false)
                setCheckedItems(new Set())
              }}>
                取消
              </Button>
              <Button size="sm" onClick={handleCompleteCheck} disabled={checkedItems.size === 0}>
                完成清点 ({checkedItems.size})
              </Button>
            </>
          ) : (
            <Button variant="outline" size="sm" onClick={() => setIsCheckMode(true)}>
              开始清点
            </Button>
          )}
        </div>
      </div>

      {isCheckMode && (
        <Card className="p-4 bg-muted/50">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Checkbox 
                checked={inventories.length > 0 && checkedItems.size === inventories.length}
                onCheckedChange={handleCheckAll}
              />
              <Label className="text-sm">全选</Label>
            </div>
            <Separator orientation="vertical" className="h-6" />
            <div className="flex-1">
              <Input
                placeholder="清点备注（可选）"
                value={checkNotes}
                onChange={(e) => setCheckNotes(e.target.value)}
                className="max-w-xs"
              />
            </div>
          </div>
        </Card>
      )}

      {inventories.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          随身携带中暂无物资
        </div>
      ) : (
        <div className="grid gap-2">
          {inventories.map((inv) => (
            <Card 
              key={inv.id} 
              className={`p-4 transition-colors ${isCheckMode ? 'cursor-pointer hover:bg-muted/50' : ''} ${checkedItems.has(inv.id) ? 'bg-primary/5 border-primary' : ''}`}
              onClick={isCheckMode ? () => handleToggleCheck(inv.id) : undefined}
            >
              <div className="flex items-center gap-4">
                {isCheckMode && (
                  <Checkbox 
                    checked={checkedItems.has(inv.id)}
                    onCheckedChange={() => handleToggleCheck(inv.id)}
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{inv.item_name || `物资#${inv.item_id}`}</span>
                    <Badge variant="secondary" className="text-xs">
                      {inv.quantity} {inv.unit}
                    </Badge>
                  </div>
                  {inv.notes && (
                    <p className="text-sm text-muted-foreground mt-1">{inv.notes}</p>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-xs text-muted-foreground">
                    最后清点: {formatCheckTime(inv.last_check_time)}
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ============ Inventory Check Dialog ============

const InventoryCheckDialog = ({ inventory, onChecked }: {
  inventory: InventoryData
  onChecked?: () => void
}) => {
  const [open, setOpen] = useState(false)
  const [quantity, setQuantity] = useState(inventory.quantity)
  const [notes, setNotes] = useState(inventory.notes)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { updateInventory, recordConsumption, recordReplenishment } = useInventoryStore()

  useEffect(() => {
    setQuantity(inventory.quantity)
    setNotes(inventory.notes)
  }, [inventory])

  const handleCheck = async () => {
    setIsSubmitting(true)
    try {
      const oldQty = parseFloat(inventory.quantity)
      const newQty = parseFloat(quantity)
      
      // 更新库存记录
      await updateInventory(inventory.id, {
        item_id: inventory.item_id,
        residence_id: inventory.residence_id,
        quantity,
        notes,
        last_check_time: Date.now(),
      })

      // 如果数量有变化，记录消耗或补充
      if (newQty < oldQty) {
        await recordConsumption(inventory.id, {
          quantity: (oldQty - newQty).toString(),
          reason: '清点调整',
        })
      } else if (newQty > oldQty) {
        await recordReplenishment(inventory.id, {
          quantity: (newQty - oldQty).toString(),
          notes: '清点调整',
        })
      }

      setOpen(false)
      onChecked?.()
    } catch (error) {
      console.error('Failed to update inventory:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">清点</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>清点物资</DialogTitle>
          <DialogDescription>
            确认「{inventory.item_name}」的实际库存
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label>当前数量</Label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className="w-24"
                step="0.1"
                min="0"
              />
              <span className="text-muted-foreground">{inventory.unit}</span>
              {quantity !== inventory.quantity && (
                <Badge variant={parseFloat(quantity) < parseFloat(inventory.quantity) ? 'destructive' : 'default'}>
                  {parseFloat(quantity) < parseFloat(inventory.quantity) ? '-' : '+'}
                  {Math.abs(parseFloat(quantity) - parseFloat(inventory.quantity)).toFixed(1)}
                </Badge>
              )}
            </div>
          </div>
          <div className="grid gap-2">
            <Label>备注</Label>
            <Textarea
              value={notes}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNotes(e.target.value)}
              placeholder="清点备注"
              rows={2}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
          <Button onClick={handleCheck} disabled={isSubmitting}>
            {isSubmitting ? '保存中...' : '确认清点'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ============ Journey Card Component ============

const JourneyCard = () => {
  const { journeys, isLoading, fetchJourneys } = useJourneyStore()

  useEffect(() => {
    fetchJourneys()
  }, [fetchJourneys])

  const activeJourneys = journeys.filter(
    (j) => j.status === JourneyStatus.PLANNED || j.status === JourneyStatus.IN_TRANSIT
  )

  if (isLoading) {
    return <Skeleton className="h-24 w-full" />
  }

  if (activeJourneys.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">旅程</CardTitle>
          <CardDescription>暂无进行中的旅程</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">进行中的旅程</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {activeJourneys.map((journey) => (
            <div key={journey.id} className="flex items-center justify-between p-2 border rounded">
              <div>
                <span className="font-medium">
                  {journey.from_residence_name} → {journey.to_residence_name}
                </span>
                {journey.transport_mode && (
                  <span className="text-sm text-muted-foreground ml-2">
                    ({journey.transport_mode})
                  </span>
                )}
              </div>
              <Badge variant={journey.status === JourneyStatus.IN_TRANSIT ? 'default' : 'secondary'}>
                {JourneyStatusLabels[journey.status as JourneyStatus]}
              </Badge>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ============ Category Seed Button ============

const CategorySeedButton = () => {
  const { categories, seedCategories, fetchCategories, isLoading } = useCategoryStore()
  const [seeding, setSeeding] = useState(false)

  useEffect(() => {
    fetchCategories()
  }, [fetchCategories])

  const handleSeed = async () => {
    setSeeding(true)
    try {
      await seedCategories()
    } catch (error) {
      console.error('Failed to seed categories:', error)
    } finally {
      setSeeding(false)
    }
  }

  if (categories.length > 0) {
    return null
  }

  return (
    <Button variant="outline" onClick={handleSeed} disabled={seeding || isLoading}>
      {seeding ? '初始化中...' : '初始化物资类别'}
    </Button>
  )
}

// ============ Add Inventory Dialog ============

const AddInventoryDialog = ({ onInventoryAdded }: { onInventoryAdded?: () => void }) => {
  const [open, setOpen] = useState(false)
  const [itemId, setItemId] = useState<string>('')
  const [quantity, setQuantity] = useState('1')
  const [unit, setUnit] = useState('个')
  const [minQuantity, setMinQuantity] = useState('0')
  const [notes, setNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { currentResidence } = useResidenceStore()
  const { items, fetchItems } = useItemsStore()
  const { createInventory } = useInventoryStore()

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  const handleSubmit = async () => {
    if (!itemId || !currentResidence) return
    
    setIsSubmitting(true)
    try {
      await createInventory({
        item_id: parseInt(itemId),
        residence_id: currentResidence.id,
        quantity,
        unit,
        min_quantity: minQuantity,
        notes,
      })
      setOpen(false)
      resetForm()
      onInventoryAdded?.()
    } catch (error) {
      console.error('Failed to create inventory:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const resetForm = () => {
    setItemId('')
    setQuantity('1')
    setUnit('个')
    setMinQuantity('0')
    setNotes('')
  }

  if (!currentResidence) {
    return null
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">添加库存</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>添加库存</DialogTitle>
          <DialogDescription>
            将物资添加到「{currentResidence.name}」的库存中
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label>选择物资 *</Label>
            <Select value={itemId} onValueChange={setItemId}>
              <SelectTrigger>
                <SelectValue placeholder="选择一个物资" />
              </SelectTrigger>
              <SelectContent>
                {items.map((item) => (
                  <SelectItem key={item.id} value={item.id.toString()}>
                    {item.name} {item.brand && `(${item.brand})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="grid gap-2">
              <Label>数量</Label>
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                min="0"
                step="0.1"
              />
            </div>
            <div className="grid gap-2">
              <Label>单位</Label>
              <Input
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="个"
              />
            </div>
            <div className="grid gap-2">
              <Label>最低库存</Label>
              <Input
                type="number"
                value={minQuantity}
                onChange={(e) => setMinQuantity(e.target.value)}
                min="0"
                step="0.1"
              />
            </div>
          </div>
          <div className="grid gap-2">
            <Label>备注</Label>
            <Input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="库存备注"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !itemId}>
            {isSubmitting ? '添加中...' : '添加'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ============ Main Page Component ============

const NecessityPage = () => {
  const isMobile = useIsMobile()
  const { fetchItems } = useItemsStore()
  const { currentResidence } = useResidenceStore()
  const { fetchInventoriesByResidence, fetchLowStock, fetchStats } = useInventoryStore()

  const refreshInventory = useCallback(() => {
    if (currentResidence) {
      fetchInventoriesByResidence(currentResidence.id)
      fetchLowStock(currentResidence.id)
      fetchStats(currentResidence.id)
    }
  }, [currentResidence, fetchInventoriesByResidence, fetchLowStock, fetchStats])

  return (
    <PageLayout>
      <div className="flex items-center justify-between mb-4">
        <div className="text-xl md:text-2xl font-bold px-2 md:px-0">物资管理</div>
        <div className="flex gap-2">
          <CategorySeedButton />
          <AddItemDialog onItemAdded={() => fetchItems()} />
        </div>
      </div>

      <div className={`flex gap-4 ${isMobile ? 'flex-col' : 'flex-row'}`}>
        {/* 左侧：住所选择 */}
        <div className={`${isMobile ? 'w-full' : 'w-[250px] min-w-[250px]'}`}>
          <ResidenceSelector />
          <div className="mt-4">
            <JourneyCard />
          </div>
        </div>

        {/* 右侧：主内容区 */}
        <div className={`flex-1 ${isMobile ? 'w-full' : ''}`}>
          <Tabs defaultValue="inventory" className="w-full">
            <TabsList className="mb-4">
              <TabsTrigger value="inventory">库存</TabsTrigger>
              <TabsTrigger value="items">物资</TabsTrigger>
              <TabsTrigger value="portable">随身携带</TabsTrigger>
            </TabsList>

            <TabsContent value="inventory">
              <StatsCard />
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>库存清单</CardTitle>
                      <CardDescription>
                        当前住所的物资库存情况
                      </CardDescription>
                    </div>
                    <AddInventoryDialog onInventoryAdded={refreshInventory} />
                  </div>
                </CardHeader>
                <CardContent>
                  <InventoryTable />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="items">
              <Card>
                <CardHeader>
                  <CardTitle>物资列表</CardTitle>
                  <CardDescription>
                    管理所有物资信息，支持增删查改
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ItemsTable />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="portable">
              <Card>
                <CardHeader>
                  <CardTitle>随身携带物资</CardTitle>
                  <CardDescription>
                    查看和清点当前随身携带的物资
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <PortableItemsView />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </PageLayout>
  )
}

export default NecessityPage
