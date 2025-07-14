import { QueryClient } from '@tanstack/react-query';

const defaultFetcher = async ({ queryKey }: { queryKey: string[] }) => {
  const [url, ...params] = queryKey;
  const searchParams = new URLSearchParams();
  
  // Add query parameters if they exist
  if (params.length > 0) {
    params.forEach((param, index) => {
      if (param) {
        searchParams.append(['userId', 'status', 'managerId'][index] || `param${index}`, param);
      }
    });
  }
  
  const fullUrl = searchParams.toString() ? `${url}?${searchParams.toString()}` : url;
  const response = await fetch(fullUrl);
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: defaultFetcher,
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

export const apiRequest = async (url: string, options: RequestInit = {}) => {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};