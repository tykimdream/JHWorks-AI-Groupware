export function RejectionContext({ comment }: { comment: string | null }) {
  if (!comment) return null;
  return <section aria-label="최근 반려 의견" className="tw:my-5 tw:rounded-lg tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-canvas tw:p-5">
    <h2 className="tw:m-0 tw:text-base">최근 반려 의견</h2>
    <blockquote className="tw:mx-0 tw:my-3 tw:whitespace-pre-wrap tw:break-words tw:text-jhw-text">{comment}</blockquote>
    <p className="tw:m-0 tw:text-sm tw:text-jhw-muted">결재자가 남긴 원문입니다. 요청한 보완 사항을 확인하고 직접 수정해주세요.</p>
  </section>;
}
