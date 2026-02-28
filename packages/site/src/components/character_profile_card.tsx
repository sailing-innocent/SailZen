/**
 * @file character_profile_card.tsx
 * @brief Character Profile Card Component
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Badge } from '@components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { Avatar, AvatarFallback } from '@components/ui/avatar'
import { Separator } from '@components/ui/separator'
import {
  User,
  Tag,
  Sparkles,
  Users,
  BookOpen,
  Edit2,
  Save,
  X,
} from 'lucide-react'
import type {
  Character,
  CharacterProfile,
  CharacterAttribute,
  CharacterAlias,
  CharacterRoleType,
} from '@lib/data/analysis'

interface CharacterProfileCardProps {
  profile: CharacterProfile | null
  isLoading?: boolean
  onEdit?: (profile: CharacterProfile) => void
}

const roleTypeLabels: Record<CharacterRoleType, string> = {
  protagonist: '主角',
  antagonist: '反派',
  deuteragonist: '二号主角',
  supporting: '配角',
  minor: '龙套',
  mentioned: '提及',
}

const roleTypeColors: Record<CharacterRoleType, string> = {
  protagonist: 'bg-red-500',
  antagonist: 'bg-purple-500',
  deuteragonist: 'bg-orange-500',
  supporting: 'bg-blue-500',
  minor: 'bg-gray-500',
  mentioned: 'bg-slate-400',
}

const attributeCategoryLabels: Record<string, string> = {
  appearance: '外貌',
  personality: '性格',
  ability: '能力',
  background: '背景',
  relationship: '关系',
  other: '其他',
}

const attributeCategoryColors: Record<string, string> = {
  appearance: 'bg-pink-100 text-pink-800',
  personality: 'bg-blue-100 text-blue-800',
  ability: 'bg-amber-100 text-amber-800',
  background: 'bg-green-100 text-green-800',
  relationship: 'bg-purple-100 text-purple-800',
  other: 'bg-gray-100 text-gray-800',
}

export function CharacterProfileCard({
  profile,
  isLoading = false,
  onEdit,
}: CharacterProfileCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')

  if (isLoading) {
    return (
      <Card className="w-full h-full">
        <CardContent className="flex items-center justify-center h-64">
          <div className="w-8 h-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </CardContent>
      </Card>
    )
  }

  if (!profile) {
    return (
      <Card className="w-full h-full">
        <CardContent className="flex flex-col items-center justify-center h-64 text-muted-foreground">
          <User className="w-16 h-16 mb-4 opacity-50" />
          <p>选择一个人物查看详情</p>
        </CardContent>
      </Card>
    )
  }

  const { character, aliases, attributes, relations, stats } = profile

  // 按类别分组属性
  const groupedAttributes = attributes.reduce((acc, attr) => {
    const category = attr.category || 'other'
    if (!acc[category]) acc[category] = []
    acc[category].push(attr)
    return acc
  }, {} as Record<string, CharacterAttribute[]>)

  return (
    <Card className="w-full h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <Avatar className={`w-16 h-16 ${roleTypeColors[character.role_type]}`}>
              <AvatarFallback className="text-2xl text-white">
                {character.canonical_name.charAt(0)}
              </AvatarFallback>
            </Avatar>
            <div>
              <CardTitle className="text-xl flex items-center gap-2">
                {character.canonical_name}
                <Badge className={roleTypeColors[character.role_type]}>
                  {roleTypeLabels[character.role_type]}
                </Badge>
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                提及 {stats?.mention_count || 0} 次
              </p>
            </div>
          </div>
          {onEdit && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsEditing(!isEditing)}
            >
              {isEditing ? (
                <X className="w-4 h-4" />
              ) : (
                <Edit2 className="w-4 h-4" />
              )}
            </Button>
          )}
        </div>

        {/* 别名 */}
        {aliases && aliases.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            <Tag className="w-4 h-4 text-muted-foreground" />
            {aliases.map((alias) => (
              <Badge key={alias.id} variant="secondary" className="text-xs">
                {alias.alias}
              </Badge>
            ))}
          </div>
        )}

        {/* 描述 */}
        {character.description && (
          <p className="text-sm text-muted-foreground mt-3">
            {character.description}
          </p>
        )}
      </CardHeader>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <TabsList className="mx-6">
          <TabsTrigger value="overview">
            <BookOpen className="w-4 h-4 mr-2" />
            概览
          </TabsTrigger>
          <TabsTrigger value="attributes">
            <Sparkles className="w-4 h-4 mr-2" />
            属性 ({attributes.length})
          </TabsTrigger>
          <TabsTrigger value="relations">
            <Users className="w-4 h-4 mr-2" />
            关系 ({relations.length})
          </TabsTrigger>
        </TabsList>

        <CardContent className="flex-1 overflow-y-auto pt-4">
          <TabsContent value="overview" className="mt-0 space-y-4">
            {/* 基本信息 */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium">基本信息</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">标准名称:</span>
                  <p>{character.canonical_name}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">角色类型:</span>
                  <p>{roleTypeLabels[character.role_type]}</p>
                </div>
                {stats?.first_appearance && (
                  <div>
                    <span className="text-muted-foreground">首次出场:</span>
                    <p>{stats.first_appearance}</p>
                  </div>
                )}
                {stats?.last_appearance && (
                  <div>
                    <span className="text-muted-foreground">最后出场:</span>
                    <p>{stats.last_appearance}</p>
                  </div>
                )}
              </div>
            </div>

            <Separator />

            {/* 属性摘要 */}
            {Object.keys(groupedAttributes).length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium">属性摘要</h4>
                <div className="space-y-2">
                  {Object.entries(groupedAttributes).slice(0, 3).map(([category, attrs]) => (
                    <div key={category} className="flex items-center gap-2">
                      <Badge
                        variant="secondary"
                        className={attributeCategoryColors[category]}
                      >
                        {attributeCategoryLabels[category]}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        {attrs.slice(0, 2).map((a) => a.attr_value).join(', ')}
                        {attrs.length > 2 && ` 等 ${attrs.length} 项`}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="attributes" className="mt-0 space-y-4">
            {Object.entries(groupedAttributes).length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Sparkles className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>暂无属性信息</p>
              </div>
            ) : (
              Object.entries(groupedAttributes).map(([category, attrs]) => (
                <div key={category} className="space-y-2">
                  <h4 className="text-sm font-medium flex items-center gap-2">
                    <Badge className={attributeCategoryColors[category]}>
                      {attributeCategoryLabels[category]}
                    </Badge>
                    <span className="text-muted-foreground">({attrs.length})</span>
                  </h4>
                  <div className="grid gap-2">
                    {attrs.map((attr) => (
                      <div
                        key={attr.id}
                        className="flex items-start justify-between p-2 rounded bg-accent/50"
                      >
                        <div>
                          <p className="text-sm font-medium">{attr.attr_key}</p>
                          <p className="text-sm text-muted-foreground">
                            {attr.attr_value}
                          </p>
                        </div>
                        {attr.confidence && (
                          <Badge variant="outline" className="text-xs">
                            {(attr.confidence * 100).toFixed(0)}%
                          </Badge>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </TabsContent>

          <TabsContent value="relations" className="mt-0">
            {relations.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Users className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>暂无关系信息</p>
              </div>
            ) : (
              <div className="space-y-2">
                {relations.map((relation) => (
                  <div
                    key={relation.id}
                    className="flex items-center gap-3 p-3 rounded bg-accent/50"
                  >
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                      <Users className="w-4 h-4" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">
                        {relation.relation_type}
                        {relation.relation_subtype && (
                          <span className="text-muted-foreground">
                            {' '}
                            ({relation.relation_subtype})
                          </span>
                        )}
                      </p>
                      {relation.description && (
                        <p className="text-sm text-muted-foreground">
                          {relation.description}
                        </p>
                      )}
                    </div>
                    {relation.strength && (
                      <Badge variant="outline" className="text-xs">
                        强度: {(relation.strength * 100).toFixed(0)}%
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </CardContent>
      </Tabs>
    </Card>
  )
}
