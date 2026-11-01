import { useQuery } from '@tanstack/react-query';
import { modelApi } from '../api/client';

export function useApiHealth() {
  return useQuery({
    queryKey: ['api-health'],
    queryFn: async () => (await modelApi.get('/health')).data,
    staleTime: 30000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}
