export type BusinessCardSendMode = 'automatic' | 'semi_automatic';
export type BusinessCardOrderStatus = 'pending_approval' | 'approved' | 'sending' | 'sent' | 'send_failed' | 'rejected' | 'cancelled';

export interface BusinessCardSettings {
  sendMode: BusinessCardSendMode;
  recipientEmail?: string;
  mailConfigured: boolean;
}

export interface BusinessCardOrderRecord {
  id: string;
  requester_id: string;
  requester_name: string;
  requester_department: string;
  card_data: Record<string, string> | string;
  image_url: string;
  image_sha256: string;
  send_mode: BusinessCardSendMode;
  status: BusinessCardOrderStatus;
  recipient_email: string;
  quantity: number;
  approved_by?: string;
  approved_at?: string;
  rejected_by?: string;
  rejected_at?: string;
  rejection_reason?: string;
  cancelled_by?: string;
  cancelled_at?: string;
  sent_at?: string;
  mail_error?: string;
  created_at: string;
  updated_at: string;
}

const request = async <T>(url: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || '명함발주 요청을 처리하지 못했습니다.');
  return payload as T;
};

export const getBusinessCardSettings = () => request<BusinessCardSettings>('/api/business-card/settings');

export const saveBusinessCardSettings = (settings: Pick<BusinessCardSettings, 'sendMode' | 'recipientEmail'>) => request<BusinessCardSettings>(
  '/api/business-card/settings',
  { method: 'POST', body: JSON.stringify(settings) },
);

export const listBusinessCardOrders = async () => {
  const payload = await request<{ orders: BusinessCardOrderRecord[] }>('/api/business-card/orders');
  return payload.orders;
};

export const createBusinessCardOrder = async (cardData: Record<string, string>, imageDataUrl: string, quantity = 200) => {
  const payload = await request<{ order: BusinessCardOrderRecord }>('/api/business-card/orders', {
    method: 'POST',
    body: JSON.stringify({ cardData, imageDataUrl, quantity }),
  });
  return payload.order;
};

export const processBusinessCardOrder = async (orderId: string, action: 'approve' | 'retry' | 'reject', reason = '') => {
  const payload = await request<{ order: BusinessCardOrderRecord }>(`/api/business-card/orders/${encodeURIComponent(orderId)}/${action}`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
  return payload.order;
};

export const cancelBusinessCardOrder = async (orderId: string) => {
  const payload = await request<{ order: BusinessCardOrderRecord }>(`/api/business-card/orders/${encodeURIComponent(orderId)}/cancel`, {
    method: 'POST',
  });
  return payload.order;
};
