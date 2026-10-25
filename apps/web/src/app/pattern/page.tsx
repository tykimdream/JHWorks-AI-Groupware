import { publicMetadata } from '@/lib/site-metadata';
import { PatternLibrary } from '@/components/pattern-library';
import './pattern.css';

export const metadata = publicMetadata(
  'JHW Pattern — 토큰과 컴포넌트 사용 가이드',
  'JHWorks에서 사용하는 색상·타이포그래피·컴포넌트와 업무 UX 패턴을 검색하고 사용 예제를 확인하세요.',
  '/pattern',
);
export default function PatternPage() {
  return <PatternLibrary />;
}
