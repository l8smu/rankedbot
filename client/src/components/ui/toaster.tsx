import React from 'react';
import { useToast } from '@/hooks/use-toast';

export const Toaster: React.FC = () => {
  const { toasts, dismiss } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`max-w-md px-4 py-3 rounded-lg shadow-lg border ${
            toast.variant === 'error'
              ? 'bg-red-50 border-red-200 text-red-800 dark:bg-red-900 dark:border-red-800 dark:text-red-200'
              : toast.variant === 'success'
              ? 'bg-green-50 border-green-200 text-green-800 dark:bg-green-900 dark:border-green-800 dark:text-green-200'
              : toast.variant === 'warning'
              ? 'bg-yellow-50 border-yellow-200 text-yellow-800 dark:bg-yellow-900 dark:border-yellow-800 dark:text-yellow-200'
              : 'bg-white border-gray-200 text-gray-800 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-200'
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              {toast.title && (
                <div className="font-medium">{toast.title}</div>
              )}
              {toast.description && (
                <div className="text-sm mt-1">{toast.description}</div>
              )}
            </div>
            <button
              onClick={() => dismiss(toast.id)}
              className="ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};