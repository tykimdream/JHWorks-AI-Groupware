'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';

import { useDemoConfiguration, type AICapability } from '@/hooks/use-demo-configuration';

export const AICapabilityGate = ({
  capability,
  children,
}: {
  capability: AICapability;
  children: ReactNode;
}) => {
  const { configuration, error } = useDemoConfiguration();
  if (configuration?.aiCapabilities?.[capability]) return children;
  return (
    <section className="form-section" role={error ? 'alert' : 'status'}>
      <p>
        {!configuration && !error
          ? 'AI 사용 설정을 확인하고 있습니다.'
          : error
            ? 'AI 사용 설정을 불러오지 못했습니다. 직접 작성은 계속할 수 있습니다.'
            : '현재 이 AI 기능을 사용할 수 없습니다. 입력 내용을 직접 작성해 업무를 이어갈 수 있습니다.'}
      </p>
      <Link href="/approvals/new">직접 작성하기 →</Link>
    </section>
  );
};
