import type { ComponentPropsWithRef, HTMLAttributes, ReactElement, ReactNode } from 'react';
export function Field(props: {
  id?: string; label: ReactNode; description?: ReactNode; error?: ReactNode;
  required?: boolean; disabled?: boolean; className?: string; children: ReactNode;
}): ReactElement;
export function Input(props: ComponentPropsWithRef<'input'>): ReactElement;
export function Select(props: ComponentPropsWithRef<'select'>): ReactElement;
export function Textarea(props: ComponentPropsWithRef<'textarea'>): ReactElement;
export function Alert(props: HTMLAttributes<HTMLDivElement> & { tone?: 'info' | 'danger' | 'success'; title?: string }): ReactElement;
export function EmptyState(props: HTMLAttributes<HTMLElement> & { title: string; description?: string }): ReactElement;
export function ConfirmationDialog(props: {
  open: boolean; title: string; description: string; confirmLabel: string; cancelLabel?: string;
  busy?: boolean; onCancel: () => void; onConfirm: () => void; children?: ReactNode;
}): ReactElement;
