import { useState, useCallback } from 'react';

interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: 'default' | 'success' | 'error' | 'warning';
  duration?: number;
}

interface ToastState {
  toasts: Toast[];
}

let toastCounter = 0;

export const useToast = () => {
  const [state, setState] = useState<ToastState>({ toasts: [] });

  const toast = useCallback(({ title, description, variant = 'default', duration = 3000 }: Omit<Toast, 'id'>) => {
    const id = `toast-${++toastCounter}`;
    const newToast: Toast = { id, title, description, variant, duration };
    
    setState((prev) => ({
      toasts: [...prev.toasts, newToast],
    }));

    if (duration > 0) {
      setTimeout(() => {
        setState((prev) => ({
          toasts: prev.toasts.filter((t) => t.id !== id),
        }));
      }, duration);
    }
  }, []);

  const dismiss = useCallback((id: string) => {
    setState((prev) => ({
      toasts: prev.toasts.filter((t) => t.id !== id),
    }));
  }, []);

  return {
    toast,
    toasts: state.toasts,
    dismiss,
  };
};