import { useQuery } from '@tanstack/react-query'
import { getScanAnalysis } from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import useI18n from '@/i18n/useI18n'

export default function useScanAnalysis(scanId: string, enabled = true) {
  const { language } = useI18n()
  return useQuery({
    queryKey: queryKeys.scans.analysis(scanId, language),
    queryFn: () => getScanAnalysis(scanId, language),
    enabled: enabled && scanId !== '',
    retry: false,
    staleTime: 30_000,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.status !== 'pending' && data?.status !== 'processing')
        return false
      return Date.now() - Date.parse(data.created_at) < 20 * 60 * 1000
        ? 3000
        : false
    },
  })
}
