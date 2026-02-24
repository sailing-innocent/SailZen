import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useChallengeStore, type ChallengeStore } from '@lib/store/challenge'
import { ChallengeStatus, CheckInStatus, type ChallengeData, type CheckInData, type CheckInStatusValue, type ChallengeStats, calculateChallengeStats, isTodayDay } from '@lib/data/challenge'
import { api_get_challenge_detail } from '@lib/api/challenge'
import { useIsMobile } from '@/hooks/use-mobile'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AlertCircle, Target, History, Trash2, Ban } from 'lucide-react'
import { cn } from '@/lib/utils'

import ChallengeCard from './challenge_card'
import ChallengeCalendar from './challenge_calendar'
import CreateChallengeDialog from './challenge_create_dialog'
import CheckInDialog from './challenge_checkin_dialog'

interface ChallengeViewProps {
  // 可以在这里添加 props，如果需要的话
}

const ChallengeView: React.FC<ChallengeViewProps> = () => {
  const isMobile = useIsMobile()

  // Store state
  const activeChallenges = useChallengeStore((state: ChallengeStore) => state.activeChallenges)
  const challenges = useChallengeStore((state: ChallengeStore) => state.challenges)
  const currentChallenge = useChallengeStore((state: ChallengeStore) => state.currentChallenge)
  const currentCheckIns = useChallengeStore((state: ChallengeStore) => state.currentCheckIns)
  const currentStats = useChallengeStore((state: ChallengeStore) => state.currentStats)
  const isLoading = useChallengeStore((state: ChallengeStore) => state.isLoading)
  const isCreating = useChallengeStore((state: ChallengeStore) => state.isCreating)
  const isCheckingIn = useChallengeStore((state: ChallengeStore) => state.isCheckingIn)
  const error = useChallengeStore((state: ChallengeStore) => state.error)

  // Store actions
  const fetchChallenges = useChallengeStore((state: ChallengeStore) => state.fetchChallenges)
  const fetchActiveChallenges = useChallengeStore((state: ChallengeStore) => state.fetchActiveChallenges)
  const fetchChallengeDetail = useChallengeStore((state: ChallengeStore) => state.fetchChallengeDetail)
  const createChallenge = useChallengeStore((state: ChallengeStore) => state.createChallenge)
  const deleteChallenge = useChallengeStore((state: ChallengeStore) => state.deleteChallenge)
  const abortChallenge = useChallengeStore((state: ChallengeStore) => state.abortChallenge)
  const checkInSuccess = useChallengeStore((state: ChallengeStore) => state.checkInSuccess)
  const checkInFailed = useChallengeStore((state: ChallengeStore) => state.checkInFailed)
  const resetCheckIn = useChallengeStore((state: ChallengeStore) => state.resetCheckIn)
  const clearError = useChallengeStore((state: ChallengeStore) => state.clearError)
  const getTodayMissionId = useChallengeStore((state: ChallengeStore) => state.getTodayMissionId)

  // Local state
  const [selectedChallengeId, setSelectedChallengeId] = useState<number | null>(null)
  const [isCheckInDialogOpen, setIsCheckInDialogOpen] = useState(false)
  const [selectedDay, setSelectedDay] = useState<{ day: number; date: Date; status: CheckInStatusValue } | null>(null)
  const [activeTab, setActiveTab] = useState('active')
  // 存储所有挑战的 stats，用于左侧列表显示进度
  const [challengeStatsMap, setChallengeStatsMap] = useState<Map<number, ChallengeStats>>(new Map())

  // 初始化加载
  useEffect(() => {
    fetchActiveChallenges()
    fetchChallenges()
  }, [fetchActiveChallenges, fetchChallenges])

  // 跟踪正在加载的 challenge IDs，避免重复请求
  const loadingChallengeIds = useRef<Set<number>>(new Set())

  // 加载单个挑战的 stats
  const loadSingleChallengeStats = useCallback(async (challengeId: number) => {
    if (loadingChallengeIds.current.has(challengeId)) {
      return
    }

    loadingChallengeIds.current.add(challengeId)

    try {
      const detail = await api_get_challenge_detail(challengeId)
      if (detail) {
        const stats = calculateChallengeStats(
          detail.checkIns,
          detail.challenge.startDate,
          detail.challenge.days
        )
        setChallengeStatsMap(prev => {
          const newMap = new Map(prev)
          newMap.set(challengeId, stats)
          return newMap
        })
      }
    } catch (err) {
      console.error(`Failed to load stats for challenge ${challengeId}:`, err)
    } finally {
      loadingChallengeIds.current.delete(challengeId)
    }
  }, [])

  // 加载所有挑战的 stats（用于左侧列表显示）
  const loadChallengeStats = useCallback(async (challengeList: ChallengeData[]) => {
    // 异步加载每个挑战的 stats
    for (const challenge of challengeList) {
      await loadSingleChallengeStats(challenge.id)
    }
  }, [loadSingleChallengeStats])

  // 当挑战列表变化时，加载它们的 stats
  useEffect(() => {
    if (activeChallenges.length > 0 || challenges.length > 0) {
      const allChallenges = [...activeChallenges, ...challenges.filter(c => c.status !== ChallengeStatus.ACTIVE)]
      // 去重
      const uniqueChallenges = Array.from(new Map(allChallenges.map(c => [c.id, c])).values())
      loadChallengeStats(uniqueChallenges)
    }
  }, [activeChallenges.length, challenges.length])

  // 加载选中挑战的详情
  useEffect(() => {
    if (selectedChallengeId) {
      fetchChallengeDetail(selectedChallengeId)
    }
  }, [selectedChallengeId, fetchChallengeDetail])

  // 自动选择第一个活跃挑战
  useEffect(() => {
    if (activeChallenges.length > 0 && !selectedChallengeId) {
      setSelectedChallengeId(activeChallenges[0].id)
    }
  }, [activeChallenges, selectedChallengeId])

  // 处理创建挑战
  const handleCreateChallenge = async (props: Parameters<typeof createChallenge>[0]) => {
    const challenge = await createChallenge(props)
    if (challenge) {
      setSelectedChallengeId(challenge.id)
      setActiveTab('active')
    }
  }

  // 处理打卡
  const handleCheckIn = (day?: number) => {
    if (day) {
      const checkIn = currentCheckIns.find(c => c.day === day)
      if (checkIn) {
        setSelectedDay({ day, date: checkIn.date, status: checkIn.status })
      }
    } else {
      // 今日打卡 - 使用 isTodayDay 函数查找今天的打卡记录
      const todayCheckIn = currentCheckIns.find(c => {
        if (!currentChallenge) return false
        return isTodayDay(currentChallenge.startDate, c.day)
      })
      if (todayCheckIn) {
        setSelectedDay({
          day: todayCheckIn.day,
          date: todayCheckIn.date,
          status: todayCheckIn.status
        })
      }
    }
    setIsCheckInDialogOpen(true)
  }

  // 处理打卡成功
  const handleCheckInSuccess = async () => {
    const missionId = getTodayMissionId()
    if (missionId && selectedChallengeId) {
      await checkInSuccess(missionId, selectedChallengeId)
      // 刷新该挑战的 stats（更新左侧列表显示）
      await loadSingleChallengeStats(selectedChallengeId)
      setIsCheckInDialogOpen(false)
    }
  }

  // 处理打卡失败
  const handleCheckInFailed = async () => {
    const missionId = getTodayMissionId()
    if (missionId && selectedChallengeId) {
      await checkInFailed(missionId, selectedChallengeId)
      // 刷新该挑战的 stats（更新左侧列表显示）
      await loadSingleChallengeStats(selectedChallengeId)
      setIsCheckInDialogOpen(false)
    }
  }

  // 处理重置打卡
  const handleResetCheckIn = async () => {
    if (selectedDay && selectedChallengeId) {
      const checkIn = currentCheckIns.find(c => c.day === selectedDay.day)
      if (checkIn) {
        await resetCheckIn(checkIn.mission.id, selectedChallengeId)
        // 刷新该挑战的 stats（更新左侧列表显示）
        await loadSingleChallengeStats(selectedChallengeId)
        setIsCheckInDialogOpen(false)
      }
    }
  }

  // 处理删除挑战
  const handleDeleteChallenge = async (challengeId: number) => {
    if (confirm('确定要删除这个挑战吗？所有打卡记录也将被删除。')) {
      await deleteChallenge(challengeId)
      if (selectedChallengeId === challengeId) {
        setSelectedChallengeId(null)
      }
    }
  }

  // 处理中止挑战
  const handleAbortChallenge = async (challengeId: number) => {
    if (confirm('确定要中止这个挑战吗？所有未打卡的天数将被标记为失败。')) {
      await abortChallenge(challengeId)
    }
  }

  // 渲染挑战列表
  const renderChallengeList = (challengeList: ChallengeData[], showActions = true) => {
    if (challengeList.length === 0) {
      return (
        <div className="text-center py-8 text-muted-foreground">
          <Target className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p>暂无挑战</p>
          <p className="text-sm">点击上方按钮创建新挑战</p>
        </div>
      )
    }

    return (
      <div className={cn('grid gap-4', isMobile ? 'grid-cols-1' : 'grid-cols-2')}>
        {challengeList.map((challenge) => (
          <div
            key={challenge.id}
            className={cn(
              'cursor-pointer transition-all',
              selectedChallengeId === challenge.id && 'ring-2 ring-primary rounded-lg'
            )}
            onClick={() => setSelectedChallengeId(challenge.id)}
          >
            <ChallengeCard
              challenge={challenge}
              stats={challengeStatsMap.get(challenge.id) ?? null}
              onCheckIn={() => handleCheckIn()}
              onViewDetail={() => setSelectedChallengeId(challenge.id)}
              isLoading={isLoading}
            />
            {showActions && selectedChallengeId === challenge.id && challenge.status === ChallengeStatus.ACTIVE && (
              <div className="flex gap-2 mt-2 px-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex-1 text-red-600 hover:text-red-700 hover:bg-red-50"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleAbortChallenge(challenge.id)
                  }}
                >
                  <Ban className="h-4 w-4 mr-1" />
                  中止
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex-1 text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDeleteChallenge(challenge.id)
                  }}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  删除
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 错误提示 */}
      {error && (
        <Alert variant="destructive" className="animate-in fade-in">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button variant="ghost" size="sm" onClick={clearError}>
              关闭
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* 头部操作区 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold">打卡挑战</h2>
          {activeChallenges.length > 0 && (
            <Badge variant="secondary">{activeChallenges.length} 进行中</Badge>
          )}
        </div>
        <CreateChallengeDialog onCreate={handleCreateChallenge} isCreating={isCreating} />
      </div>

      {/* 主要内容区 */}
      <div className={cn('grid gap-6', isMobile ? 'grid-cols-1' : 'grid-cols-5')}>
        {/* 左侧：挑战列表 */}
        <div className={isMobile ? '' : 'col-span-2'}>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full grid grid-cols-2">
              <TabsTrigger value="active" className="gap-1">
                <Target className="h-4 w-4" />
                进行中
                {activeChallenges.length > 0 && (
                  <span className="ml-1 text-xs">({activeChallenges.length})</span>
                )}
              </TabsTrigger>
              <TabsTrigger value="history" className="gap-1">
                <History className="h-4 w-4" />
                历史
              </TabsTrigger>
            </TabsList>

            <TabsContent value="active" className="mt-4">
              {renderChallengeList(activeChallenges)}
            </TabsContent>

            <TabsContent value="history" className="mt-4">
              {renderChallengeList(
                challenges.filter(c => c.status !== ChallengeStatus.ACTIVE),
                false
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* 右侧：挑战详情 */}
        <div className={isMobile ? '' : 'col-span-3'}>
          {currentChallenge && currentStats ? (
            <div className="space-y-4">
              <ChallengeCard
                challenge={currentChallenge}
                stats={currentStats}
                onCheckIn={() => handleCheckIn()}
                onViewDetail={() => { }}
                isLoading={isCheckingIn}
              />

              {/* 打卡日历 */}
              <div>{currentChallenge.startDate.toDateString()}</div>
              <div className="rounded-lg border p-4">
                <h3 className="text-sm font-medium mb-4">打卡日历</h3>
                <ChallengeCalendar
                  checkIns={currentCheckIns}
                  startDate={currentChallenge.startDate}
                  onCheckInClick={(day) => handleCheckIn(day)}
                  onDayClick={(checkIn) => {
                    setSelectedDay({
                      day: checkIn.day,
                      date: checkIn.date,
                      status: checkIn.status,
                    })
                    setIsCheckInDialogOpen(true)
                  }}
                />
              </div>
            </div>
          ) : (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center text-muted-foreground border rounded-lg">
              <Target className="h-16 w-16 mb-4 opacity-30" />
              <p>选择一个挑战查看详情</p>
              <p className="text-sm mt-1">或者创建一个新的挑战开始打卡</p>
            </div>
          )}
        </div>
      </div>

      {/* 打卡对话框 */}
      {selectedDay && currentChallenge && (
        <CheckInDialog
          isOpen={isCheckInDialogOpen}
          onClose={() => {
            setIsCheckInDialogOpen(false)
            setSelectedDay(null)
          }}
          day={selectedDay.day}
          date={selectedDay.date}
          currentStatus={selectedDay.status}
          challengeTitle={currentChallenge.title}
          onSuccess={handleCheckInSuccess}
          onFail={handleCheckInFailed}
          onReset={handleResetCheckIn}
          isLoading={isCheckingIn}
        />
      )}
    </div>
  )
}

export default ChallengeView
