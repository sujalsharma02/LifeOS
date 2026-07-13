export function SparkleIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <defs>
        <linearGradient id="sparkle-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4285f4" />
          <stop offset="50%" stopColor="#9b72cb" />
          <stop offset="100%" stopColor="#d96570" />
        </linearGradient>
      </defs>
      <path
        fill="url(#sparkle-grad)"
        d="M12 1.5c.4 4.9 1.6 7.6 3.5 9.2 1.7 1.4 4 2 7 2.3v.9c-3 .3-5.3.9-7 2.3-1.9 1.6-3.1 4.3-3.5 9.3h-.9c-.4-5-1.6-7.7-3.5-9.3-1.7-1.4-4-2-7-2.3v-.9c3-.3 5.3-.9 7-2.3 1.9-1.6 3.1-4.3 3.5-9.2h.9Z"
      />
    </svg>
  );
}

export function SendIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M3.4 20.4 21.8 12 3.4 3.6l-.01 6.53L15 12 3.39 13.87 3.4 20.4Z" />
    </svg>
  );
}

export function ChatIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7l-5 4V6a2 2 0 0 1 2-2Zm3 6h2v2H7v-2Zm4 0h2v2h-2v-2Zm4 0h2v2h-2v-2Z" />
    </svg>
  );
}

export function BookIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M6 2h13a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3Zm0 16a1 1 0 0 0-1 1 1 1 0 0 0 1 1h12v-2H6Zm2-11h8v2H8V7Z" />
    </svg>
  );
}

export function GearIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="m9.3 21-.5-3a6.8 6.8 0 0 1-1.6-.9l-2.8 1.1-2.7-4.6L4 11.8a7.6 7.6 0 0 1 0-1.9L1.7 8.1l2.7-4.6 2.8 1.1c.5-.4 1-.7 1.6-.9l.5-3h5.4l.5 3c.6.2 1.1.5 1.6.9l2.8-1.1 2.7 4.6-2.3 1.8a7.6 7.6 0 0 1 0 1.9l2.3 1.8-2.7 4.6-2.8-1.1c-.5.4-1 .7-1.6.9l-.5 3H9.3ZM12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
    </svg>
  );
}

export function MicIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm-7-3h1.7a5.3 5.3 0 0 0 10.6 0H19a7 7 0 0 1-6 6.92V21h-2v-3.08A7 7 0 0 1 5 11Z" />
    </svg>
  );
}

export function ChartIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M4 20a1 1 0 0 1-1-1V4h2v14h15v2H4Zm3-4v-6h2.5v6H7Zm4.75 0V6h2.5v10h-2.5Zm4.75 0v-4H19v4h-2.5Z" />
    </svg>
  );
}

export function PlusIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" />
    </svg>
  );
}
