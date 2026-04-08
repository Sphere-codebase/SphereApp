import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/errors";

const DEFAULT_STALE_TIME = 30_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: DEFAULT_STALE_TIME,
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          if (error.status >= 400 && error.status < 500) {
            return false;
          }
        }
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          if (error.status >= 400 && error.status < 500) {
            return false;
          }
        }
        return failureCount < 1;
      },
    },
  },
});
