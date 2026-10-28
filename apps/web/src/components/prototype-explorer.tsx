'use client';

import { useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Field, Input } from '@jhworks/pattern/react';
import { GuardedLink as Link } from '@/components/navigation-guard';
import { useWorkspaceEmployee } from '@/components/app-shell';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { storeManualDraft } from '@/lib/manual-draft-handoff';

const journeys = [
  {
    title: '경비 정산과 결재',
    description:
      '지출 내용 작성 → 누락 점검 → 제출 → 결재자로 역할 전환 → 승인·반려',
    href: '/approvals/new?type=EXPENSE',
    action: '경비 직접 작성',
  },
  {
    title: '휴가와 팀 일정',
    description: '잔여 연차 확인 → 팀 일정 비교 → 날짜 선택 → 휴가 결재 작성',
    href: '/attendance',
    action: '휴가 일정 확인',
  },
  {
    title: '회사 규정과 내 조직',
    description: '정책 원문·버전 확인 → 소속 부서·관리자 확인 → 관련 결재 작성',
    href: '/policies',
    action: '회사 규정 살펴보기',
  },
];

export function PrototypeExplorer() {
  const employee = useWorkspaceEmployee();
  const { configuration } = useDemoConfiguration();
  const router = useRouter();
  const [step, setStep] = useState<'request' | 'questions' | 'preview'>(
    'request',
  );
  const [date, setDate] = useState('');
  const [merchant, setMerchant] = useState('');
  const [receipt, setReceipt] = useState('');
  const [error, setError] = useState<string | null>(null);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  const dateInput = useRef<HTMLInputElement>(null);
  const latestDate = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Seoul',
  }).format(new Date());
  const purpose = '코엑스 전시회 출장 교통비 정산';
  function prepare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!merchant.trim() || !date || date > latestDate) {
      setError(
        '실제 지출일과 사용처를 입력해 주세요. 미래 날짜는 사용할 수 없습니다.',
      );
      return;
    }
    setError(null);
    setStep('preview');
    requestAnimationFrame(() => previewHeading.current?.focus());
  }
  function continueDraft() {
    if (!employee) return;
    const stored = storeManualDraft(employee.id, {
      type: 'EXPENSE',
      content: `${purpose}\n지출일: ${date}\n사용처: ${merchant.trim()}\n금액: 170,000원\n${receipt.trim() ? `증빙 참조: ${receipt.trim()}` : '증빙 참조는 아직 입력하지 않았습니다.'}`,
      expensePreset: {
        title: '코엑스 전시회 출장 교통비 정산',
        amount: 170000,
        details: {
          kind: 'EXPENSE',
          expenseDate: date,
          merchant: merchant.trim(),
          category: 'TRANSPORTATION',
          purpose,
          receiptReference: receipt.trim() || null,
        },
      },
    });
    if (!stored) {
      setError(
        '입력 내용을 옮기지 못했습니다. 이 화면의 내용을 복사하거나 브라우저 저장 설정을 확인해 주세요.',
      );
      return;
    }
    router.push('/approvals/new?handoff=manual');
  }
  return (
    <div className="tw:grid tw:gap-8">
      <section
        aria-labelledby="prototype-title"
        className="tw:min-w-0 tw:overflow-hidden tw:rounded-xl tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-surface"
      >
        <header className="tw:border-0 tw:border-b tw:border-solid tw:border-jhw-border tw:p-5 tw:md:p-7">
          <span className="small-pill">예시 체험 · 실제 AI 호출 없음</span>
          <h2 id="prototype-title" className="tw:mt-4 tw:mb-2 tw:text-2xl">
            한 문장에서 경비 양식까지
          </h2>
          <p className="tw:m-0 tw:max-w-2xl tw:text-sm tw:leading-7 tw:text-jhw-muted">
            정해진 전시회 출장 경비 사례로 ‘요청 → 부족한 정보 확인 → 미리보기’를
            체험합니다. 질문과 금액은 고정된 예시이며, 입력한 정보만 양식에
            옮깁니다.
          </p>
        </header>
        <div className="tw:grid tw:md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="tw:min-w-0 tw:bg-jhw-canvas tw:p-5 tw:md:p-7">
            <h3 className="tw:mt-0 tw:text-base">업무 요청</h3>
            <blockquote className="tw:mx-0 tw:my-4 tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-primary tw:pl-4 tw:text-lg tw:leading-8">
              “코엑스 전시회 출장 교통비 17만원 쓴 거, 경비 결재 준비해줘.”
            </blockquote>
            <dl className="tw:grid tw:grid-cols-[80px_minmax(0,1fr)] tw:gap-x-3 tw:gap-y-4 tw:text-sm">
              <dt className="tw:text-jhw-muted">요청의 금액</dt>
              <dd className="tw:m-0 tw:font-semibold">170,000원</dd>
              <dt className="tw:text-jhw-muted">업무 유형</dt>
              <dd className="tw:m-0">경비 정산 · 교통비</dd>
              <dt className="tw:text-jhw-muted">확인할 정보</dt>
              <dd className="tw:m-0">지출일, 사용처, 증빙 참조</dd>
            </dl>
            <p className="tw:mt-6 tw:text-sm tw:leading-7 tw:text-jhw-muted">
              사용처나 날짜를 임의로 채우지 않습니다. 규정 적용 여부와 중복
              후보는 문서를 저장한 뒤 실제 사전 점검에서 확인합니다.
            </p>
            <Link href="/policies">경비 규정 원문 확인</Link>
            {configuration?.aiCapabilities?.approvalDraft && (
              <p className="tw:mt-5">
                <Link href="/approvals/ai-draft">
                  내 요청으로 실제 AI 초안 작성
                </Link>
              </p>
            )}
          </div>
          <div className="tw:min-w-0 tw:p-5 tw:md:p-7">
            <ol
              aria-label="예시 체험 진행"
              className="tw:mb-6 tw:flex tw:list-none tw:flex-wrap tw:gap-4 tw:p-0 tw:text-sm tw:text-jhw-muted"
            >
              {['요청', '정보 보완', '미리보기'].map((label, index) => (
                <li
                  key={label}
                  aria-current={
                    index === ['request', 'questions', 'preview'].indexOf(step)
                      ? 'step'
                      : undefined
                  }
                  className={
                    index === ['request', 'questions', 'preview'].indexOf(step)
                      ? 'tw:font-semibold tw:text-jhw-primary'
                      : ''
                  }
                >
                  {index + 1}. {label}
                </li>
              ))}
            </ol>
            {step === 'request' ? (
              <div>
                <h3 className="tw:mt-0">아직 모르는 정보부터 확인해요</h3>
                <p className="tw:text-sm tw:leading-7 tw:text-jhw-muted">
                  금액과 목적은 알지만 언제, 어디서 사용했는지는 알 수 없습니다.
                  질문을 확인하고 직접 답해 보세요.
                </p>
                <Button
                  onClick={() => {
                    setStep('questions');
                    requestAnimationFrame(() => dateInput.current?.focus());
                  }}
                >
                  빠진 정보 확인
                </Button>
              </div>
            ) : step === 'questions' ? (
              <form onSubmit={prepare} className="tw:grid tw:gap-5">
                <h3 className="tw:my-0">언제, 어디서 사용했나요?</h3>
                <Field id="prototype-date" label="실제 지출일">
                  <Input
                    ref={dateInput}
                    id="prototype-date"
                    type="date"
                    required
                    max={latestDate}
                    value={date}
                    onChange={(event) => setDate(event.target.value)}
                  />
                </Field>
                <Field id="prototype-merchant" label="사용처">
                  <Input
                    id="prototype-merchant"
                    required
                    maxLength={200}
                    value={merchant}
                    onChange={(event) => setMerchant(event.target.value)}
                    placeholder="예: 가상 교통 서비스"
                  />
                </Field>
                <Field id="prototype-receipt" label="증빙 참조 (선택)">
                  <Input
                    id="prototype-receipt"
                    maxLength={200}
                    value={receipt}
                    onChange={(event) => setReceipt(event.target.value)}
                    placeholder="예: DEMO-RECEIPT-001"
                  />
                </Field>
                <p className="tw:my-0 tw:text-sm tw:leading-6 tw:text-jhw-muted">
                  가상 정보로 체험하세요. 영수증 파일은 업로드하지 않습니다.
                </p>
                <div>
                  <Button type="submit">미리보기 확인</Button>
                </div>
              </form>
            ) : (
              <div>
                <h3 ref={previewHeading} tabIndex={-1} className="tw:mt-0">
                  작성할 경비 내용
                </h3>
                <dl className="tw:grid tw:grid-cols-[72px_minmax(0,1fr)] tw:gap-x-4 tw:gap-y-4 tw:text-sm tw:leading-6">
                  <dt className="tw:text-jhw-muted">제목</dt>
                  <dd className="tw:m-0">코엑스 전시회 출장 교통비 정산</dd>
                  <dt className="tw:text-jhw-muted">지출일</dt>
                  <dd className="tw:m-0">{date}</dd>
                  <dt className="tw:text-jhw-muted">사용처</dt>
                  <dd className="tw:m-0 tw:break-words">{merchant}</dd>
                  <dt className="tw:text-jhw-muted">금액</dt>
                  <dd className="tw:m-0 tw:text-lg tw:font-semibold">
                    170,000원
                  </dd>
                  <dt className="tw:text-jhw-muted">증빙 참조</dt>
                  <dd className="tw:m-0 tw:break-words">
                    {receipt.trim() || '미입력 · 작성 화면에서 보완 가능'}
                  </dd>
                  <dt className="tw:text-jhw-muted">결재자</dt>
                  <dd className="tw:m-0">
                    {employee?.manager?.name ?? '현재 계정의 직속 관리자 없음'}
                  </dd>
                </dl>
                <p className="tw:my-5 tw:text-sm tw:leading-6 tw:text-jhw-muted">
                  아직 저장되지 않았습니다. 다음 화면에서 내용을 수정하고 ‘초안
                  저장’을 눌러야 문서가 만들어집니다.
                </p>
                <div className="tw:flex tw:flex-wrap tw:gap-3">
                  <Button onClick={continueDraft} disabled={!employee?.manager}>
                    이 내용으로 결재 작성
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setStep('questions');
                      setError(null);
                      requestAnimationFrame(() => dateInput.current?.focus());
                    }}
                  >
                    입력 수정
                  </Button>
                </div>
                {!employee?.manager && (
                  <p className="tw:text-sm tw:leading-6">
                    작성자로 역할을 바꾼 뒤 경비 작성을 체험해 주세요.
                  </p>
                )}
              </div>
            )}
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
          </div>
        </div>
      </section>
      <section aria-labelledby="journeys-title">
        <div className="tw:mb-5 tw:flex tw:flex-wrap tw:items-center tw:justify-between tw:gap-3">
          <h2 id="journeys-title" className="tw:m-0 tw:text-xl">
            직접 해볼 세 가지 업무
          </h2>
          <span className="small-pill">
            {configuration?.enabled
              ? `${configuration.durationMinutes}분 · 내 방문 공간`
              : '가상 회사 업무 체험'}
          </span>
        </div>
        <ul className="tw:m-0 tw:grid tw:list-none tw:gap-0 tw:rounded-xl tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:p-0">
          {journeys.map((journey, index) => (
            <li
              key={journey.href}
              className={`tw:grid tw:gap-3 tw:p-5 tw:md:grid-cols-[minmax(0,1fr)_auto] tw:md:items-center ${index ? 'tw:border-0 tw:border-t tw:border-solid tw:border-jhw-border' : ''}`}
            >
              <div>
                <h3 className="tw:m-0 tw:text-base">{journey.title}</h3>
                <p className="tw:mt-2 tw:mb-0 tw:text-sm tw:leading-6 tw:text-jhw-muted">
                  {journey.description}
                </p>
              </div>
              <Link className="secondary-button" href={journey.href}>
                {journey.action}
              </Link>
            </li>
          ))}
        </ul>
        <p className="tw:mb-0 tw:text-sm tw:leading-6 tw:text-jhw-muted">
          저장·제출·승인은 각각 직접 확인합니다. 제출 후 메뉴의 ‘결재자로
          체험하기’로 역할을 바꿔 결과까지 확인해 보세요.
        </p>
      </section>

      <div className="tw:flex tw:flex-wrap tw:gap-4 tw:text-sm">
        <Link href="/organization">내 부서와 관리자 확인</Link>
        <Link href="/approvals">내 결재 목록</Link>
        <Link href="/feedback">체험 의견 남기기</Link>
      </div>
    </div>
  );
}
