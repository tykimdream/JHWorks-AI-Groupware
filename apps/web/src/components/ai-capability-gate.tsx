'use client';

import { GuardedLink as Link } from '@/components/navigation-guard';
import type { ReactNode } from 'react';

import { useDemoConfiguration, type AICapability } from '@/hooks/use-demo-configuration';

const alternatives: Record<AICapability, { title: string; description: string; href: string; action: string }> = {
  approvalDraft: {
    title: '경비 예시부터 시작해 보세요',
    description: '날짜와 사용처를 입력해 미리보기를 확인한 뒤 결재 양식으로 옮길 수 있습니다. 예시는 실제 AI를 호출하지 않습니다.',
    href: '/explore',
    action: '경비 예시 체험하기',
  },
  leaveAssistant: {
    title: '연차와 팀 일정으로 휴가 날짜를 찾아보세요',
    description: '아래에서 기간과 사용할 연차를 선택하면 일정 충돌을 확인해 신청 후보를 보여줍니다.',
    href: '#manual-leave-search',
    action: '휴가 후보 찾아보기',
  },
  workAssistant: {
    title: '찾으려는 업무를 선택하세요',
    description: '업무 체험 안내에서 결재, 휴가 일정, 회사 규정을 확인할 수 있습니다.',
    href: '/explore',
    action: '업무 체험 안내 보기',
  },
  approvalReview: {
    title: '결재 내용을 직접 확인하세요',
    description: '결재 목록에서 문서를 열어 지출 내용과 처리 이력을 확인할 수 있습니다.',
    href: '/approvals',
    action: '결재 목록 보기',
  },
  policyEmbedding: {
    title: '규정 원문에서 확인하세요',
    description: '업무 분류와 검색어로 회사 규정의 원문과 시행일을 확인할 수 있습니다.',
    href: '/policies',
    action: '회사 규정 보기',
  },
};

export const AICapabilityGate = ({
  capability,
  children,
}: {
  capability: AICapability;
  children: ReactNode;
}) => {
  const { configuration, error } = useDemoConfiguration();
  if (configuration?.aiCapabilities?.[capability]) return children;
  const alternative = alternatives[capability];
  return (
    <section className="tw:mb-6 tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-border tw:py-1 tw:pl-4" aria-label="AI 사용 안내">
      {error ? (
        <p className="tw:mt-0 tw:text-sm" role="alert">AI 사용 설정을 불러오지 못했습니다. 아래 방법으로 업무를 계속할 수 있습니다.</p>
      ) : !configuration ? (
        <p className="tw:mt-0 tw:text-sm" role="status">AI 사용 설정을 확인하고 있습니다.</p>
      ) : (
        <p className="tw:mt-0 tw:mb-2 tw:text-sm tw:text-jhw-muted">이 환경에서는 해당 AI 기능을 사용하지 않습니다.</p>
      )}
      <h2 className="tw:mt-0 tw:mb-1 tw:text-lg">{alternative.title}</h2>
      <p className="tw:mt-0 tw:mb-3 tw:max-w-3xl tw:text-sm tw:leading-6">{alternative.description}</p>
      <div className="tw:flex tw:flex-wrap tw:gap-3">
        {alternative.href.startsWith('#') ? (
          <a className="secondary-button" href={alternative.href}>{alternative.action}</a>
        ) : (
          <Link className="secondary-button" href={alternative.href}>{alternative.action}</Link>
        )}
        {capability === 'approvalDraft' && (
          <Link className="secondary-button" href="/approvals/new">결재 직접 작성하기</Link>
        )}
      </div>
    </section>
  );
};
