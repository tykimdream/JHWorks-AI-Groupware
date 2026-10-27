'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, Field, Input, Select } from '@jhworks/pattern/react';
import { GuardedLink as Link } from '@/components/navigation-guard';
import { useSessionScope } from '@/components/session-data-provider';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type { CompanyPolicy } from '@/lib/types';

const keywords: Record<string, string[]> = {
  영수증: ['receipt'],
  증빙: ['receipt'],
  숙박: ['hotel', 'lodging', 'accommodation'],
  연차: ['annual leave'],
  휴가: ['leave'],
  교통: ['transport'],
  식비: ['meal'],
  사전승인: ['prior approval'],
};
const labels = {
  TRAVEL: '출장',
  EXPENSE: '경비',
  LEAVE: '휴가',
  APPROVAL: '결재',
  SECURITY: '보안',
};

export function PolicyLibrary() {
  const { epoch } = useSessionScope();
  const [search, setSearch] = useState('');
  const [type, setType] = useState('ALL');
  const query = useQuery({
    queryKey: ['session', epoch, 'policies'],
    queryFn: ({ signal }) => apiFetch<CompanyPolicy[]>('/policies', { signal }),
  });
  const term = search.trim().toLocaleLowerCase('ko-KR');
  const words = term.split(/\s+/).map((word) => word.replace(/(관련|에​?대해|에서|으로|에는|은|는|이|가|을|를|의|에)$/g, '')).filter((word) => word.length >= 2);
  const terms = [...new Set([...words, ...Object.entries(keywords).filter(([key]) => term.includes(key)).flatMap(([key, aliases]) => [key, ...aliases])])];
  const policies = (query.data ?? []).filter(
    (policy) => type === 'ALL' || policy.type === type,
  );
  const visible = policies
    .map((policy) => ({
      ...policy,
      sections: [...policy.sections]
        .sort((a, b) => a.order - b.order)
        .filter(
          (section) =>
            !term ||
            terms.some((word) =>
              `${policy.title} ${section.title} ${section.content} ${section.sectionId}`
                .toLocaleLowerCase('ko-KR')
                .includes(word),
            ),
        ),
    }))
    .filter((policy) => policy.sections.length > 0);
  return (
    <div className="tw:grid tw:gap-6">
      <div className="tw:grid tw:gap-4 tw:rounded-xl tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:p-5 tw:md:grid-cols-[minmax(0,1fr)_180px]">
        <Field id="policy-search" label="규정 검색">
          <Input
            id="policy-search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="예: 증빙, 숙박, 연차"
            maxLength={100}
          />
        </Field>
        <Field id="policy-type" label="업무 분류">
          <Select
            id="policy-type"
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            <option value="ALL">전체 규정</option>
            {Object.entries(labels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {query.isPending ? (
        <p role="status">회사 규정을 불러오고 있습니다.</p>
      ) : query.isError ? (
        <div role="alert">
          <p>
            {getUserErrorMessage(
              query.error,
              '규정을 불러오지 못했습니다. 다시 시도해 주세요.',
            )}
          </p>
          <Button variant="secondary" onClick={() => void query.refetch()}>
            규정 다시 불러오기
          </Button>
        </div>
      ) : (
        <>
          <p role="status" className="tw:m-0 tw:text-sm tw:text-jhw-muted">
            {visible.length}개 규정 ·{' '}
            {visible.reduce((sum, policy) => sum + policy.sections.length, 0)}개
            항목{term && ' 검색됨'}
          </p>
          {!visible.length && (
            <section className="form-section">
              <h2>
                {query.data?.length
                  ? '일치하는 규정이 없습니다'
                  : '등록된 활성 규정이 없습니다'}
              </h2>
              <p>검색어를 줄이거나 다른 업무 분류를 선택해 주세요.</p>
              <Button
                variant="secondary"
                onClick={() => {
                  setSearch('');
                  setType('ALL');
                }}
              >
                검색 초기화
              </Button>
            </section>
          )}
          {visible.map((policy) => (
            <article
              key={policy.id}
              className="tw:min-w-0 tw:rounded-xl tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:p-5 tw:md:p-7"
            >
              <header className="tw:mb-5 tw:flex tw:flex-wrap tw:items-start tw:justify-between tw:gap-3">
                <div>
                  <span className="small-pill">{labels[policy.type]}</span>
                  <h2 className="tw:mt-3 tw:mb-1 tw:text-xl">{policy.title}</h2>
                  <p className="tw:m-0 tw:text-sm tw:text-jhw-muted">
                    버전 {policy.version} · 시행일 {policy.effectiveFrom}
                  </p>
                </div>
                {['EXPENSE', 'TRAVEL', 'LEAVE'].includes(policy.type) && (
                  <Link
                    className="secondary-button"
                    href={
                      policy.type === 'LEAVE'
                        ? '/attendance'
                        : `/approvals/new${policy.type === 'EXPENSE' ? '?type=EXPENSE' : ''}`
                    }
                  >
                    {policy.type === 'LEAVE'
                      ? '휴가 일정 확인'
                      : '관련 결재 작성'}
                  </Link>
                )}
              </header>
              <div className="tw:grid tw:gap-3">
                {policy.sections.map((section) => (
                  <details
                    key={section.sectionId}
                    id={`policy-${policy.id}-${section.sectionId}`}
                    open={term ? true : undefined}
                    className="tw:rounded-lg tw:border tw:border-solid tw:border-jhw-border tw:px-4 tw:py-3 tw:open:bg-jhw-canvas"
                  >
                    <summary className="tw:cursor-pointer tw:leading-6 tw:font-semibold">
                      <span className="tw:mr-2 tw:text-sm tw:font-normal tw:text-jhw-muted">
                        {section.sectionId}
                      </span>
                      {section.title}
                    </summary>
                    <p className="tw:mb-1 tw:whitespace-pre-wrap tw:break-words tw:text-sm tw:leading-7">
                      {section.content}
                    </p>
                  </details>
                ))}
              </div>
            </article>
          ))}
        </>
      )}
      <p className="tw:text-sm tw:leading-6 tw:text-jhw-muted">
        데모를 위해 만든 가상 회사 규정입니다. 검색은 제목·본문의 단어를 찾으며
        AI를 호출하지 않습니다.
      </p>
    </div>
  );
}
