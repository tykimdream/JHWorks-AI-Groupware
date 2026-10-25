import type { Metadata } from 'next';
import { PatternLibrary } from '@/components/pattern-library';
import './pattern.css';

export const metadata: Metadata = {
  title: 'JHW Pattern — JHWorks 디자인 시스템',
  description: 'JHWorks에서 실제로 사용하는 토큰, 컴포넌트와 업무 UX 패턴의 사용법',
};
export default function PatternPage() {
  return <PatternLibrary />;
}
