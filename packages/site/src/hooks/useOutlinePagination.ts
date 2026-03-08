/**
 * @file useOutlinePagination.ts
 * @brief Hook for paginated outline data loading
 * @author sailing-innocent
 * @date 2026-03-07
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import {
  api_get_outline_nodes_paginated,
  api_get_node_evidence,
  api_get_node_detail,
  api_get_nodes_details_batch,
} from '@lib/api/analysis'
import type {
  OutlineNodeListItem,
  PaginatedOutlineNodesResponse,
  NodeEvidence,
  NodeDetailResponse,
} from '@lib/data/analysis'

const DEFAULT_PAGE_SIZE = 50

interface UseOutlinePaginationOptions {
  outlineId: string
  parentId?: string
  pageSize?: number
}

interface UseOutlinePaginationReturn {
  nodes: OutlineNodeListItem[]
  isLoading: boolean
  isLoadingMore: boolean
  hasMore: boolean
  error: Error | null
  loadMore: () => Promise<void>
  refresh: () => Promise<void>
  totalCount?: number
}

/**
 * Hook for paginated outline node loading with infinite scroll support
 */
export function useOutlinePagination(
  options: UseOutlinePaginationOptions
): UseOutlinePaginationReturn {
  const { outlineId, parentId, pageSize = DEFAULT_PAGE_SIZE } = options

  const [nodes, setNodes] = useState<OutlineNodeListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined)

  const cursorRef = useRef<string | undefined>(undefined)
  const isFetchingRef = useRef(false)

  const fetchNodes = useCallback(
    async (isInitial: boolean = false) => {
      if (isFetchingRef.current) return
      if (!isInitial && !hasMore) return

      isFetchingRef.current = true

      try {
        if (isInitial) {
          setIsLoading(true)
          setError(null)
        } else {
          setIsLoadingMore(true)
        }

        const response: PaginatedOutlineNodesResponse =
          await api_get_outline_nodes_paginated(
            outlineId,
            pageSize,
            isInitial ? undefined : cursorRef.current,
            parentId
          )

        if (isInitial) {
          setNodes(response.nodes)
        } else {
          setNodes((prev) => [...prev, ...response.nodes])
        }

        cursorRef.current = response.next_cursor
        setHasMore(response.has_more)

        if (response.total_count !== undefined) {
          setTotalCount(response.total_count)
        }
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)))
      } finally {
        isFetchingRef.current = false
        setIsLoading(false)
        setIsLoadingMore(false)
      }
    },
    [outlineId, parentId, pageSize, hasMore]
  )

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return
    await fetchNodes(false)
  }, [fetchNodes, isLoadingMore, hasMore])

  const refresh = useCallback(async () => {
    cursorRef.current = undefined
    setHasMore(true)
    await fetchNodes(true)
  }, [fetchNodes])

  // Initial load
  useEffect(() => {
    fetchNodes(true)
  }, [fetchNodes])

  return {
    nodes,
    isLoading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    refresh,
    totalCount,
  }
}

interface EvidenceCache {
  [nodeId: string]: NodeEvidence[]
}

interface UseNodeEvidenceOptions {
  nodeId: string
  preload?: boolean
}

interface UseNodeEvidenceReturn {
  evidence: NodeEvidence[]
  isLoading: boolean
  error: Error | null
  loadEvidence: () => Promise<void>
}

const evidenceCache: EvidenceCache = {}

/**
 * Hook for lazy loading node evidence with caching
 */
export function useNodeEvidence(
  options: UseNodeEvidenceOptions
): UseNodeEvidenceReturn {
  const { nodeId, preload = false } = options

  const [evidence, setEvidence] = useState<NodeEvidence[]>(() => {
    return evidenceCache[nodeId] || []
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const loadEvidence = useCallback(async () => {
    if (evidenceCache[nodeId]) {
      setEvidence(evidenceCache[nodeId])
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await api_get_node_evidence(nodeId)
      evidenceCache[nodeId] = response.evidence_list
      setEvidence(response.evidence_list)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setIsLoading(false)
    }
  }, [nodeId])

  useEffect(() => {
    if (preload) {
      loadEvidence()
    }
  }, [preload, loadEvidence])

  return {
    evidence,
    isLoading,
    error,
    loadEvidence,
  }
}

interface NodeDetailsCache {
  [nodeId: string]: NodeDetailResponse
}

interface UseNodeDetailOptions {
  nodeId: string
}

interface UseNodeDetailReturn {
  detail: NodeDetailResponse | null
  isLoading: boolean
  error: Error | null
  loadDetail: () => Promise<void>
}

const nodeDetailsCache: NodeDetailsCache = {}

/**
 * Hook for loading node details with caching
 */
export function useNodeDetail(
  options: UseNodeDetailOptions
): UseNodeDetailReturn {
  const { nodeId } = options

  const [detail, setDetail] = useState<NodeDetailResponse | null>(() => {
    return nodeDetailsCache[nodeId] || null
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const loadDetail = useCallback(async () => {
    if (nodeDetailsCache[nodeId]) {
      setDetail(nodeDetailsCache[nodeId])
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await api_get_node_detail(nodeId)
      nodeDetailsCache[nodeId] = response
      setDetail(response)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setIsLoading(false)
    }
  }, [nodeId])

  return {
    detail,
    isLoading,
    error,
    loadDetail,
  }
}

interface UseBatchNodeDetailsOptions {
  nodeIds: string[]
}

interface UseBatchNodeDetailsReturn {
  details: Map<string, NodeDetailResponse>
  isLoading: boolean
  error: Error | null
  loadDetails: () => Promise<void>
}

/**
 * Hook for batch loading node details
 */
export function useBatchNodeDetails(
  options: UseBatchNodeDetailsOptions
): UseBatchNodeDetailsReturn {
  const { nodeIds } = options

  const [details, setDetails] = useState<Map<string, NodeDetailResponse>>(
    new Map()
  )
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const loadDetails = useCallback(async () => {
    if (nodeIds.length === 0) return

    setIsLoading(true)
    setError(null)

    try {
      const responses = await api_get_nodes_details_batch(nodeIds)
      const detailsMap = new Map<string, NodeDetailResponse>()

      responses.forEach((detail) => {
        detailsMap.set(detail.id, detail)
        nodeDetailsCache[detail.id] = detail
      })

      setDetails(detailsMap)
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      setIsLoading(false)
    }
  }, [nodeIds])

  return {
    details,
    isLoading,
    error,
    loadDetails,
  }
}

export default useOutlinePagination
