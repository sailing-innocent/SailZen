/**
 * @file character_profile_card.tsx
 * @brief Character Profile Card Component
 * @author sailing-innocent
 * @date 2025-02-01
 */

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  api_add_character_alias,
  api_remove_character_alias,
  api_add_character_attribute,
  api_delete_character_attribute,
} from '@lib/api/analysis'
import type { CharacterProfile, CharacterAttributeCategory } from '@lib/data/analysis'

interface CharacterProfileCardProps {
  profile: CharacterProfile
  onBack: () => void
  onUpdate: () => void
}

const ROLE_TYPE_LABELS: Record<string, string> = {
  protagonist: '主角',
  antagonist: '反派',
  deuteragonist: '二号主角',
  supporting: '配角',
  minor: '龙套',
  mentioned: '提及',
}

const ATTRIBUTE_CATEGORY_LABELS: Record<CharacterAttributeCategory, string> = {
  basic: '基础信息',
  appearance: '外貌特征',
  personality: '性格特点',
  ability: '能力技能',
  background: '背景经历',
  goal: '目标动机',
}

const ALIAS_TYPE_LABELS: Record<string, string> = {
  nickname: '昵称',
  title: '头衔',
  formal_name: '正式名',
  pen_name: '笔名',
  code_name: '代号',
}

export default function CharacterProfileCard({ profile, onBack, onUpdate }: CharacterProfileCardProps) {
  const [addAliasOpen, setAddAliasOpen] = useState(false)
  const [newAlias, setNewAlias] = useState({ alias: '', alias_type: 'nickname' })
  const [addAttrOpen, setAddAttrOpen] = useState(false)
  const [newAttr, setNewAttr] = useState({ category: 'basic' as CharacterAttributeCategory, key: '', value: '' })

  const handleAddAlias = async () => {
    if (!newAlias.alias.trim()) return
    try {
      await api_add_character_alias(profile.character.id, newAlias.alias, newAlias.alias_type)
      setAddAliasOpen(false)
      setNewAlias({ alias: '', alias_type: 'nickname' })
      onUpdate()
    } catch (err) {
      console.error('Failed to add alias:', err)
    }
  }

  const handleRemoveAlias = async (aliasId: number) => {
    try {
      await api_remove_character_alias(aliasId)
      onUpdate()
    } catch (err) {
      console.error('Failed to remove alias:', err)
    }
  }

  const handleAddAttribute = async () => {
    if (!newAttr.key.trim()) return
    try {
      await api_add_character_attribute(
        profile.character.id,
        newAttr.category,
        newAttr.key,
        newAttr.value
      )
      setAddAttrOpen(false)
      setNewAttr({ category: 'basic', key: '', value: '' })
      onUpdate()
    } catch (err) {
      console.error('Failed to add attribute:', err)
    }
  }

  const handleRemoveAttribute = async (attrId: number) => {
    try {
      await api_delete_character_attribute(attrId)
      onUpdate()
    } catch (err) {
      console.error('Failed to remove attribute:', err)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onBack}>← 返回</Button>
          <h2 className="text-xl font-bold">{profile.character.canonical_name}</h2>
          <Badge variant="outline">{ROLE_TYPE_LABELS[profile.character.role_type]}</Badge>
        </div>
      </div>

      {/* Description */}
      {profile.character.description && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-muted-foreground">{profile.character.description}</p>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="aliases" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="aliases">别名 ({profile.aliases.length})</TabsTrigger>
          <TabsTrigger value="attributes">属性</TabsTrigger>
          <TabsTrigger value="relations">关系 ({profile.relations.length})</TabsTrigger>
          <TabsTrigger value="arcs">弧线 ({profile.arcs.length})</TabsTrigger>
        </TabsList>

        {/* Aliases Tab */}
        <TabsContent value="aliases" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">人物别名</CardTitle>
                <Dialog open={addAliasOpen} onOpenChange={setAddAliasOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm">添加别名</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>添加别名</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label>别名</Label>
                        <Input
                          value={newAlias.alias}
                          onChange={(e) => setNewAlias({ ...newAlias, alias: e.target.value })}
                          placeholder="输入别名"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>类型</Label>
                        <Select
                          value={newAlias.alias_type}
                          onValueChange={(v) => setNewAlias({ ...newAlias, alias_type: v })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {Object.entries(ALIAS_TYPE_LABELS).map(([value, label]) => (
                              <SelectItem key={value} value={value}>{label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setAddAliasOpen(false)}>取消</Button>
                      <Button onClick={handleAddAlias}>添加</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {profile.aliases.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">暂无别名</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {profile.aliases.map((alias) => (
                    <Badge
                      key={alias.id}
                      variant="secondary"
                      className="flex items-center gap-1"
                    >
                      {alias.alias}
                      <span className="text-xs opacity-60">({ALIAS_TYPE_LABELS[alias.alias_type] || alias.alias_type})</span>
                      <button
                        className="ml-1 hover:text-red-500"
                        onClick={() => handleRemoveAlias(alias.id)}
                      >
                        ×
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Attributes Tab */}
        <TabsContent value="attributes" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">人物属性</CardTitle>
                <Dialog open={addAttrOpen} onOpenChange={setAddAttrOpen}>
                  <DialogTrigger asChild>
                    <Button size="sm">添加属性</Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>添加属性</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label>分类</Label>
                        <Select
                          value={newAttr.category}
                          onValueChange={(v) => setNewAttr({ ...newAttr, category: v as CharacterAttributeCategory })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {Object.entries(ATTRIBUTE_CATEGORY_LABELS).map(([value, label]) => (
                              <SelectItem key={value} value={value}>{label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>属性名</Label>
                        <Input
                          value={newAttr.key}
                          onChange={(e) => setNewAttr({ ...newAttr, key: e.target.value })}
                          placeholder="如：年龄、身高、武器"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>属性值</Label>
                        <Input
                          value={newAttr.value}
                          onChange={(e) => setNewAttr({ ...newAttr, value: e.target.value })}
                          placeholder="属性值"
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setAddAttrOpen(false)}>取消</Button>
                      <Button onClick={handleAddAttribute}>添加</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-64">
                {Object.keys(profile.attributes).length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">暂无属性</p>
                ) : (
                  <div className="space-y-4">
                    {Object.entries(profile.attributes).map(([category, attrs]) => (
                      <div key={category}>
                        <h4 className="font-medium text-sm mb-2">
                          {ATTRIBUTE_CATEGORY_LABELS[category as CharacterAttributeCategory] || category}
                        </h4>
                        <div className="space-y-1">
                          {attrs.map((attr) => (
                            <div key={attr.id} className="flex items-center justify-between text-sm py-1 px-2 rounded hover:bg-muted/50">
                              <span>
                                <span className="font-medium">{attr.attr_key}：</span>
                                <span className="text-muted-foreground">{String(attr.attr_value)}</span>
                              </span>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-red-500 hover:text-red-700"
                                onClick={() => handleRemoveAttribute(attr.id)}
                              >
                                删除
                              </Button>
                            </div>
                          ))}
                        </div>
                        <Separator className="mt-2" />
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Relations Tab */}
        <TabsContent value="relations" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">人物关系</CardTitle>
            </CardHeader>
            <CardContent>
              {profile.relations.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">暂无关系</p>
              ) : (
                <div className="space-y-2">
                  {profile.relations.map((relation) => {
                    const isSource = relation.source_character_id === profile.character.id
                    const otherName = isSource ? relation.target_character_name : relation.source_character_name
                    return (
                      <div key={relation.id} className="flex items-center justify-between p-2 rounded hover:bg-muted/50">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{otherName}</span>
                          <Badge variant="outline">{relation.relation_type}</Badge>
                          {relation.relation_subtype && (
                            <span className="text-xs text-muted-foreground">({relation.relation_subtype})</span>
                          )}
                        </div>
                        {relation.description && (
                          <span className="text-sm text-muted-foreground">{relation.description}</span>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Arcs Tab */}
        <TabsContent value="arcs" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">人物弧线</CardTitle>
            </CardHeader>
            <CardContent>
              {profile.arcs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">暂无弧线记录</p>
              ) : (
                <div className="space-y-3">
                  {profile.arcs.map((arc) => (
                    <div key={arc.id} className="p-3 border rounded-lg">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium">{arc.title}</span>
                        <Badge variant="secondary">{arc.arc_type}</Badge>
                      </div>
                      {arc.description && (
                        <p className="text-sm text-muted-foreground">{arc.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
