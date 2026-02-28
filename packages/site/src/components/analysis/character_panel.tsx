/**
 * @file character_panel.tsx
 * @brief Character Management Panel
 * @author sailing-innocent
 * @date 2025-02-01
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  api_get_characters_by_edition,
  api_create_character,
  api_delete_character,
  api_get_character_profile,
  api_get_relation_graph,
} from '@lib/api/analysis'
import type { Character, CharacterProfile, CharacterRoleType, RelationGraphData } from '@lib/data/analysis'
import CharacterProfileCard from './character_profile_card'
import RelationGraph from './relation_graph'

interface CharacterPanelProps {
  editionId: number
}

const ROLE_TYPE_LABELS: Record<CharacterRoleType, string> = {
  protagonist: '主角',
  antagonist: '反派',
  deuteragonist: '二号主角',
  supporting: '配角',
  minor: '龙套',
  mentioned: '提及',
}

export default function CharacterPanel({ editionId }: CharacterPanelProps) {
  const [characters, setCharacters] = useState<Character[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null)
  const [characterProfile, setCharacterProfile] = useState<CharacterProfile | null>(null)
  const [showGraph, setShowGraph] = useState(false)
  const [graphData, setGraphData] = useState<RelationGraphData | null>(null)

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newCharacter, setNewCharacter] = useState({
    canonical_name: '',
    role_type: 'supporting' as CharacterRoleType,
    description: '',
  })

  const fetchCharacters = async () => {
    setLoading(true)
    setError(null)
    try {
      const roleType = roleFilter === 'all' ? undefined : roleFilter
      const result = await api_get_characters_by_edition(editionId, roleType)
      
      // Handle backend response format: {success: true, data: [...]}
      const characterList = result.data || result || []
      
      // Filter by search keyword
      const filtered = searchKeyword
        ? characterList.filter((c: Character) => 
            c.canonical_name.toLowerCase().includes(searchKeyword.toLowerCase())
          )
        : characterList
      
      setCharacters(filtered)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCharacters()
  }, [editionId, roleFilter])

  const handleSearch = () => {
    fetchCharacters()
  }

  const handleSelectCharacter = async (character: Character) => {
    setSelectedCharacter(character)
    try {
      const profile = await api_get_character_profile(character.id)
      setCharacterProfile(profile)
    } catch (err) {
      console.error('Failed to load profile:', err)
    }
  }

  const handleCreateCharacter = async () => {
    if (!newCharacter.canonical_name.trim()) return

    try {
      const result = await api_create_character(
        editionId,
        {
          canonical_name: newCharacter.canonical_name,
          role_type: newCharacter.role_type,
          description: newCharacter.description || undefined,
        }
      )
      // Handle backend response format: {success: true, data: {...}}
      const created = result.data || result
      setCharacters([created, ...characters])
      setCreateDialogOpen(false)
      setNewCharacter({ canonical_name: '', role_type: 'supporting', description: '' })
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败')
    }
  }

  const handleDeleteCharacter = async (character: Character) => {
    if (!confirm(`确定要删除「${character.canonical_name}」吗？`)) return

    try {
      await api_delete_character(character.id)
      setCharacters(characters.filter(c => c.id !== character.id))
      if (selectedCharacter?.id === character.id) {
        setSelectedCharacter(null)
        setCharacterProfile(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleShowGraph = async () => {
    try {
      const data = await api_get_relation_graph(editionId)
      setGraphData(data)
      setShowGraph(true)
    } catch (err) {
      console.error('Failed to load graph:', err)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    )
  }

  // Show relation graph
  if (showGraph && graphData) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">人物关系图</h3>
          <Button variant="outline" onClick={() => setShowGraph(false)}>
            返回列表
          </Button>
        </div>
        <RelationGraph data={graphData} onNodeClick={(id) => {
          const char = characters.find(c => c.id === id)
          if (char) {
            setShowGraph(false)
            handleSelectCharacter(char)
          }
        }} />
      </div>
    )
  }

  // Show character profile
  if (selectedCharacter && characterProfile) {
    return (
      <CharacterProfileCard
        profile={characterProfile}
        onBack={() => {
          setSelectedCharacter(null)
          setCharacterProfile(null)
        }}
        onUpdate={() => {
          fetchCharacters()
          handleSelectCharacter(selectedCharacter)
        }}
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="搜索人物..."
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 min-w-48"
        />
        <Select value={roleFilter} onValueChange={setRoleFilter}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="角色类型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部</SelectItem>
            {Object.entries(ROLE_TYPE_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={handleSearch}>搜索</Button>
        <Button variant="outline" onClick={handleShowGraph}>关系图</Button>
        
        {/* Create Dialog */}
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>新增人物</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新增人物</DialogTitle>
              <DialogDescription>创建一个新的人物角色</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">人物名称</Label>
                <Input
                  id="name"
                  value={newCharacter.canonical_name}
                  onChange={(e) => setNewCharacter({ ...newCharacter, canonical_name: e.target.value })}
                  placeholder="输入人物名称"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">角色类型</Label>
                <Select
                  value={newCharacter.role_type}
                  onValueChange={(v) => setNewCharacter({ ...newCharacter, role_type: v as CharacterRoleType })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ROLE_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="desc">描述</Label>
                <Textarea
                  id="desc"
                  value={newCharacter.description}
                  onChange={(e) => setNewCharacter({ ...newCharacter, description: e.target.value })}
                  placeholder="人物描述（可选）"
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>取消</Button>
              <Button onClick={handleCreateCharacter}>创建</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Error message */}
      {error && (
        <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>
      )}

      {/* Character List */}
      {characters.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          暂无人物，点击「新增人物」开始创建
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {characters.map((character) => (
            <Card
              key={character.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => handleSelectCharacter(character)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base">{character.canonical_name}</CardTitle>
                  <Badge variant="outline">{ROLE_TYPE_LABELS[character.role_type]}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                {character.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                    {character.description}
                  </p>
                )}
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <div className="flex gap-3">
                    <span>{character.alias_count} 别名</span>
                    <span>{character.relation_count} 关系</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-500 hover:text-red-700 h-6 px-2"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteCharacter(character)
                    }}
                  >
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
