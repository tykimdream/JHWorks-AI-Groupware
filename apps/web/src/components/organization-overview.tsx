'use client';

import { useQuery } from '@tanstack/react-query';
import { Button } from '@jhworks/pattern/react';
import { useWorkspaceEmployee } from '@/components/app-shell';
import { GuardedLink as Link } from '@/components/navigation-guard';
import { useSessionScope } from '@/components/session-data-provider';
import { useDemoConfiguration } from '@/hooks/use-demo-configuration';
import { apiFetch, getUserErrorMessage } from '@/lib/api';
import type { Department } from '@/lib/types';

export function OrganizationOverview() {
  const employee = useWorkspaceEmployee();
  const { epoch } = useSessionScope();
  const { configuration } = useDemoConfiguration();
  const query = useQuery({
    queryKey: ['session', epoch, 'departments'],
    queryFn: ({ signal }) => apiFetch<Department[]>('/departments', { signal }),
  });
  if (!employee) return null;
  return (
    <div className="tw:grid tw:gap-6">
      <section
        aria-labelledby="my-organization"
        className="tw:rounded-xl tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:p-6"
      >
        <h2 id="my-organization" className="tw:mt-0 tw:text-xl">
          내 업무 관계
        </h2>
        <div className="tw:grid tw:gap-6 tw:md:grid-cols-2">
          <div>
            <span className="small-pill">내 프로필</span>
            <h3 className="tw:mb-1">{employee.name}</h3>
            <p className="tw:my-1">
              {employee.department.name} · {employee.position}
            </p>
            <p className="tw:break-all tw:text-sm tw:text-jhw-muted">
              {employee.email}
            </p>
          </div>
          <div className="tw:border-0 tw:border-l-2 tw:border-solid tw:border-jhw-border tw:pl-5">
            <span className="small-pill">직속 관리자</span>
            <h3 className="tw:mb-1">
              {employee.manager?.name ?? '지정된 직속 관리자 없음'}
            </h3>
            <p className="tw:my-1">
              {employee.manager?.position ??
                '현재 계정에 연결된 관리자가 없습니다.'}
            </p>
            <p className="tw:text-sm tw:leading-6 tw:text-jhw-muted">
              {employee.manager
                ? '결재를 제출하면 지정된 관리자에게 검토 요청이 전달됩니다.'
                : '새 결재의 제출 가능 여부는 서버에서 확인합니다.'}
            </p>
          </div>
        </div>
        <Link className="secondary-button" href="/approvals">
          내 결재 확인
        </Link>
      </section>
      <section
        aria-labelledby="departments-title"
        className="tw:rounded-xl tw:border tw:border-solid tw:border-jhw-border tw:bg-jhw-surface tw:p-6"
      >
        <h2 id="departments-title" className="tw:mt-0 tw:text-xl">
          조회 가능한 부서
        </h2>
        <p className="tw:text-sm tw:leading-6 tw:text-jhw-muted">
          {configuration?.enabled
            ? '현재 방문 공간에 속한 부서만 표시합니다. 역할을 바꿔도 다른 방문자의 조직 정보는 보이지 않습니다.'
            : '현재 계정에 허용된 활성 부서를 표시합니다.'}
        </p>
        {query.isPending ? (
          <p role="status">부서를 불러오고 있습니다.</p>
        ) : query.isError ? (
          <div role="alert">
            <p>
              {getUserErrorMessage(
                query.error,
                '부서 목록을 불러오지 못했습니다.',
              )}
            </p>
            <Button variant="secondary" onClick={() => void query.refetch()}>
              부서 다시 불러오기
            </Button>
          </div>
        ) : query.data.length ? (
          <ul className="tw:m-0 tw:grid tw:list-none tw:gap-3 tw:p-0">
            {query.data.map((department) => (
              <li
                key={department.id}
                className="tw:flex tw:items-center tw:justify-between tw:gap-4 tw:rounded-lg tw:bg-jhw-canvas tw:p-4"
              >
                <strong>{department.name}</strong>
                {department.id === employee.departmentId && (
                  <span className="small-pill">내 부서</span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p role="status">조회 가능한 부서가 없습니다.</p>
        )}
      </section>
      <p className="tw:text-sm tw:text-jhw-muted">
        가상 조직의 조회 화면입니다. 직원 추가·인사 관리 기능은 제공하지
        않습니다.
      </p>
    </div>
  );
}
