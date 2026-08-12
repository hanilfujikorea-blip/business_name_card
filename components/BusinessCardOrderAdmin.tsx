import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BusinessCardOrderRecord,
  BusinessCardSettings,
  getBusinessCardSettings,
  listBusinessCardOrders,
  processBusinessCardOrder,
  saveBusinessCardSettings,
} from '../services/businessCardOrderService';

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  pending_approval: { label: '승인 대기', className: 'bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300' },
  approved: { label: '승인됨', className: 'bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-300' },
  sending: { label: '발송 중', className: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300' },
  sent: { label: '발송 완료', className: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300' },
  send_failed: { label: '발송 실패', className: 'bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300' },
  rejected: { label: '반려', className: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200' },
  cancelled: { label: '신청 취소', className: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200' },
};

const formatDate = (value?: string) => value ? new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
}).format(new Date(value)) : '-';

const parseCardData = (order: BusinessCardOrderRecord): Record<string, string> => {
  try {
    return typeof order.card_data === 'string' ? JSON.parse(order.card_data || '{}') : order.card_data || {};
  } catch {
    return {};
  }
};

const BusinessCardOrderAdmin: React.FC = () => {
  const [orders, setOrders] = useState<BusinessCardOrderRecord[]>([]);
  const [settings, setSettings] = useState<BusinessCardSettings>({ sendMode: 'semi_automatic', recipientEmail: '', mailConfigured: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [processingId, setProcessingId] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [companyFilter, setCompanyFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [nextSettings, nextOrders] = await Promise.all([getBusinessCardSettings(), listBusinessCardOrders()]);
      setSettings(nextSettings);
      setOrders(nextOrders);
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : '대시보드를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const stats = useMemo(() => ({
    total: orders.length,
    pending: orders.filter(order => order.status === 'pending_approval').length,
    sent: orders.filter(order => order.status === 'sent').length,
    failed: orders.filter(order => order.status === 'send_failed').length,
  }), [orders]);

  const filteredOrders = useMemo(() => {
    const keyword = searchTerm.trim().toLocaleLowerCase('ko-KR');
    return orders.filter(order => {
      const cardData = parseCardData(order);
      const matchesKeyword = !keyword || [
        order.id,
        order.requester_name,
        order.requester_department,
        cardData.companyKo,
        cardData.departmentKo,
        cardData.email,
        cardData.mobilePhone,
      ].some(value => String(value || '').toLocaleLowerCase('ko-KR').includes(keyword));
      const matchesCompany = !companyFilter || cardData.companyKo === companyFilter;
      const matchesStatus = !statusFilter || order.status === statusFilter;
      return matchesKeyword && matchesCompany && matchesStatus;
    });
  }, [companyFilter, orders, searchTerm, statusFilter]);

  const handleSaveSettings = async () => {
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const saved = await saveBusinessCardSettings(settings);
      setSettings(saved);
      setMessage('발송 설정을 저장했습니다.');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '설정을 저장하지 못했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (order: BusinessCardOrderRecord, action: 'approve' | 'retry' | 'reject') => {
    let reason = '';
    if (action === 'reject') {
      reason = window.prompt('반려 사유를 입력해 주세요.')?.trim() || '';
      if (!reason) return;
    }
    setProcessingId(order.id);
    setMessage('');
    setError('');
    try {
      await processBusinessCardOrder(order.id, action, reason);
      setMessage(action === 'reject' ? '신청을 반려했습니다.' : '발송 처리를 완료했습니다.');
      await refresh();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '요청을 처리하지 못했습니다.');
      await refresh();
    } finally {
      setProcessingId('');
    }
  };

  return (
    <section className="min-h-full bg-slate-100 px-4 py-6 dark:bg-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">시스템 관리</p>
          <div className="mt-1 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-black text-slate-900 dark:text-white">명함발주 관리</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">직원 신청 이력과 승인·발송 상태를 관리합니다.</p>
            </div>
            <button type="button" onClick={refresh} disabled={loading} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800">
              {loading ? '새로고침 중…' : '새로고침'}
            </button>
          </div>
        </header>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[['전체 신청', stats.total], ['승인 대기', stats.pending], ['발송 완료', stats.sent], ['발송 실패', stats.failed]].map(([label, count]) => (
            <div key={String(label)} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-bold text-slate-500 dark:text-slate-400">{label}</p>
              <p className="mt-2 text-3xl font-black text-slate-900 dark:text-white">{count}</p>
            </div>
          ))}
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="grid gap-3 lg:grid-cols-[minmax(260px,1fr)_240px_220px_auto]">
            <label>
              <span className="mb-1.5 block text-xs font-bold text-slate-600 dark:text-slate-300">신청 검색</span>
              <input type="search" value={searchTerm} onChange={event => setSearchTerm(event.target.value)} placeholder="이름, 신청번호, 부서, 이메일, 전화번호" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 dark:border-slate-700 dark:bg-slate-950 dark:text-white" />
            </label>
            <label>
              <span className="mb-1.5 block text-xs font-bold text-slate-600 dark:text-slate-300">회사</span>
              <select value={companyFilter} onChange={event => setCompanyFilter(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 dark:border-slate-700 dark:bg-slate-950 dark:text-white">
                <option value="">전체 회사</option>
                <option value="한일후지코리아(주)">한일후지코리아(주)</option>
                <option value="(주)후지글로벌로지스틱">(주)후지글로벌로지스틱</option>
              </select>
            </label>
            <label>
              <span className="mb-1.5 block text-xs font-bold text-slate-600 dark:text-slate-300">상태</span>
              <select value={statusFilter} onChange={event => setStatusFilter(event.target.value)} className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 dark:border-slate-700 dark:bg-slate-950 dark:text-white">
                <option value="">전체 상태</option>
                {Object.entries(STATUS_LABELS).map(([value, meta]) => <option key={value} value={value}>{meta.label}</option>)}
              </select>
            </label>
            <button type="button" onClick={() => { setSearchTerm(''); setCompanyFilter(''); setStatusFilter(''); }} disabled={!searchTerm && !companyFilter && !statusFilter} className="self-end rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-50 disabled:cursor-default disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">필터 초기화</button>
          </div>
          <p className="mt-3 text-xs font-bold text-slate-500 dark:text-slate-400">검색 결과 {filteredOrders.length}건 · 전체 {orders.length}건</p>
        </section>

        <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 xl:sticky xl:top-6 xl:self-start">
            <h3 className="font-black text-slate-900 dark:text-white">기본 발송 설정</h3>
            <div className="mt-5 space-y-5">
              <div>
                <span className="mb-2 block text-xs font-bold text-slate-600 dark:text-slate-300">발송 방식</span>
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" onClick={() => setSettings(previous => ({ ...previous, sendMode: 'semi_automatic' }))} className={`rounded-xl border px-3 py-3 text-sm font-black ${settings.sendMode === 'semi_automatic' ? 'border-emerald-600 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' : 'border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300'}`}>반자동</button>
                  <button type="button" onClick={() => setSettings(previous => ({ ...previous, sendMode: 'automatic' }))} className={`rounded-xl border px-3 py-3 text-sm font-black ${settings.sendMode === 'automatic' ? 'border-red-500 bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300' : 'border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300'}`}>자동</button>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-500 dark:text-slate-400">{settings.sendMode === 'automatic' ? '직원 확정 즉시 지정 메일로 발송합니다.' : '관리자가 시안을 확인하고 승인한 뒤 발송합니다.'}</p>
              </div>
              <label>
                <span className="mb-1.5 block text-xs font-bold text-slate-600 dark:text-slate-300">발주 수신 이메일</span>
                <input type="email" value={settings.recipientEmail || ''} onChange={event => setSettings(previous => ({ ...previous, recipientEmail: event.target.value }))} placeholder="vendor@example.com" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 dark:border-slate-700 dark:bg-slate-950 dark:text-white" />
              </label>
              <div className={`rounded-xl p-3 text-xs font-semibold ${settings.mailConfigured ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'}`}>
                {settings.mailConfigured ? 'SMTP 발송 준비 완료' : 'SMTP 설정 전: 신청은 저장되지만 메일은 발송되지 않습니다.'}
              </div>
              <button type="button" onClick={handleSaveSettings} disabled={saving} className="w-full rounded-xl bg-emerald-600 px-4 py-3 text-sm font-black text-white hover:bg-emerald-700 disabled:opacity-50">{saving ? '저장 중…' : '발송 설정 저장'}</button>
            </div>
          </aside>

          <div className="space-y-4">
            {(message || error) && <p role="status" className={`rounded-xl border px-4 py-3 text-sm font-semibold ${error ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300' : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300'}`}>{error || message}</p>}
            {!loading && orders.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">아직 접수된 명함 신청이 없습니다.</div>}
            {!loading && orders.length > 0 && filteredOrders.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">검색 조건에 맞는 신청이 없습니다.</div>}
            {filteredOrders.map(order => {
              const status = STATUS_LABELS[order.status] || STATUS_LABELS.pending_approval;
              const cardData = parseCardData(order);
              const processing = processingId === order.id;
              return (
                <article key={order.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
                  <div className="grid md:grid-cols-[240px_1fr]">
                    <a href={order.image_url} target="_blank" rel="noreferrer" className="block bg-slate-200 p-3 dark:bg-slate-800" title="명함 시안 크게 보기">
                      <img src={order.image_url} alt={`${order.requester_name} 명함 시안`} className="h-full max-h-64 w-full rounded-lg object-contain" />
                    </a>
                    <div className="p-5">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-lg font-black text-slate-900 dark:text-white">{order.requester_name}</h3>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${status.className}`}>{status.label}</span>
                          </div>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{order.requester_department || cardData.departmentKo}</p>
                        </div>
                        <p className="text-xs text-slate-400">{formatDate(order.created_at)}</p>
                      </div>
                      <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
                        <div><dt className="text-xs font-bold text-slate-400">이메일</dt><dd className="truncate text-slate-700 dark:text-slate-200">{cardData.email}</dd></div>
                        <div><dt className="text-xs font-bold text-slate-400">휴대전화</dt><dd className="text-slate-700 dark:text-slate-200">{cardData.mobilePhone}</dd></div>
                        <div><dt className="text-xs font-bold text-slate-400">신청 수량</dt><dd className="font-bold text-slate-700 dark:text-slate-200">{order.quantity || 200}매</dd></div>
                        <div><dt className="text-xs font-bold text-slate-400">신청 방식</dt><dd className="text-slate-700 dark:text-slate-200">{order.send_mode === 'automatic' ? '자동' : '반자동'}</dd></div>
                        <div><dt className="text-xs font-bold text-slate-400">발송 대상</dt><dd className="truncate text-slate-700 dark:text-slate-200">{order.recipient_email || '미설정'}</dd></div>
                      </dl>
                      {(order.mail_error || order.rejection_reason) && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">{order.mail_error || order.rejection_reason}</p>}
                      <div className="mt-5 flex flex-wrap gap-2">
                        {order.status === 'pending_approval' && <button type="button" onClick={() => handleAction(order, 'approve')} disabled={processing} className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-black text-white hover:bg-emerald-700 disabled:opacity-50">승인 후 발송</button>}
                        {order.status === 'send_failed' && <button type="button" onClick={() => handleAction(order, 'retry')} disabled={processing} className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-black text-white hover:bg-blue-700 disabled:opacity-50">재발송</button>}
                        {!['sent', 'rejected', 'cancelled', 'sending'].includes(order.status) && <button type="button" onClick={() => handleAction(order, 'reject')} disabled={processing} className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-black text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">반려</button>}
                        <a href={order.image_url} download className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-black text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">JPG 다운로드</a>
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};

export default BusinessCardOrderAdmin;
