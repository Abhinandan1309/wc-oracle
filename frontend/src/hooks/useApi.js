import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

const BASE = '/api'
const STALE = 5 * 60 * 1000   // 5 min cache

async function fetchJson(path) {
  const res = await fetch(BASE + path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export function useSchedule() {
  return useQuery({
    queryKey: ['schedule'],
    queryFn:  () => fetchJson('/schedule'),
    staleTime: STALE,
    refetchInterval: STALE,
  })
}

export function useStandings() {
  return useQuery({
    queryKey: ['standings'],
    queryFn:  () => fetchJson('/standings'),
    staleTime: STALE,
    refetchInterval: STALE,
  })
}

export function useSimulation() {
  return useQuery({
    queryKey: ['simulation'],
    queryFn:  () => fetchJson('/simulation'),
    staleTime: STALE,
    refetchInterval: STALE,
  })
}

export function useTeams() {
  return useQuery({
    queryKey: ['teams'],
    queryFn:  () => fetchJson('/teams'),
    staleTime: Infinity,
  })
}

export function useLive() {
  return useQuery({
    queryKey: ['live'],
    queryFn:  () => fetchJson('/live'),
    refetchInterval: 30000,
    staleTime: 0,
  })
}

export function useRunSimulation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => fetch(BASE + '/simulate', { method: 'POST' }).then(r => r.json()),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ['simulation'] }), 15000)
    },
  })
}

export function useBracket() {
  return useQuery({
    queryKey: ['bracket'],
    queryFn:  () => fetchJson('/bracket'),
    staleTime: STALE,
    refetchInterval: STALE,
  })
}

export function usePaths() {
  return useQuery({
    queryKey: ['paths'],
    queryFn:  () => fetchJson('/paths'),
    staleTime: STALE,
    refetchInterval: STALE,
  })
}

export function useChampionHistory() {
  return useQuery({
    queryKey: ['champion-history'],
    queryFn:  () => fetchJson('/champion-history'),
    staleTime: STALE,
    refetchInterval: STALE,
  })
}

export function useAccuracy() {
  return useQuery({
    queryKey: ['accuracy'],
    queryFn:  () => fetchJson('/accuracy'),
    staleTime: STALE,
  })
}

export function useAvailability() {
  return useQuery({
    queryKey: ['availability'],
    queryFn:  () => fetchJson('/availability'),
    staleTime: 60_000,
  })
}

export function useWhatIf() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (overrides) =>
      fetch(BASE + '/bracket/whatif', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ overrides }),
      }).then(r => r.json()),
  })
}

export function useSetAvailability() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ team, ...body }) =>
      fetch(BASE + `/availability/${encodeURIComponent(team)}`, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(body),
      }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['availability'] }),
  })
}
