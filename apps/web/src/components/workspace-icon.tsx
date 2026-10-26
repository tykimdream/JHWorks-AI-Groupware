import type { CSSProperties } from 'react';

export type WorkspaceIconName =
  | 'organization'
  | 'home'
  | 'document'
  | 'calendar'
  | 'sparkles'
  | 'arrow'
  | 'search'
  | 'check'
  | 'clock'
  | 'message'
  | 'plus';

const paths: Record<WorkspaceIconName, string> = {
  organization: 'M9 3h6v5H9ZM3 16h6v5H3ZM15 16h6v5h-6ZM12 8v4M6 16v-4h12v4',
  home: 'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  document: 'M14 3H5v18h14V8Zm0 0v5h5M8 12h8M8 16h5',
  calendar: 'M4 5h16v16H4ZM7 3v4M17 3v4M4 10h16M8 14h2M14 14h2M8 17h2',
  sparkles: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4M18 4h4',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  search: 'M16 16 21 21M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  check: 'm5 12 4 4L19 6',
  clock: 'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  message: 'M21 3H3v14h5v4l5-4h8ZM7 8h10M7 12h6',
  plus: 'M12 5v14M5 12h14',
};

export function WorkspaceIcon({
  name,
  size = 20,
  style,
}: {
  name: WorkspaceIconName;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
