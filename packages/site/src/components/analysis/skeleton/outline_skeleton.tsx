/**
 * @file outline_skeleton.tsx
 * @brief Loading skeleton components for outline panels
 * @author sailing-innocent
 * @date 2026-03-07
 */

import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface OutlineNodeSkeletonProps {
  depth?: number
  className?: string
}

/**
 * Skeleton for a single outline node row
 */
export function OutlineNodeSkeleton({ depth = 0, className }: OutlineNodeSkeletonProps) {
  const indent = depth * 20 + 12

  return (
    <div
      className={cn('flex items-center gap-2 py-3 px-4 border-b border-border/50', className)}
      style={{ paddingLeft: `${indent}px` }}
    >
      {/* Expand/collapse placeholder */}
      <Skeleton className="h-6 w-6 shrink-0 rounded" />

      {/* Title and content */}
      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <Skeleton className="h-5 w-20 shrink-0" />
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-4 w-16 shrink-0" />
        </div>
        <Skeleton className="h-4 w-3/4" />
      </div>

      {/* Actions placeholder */}
      <Skeleton className="h-7 w-16 shrink-0" />
    </div>
  )
}

interface OutlineListSkeletonProps {
  count?: number
  className?: string
}

/**
 * Skeleton for outline node list with multiple rows
 */
export function OutlineListSkeleton({ count = 10, className }: OutlineListSkeletonProps) {
  return (
    <div className={cn('space-y-0', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <OutlineNodeSkeleton key={i} depth={i % 3} />
      ))}
    </div>
  )
}

interface OutlineCardSkeletonProps {
  className?: string
}

/**
 * Skeleton for outline card in list view
 */
export function OutlineCardSkeleton({ className }: OutlineCardSkeletonProps) {
  return (
    <div className={cn('p-4 border rounded-lg space-y-3', className)}>
      <div className="flex items-start justify-between">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <div className="flex items-center justify-between pt-2">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-6 w-12" />
      </div>
    </div>
  )
}

interface OutlineCardsSkeletonProps {
  count?: number
  className?: string
}

/**
 * Skeleton for outline cards grid
 */
export function OutlineCardsSkeleton({ count = 4, className }: OutlineCardsSkeletonProps) {
  return (
    <div className={cn('grid grid-cols-1 md:grid-cols-2 gap-4', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <OutlineCardSkeleton key={i} />
      ))}
    </div>
  )
}

interface OutlineTreeSkeletonProps {
  className?: string
}

/**
 * Skeleton for full outline tree panel
 */
export function OutlineTreeSkeleton({ className }: OutlineTreeSkeletonProps) {
  return (
    <div className={cn('space-y-4', className)}>
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-20" />
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-5 w-20" />
        </div>
        <Skeleton className="h-9 w-24" />
      </div>

      {/* Description skeleton */}
      <div className="p-4 border rounded-lg">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3 mt-2" />
      </div>

      {/* Tree skeleton */}
      <div className="border rounded-lg h-[600px]">
        <div className="p-4 border-b">
          <Skeleton className="h-5 w-24" />
        </div>
        <OutlineListSkeleton count={15} />
      </div>
    </div>
  )
}

interface PaginationSkeletonProps {
  className?: string
}

/**
 * Skeleton for pagination loading state
 */
export function PaginationSkeleton({ className }: PaginationSkeletonProps) {
  return (
    <div className={cn('py-4 flex items-center justify-center gap-2', className)}>
      <Skeleton className="h-4 w-4 rounded-full" />
      <Skeleton className="h-4 w-24" />
    </div>
  )
}

interface EvidenceSkeletonProps {
  className?: string
}

/**
 * Skeleton for evidence loading state
 */
export function EvidenceSkeleton({ className }: EvidenceSkeletonProps) {
  return (
    <div className={cn('bg-muted rounded-md p-3 space-y-2', className)}>
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-4/6" />
    </div>
  )
}

// Export all skeleton components
export {
  OutlineNodeSkeleton,
  OutlineListSkeleton,
  OutlineCardSkeleton,
  OutlineCardsSkeleton,
  OutlineTreeSkeleton,
  PaginationSkeleton,
  EvidenceSkeleton,
}
