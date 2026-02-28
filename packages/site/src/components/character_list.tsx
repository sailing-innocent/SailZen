/**
 * @file character_list.tsx
 * @brief Character List Component
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import { Badge } from '@components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@components/ui/dropdown-menu'
import {
  Users,
  Search,
  MoreVertical,
  User,
  UserCog,
  UserMinus,
  Trash2,
  Merge,
} from 'lucide-react'
import type { Character, CharacterRoleType } from '@lib/data/analysis'

interface CharacterListProps {
  characters: Character[]
  selectedCharacterId?: string
  onSelectCharacter: (character: Character) => void
  onDeleteCharacter?: (characterId: string) => void
  onMergeCharacter?: (characterId: string) => void
  isLoading?: boolean
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

const roleTypeIcons: Record<CharacterRoleType, React.ReactNode> = {
  protagonist: <User className="w-4 h-4" />,
  antagonist: <UserMinus className="w-4 h-4" />,
  deuteragonist: <UserCog className="w-4 h-4" />,
  supporting: <User className="w-4 h-4" />,
  minor: <User className="w-4 h-4" />,
  mentioned: <User className="w-4 h-4" />,
}

export function CharacterList({
  characters,
  selectedCharacterId,
  onSelectCharacter,
  onDeleteCharacter,
  onMergeCharacter,
  isLoading = false,
}: CharacterListProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<CharacterRoleType | 'all'>('all')
  const [sortBy, setSortBy] = useState<'name' | 'role' | 'updated'>('role')

  const filteredCharacters = useMemo(() => {
    let result = [...characters]

    // 搜索过滤
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (char) =>
          char.canonical_name.toLowerCase().includes(query) ||
          char.aliases?.some((a) => a.alias.toLowerCase().includes(query)) ||
          char.description?.toLowerCase().includes(query)
      )
    }

    // 角色类型过滤
    if (roleFilter !== 'all') {
      result = result.filter((char) => char.role_type === roleFilter)
    }

    // 排序
    result.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.canonical_name.localeCompare(b.canonical_name)
        case 'role': {
          const roleOrder = {
            protagonist: 0,
            deuteragonist: 1,
            supporting: 2,
            minor: 3,
            antagonist: 4,
            mentioned: 5,
          }
          return roleOrder[a.role_type] - roleOrder[b.role_type]
        }
        case 'updated':
          return (
            new Date(b.updated_at || 0).getTime() -
            new Date(a.updated_at || 0).getTime()
          )
        default:
          return 0
      }
    })

    return result
  }, [characters, searchQuery, roleFilter, sortBy])

  const characterCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: characters.length,
    }
    characters.forEach((char) => {
      counts[char.role_type] = (counts[char.role_type] || 0) + 1
    })
    return counts
  }, [characters])

  if (isLoading) {
    return (
      <Card className="w-full h-full">
        <CardContent className="flex items-center justify-center h-64">
          <div className="w-8 h-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="w-full h-full flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            人物列表
            <Badge variant="secondary">{filteredCharacters.length}</Badge>
          </div>
        </CardTitle>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col gap-4 overflow-hidden">
        {/* 搜索和过滤 */}
        <div className="space-y-3">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索人物..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>

          <div className="flex gap-2">
            <Select
              value={roleFilter}
              onValueChange={(value) =>
                setRoleFilter(value as CharacterRoleType | 'all')
              }
            >
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="角色类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  全部 ({characterCounts.all})
                </SelectItem>
                {Object.entries(roleTypeLabels).map(([role, label]) => (
                  <SelectItem key={role} value={role}>
                    {label} ({characterCounts[role] || 0})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={sortBy} onValueChange={(value) => setSortBy(value as typeof sortBy)}>
              <SelectTrigger className="w-28">
                <SelectValue placeholder="排序" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="role">按角色</SelectItem>
                <SelectItem value="name">按名称</SelectItem>
                <SelectItem value="updated">按更新</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 人物列表 */}
        <div className="flex-1 overflow-y-auto space-y-2 -mx-2 px-2">
          {filteredCharacters.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Users className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>没有找到人物</p>
            </div>
          ) : (
            filteredCharacters.map((character) => (
              <div
                key={character.id}
                onClick={() => onSelectCharacter(character)}
                className={`
                  group flex items-center gap-3 p-3 rounded-lg cursor-pointer
                  transition-colors hover:bg-accent
                  ${selectedCharacterId === character.id ? 'bg-accent border border-accent-foreground/20' : 'border border-transparent'}
                `}
              >
                {/* 角色图标 */}
                <div
                  className={`
                    w-10 h-10 rounded-full flex items-center justify-center text-white
                    ${roleTypeColors[character.role_type]}
                  `}
                >
                  {roleTypeIcons[character.role_type]}
                </div>

                {/* 人物信息 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">
                      {character.canonical_name}
                    </span>
                    <Badge
                      variant="secondary"
                      className="text-xs shrink-0"
                    >
                      {roleTypeLabels[character.role_type]}
                    </Badge>
                  </div>
                  <div className="text-sm text-muted-foreground truncate">
                    {character.aliases && character.aliases.length > 0 ? (
                      <span>别名: {character.aliases.map((a) => a.alias).join(', ')}</span>
                    ) : (
                      <span className="italic">无别名</span>
                    )}
                  </div>
                </div>

                {/* 操作菜单 */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreVertical className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {onMergeCharacter && (
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation()
                          onMergeCharacter(character.id)
                        }}
                      >
                        <Merge className="w-4 h-4 mr-2" />
                        合并人物
                      </DropdownMenuItem>
                    )}
                    {onDeleteCharacter && (
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          onDeleteCharacter(character.id)
                        }}
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        删除
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}
