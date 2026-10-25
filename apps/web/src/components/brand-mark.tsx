// Relay: two open, opposing forms represent a handoff between people and workflow stages.
export const relayPath = 'M6 8h17a7 7 0 0 1 7 7v7h-8v-5a1 1 0 0 0-1-1h-7v18H6V8Zm36 32H25a7 7 0 0 1-7-7v-7h8v5a1 1 0 0 0 1 1h7V14h8v26Z';

export function BrandMark({ size = 36, color = 'var(--jhw-color-primary)', className }: { size?: number; color?: string; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" width={size} height={size} fill={color} aria-hidden="true">
      <path d={relayPath} />
    </svg>
  );
}
