import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { UserProfile } from '../types';
import { BusinessCardOrderRecord, cancelBusinessCardOrder, createBusinessCardOrder, listBusinessCardOrders } from '../services/businessCardOrderService';

interface BusinessCardOrderProps {
  user: UserProfile;
}

type CardInformation = {
  koreanName: string;
  englishName: string;
  companyKo: string;
  companyEn: string;
  positionKo: string;
  positionEn: string;
  departmentKo: string;
  departmentEn: string;
  officeKo: string;
  officeEn: string;
  addressKo: string;
  addressEn: string;
  postalCode: string;
  telephone: string;
  fax: string;
  directPhone: string;
  mobilePhone: string;
  email: string;
  website: string;
};

type FormField = keyof CardInformation;
type Stage = 'editing' | 'reviewing' | 'completed';

const ORDER_STATUS_META: Record<BusinessCardOrderRecord['status'], { label: string; description: string; className: string }> = {
  pending_approval: {
    label: '승인 대기',
    description: '관리자 승인 후 발주가 진행됩니다.',
    className: 'bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300',
  },
  approved: {
    label: '승인됨',
    description: '관리자 승인이 완료되어 발주를 준비하고 있습니다.',
    className: 'bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-300',
  },
  sending: {
    label: '승인됨 · 발주 중',
    description: '승인된 명함 시안을 발주처로 전송하고 있습니다.',
    className: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300',
  },
  sent: {
    label: '발주 요청 완료',
    description: '승인된 명함 시안이 지정된 발주처로 전달되었습니다.',
    className: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300',
  },
  send_failed: {
    label: '승인됨 · 처리 대기',
    description: '관리자 승인은 완료되었으며 발주 전송을 다시 처리하고 있습니다.',
    className: 'bg-orange-100 text-orange-800 dark:bg-orange-950/50 dark:text-orange-300',
  },
  rejected: {
    label: '반려됨',
    description: '신청 내용을 확인하고 수정한 뒤 새로 신청해 주세요.',
    className: 'bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300',
  },
  cancelled: {
    label: '신청 취소',
    description: '승인 전에 신청을 취소했습니다. 필요하면 같은 내용으로 다시 신청할 수 있습니다.',
    className: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  },
};

const formatOrderDate = (value?: string) => value ? new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
}).format(new Date(value)) : '-';

const COMPANY_OPTIONS = [
  {
    korean: '한일후지코리아(주)',
    english: 'HANIL-FUJI(Korea) CO., LTD.',
    defaults: {
      officeKo: '부산신항 배후물류단지',
      officeEn: 'Head Office : Busan New Port Free Trading Zone',
      addressKo: '경남 창원시 진해구 신항로 434-2',
      addressEn: '434-2, Sinhang-ro, Jinhae-gu, Changwon-si, Gyeongnam',
      postalCode: '51609',
      telephone: '051-712-8400',
      fax: '0504-848-8942',
      website: 'www.hanil-fuji.com',
    },
  },
  {
    korean: '(주)후지글로벌로지스틱',
    english: 'Fuji Global Logistics Co., Ltd.',
    defaults: {
      officeKo: '부산신항 배후물류단지',
      officeEn: 'Head Office : Busan New Port Free Trading Zone',
      addressKo: '경남 창원시 진해구 신항로 434-2',
      addressEn: '434-2, Sinhang-ro, Jinhae-gu, Changwon-si, Gyeongnam',
      postalCode: '51609',
      telephone: '',
      fax: '',
      website: 'www.fujiglobal.co.kr',
    },
  },
] as const;

const EMPTY_COMPANY_DEFAULTS = {
  officeKo: '', officeEn: '', addressKo: '', addressEn: '', postalCode: '', telephone: '', fax: '', website: '',
} as const;

const FIELD_GROUPS: Array<{
  title: string;
  description: string;
  fields: Array<{ key: FormField; label: string; placeholder: string; required?: boolean; readOnly?: boolean; type?: string }>;
}> = [
  {
    title: '기본 정보',
    description: '명함 중앙에 표시되는 이름과 소속 정보입니다.',
    fields: [
      { key: 'koreanName', label: '이름', placeholder: '장호철', required: true },
      { key: 'englishName', label: '영문 이름', placeholder: 'AARON JANG', required: true },
      { key: 'companyKo', label: '소속 회사', placeholder: '회사를 선택해 주세요', required: true },
      { key: 'positionKo', label: '직급/직책', placeholder: '과장' },
      { key: 'positionEn', label: '직급/직책(영문)', placeholder: 'TEAM LEADER' },
      { key: 'departmentKo', label: '부서/팀', placeholder: '부품영업2팀 / 부품사업부', required: true },
      { key: 'departmentEn', label: '부서/팀(영문)', placeholder: 'MACHINERY SALES TEAM 2 / MACHINERY SOLUTION DIVISION', required: true },
    ],
  },
  {
    title: '근무지 정보',
    description: '명함 하단의 사무실명과 주소에 사용됩니다.',
    fields: [
      { key: 'officeKo', label: '근무지명', placeholder: '부산신항 배후물류단지' },
      { key: 'officeEn', label: '근무지명(영문)', placeholder: 'Head Office : Busan New Port Free Trading Zone' },
      { key: 'addressKo', label: '주소', placeholder: '경남 창원시 진해구 신항로 434-2' },
      { key: 'addressEn', label: '주소(영문)', placeholder: '434-2, Sinhang-ro, Jinhae-gu, Changwon-si, Gyeongnam' },
      { key: 'postalCode', label: '우편번호', placeholder: '51609' },
      { key: 'website', label: '홈페이지', placeholder: '회사 홈페이지', readOnly: true },
    ],
  },
  {
    title: '연락처',
    description: '전화번호는 하이픈을 포함해 명함에 표시될 형태로 입력해 주세요.',
    fields: [
      { key: 'telephone', label: '대표 전화', placeholder: '051-712-8400' },
      { key: 'fax', label: 'FAX', placeholder: '0504-848-8942' },
      { key: 'directPhone', label: '직통 전화', placeholder: '051-712-8482' },
      { key: 'mobilePhone', label: '휴대전화', placeholder: '010-6476-8180', required: true },
      { key: 'email', label: '이메일', placeholder: 'name@hanilss.com', required: true, type: 'email' },
    ],
  },
];

const CARD_INFORMATION_KEYS: FormField[] = [
  'koreanName', 'englishName', 'companyKo', 'companyEn', 'positionKo', 'positionEn',
  'departmentKo', 'departmentEn', 'officeKo', 'officeEn', 'addressKo', 'addressEn',
  'postalCode', 'telephone', 'fax', 'directPhone', 'mobilePhone', 'email', 'website',
];

const fallback = (value: string, placeholder: string) => value.trim() || placeholder;

const splitDepartment = (value: string) => value
  .split('/')
  .map(part => part.trim())
  .filter(Boolean);

const replaceDepartmentCompany = (value: string, companyNames: string[], nextCompany: string) => {
  const candidates = new Set(companyNames.map(name => name.trim()).filter(Boolean));
  return value.split('/').map(part => {
    const trimmed = part.trim();
    return candidates.has(trimmed) ? nextCompany : trimmed;
  }).filter(Boolean).join(' / ');
};

const CARD_WIDTH = 1400;
const CARD_HEIGHT = 787;
const CARD_FONT = 'Malgun Gothic, Arial, sans-serif';

const wrapCardText = (value: string, maximumCharacters: number) => {
  const words = value.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [''];
  return words.reduce<string[]>((lines, word) => {
    const current = lines.at(-1) || '';
    if (!current || `${current} ${word}`.length > maximumCharacters) lines.push(word);
    else lines[lines.length - 1] = `${current} ${word}`;
    return lines;
  }, []);
};

const estimateCardTextWidth = (value: string, fontSize: number, letterSpacing = 0) => {
  const characters = Array.from(value);
  const glyphWidth = characters.reduce((width, character) => {
    if (/\s/.test(character)) return width + (fontSize * 0.36);
    if (character.charCodeAt(0) > 255) return width + fontSize;
    if (/[A-Z]/.test(character)) return width + (fontSize * 0.68);
    if (/[a-z]/.test(character)) return width + (fontSize * 0.56);
    return width + (fontSize * 0.58);
  }, 0);
  return glyphWidth + (Math.max(0, characters.length - 1) * letterSpacing);
};

const fitCardTextSize = (
  value: string,
  maximumWidth: number,
  preferredSize: number,
  minimumSize: number,
  letterSpacing = 0,
) => {
  let fontSize = preferredSize;
  while (fontSize > minimumSize && estimateCardTextWidth(value, fontSize, letterSpacing) > maximumWidth) {
    fontSize -= 2;
  }
  return fontSize;
};

const SvgTextLines: React.FC<{
  lines: string[];
  x: number;
  y: number;
  lineHeight: number;
  textAnchor?: 'start' | 'middle' | 'end';
}> = ({ lines, x, y, lineHeight, textAnchor = 'start' }) => (
  <text x={x} y={y} textAnchor={textAnchor}>
    {lines.map((line, index) => <tspan key={`${line}-${index}`} x={x} dy={index === 0 ? 0 : lineHeight}>{line}</tspan>)}
  </text>
);

const SvgCardFrame: React.FC<{ accent: string }> = ({ accent }) => (
  <>
    <rect x={1.5} y={1.5} width={CARD_WIDTH - 3} height={CARD_HEIGHT - 3} fill="#ffffff" stroke="#64748b" strokeWidth={3} />
    <path d="M 0 0 H 630 V 18 Q 630 47 601 47 H 0 Z" fill={accent} />
    <image href="/sidebar_logo.png" x={112} y={108} width={104} height={104} preserveAspectRatio="xMidYMid slice" />
  </>
);

const KoreanCard = React.forwardRef<SVGSVGElement, { info: CardInformation }>(({ info }, ref) => {
  const departments = splitDepartment(info.departmentKo);
  const address = `${fallback(info.addressKo, '주소')} ${info.postalCode ? `(우 ${info.postalCode})` : ''}`.trim();
  const addressLines = wrapCardText(address, 44);
  const contactStart = 638 + (addressLines.length * 28) + 10;
  const name = fallback(info.koreanName, '이름');
  const position = fallback(info.positionKo, '직급');
  const nameSize = fitCardTextSize(name, 560, 92, 58, 12);
  const nameWidth = estimateCardTextWidth(name, nameSize, 12);
  const positionRight = Math.max(300, 1246 - nameWidth - 48);
  const positionSize = fitCardTextSize(position, positionRight - 96, 36, 24, 4);

  return (
    <svg ref={ref} viewBox={`0 0 ${CARD_WIDTH} ${CARD_HEIGHT}`} className="block h-auto w-full bg-white shadow-sm" role="img" aria-label="한글 명함 시안" xmlns="http://www.w3.org/2000/svg">
      <SvgCardFrame accent="#059669" />
      <g fill="#0f172a" fontFamily={CARD_FONT}>
        <text x={236} y={178} fontSize={70} fontWeight={900} letterSpacing={-2}>{fallback(info.companyKo, '회사 선택')}</text>
        <text data-role="card-name" x={1246} y={354} textAnchor="end" fontSize={nameSize} fontWeight={900} letterSpacing={12}>{name}</text>
        <text data-role="card-position" x={positionRight} y={354} textAnchor="end" fontSize={positionSize} fontWeight={600} letterSpacing={4}>{position}</text>
        <g fontSize={34} fontWeight={700}>
          <SvgTextLines lines={departments.length ? departments : ['부서 / 팀']} x={1246} y={410} lineHeight={38} textAnchor="end" />
        </g>
        <text x={98} y={606} fontSize={32} fontWeight={800}>{fallback(info.officeKo, '근무지명')}</text>
        <g fontSize={25} fontWeight={400} letterSpacing={-0.5}>
          <SvgTextLines lines={addressLines} x={98} y={638} lineHeight={28} />
        </g>
        <g fontSize={28} fontWeight={400}>
          <text x={98} y={contactStart}>Tel. {fallback(info.telephone, '000-000-0000')}</text>
          <text x={98} y={contactStart + 31}>Fax. {fallback(info.fax, '000-000-0000')}</text>
          <text x={98} y={contactStart + 62}>E-mail. {fallback(info.email, 'name@company.com')}</text>
        </g>
        <g fontSize={24} fontWeight={400} letterSpacing={-0.4}>
          <text x={780} y={contactStart}>Direct Phone. {fallback(info.directPhone, '000-000-0000')}</text>
          <text x={780} y={contactStart + 31}>Mobile Phone. {fallback(info.mobilePhone, '010-0000-0000')}</text>
          <text x={780} y={contactStart + 62}>{fallback(info.website, 'www.hanil-fuji.com')}</text>
        </g>
      </g>
    </svg>
  );
});

const EnglishCard = React.forwardRef<SVGSVGElement, { info: CardInformation }>(({ info }, ref) => {
  const departments = splitDepartment(info.departmentEn).map(part => part.toUpperCase());
  const company = fallback(info.companyEn, 'COMPANY').toUpperCase();
  const name = fallback(info.englishName, 'ENGLISH NAME').toUpperCase();
  const position = fallback(info.positionEn, 'POSITION').toUpperCase();
  const address = `${fallback(info.addressEn, 'Office address')}${info.postalCode ? `, ${info.postalCode} Korea` : ''}`;
  const addressLines = wrapCardText(address, 52);
  const contactStart = 636 + (addressLines.length * 27) + 10;
  const companySize = company.length > 36 ? 48 : 56;
  const nameSize = fitCardTextSize(name, 720, 88, 42, 6);
  const nameWidth = estimateCardTextWidth(name, nameSize, 6);
  const positionRight = Math.max(300, 1246 - nameWidth - 48);
  const positionSize = fitCardTextSize(position, positionRight - 96, 32, 22);

  return (
    <svg ref={ref} viewBox={`0 0 ${CARD_WIDTH} ${CARD_HEIGHT}`} className="block h-auto w-full bg-white shadow-sm" role="img" aria-label="영문 명함 시안" xmlns="http://www.w3.org/2000/svg">
      <SvgCardFrame accent="#dc2626" />
      <g fill="#0f172a" fontFamily={CARD_FONT}>
        <text x={236} y={info.companyKo === '한일후지코리아(주)' ? 145 : 178} fontSize={companySize} fontWeight={900} letterSpacing={-1.5}>{company}</text>
        {info.companyKo === '한일후지코리아(주)' && <text x={236} y={198} fontSize={48} fontWeight={900} letterSpacing={-1.5}>MARINE SUPPLY AND ENGINEERING</text>}
        <text data-role="card-name" x={1246} y={365} textAnchor="end" fontSize={nameSize} fontWeight={900} letterSpacing={6}>{name}</text>
        <text data-role="card-position" x={positionRight} y={365} textAnchor="end" fontSize={positionSize} fontWeight={600}>{position}</text>
        <g fontSize={32} fontWeight={700}>
          <SvgTextLines lines={departments.length ? departments : ['DEPARTMENT / TEAM']} x={1246} y={422} lineHeight={36} textAnchor="end" />
        </g>
        <text x={98} y={604} fontSize={24} fontWeight={700} fill="#1e3a8a">{fallback(info.officeEn, 'Head Office')}</text>
        <g fontSize={24} fontWeight={400} letterSpacing={-0.5}>
          <SvgTextLines lines={addressLines} x={98} y={636} lineHeight={27} />
        </g>
        <g fontSize={27} fontWeight={400}>
          <text x={98} y={contactStart}>Tel. +82-{fallback(info.telephone, '00-000-0000').replace(/^0/, '')}</text>
          <text x={98} y={contactStart + 30}>Fax. +82-{fallback(info.fax, '000-000-0000').replace(/^0/, '')}</text>
          <text x={98} y={contactStart + 60}>E-mail. {fallback(info.email, 'name@company.com')}</text>
        </g>
        <g fontSize={23} fontWeight={400} letterSpacing={-0.4}>
          <text x={780} y={contactStart}>Direct Phone. +82-{fallback(info.directPhone, '00-000-0000').replace(/^0/, '')}</text>
          <text x={780} y={contactStart + 30}>Mobile Phone. +82-{fallback(info.mobilePhone, '10-0000-0000').replace(/^0/, '')}</text>
          <text x={780} y={contactStart + 60}>{fallback(info.website, 'www.hanil-fuji.com')}</text>
        </g>
      </g>
    </svg>
  );
});

const loadImage = (source: string): Promise<HTMLImageElement> => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => resolve(image);
  image.onerror = () => reject(new Error('명함 시안을 이미지로 변환하지 못했습니다.'));
  image.src = source;
});

const blobToDataUrl = (blob: Blob) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result || ''));
  reader.onerror = () => reject(new Error('회사 로고를 명함 시안에 포함하지 못했습니다.'));
  reader.readAsDataURL(blob);
});

const embedSvgImages = async (svg: SVGSVGElement) => {
  await Promise.all(Array.from(svg.querySelectorAll('image')).map(async image => {
    const source = image.getAttribute('href');
    if (!source || source.startsWith('data:')) return;
    const response = await fetch(new URL(source, window.location.href), { credentials: 'same-origin' });
    if (!response.ok) throw new Error('회사 로고를 명함 시안에 포함하지 못했습니다.');
    image.setAttribute('href', await blobToDataUrl(await response.blob()));
  }));
};

const renderPreviewCard = async (element: SVGSVGElement, outputWidth: number) => {
  const clone = element.cloneNode(true) as SVGSVGElement;
  await embedSvgImages(clone);
  const outputHeight = Math.round(outputWidth * (CARD_HEIGHT / CARD_WIDTH));
  clone.removeAttribute('class');
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  clone.setAttribute('width', String(outputWidth));
  clone.setAttribute('height', String(outputHeight));
  const serialized = new XMLSerializer().serializeToString(clone);
  const objectUrl = URL.createObjectURL(new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' }));

  try {
    const image = await loadImage(objectUrl);
    const canvas = document.createElement('canvas');
    canvas.width = outputWidth;
    canvas.height = outputHeight;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('이미지 생성 기능을 사용할 수 없습니다.');
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
};

const createBusinessCardImage = async (koreanCard: SVGSVGElement, englishCard: SVGSVGElement) => {
  if (document.fonts?.ready) await document.fonts.ready;
  await new Promise<void>(resolve => window.requestAnimationFrame(() => resolve()));

  const outputWidth = 1400;
  const gap = 20;
  const [koreanCanvas, englishCanvas] = await Promise.all([
    renderPreviewCard(koreanCard, outputWidth),
    renderPreviewCard(englishCard, outputWidth),
  ]);
  const canvas = document.createElement('canvas');
  canvas.width = outputWidth;
  canvas.height = koreanCanvas.height + gap + englishCanvas.height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('이미지 생성 기능을 사용할 수 없습니다.');
  context.fillStyle = '#e2e8f0';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(koreanCanvas, 0, 0);
  context.drawImage(englishCanvas, 0, koreanCanvas.height + gap);
  return canvas.toDataURL('image/jpeg', 0.95);
};

const BusinessCardOrder: React.FC<BusinessCardOrderProps> = ({ user }) => {
  const koreanCardRef = useRef<SVGSVGElement>(null);
  const englishCardRef = useRef<SVGSVGElement>(null);
  const initialInformation = useMemo<CardInformation>(() => {
    const profileCompany = COMPANY_OPTIONS.find(company => company.korean === user.companyName);
    const companyDefaults = profileCompany?.defaults || EMPTY_COMPANY_DEFAULTS;
    const profilePhone = user.phone || '';
    const isMobilePhone = profilePhone.replace(/\D/g, '').startsWith('010');
    return {
      koreanName: user.name || '',
      englishName: user.englishName || '',
      companyKo: profileCompany?.korean || '',
      companyEn: profileCompany?.english || '',
      positionKo: user.position || '',
      positionEn: '',
      departmentKo: [user.team, user.department].filter(Boolean).join(' / '),
      departmentEn: '',
      officeKo: companyDefaults.officeKo,
      officeEn: companyDefaults.officeEn,
      addressKo: companyDefaults.addressKo,
      addressEn: companyDefaults.addressEn,
      postalCode: companyDefaults.postalCode,
      telephone: companyDefaults.telephone,
      fax: companyDefaults.fax,
      directPhone: isMobilePhone ? (user.extensionNumber || '') : (profilePhone || user.extensionNumber || ''),
      mobilePhone: isMobilePhone ? profilePhone : '',
      email: user.email || '',
      website: companyDefaults.website,
    };
  }, [user]);

  const [info, setInfo] = useState<CardInformation>(initialInformation);
  const [stage, setStage] = useState<Stage>('editing');
  const [validationMessage, setValidationMessage] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [submittedOrder, setSubmittedOrder] = useState<BusinessCardOrderRecord | null>(null);
  const [orderHistory, setOrderHistory] = useState<BusinessCardOrderRecord[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [cancellingId, setCancellingId] = useState('');
  const [quantity, setQuantity] = useState(200);

  const refreshOrderHistory = useCallback(async (showLoading = true) => {
    if (showLoading) setIsHistoryLoading(true);
    setHistoryError('');
    try {
      setOrderHistory(await listBusinessCardOrders());
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : '신청내역을 불러오지 못했습니다.');
    } finally {
      if (showLoading) setIsHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshOrderHistory();
    const intervalId = window.setInterval(() => refreshOrderHistory(false), 30_000);
    return () => window.clearInterval(intervalId);
  }, [refreshOrderHistory]);

  const handleChange = (field: FormField, value: string) => {
    setInfo(previous => ({ ...previous, [field]: value }));
    setValidationMessage('');
    if (stage !== 'editing') setStage('editing');
  };

  const handleCompanyChange = (koreanCompany: string) => {
    const company = COMPANY_OPTIONS.find(option => option.korean === koreanCompany);
    setInfo(previous => ({
      ...previous,
      companyKo: company?.korean || '',
      companyEn: company?.english || '',
      ...(company?.defaults || EMPTY_COMPANY_DEFAULTS),
      departmentKo: company
        ? replaceDepartmentCompany(previous.departmentKo, [previous.companyKo, user.companyName], company.korean)
        : previous.departmentKo,
    }));
    setValidationMessage('');
    if (stage !== 'editing') setStage('editing');
  };

  const handleReuseOrder = (order: BusinessCardOrderRecord) => {
    let cardData: Record<string, unknown> = {};
    try {
      cardData = typeof order.card_data === 'string' ? JSON.parse(order.card_data || '{}') : order.card_data || {};
    } catch {
      setHistoryError('이 신청의 저장된 정보를 불러오지 못했습니다.');
      return;
    }
    const nextInformation = { ...initialInformation };
    CARD_INFORMATION_KEYS.forEach(key => {
      if (typeof cardData[key] === 'string') nextInformation[key] = cardData[key] as string;
    });
    const company = COMPANY_OPTIONS.find(option => option.korean === nextInformation.companyKo);
    if (company) {
      nextInformation.companyEn = company.english;
      nextInformation.website = company.defaults.website;
    }
    setInfo(nextInformation);
    setQuantity(order.quantity === 400 ? 400 : 200);
    setSubmittedOrder(null);
    setValidationMessage('');
    setHistoryError('');
    setStage('editing');
    window.setTimeout(() => document.getElementById('business-card-order-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  };

  const handleCancelOrder = async (order: BusinessCardOrderRecord) => {
    if (!window.confirm(`신청번호 ${order.id}를 취소하시겠습니까?`)) return;
    setCancellingId(order.id);
    setHistoryError('');
    try {
      const cancelled = await cancelBusinessCardOrder(order.id);
      setOrderHistory(previous => previous.map(item => item.id === cancelled.id ? cancelled : item));
      setSubmittedOrder(previous => previous?.id === cancelled.id ? cancelled : previous);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : '명함 신청을 취소하지 못했습니다.');
    } finally {
      setCancellingId('');
    }
  };

  const handleReview = (event: FormEvent) => {
    event.preventDefault();
    const requiredFields = FIELD_GROUPS.flatMap(group => group.fields).filter(field => field.required);
    const emptyField = requiredFields.find(field => !info[field.key].trim());
    if (emptyField) {
      setValidationMessage(`${emptyField.label} 항목을 입력해 주세요.`);
      return;
    }
    if (![200, 400].includes(quantity)) {
      setValidationMessage('명함 수량은 200매 또는 400매만 선택할 수 있습니다.');
      return;
    }
    setValidationMessage('');
    setStage('reviewing');
  };

  const handleOrder = async () => {
    setIsGenerating(true);
    setValidationMessage('');
    try {
      if (!koreanCardRef.current || !englishCardRef.current) throw new Error('화면의 명함 시안을 확인할 수 없습니다.');
      const imageDataUrl = await createBusinessCardImage(koreanCardRef.current, englishCardRef.current);
      const order = await createBusinessCardOrder(info, imageDataUrl, quantity);
      setSubmittedOrder(order);
      setOrderHistory(previous => [order, ...previous.filter(item => item.id !== order.id)]);
      setStage('completed');
    } catch (error) {
      setValidationMessage(error instanceof Error ? error.message : '명함 신청을 접수하지 못했습니다.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <section className="min-h-full bg-slate-100 px-4 py-6 dark:bg-slate-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1500px]">
        <header className="mb-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-7">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="mb-2 text-sm font-bold text-emerald-600 dark:text-emerald-400">업무 지원 · 명함발주</p>
              <h2 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white sm:text-3xl">내 정보로 명함 시안 만들기</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-400">
                정보를 입력하면 오른쪽 시안에 즉시 반영됩니다.
              </p>
            </div>
            <ol className="grid grid-cols-3 overflow-hidden rounded-xl border border-slate-200 bg-slate-50 text-center text-xs font-bold dark:border-slate-700 dark:bg-slate-800 sm:min-w-[420px]">
              {[
                ['editing', '1. 정보 입력'],
                ['reviewing', '2. 시안 확인'],
                ['completed', '3. 신청 완료'],
              ].map(([step, label], index) => {
                const stageIndex = ['editing', 'reviewing', 'completed'].indexOf(stage);
                return (
                  <li key={step} className={`px-3 py-3 ${index <= stageIndex ? 'bg-emerald-600 text-white' : 'text-slate-500 dark:text-slate-400'}`}>
                    {label}
                  </li>
                );
              })}
            </ol>
          </div>
        </header>

        <div className="grid items-start gap-6 xl:grid-cols-[minmax(420px,0.88fr)_minmax(600px,1.12fr)]">
          <form id="business-card-order-form" onSubmit={handleReview} className="space-y-5">
            {FIELD_GROUPS.map(group => (
              <fieldset key={group.title} disabled={stage !== 'editing'} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm disabled:opacity-75 dark:border-slate-800 dark:bg-slate-900">
                <legend className="sr-only">{group.title}</legend>
                <h3 className="text-base font-black text-slate-900 dark:text-white">{group.title}</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">{group.description}</p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  {group.fields.map(field => (
                    <label key={field.key} className={(field.key === 'officeKo' || field.key === 'officeEn' || field.key === 'addressKo' || field.key === 'addressEn' || field.key === 'companyKo') ? 'sm:col-span-2' : ''}>
                      <span className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-300">
                        {field.label}{field.required && <span className="ml-1 text-red-500" aria-label="필수">*</span>}
                      </span>
                      {field.key === 'companyKo' ? (
                        <>
                          <select
                            value={info.companyKo}
                            onChange={event => handleCompanyChange(event.target.value)}
                            required
                            className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:disabled:bg-slate-800"
                          >
                            <option value="">회사를 선택해 주세요</option>
                            {COMPANY_OPTIONS.map(company => <option key={company.korean} value={company.korean}>{company.korean}</option>)}
                          </select>
                          {info.companyEn && <span className="mt-1.5 block text-xs text-slate-500 dark:text-slate-400">영문 표기: {info.companyEn}</span>}
                        </>
                      ) : (
                        <input
                          type={field.type || 'text'}
                          value={info[field.key]}
                          onChange={event => handleChange(field.key, event.target.value)}
                          placeholder={field.placeholder}
                          required={field.required}
                          readOnly={field.readOnly}
                          title={field.readOnly ? '회사 선택에 따라 자동 적용되는 고정 정보입니다.' : undefined}
                          className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 read-only:cursor-not-allowed read-only:bg-slate-100 read-only:text-slate-600 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:read-only:bg-slate-800 dark:read-only:text-slate-300 dark:disabled:bg-slate-800"
                        />
                      )}
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}

            <fieldset disabled={stage !== 'editing'} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm disabled:opacity-75 dark:border-slate-800 dark:bg-slate-900">
              <legend className="sr-only">발주 정보</legend>
              <h3 className="text-base font-black text-slate-900 dark:text-white">발주 정보</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-slate-400">필요한 명함 수량을 선택해 주세요. 기본 수량은 200매입니다.</p>
              <label className="mt-4 block max-w-xs">
                <span className="mb-1.5 block text-xs font-bold text-slate-700 dark:text-slate-300">수량 <span className="ml-1 text-red-500" aria-label="필수">*</span></span>
                <select value={quantity} onChange={event => setQuantity(Number(event.target.value))} required className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm font-bold text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 disabled:bg-slate-100 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:disabled:bg-slate-800">
                  <option value={200}>200매</option>
                  <option value={400}>400매</option>
                </select>
              </label>
            </fieldset>

            {validationMessage && (
              <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
                {validationMessage}
              </p>
            )}

            {stage === 'editing' && (
              <button type="submit" className="w-full rounded-xl bg-emerald-600 px-5 py-3.5 text-sm font-black text-white shadow-lg shadow-emerald-600/20 transition hover:bg-emerald-700 focus:outline-none focus:ring-4 focus:ring-emerald-500/30">
                입력 완료 · 시안 확인하기
              </button>
            )}
            {stage === 'reviewing' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <button type="button" onClick={() => setStage('editing')} className="rounded-xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-black text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
                  수정하기
                </button>
                <button type="button" onClick={handleOrder} disabled={isGenerating} className="rounded-xl bg-emerald-600 px-5 py-3.5 text-sm font-black text-white shadow-lg shadow-emerald-600/20 transition hover:bg-emerald-700 disabled:cursor-wait disabled:opacity-60">
                  {isGenerating ? '발주 접수 중…' : '시안 확정 · 발주하기'}
                </button>
              </div>
            )}

            {stage === 'completed' && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900/60 dark:bg-emerald-950/30">
                <p className="font-black text-emerald-800 dark:text-emerald-300">
                  {submittedOrder?.status === 'sent' ? '명함 시안이 자동 발송되었습니다.' : '명함 발주 신청이 접수되었습니다.'}
                </p>
                <p className="mt-1 text-sm leading-6 text-emerald-700 dark:text-emerald-400">
                  {submittedOrder?.status === 'pending_approval' && '관리자 승인 후 발주가 진행됩니다.'}
                  {submittedOrder?.status === 'sent' && '관리자가 지정한 수신 이메일로 JPG 발송을 완료했습니다.'}
                  {submittedOrder?.status === 'send_failed' && '신청과 JPG는 안전하게 저장됐지만 메일 발송에 실패했습니다. 관리자가 설정 확인 후 재발송할 수 있습니다.'}
                  {submittedOrder?.status === 'cancelled' && '승인 전에 신청을 취소했습니다.'}
                </p>
                {submittedOrder && <p className="mt-2 text-xs font-bold text-emerald-700/80 dark:text-emerald-400/80">신청번호: {submittedOrder.id}</p>}
                {submittedOrder && <p className="mt-1 text-xs font-bold text-emerald-700/80 dark:text-emerald-400/80">신청수량: {submittedOrder.quantity || 200}매</p>}
              </div>
            )}
          </form>

          <aside className="xl:sticky xl:top-6">
            <div className="rounded-2xl border border-slate-200 bg-slate-900 p-4 shadow-xl dark:border-slate-700 sm:p-6">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold text-emerald-400">LIVE PREVIEW</p>
                  <h3 className="mt-0.5 font-black text-white">명함 시안 미리보기</h3>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-bold ${stage === 'editing' ? 'bg-amber-400/15 text-amber-300' : 'bg-emerald-400/15 text-emerald-300'}`}>
                  {stage === 'editing' ? '작성 중' : stage === 'reviewing' ? '확인 대기' : '신청 접수 완료'}
                </span>
              </div>
              <div className="mx-auto max-w-[620px] space-y-2 rounded-xl bg-slate-200 p-2">
                <KoreanCard ref={koreanCardRef} info={info} />
                <EnglishCard ref={englishCardRef} info={info} />
              </div>
              <p className="mt-4 text-xs leading-5 text-slate-400">
                화면 비율에 맞춘 미리보기입니다. 발주 시에는 한글·영문 시안이 포함된 고해상도 JPG로 생성됩니다.
              </p>
            </div>
          </aside>
        </div>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-7">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">MY ORDERS</p>
              <h3 className="mt-1 text-xl font-black text-slate-900 dark:text-white">나의 명함 신청내역</h3>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">관리자 승인 또는 반려 결과와 발주 진행 상태를 확인할 수 있습니다.</p>
            </div>
            <button
              type="button"
              onClick={() => refreshOrderHistory()}
              disabled={isHistoryLoading}
              className="self-start rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-black text-slate-700 transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800 sm:self-auto"
            >
              {isHistoryLoading ? '확인 중…' : '상태 새로고침'}
            </button>
          </div>

          {historyError && (
            <p role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
              {historyError}
            </p>
          )}

          {!historyError && isHistoryLoading && orderHistory.length === 0 && (
            <p className="mt-5 rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:bg-slate-950 dark:text-slate-400">신청내역을 확인하고 있습니다.</p>
          )}

          {!historyError && !isHistoryLoading && orderHistory.length === 0 && (
            <p className="mt-5 rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:bg-slate-950 dark:text-slate-400">아직 신청한 명함이 없습니다.</p>
          )}

          {orderHistory.length > 0 && (
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              {orderHistory.map(order => {
                const status = ORDER_STATUS_META[order.status];
                return (
                  <article key={order.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-950 sm:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold text-slate-400">신청번호</p>
                        <p className="mt-1 font-black text-slate-900 dark:text-white">{order.id}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1.5 text-xs font-black ${status.className}`}>{status.label}</span>
                    </div>
                    <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-200">{status.description}</p>
                    <p className="mt-1 text-xs text-slate-400">신청일시 {formatOrderDate(order.created_at)}</p>
                    <p className="mt-1 text-xs font-bold text-slate-500 dark:text-slate-300">신청수량 {order.quantity || 200}매</p>
                    {order.status === 'rejected' && (
                      <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 dark:border-red-900/60 dark:bg-red-950/40">
                        <p className="text-xs font-black text-red-700 dark:text-red-300">반려 사유</p>
                        <p className="mt-1 text-sm leading-6 text-red-700 dark:text-red-300">{order.rejection_reason || '관리자에게 반려 사유를 확인해 주세요.'}</p>
                      </div>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2">
                      <a href={order.image_url} target="_blank" rel="noreferrer" className="inline-flex rounded-lg border border-slate-300 px-3 py-2 text-xs font-black text-slate-600 transition hover:bg-white dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
                        신청 시안 보기
                      </a>
                      {['rejected', 'sent', 'cancelled'].includes(order.status) && (
                        <button type="button" onClick={() => handleReuseOrder(order)} className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs font-black text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                          {order.status === 'rejected' ? '수정 후 재신청' : '이 내용으로 다시 신청'}
                        </button>
                      )}
                      {order.status === 'pending_approval' && (
                        <button type="button" onClick={() => handleCancelOrder(order)} disabled={cancellingId === order.id} className="rounded-lg border border-red-300 px-3 py-2 text-xs font-black text-red-600 transition hover:bg-red-50 disabled:cursor-wait disabled:opacity-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/30">
                          {cancellingId === order.id ? '취소 중…' : '신청 취소'}
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </section>
  );
};

export default BusinessCardOrder;
