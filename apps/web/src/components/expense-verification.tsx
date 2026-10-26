import { GuardedLink as Link } from '@/components/navigation-guard';
import type { ApprovalDraftPrepareResponse } from '@/lib/types';

const fields: Record<string, string> = {
  amount: '지출 금액', expense_date: '지출일', merchant: '사용처',
  expense_category: '비용 구분', expense_purpose: '업무 목적', receipt_reference: '증빙 참조',
};
const outcomes: Record<string, string> = {
  INPUT_MATCHED: '입력과 일치', MISSING: '미입력', UNVERIFIED: '입력과 대조되지 않음',
  PASSED: '단계 완료', NEEDS_INPUT: '보완 필요', UNSUPPORTED: '지원하지 않는 요청',
  UNAVAILABLE: '조회 불가', NOT_APPLICABLE: '대상 아님', FAILED: '중단',
};
const stages: Record<string, string> = {
  input: '입력 확인', provider: '모델 요청', normalize: '응답 형식', validate: '필드 검사',
  policy: '규정 조회·검사', preview: '미리보기 준비',
};

export function ExpenseVerification({ result }: { result: ApprovalDraftPrepareResponse }) {
  const grounding = result.grounding;
  if (!grounding || grounding.status === 'NOT_APPLICABLE') return null;
  const policy = result.policyValidation;
  return (
    <section aria-label="경비 초안 검증 결과" className="tw:my-6 tw:border-0 tw:border-t tw:border-solid tw:border-jhw-border tw:pt-5">
      <h3 className="tw:mt-0">초안 검증 결과</h3>
      <p className="tw:max-w-3xl tw:text-sm tw:leading-6 tw:text-jhw-muted">
        원문과 필드값의 대응을 검사합니다. 지출 사실·영수증 진위·규정 전체의 준수를 보증하지 않습니다.
      </p>
      <dl className="tw:grid tw:grid-cols-1 tw:gap-2 tw:sm:grid-cols-2">
        {grounding.checks.map((check) => (
          <div key={check.field} className="tw:flex tw:flex-wrap tw:justify-between tw:gap-2 tw:rounded-lg tw:bg-jhw-canvas tw:p-3 tw:text-sm">
            <dt>{fields[check.field] ?? check.field}</dt>
            <dd className="tw:m-0 tw:font-semibold">{outcomes[check.status]}</dd>
          </div>
        ))}
      </dl>
      {policy && (
        <div className="tw:mt-5">
          <h4>규정 원문과 업무 기준</h4>
          <p className="tw:text-sm tw:leading-6 tw:text-jhw-muted">
            {policy.status === 'CATALOG_CHECKED'
              ? '서버의 현재 활성 규정 원문에서 확인한 기준입니다. 자동 판정하지 않은 항목도 함께 표시합니다.'
              : '적용할 활성 규정을 확인하지 못했습니다. 규정 준수 여부는 확인되지 않았습니다.'}
          </p>
          <ul className="tw:grid tw:list-none tw:gap-3 tw:p-0">
            {policy.checks.map((check) => {
              const citation = policy.citations.find((item) => item.citationKey === check.citationKey);
              return (
                <li key={check.citationKey} className="tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-border tw:pl-3 tw:text-sm tw:leading-6">
                  <strong>{check.outcome === 'ACTION_REQUIRED' ? '추가 확인 필요' : check.outcome === 'NOT_APPLICABLE' ? '이 기준의 대상 아님' : '자동 판정하지 않음'}</strong>
                  <p className="tw:my-1">{check.message}</p>
                  {citation && (
                    <details className="tw:my-1">
                      <summary className="tw:cursor-pointer tw:text-jhw-muted">근거: {citation.sectionTitle} · {citation.version} · {citation.sectionId}</summary>
                      <p className="tw:my-2">{citation.excerpt}</p>
                      <Link href="/policies">규정 전체 보기</Link>
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {result.execution && (
        <details className="tw:mt-4 tw:break-words tw:text-sm">
          <summary className="tw:cursor-pointer">검사 실행 정보</summary>
          <p className="tw:break-all">실행 ID: {result.execution.runId}</p>
          <p>모델: {result.execution.model ?? '정보 없음'} · {result.execution.promptVersion}</p>
          <ol className="tw:pl-5">
            {result.execution.stages.map((stage) => (
              <li key={stage.stage}>{stages[stage.stage] ?? stage.stage}: {outcomes[stage.outcome] ?? stage.outcome}</li>
            ))}
          </ol>
          <p className="tw:text-jhw-muted">단계 완료는 답변 전체의 사실 검증 완료를 뜻하지 않습니다.</p>
        </details>
      )}
    </section>
  );
}
