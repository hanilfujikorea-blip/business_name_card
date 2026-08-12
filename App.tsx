import React, { useEffect, useState } from 'react';
import BusinessCardOrder from './components/BusinessCardOrder';
import BusinessCardOrderAdmin from './components/BusinessCardOrderAdmin';
import { UserProfile, UserRole } from './types';

const DEMO_USER: UserProfile = {
  id: 'TEAM_USER',
  name: '홍길동',
  englishName: 'GILDONG HONG',
  companyName: '한일후지코리아(주)',
  department: '재무관리사업부',
  team: '인사총무팀',
  position: '대리',
  phone: '010-1234-5678',
  extensionNumber: '051-000-0000',
  email: 'team.user@example.com',
  avatarUrl: '',
  role: UserRole.USER,
};

const DEMO_ADMIN: UserProfile = {
  ...DEMO_USER,
  id: 'TEAM_ADMIN',
  name: '관리자',
  englishName: 'ADMIN USER',
  role: UserRole.ADMIN,
};

type DemoRole = 'USER' | 'ADMIN';

const App: React.FC = () => {
  const [role, setRole] = useState<DemoRole>('USER');
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');

  const activateRole = async (nextRole: DemoRole) => {
    setReady(false);
    setError('');
    try {
      const response = await fetch('/api/dev/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: nextRole }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || '개발용 로그인에 실패했습니다.');
      setRole(nextRole);
      setReady(true);
    } catch (sessionError) {
      setError(sessionError instanceof Error ? sessionError.message : '개발 서버에 연결할 수 없습니다.');
    }
  };

  useEffect(() => { void activateRole('USER'); }, []);

  const user = role === 'ADMIN' ? DEMO_ADMIN : DEMO_USER;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-black">명함발주</h1>
              <span className="rounded-full bg-amber-400/15 px-2 py-1 text-[11px] font-bold text-amber-300">독립 개발용</span>
            </div>
            <p className="mt-0.5 text-xs text-slate-400">기존 포털과 분리된 협업·검수 화면입니다.</p>
          </div>
          <div className="flex rounded-xl border border-slate-700 bg-slate-900 p-1">
            <button
              type="button"
              onClick={() => void activateRole('USER')}
              className={`rounded-lg px-4 py-2 text-sm font-bold transition ${role === 'USER' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              직원 신청
            </button>
            <button
              type="button"
              onClick={() => void activateRole('ADMIN')}
              className={`rounded-lg px-4 py-2 text-sm font-bold transition ${role === 'ADMIN' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              관리자 대시보드
            </button>
          </div>
        </div>
      </header>

      {error ? (
        <div className="mx-auto mt-12 max-w-xl rounded-xl border border-red-800 bg-red-950/40 p-6 text-center text-red-200">
          <p>{error}</p>
          <button type="button" onClick={() => void activateRole(role)} className="mt-4 rounded-lg bg-red-700 px-4 py-2 font-bold">다시 연결</button>
        </div>
      ) : !ready ? (
        <div className="py-24 text-center text-slate-400">개발용 화면을 준비하고 있습니다...</div>
      ) : role === 'ADMIN' ? (
        <BusinessCardOrderAdmin />
      ) : (
        <BusinessCardOrder user={user} />
      )}
    </div>
  );
};

export default App;
