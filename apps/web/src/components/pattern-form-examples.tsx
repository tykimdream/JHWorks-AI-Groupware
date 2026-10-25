'use client';

import { useState } from 'react';
import { Alert, Button, ConfirmationDialog, EmptyState, Field, Input, Select, Textarea } from '@jhworks/pattern/react';

export function PatternFormExample() {
  const [amount, setAmount] = useState('');
  const [invalid, setInvalid] = useState(false);
  return <div className="tw:grid tw:w-full tw:max-w-xl tw:gap-5">
    <Field label="실제 지출 금액" description="이미 지출한 금액을 원 단위로 입력합니다." error={invalid ? '0원보다 큰 금액을 입력해주세요.' : undefined} required>
      <Input type="number" min="1" value={amount} onChange={(event) => { setAmount(event.target.value); setInvalid(false); }} />
    </Field>
    <Field label="비용 구분"><Select defaultValue=""><option value="">선택해주세요</option><option value="TRANSPORTATION">교통비</option><option value="MEALS">식비</option></Select></Field>
    <Field label="업무 목적"><Textarea rows={3} placeholder="예: CES 고객 미팅 참석을 위한 이동" /></Field>
    <Button variant="secondary" onClick={() => setInvalid(!amount || Number(amount) <= 0)}>입력 조건 확인</Button>
  </div>;
}

export function PatternAlertExample() {
  const [recovered, setRecovered] = useState(false);
  return <div className="tw:grid tw:w-full tw:gap-4">
    <Alert tone="info" title="아직 제출하지 않았습니다">초안을 확인한 뒤 별도로 제출해주세요.</Alert>
    {recovered ? <Alert tone="success">예제 재시도가 완료됐습니다. 업무 API를 호출하지 않습니다.</Alert>
      : <Alert tone="danger" title="초안을 저장하지 못했습니다">입력은 유지했습니다. 연결을 확인한 뒤 다시 시도해주세요. <Button variant="secondary" onClick={() => setRecovered(true)}>예제 다시 시도</Button></Alert>}
  </div>;
}

export function PatternEmptyExample() {
  return <EmptyState title="작성한 결재가 없습니다." description="첫 초안을 작성해 업무 흐름을 시작해보세요." />;
}

export function PatternDialogExample() {
  const [open, setOpen] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  return <>
    <Button variant="secondary" onClick={() => setOpen(true)}>확인 창 예제 열기</Button>
    <ConfirmationDialog open={open} title="예제 초안을 제출할까요?" description="확인 동작만 살펴보는 합성 예제입니다. 실제 결재나 API 호출은 없습니다." confirmLabel="예제 확인" onCancel={() => setOpen(false)} onConfirm={() => { setOpen(false); setConfirmed(true); }}>
      <p>CES 합성 경비 · 170,000원 · v1</p>
    </ConfirmationDialog>
    {confirmed && <Alert tone="success">예제 확인을 완료했습니다. 업무 데이터는 변경되지 않았습니다.</Alert>}
  </>;
}
