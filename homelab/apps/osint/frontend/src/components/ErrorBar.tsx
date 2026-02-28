interface ErrorBarProps {
  error: string | null;
  onDismiss: () => void;
}

export function ErrorBar({ error, onDismiss }: ErrorBarProps) {
  if (!error) return null;

  return (
    <div className="border-t border-error/30 bg-error/10 shrink-0">
      <div className="px-4 py-2.5 flex items-center justify-between">
        <span className="text-xs text-error">{error}</span>
        <button
          className="text-xs text-error/70 hover:text-error transition-colors"
          onClick={onDismiss}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
