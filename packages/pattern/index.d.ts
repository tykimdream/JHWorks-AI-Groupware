export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
export interface PatternToken {
  name: string;
  value: string;
  group: string;
  description: string;
}
export const tokens: readonly PatternToken[];
export function buttonClass(variant?: ButtonVariant): string;
