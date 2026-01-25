'use client';

import { useDeleteSession } from '@/lib/api/sessions';

interface DeleteSessionButtonProps {
  sessionId: string;
  onDeleted?: () => void;
}

export function DeleteSessionButton({ sessionId, onDeleted }: DeleteSessionButtonProps) {
  const deleteMutation = useDeleteSession();

  const handleDelete = () => {
    if (confirm('Are you sure you want to delete this session? This action cannot be undone.')) {
      deleteMutation.mutate(sessionId, {
        onSuccess: () => {
          onDeleted?.();
        },
      });
    }
  };

  return (
    <button
      onClick={handleDelete}
      disabled={deleteMutation.isPending}
      className="px-3 py-1.5 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
    </button>
  );
}
