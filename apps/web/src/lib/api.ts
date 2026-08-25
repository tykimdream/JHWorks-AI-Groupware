const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

interface ErrorBody {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, string> | null;
  };
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, string> | null = null,
  ) {
    super(message);
  }
}

const errorMessages: Record<string, string> = {
  APPROVAL_NOT_READY: '제출에 필요한 정보를 모두 입력해주세요.',
  AI_DRAFT_UNAVAILABLE: 'AI 초안 작성을 사용할 수 없습니다. API 키와 네트워크 상태를 확인해주세요.',
  AI_REVIEW_UNAVAILABLE: 'AI 검토를 사용할 수 없습니다. API 키와 네트워크 상태를 확인해주세요.',
  AUTHENTICATION_REQUIRED: '로그인이 필요합니다.',
  COMMENT_REQUIRED: '반려 사유를 입력해주세요.',
  FORBIDDEN: '이 작업을 수행할 권한이 없습니다.',
  INVALID_STATUS: '현재 상태에서는 이 작업을 수행할 수 없습니다.',
  MANAGER_UNAVAILABLE: '결재자로 지정할 수 있는 직속 관리자가 없습니다.',
  INVALID_CONFIRMATION: '초안 확인 시간이 만료되었습니다. 미리보기를 다시 만들어주세요.',
  PREVIEW_CHANGED: '확인한 미리보기와 저장할 내용이 다릅니다. 미리보기를 다시 만들어주세요.',
  VERSION_CONFLICT: '다른 변경이 먼저 저장되었습니다. 새로고침 후 다시 시도해주세요.',
  WORK_ASSISTANT_UNAVAILABLE: 'AI 업무 조회를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.',
  LEAVE_ASSISTANT_UNAVAILABLE: 'AI 휴가 상담을 사용할 수 없습니다. API 키와 네트워크 상태를 확인해주세요.',
  LEAVE_CANDIDATE_STALE: '선택한 휴가 후보가 더 이상 유효하지 않습니다. 다시 상담해주세요.',
  LEAVE_DRAFT_STALE: '연차·일정·결재자 또는 정책이 변경되었습니다. 미리보기를 다시 만들어주세요.',
  LEAVE_POLICY_UNAVAILABLE: '활성 휴가 정책 근거를 확인할 수 없어 Draft를 준비하지 않았습니다.',
  LEAVE_PREVIEW_CHANGED: '확인한 휴가 미리보기가 변경되었습니다. 다시 준비해주세요.',
  INVALID_LEAVE_CONFIRMATION: '휴가 Draft 확인 시간이 만료되었거나 확인 정보가 올바르지 않습니다.',
};

export const getUserErrorMessage = (error: unknown, fallback: string): string => {
  if (!(error instanceof ApiError)) {
    return fallback;
  }
  return errorMessages[error.code] ?? error.message;
};

export const apiFetch = async <T>(path: string, init: RequestInit = {}): Promise<T> => {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    let body: ErrorBody = {};
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      // The fallback below keeps non-JSON infrastructure errors understandable.
    }
    throw new ApiError(
      response.status,
      body.error?.code ?? 'REQUEST_FAILED',
      body.error?.message ?? '요청을 처리하지 못했습니다.',
      body.error?.details ?? null,
    );
  }

  return (await response.json()) as T;
};
