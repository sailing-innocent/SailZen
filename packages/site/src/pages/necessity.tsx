/**
 * @file necessity.tsx
 * @brief Necessity (生活物资) Management Page
 * @author sailing-innocent
 * @date 2026-02-01
 */

import { useEffect, useState } from 'react'
import PageLayout from '@components/page_layout'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { Badge } from '@components/ui/badge'
import { Skeleton } from '@components/ui/skeleton'
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
import { Input } from '@components/ui/input'
import { Label } from '@components/ui/label'

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
      <h3 className="text-sm font-medium mb-2">选择住所</h3>
      {residences.map((residence) => (
        <ResidenceCard
          key={residence.id}
          residence={residence}
          isSelected={currentResidence?.id === residence.id}
          onSelect={() => handleSelectResidence(residence)}
        />
      ))}
    </div>
  )
}

// ============ Add Item Dialog ============

const AddItemDialog = ({ onItemAdded }: { onItemAdded?: () => void }) => {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [type, setType] = useState<ItemType>(ItemType.UNIQUE)
  const [brand, setBrand] = useState('')
  const [description, setDescription] = useState('')
  const [importance, setImportance] = useState(3)
  const [portability, setPortability] = useState(3)
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
        description,
        importance,
        portability,
      })
      setOpen(false)
      setName('')
      setBrand('')
      setDescription('')
      setType(ItemType.UNIQUE)
      setImportance(3)
      setPortability(3)
      onItemAdded?.()
    } catch (error) {
      console.error('Failed to create item:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>添加物资</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>添加新物资</DialogTitle>
          <DialogDescription>
            填写物资信息，创建后可在库存中添加位置
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="name">名称 *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="物资名称"
            />
          </div>
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
            <Label htmlFor="brand">品牌</Label>
            <Input
              id="brand"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder="品牌名称"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">描述</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="物资描述"
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

// ============ Items Table Component ============

const ItemsTable = () => {
  const { items, isLoading, fetchItems, deleteItem } = useItemsStore()

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        暂无物资，点击"添加物资"创建第一个物资
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>名称</TableHead>
          <TableHead>类型</TableHead>
          <TableHead>品牌</TableHead>
          <TableHead>重要性</TableHead>
          <TableHead>状态</TableHead>
          <TableHead className="text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="font-medium">{item.name}</TableCell>
            <TableCell>
              <Badge variant="outline">
                {ItemTypeLabels[item.type as ItemType]}
              </Badge>
            </TableCell>
            <TableCell>{item.brand || '-'}</TableCell>
            <TableCell>{'★'.repeat(item.importance)}</TableCell>
            <TableCell>
              <Badge variant={item.state === ItemState.ACTIVE ? 'default' : 'secondary'}>
                {ItemStateLabels[item.state as ItemState]}
              </Badge>
            </TableCell>
            <TableCell className="text-right">
              <Button variant="ghost" size="sm" onClick={() => deleteItem(item.id)}>
                删除
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// ============ Inventory Table Component ============

const InventoryTable = () => {
  const { inventories, isLoading, lowStockItems } = useInventoryStore()
  const { currentResidence } = useResidenceStore()

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

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>物资名称</TableHead>
          <TableHead>数量</TableHead>
          <TableHead>单位</TableHead>
          <TableHead>容器</TableHead>
          <TableHead>状态</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {inventories.map((inv) => (
          <TableRow key={inv.id}>
            <TableCell className="font-medium">{inv.item_name || `物资#${inv.item_id}`}</TableCell>
            <TableCell>
              <span className={isLowStock(inv) ? 'text-destructive font-medium' : ''}>
                {inv.quantity}
              </span>
              {isLowStock(inv) && (
                <Badge variant="destructive" className="ml-2">低库存</Badge>
              )}
            </TableCell>
            <TableCell>{inv.unit}</TableCell>
            <TableCell>{inv.container_name || '-'}</TableCell>
            <TableCell>
              {parseFloat(inv.min_quantity) > 0 && (
                <span className="text-xs text-muted-foreground">
                  最低: {inv.min_quantity}
                </span>
              )}
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

// ============ Main Page Component ============

const NecessityPage = () => {
  const isMobile = useIsMobile()
  const { fetchItems } = useItemsStore()

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
            </TabsList>

            <TabsContent value="inventory">
              <StatsCard />
              <Card>
                <CardHeader>
                  <CardTitle>库存清单</CardTitle>
                  <CardDescription>
                    当前住所的物资库存情况
                  </CardDescription>
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
                    管理所有物资信息
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ItemsTable />
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
