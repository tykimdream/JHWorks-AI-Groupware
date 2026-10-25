import { symbolPaths, symbolViewBox, wordmarkPaths, wordmarkViewBox } from '@/components/brand-artwork';

const [, , wordmarkWidth, wordmarkHeight] = wordmarkViewBox.split(' ').map(Number);

// The compact J is derived from the approved B wordmark, not a separate symbol.

export function BrandMark({ size = 36, color = 'var(--jhw-color-primary)', className }: { size?: number; color?: string; className?: string }) {
  return (
    <svg className={className} viewBox={symbolViewBox} width={size} height={size} fill={color} aria-hidden="true">
      {symbolPaths.map((path) => <path key={path} d={path} />)}
    </svg>
  );
}

export function BrandWordmark({ height = 24, color = 'currentColor', className }: { height?: number; color?: string; className?: string }) {
  return (
    <svg className={className} viewBox={wordmarkViewBox} width={height * wordmarkWidth / wordmarkHeight} height={height} fill={color} aria-hidden="true">
      {wordmarkPaths.map((path) => <path key={path} d={path} />)}
    </svg>
  );
}
