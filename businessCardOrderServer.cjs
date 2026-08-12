const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const nodemailer = require('nodemailer');

const ORDER_TABLE = 'business_card_orders';
const MODE_KEY = 'business_card_send_mode';
const RECIPIENT_KEY = 'business_card_recipient_email';
const SESSION_COOKIE = 'hfk_business_card_session';
const SESSION_TTL_MS = 12 * 60 * 60 * 1000;
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const BUSINESS_CARD_COMPANIES = new Map([
  ['한일후지코리아(주)', {
    english: 'HANIL-FUJI(Korea) CO., LTD.',
    addressKo: '경남 창원시 진해구 신항로 434-2',
    addressEn: '434-2, Sinhang-ro, Jinhae-gu, Changwon-si, Gyeongnam, Korea',
    postalCode: '51609',
    website: 'www.hanil-fuji.com',
  }],
  ['(주)후지글로벌로지스틱', {
    english: 'Fuji Global Logistics Co., Ltd.',
    addressKo: '경남 창원시 진해구 신항로 434-2',
    addressEn: '434-2, Sinhang-ro, Jinhae-gu, Changwon-si, Gyeongnam, Korea',
    postalCode: '51609',
    website: 'www.fujiglobal.co.kr',
  }],
]);
const sessions = new Map();
const sendingOrders = new Set();

function createBusinessCardOrderHandler(dependencies) {
  const {
    runQuery,
    withPostgresTransaction,
    parseJsonBody,
    sendJson,
    uploadsDir,
  } = dependencies;
  const imageDir = path.join(uploadsDir, 'business-card-orders');
  let schemaPromise = null;
  let orderCreationQueue = Promise.resolve();

  function formatKoreaDate(value) {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
    }).formatToParts(new Date(value));
    const part = type => parts.find(item => item.type === type)?.value || '';
    return `${part('year')}${part('month')}${part('day')}`;
  }

  function enqueueOrderCreation(task) {
    const pending = orderCreationQueue.then(task, task);
    orderCreationQueue = pending.then(() => undefined, () => undefined);
    return pending;
  }

  async function nextOrderId(now) {
    const datePrefix = formatKoreaDate(now);
    const result = await query({
      operation: 'select', table: ORDER_TABLE, filters: [],
      orders: [{ column: 'created_at', ascending: false }],
      selectColumns: 'id,created_at', limitCount: 5000,
    });
    const ordersForDate = (result.data || []).filter(order => {
      if (String(order.id || '').startsWith(`${datePrefix}-`)) return true;
      return order.created_at && formatKoreaDate(order.created_at) === datePrefix;
    });
    const highestAssignedNumber = ordersForDate.reduce((highest, order) => {
      const match = String(order.id || '').match(new RegExp(`^${datePrefix}-(\\d+)$`));
      return match ? Math.max(highest, Number(match[1])) : highest;
    }, 0);
    return `${datePrefix}-${Math.max(ordersForDate.length, highestAssignedNumber) + 1}`;
  }

  function ensureSchema() {
    if (String(process.env.DB_PROVIDER || 'local').toLowerCase() !== 'postgres') return Promise.resolve();
    if (!schemaPromise) {
      schemaPromise = withPostgresTransaction(async client => {
        await client.query(`
          CREATE TABLE IF NOT EXISTS "ksys"."hr_portal_business_card_orders" (
            "id" varchar(64) PRIMARY KEY,
            "requester_id" varchar(100) NOT NULL,
            "requester_name" varchar(200) NOT NULL,
            "requester_department" varchar(300) NOT NULL DEFAULT '',
            "card_data" jsonb NOT NULL DEFAULT '{}'::jsonb,
            "image_url" text NOT NULL,
            "image_path" text NOT NULL,
            "image_sha256" varchar(64) NOT NULL,
            "send_mode" varchar(24) NOT NULL DEFAULT 'semi_automatic',
            "status" varchar(32) NOT NULL DEFAULT 'pending_approval',
            "recipient_email" text NOT NULL DEFAULT '',
            "quantity" integer NOT NULL DEFAULT 200,
            "approved_by" varchar(100),
            "approved_at" timestamptz,
            "rejected_by" varchar(100),
            "rejected_at" timestamptz,
            "rejection_reason" text,
            "cancelled_by" varchar(100),
            "cancelled_at" timestamptz,
            "sent_at" timestamptz,
            "mail_message_id" text,
            "mail_error" text,
            "created_at" timestamptz NOT NULL DEFAULT NOW(),
            "updated_at" timestamptz NOT NULL DEFAULT NOW()
          )
        `);
        await client.query(`
          ALTER TABLE "ksys"."hr_portal_business_card_orders"
          ADD COLUMN IF NOT EXISTS "cancelled_by" varchar(100)
        `);
        await client.query(`
          ALTER TABLE "ksys"."hr_portal_business_card_orders"
          ADD COLUMN IF NOT EXISTS "cancelled_at" timestamptz
        `);
        await client.query(`
          ALTER TABLE "ksys"."hr_portal_business_card_orders"
          ADD COLUMN IF NOT EXISTS "quantity" integer NOT NULL DEFAULT 200
        `);
        const quantityConstraints = await client.query(`
          SELECT "conname", pg_get_constraintdef("oid") AS "definition"
          FROM "pg_constraint"
          WHERE "conrelid" = '"ksys"."hr_portal_business_card_orders"'::regclass
            AND "contype" = 'c'
            AND pg_get_constraintdef("oid") ILIKE '%quantity%'
        `);
        if (!(quantityConstraints.rows || []).some(row => String(row.definition || '').includes('100000'))) {
          await client.query(`
            ALTER TABLE "ksys"."hr_portal_business_card_orders"
            ADD CONSTRAINT "ck_hr_portal_business_card_orders_quantity"
            CHECK ("quantity" BETWEEN 1 AND 100000)
          `);
        }
        const statusConstraints = await client.query(`
          SELECT "conname", pg_get_constraintdef("oid") AS "definition"
          FROM "pg_constraint"
          WHERE "conrelid" = '"ksys"."hr_portal_business_card_orders"'::regclass
            AND "contype" = 'c'
            AND pg_get_constraintdef("oid") ILIKE '%status%'
        `);
        const statusAllowsCancellation = (statusConstraints.rows || []).some(row => String(row.definition || '').includes('cancelled'));
        if (!statusAllowsCancellation) {
          for (const row of statusConstraints.rows || []) {
            const constraintName = String(row.conname || '');
            if (!/^[A-Za-z0-9_]+$/.test(constraintName)) throw new Error('명함발주 상태 제약조건 이름이 안전하지 않습니다.');
            await client.query(`ALTER TABLE "ksys"."hr_portal_business_card_orders" DROP CONSTRAINT "${constraintName}"`);
          }
          await client.query(`
            ALTER TABLE "ksys"."hr_portal_business_card_orders"
            ADD CONSTRAINT "ck_hr_portal_business_card_orders_status"
            CHECK ("status" IN ('pending_approval', 'approved', 'sending', 'sent', 'send_failed', 'rejected', 'cancelled'))
          `);
        }
        await client.query(`
          CREATE INDEX IF NOT EXISTS "idx_hr_portal_business_card_orders_created"
          ON "ksys"."hr_portal_business_card_orders" ("created_at" DESC)
        `);
        await client.query(`
          CREATE INDEX IF NOT EXISTS "idx_hr_portal_business_card_orders_status"
          ON "ksys"."hr_portal_business_card_orders" ("status", "created_at" DESC)
        `);
      }).catch(error => {
        schemaPromise = null;
        throw error;
      });
    }
    return schemaPromise;
  }

  async function query(payload) {
    await ensureSchema();
    const result = await runQuery(payload);
    if (result?.error) throw new Error(result.error);
    return result;
  }

  function currentSession(req) {
    const cookieHeader = String(req.headers.cookie || '');
    const cookie = cookieHeader.split(';').map(item => item.trim()).find(item => item.startsWith(`${SESSION_COOKIE}=`));
    if (!cookie) return null;
    const token = decodeURIComponent(cookie.slice(SESSION_COOKIE.length + 1));
    const session = sessions.get(token);
    if (!session) return null;
    if (session.expiresAt <= Date.now()) {
      sessions.delete(token);
      return null;
    }
    return { token, ...session };
  }

  function requireSession(req, res, adminOnly = false) {
    const session = currentSession(req);
    if (!session) {
      sendJson(res, 401, { error: '로그인이 필요합니다.' });
      return null;
    }
    if (adminOnly && session.user.role !== 'ADMIN') {
      sendJson(res, 403, { error: '관리자 권한이 필요합니다.' });
      return null;
    }
    return session;
  }

  async function getSetting(settingKey, fallbackValue) {
    const result = await query({
      operation: 'select',
      table: 'site_settings',
      filters: [{ type: 'eq', column: 'setting_key', value: settingKey }],
      orders: [],
      selectColumns: '*',
      singleMode: 'maybeSingle',
    });
    const row = result.data;
    if (!row) return fallbackValue;
    return row.setting_value ?? row.value ?? fallbackValue;
  }

  async function getSettings() {
    const [modeValue, recipientValue] = await Promise.all([
      getSetting(MODE_KEY, 'semi_automatic'),
      getSetting(RECIPIENT_KEY, ''),
    ]);
    return {
      sendMode: modeValue === 'automatic' ? 'automatic' : 'semi_automatic',
      recipientEmail: typeof recipientValue === 'string' ? recipientValue : '',
      mailConfigured: mailConfiguration().configured,
    };
  }

  async function saveSetting(settingKey, settingValue) {
    await query({
      operation: 'upsert',
      table: 'site_settings',
      values: { setting_key: settingKey, setting_value: settingValue },
      options: { onConflict: 'setting_key' },
      filters: [],
      orders: [],
      selectColumns: '*',
    });
  }

  function mailConfiguration() {
    const enabled = String(process.env.BUSINESS_CARD_MAIL_ENABLED || 'false').toLowerCase() === 'true';
    const host = String(process.env.BUSINESS_CARD_SMTP_HOST || '').trim();
    const port = Number(process.env.BUSINESS_CARD_SMTP_PORT || 587);
    const user = String(process.env.BUSINESS_CARD_SMTP_USER || '').trim();
    const password = String(process.env.BUSINESS_CARD_SMTP_PASSWORD || '');
    const from = String(process.env.BUSINESS_CARD_MAIL_FROM || user).trim();
    return {
      enabled,
      host,
      port: Number.isFinite(port) ? port : 587,
      secure: String(process.env.BUSINESS_CARD_SMTP_SECURE || 'false').toLowerCase() === 'true',
      user,
      password,
      from,
      configured: Boolean(enabled && host && user && password && from),
    };
  }

  function normalizeImage(dataUrl) {
    const match = String(dataUrl || '').match(/^data:image\/jpeg;base64,([A-Za-z0-9+/=]+)$/);
    if (!match) throw Object.assign(new Error('JPG 형식의 명함 시안이 필요합니다.'), { statusCode: 400 });
    const buffer = Buffer.from(match[1], 'base64');
    if (!buffer.length || buffer.length > MAX_IMAGE_BYTES) {
      throw Object.assign(new Error('명함 시안 파일 크기가 허용 범위를 벗어났습니다.'), { statusCode: 413 });
    }
    if (buffer[0] !== 0xff || buffer[1] !== 0xd8) {
      throw Object.assign(new Error('올바른 JPG 파일이 아닙니다.'), { statusCode: 400 });
    }
    return buffer;
  }

  function cleanCardData(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw Object.assign(new Error('명함 정보가 올바르지 않습니다.'), { statusCode: 400 });
    }
    const cleaned = {};
    for (const [key, item] of Object.entries(value)) cleaned[key] = String(item ?? '').trim().slice(0, 500);
    for (const required of ['koreanName', 'englishName', 'companyKo', 'departmentKo', 'mobilePhone', 'email']) {
      if (!cleaned[required]) throw Object.assign(new Error(`필수 명함 정보가 누락되었습니다: ${required}`), { statusCode: 400 });
    }
    const company = BUSINESS_CARD_COMPANIES.get(cleaned.companyKo);
    if (!company) {
      throw Object.assign(new Error('명함발주는 한일후지코리아(주) 또는 (주)후지글로벌로지스틱만 신청할 수 있습니다.'), { statusCode: 400 });
    }
    cleaned.companyEn = company.english;
    cleaned.website = company.website;
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(cleaned.email)) {
      throw Object.assign(new Error('이메일 주소가 올바르지 않습니다.'), { statusCode: 400 });
    }
    return cleaned;
  }

  function normalizeQuantity(value) {
    const quantity = value === undefined || value === null || value === '' ? 200 : Number(value);
    if (![200, 400].includes(quantity)) {
      throw Object.assign(new Error('명함 수량은 200매 또는 400매만 선택할 수 있습니다.'), { statusCode: 400 });
    }
    return quantity;
  }

  async function getOrder(orderId) {
    const result = await query({
      operation: 'select', table: ORDER_TABLE,
      filters: [{ type: 'eq', column: 'id', value: orderId }], orders: [], selectColumns: '*', singleMode: 'maybeSingle',
    });
    return result.data || null;
  }

  async function updateOrder(orderId, values) {
    const result = await query({
      operation: 'update', table: ORDER_TABLE, values,
      filters: [{ type: 'eq', column: 'id', value: orderId }], orders: [], selectColumns: '*', singleMode: 'maybeSingle',
    });
    return result.data || null;
  }

  async function updateOrderIfStatus(orderId, expectedStatus, values) {
    const result = await query({
      operation: 'update', table: ORDER_TABLE, values,
      filters: [
        { type: 'eq', column: 'id', value: orderId },
        { type: 'eq', column: 'status', value: expectedStatus },
      ],
      orders: [], selectColumns: '*', singleMode: 'maybeSingle',
    });
    return result.data || null;
  }

  async function createApplicantNotification(order, type, title, message) {
    const now = new Date().toISOString();
    try {
      await query({
        operation: 'insert', table: 'notifications',
        values: {
          id: crypto.randomUUID(),
          recipient_id: order.requester_id,
          type,
          title,
          message,
          related_id: order.id,
          dedupe_key: `${order.requester_id}:${type}:${order.id}`,
          is_read: false,
          created_at: now,
          updated_at: now,
        },
        filters: [], orders: [], selectColumns: '*',
      });
    } catch (error) {
      console.error('[business-card-notification]', error instanceof Error ? error.message : error);
    }
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  }

  async function sendOrder(order) {
    if (sendingOrders.has(order.id)) throw Object.assign(new Error('이미 발송 처리 중입니다.'), { statusCode: 409 });
    if (order.status === 'sent') return order;
    sendingOrders.add(order.id);
    try {
      const settings = await getSettings();
      const config = mailConfiguration();
      if (!settings.recipientEmail || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(settings.recipientEmail)) {
        throw new Error('관리자 수신 이메일이 설정되지 않았습니다.');
      }
      if (!config.configured) throw new Error('SMTP 발송 설정이 완료되지 않았습니다.');
      if (!fs.existsSync(order.image_path)) throw new Error('발송할 명함 JPG 파일을 찾을 수 없습니다.');
      const fileBuffer = fs.readFileSync(order.image_path);
      const currentHash = crypto.createHash('sha256').update(fileBuffer).digest('hex');
      if (currentHash !== order.image_sha256) throw new Error('명함 JPG가 신청 이후 변경되어 발송을 중단했습니다.');

      await updateOrder(order.id, { status: 'sending', recipient_email: settings.recipientEmail, mail_error: '' });
      const transporter = nodemailer.createTransport({
        host: config.host,
        port: config.port,
        secure: config.secure,
        auth: { user: config.user, pass: config.password },
      });
      const card = typeof order.card_data === 'string' ? JSON.parse(order.card_data) : order.card_data;
      const result = await transporter.sendMail({
        from: config.from,
        to: settings.recipientEmail,
        subject: `[명함발주] ${order.requester_name} 님 명함 시안`,
        html: `<p>명함 발주를 요청합니다.</p><ul><li>신청자: ${escapeHtml(order.requester_name)}</li><li>소속: ${escapeHtml(order.requester_department)}</li><li>수량: ${escapeHtml(order.quantity)}매</li><li>이메일: ${escapeHtml(card.email)}</li><li>신청번호: ${escapeHtml(order.id)}</li></ul>`,
        attachments: [{ filename: `명함시안_${order.requester_name}.jpg`, path: order.image_path, contentType: 'image/jpeg' }],
      });
      return await updateOrder(order.id, {
        status: 'sent', sent_at: new Date().toISOString(), mail_message_id: String(result.messageId || ''), mail_error: '',
      });
    } catch (error) {
      await updateOrder(order.id, { status: 'send_failed', mail_error: String(error?.message || error).slice(0, 2000) });
      throw error;
    } finally {
      sendingOrders.delete(order.id);
    }
  }

  async function handle(req, res) {
    const requestUrl = new URL(req.url || '/', 'http://localhost');
    const pathname = requestUrl.pathname;
    if (!pathname.startsWith('/api/business-card/')) return false;

    try {
      if (pathname === '/api/business-card/session' && req.method === 'GET') {
        const session = requireSession(req, res);
        if (!session) return true;
        sendJson(res, 200, { user: session.user });
        return true;
      }
      if (pathname === '/api/business-card/session/logout' && req.method === 'POST') {
        const session = currentSession(req);
        if (session) sessions.delete(session.token);
        res.setHeader('Set-Cookie', `${SESSION_COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0`);
        sendJson(res, 200, { success: true });
        return true;
      }
      if (pathname === '/api/business-card/settings' && req.method === 'GET') {
        const session = requireSession(req, res);
        if (!session) return true;
        const settings = await getSettings();
        sendJson(res, 200, session.user.role === 'ADMIN' ? settings : { sendMode: settings.sendMode, mailConfigured: settings.mailConfigured });
        return true;
      }
      if (pathname === '/api/business-card/settings' && req.method === 'POST') {
        const session = requireSession(req, res, true);
        if (!session) return true;
        const body = await parseJsonBody(req, 16 * 1024);
        const sendMode = body.sendMode === 'automatic' ? 'automatic' : 'semi_automatic';
        const recipientEmail = String(body.recipientEmail || '').trim();
        if (recipientEmail && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(recipientEmail)) {
          throw Object.assign(new Error('수신 이메일 주소가 올바르지 않습니다.'), { statusCode: 400 });
        }
        await saveSetting(MODE_KEY, sendMode);
        await saveSetting(RECIPIENT_KEY, recipientEmail);
        sendJson(res, 200, await getSettings());
        return true;
      }
      if (pathname === '/api/business-card/orders' && req.method === 'GET') {
        const session = requireSession(req, res);
        if (!session) return true;
        const filters = session.user.role === 'ADMIN' ? [] : [{ type: 'eq', column: 'requester_id', value: session.user.id }];
        const result = await query({
          operation: 'select', table: ORDER_TABLE, filters,
          orders: [{ column: 'created_at', ascending: false }], selectColumns: '*', limitCount: 200,
        });
        sendJson(res, 200, { orders: result.data || [] });
        return true;
      }
      if (pathname === '/api/business-card/orders' && req.method === 'POST') {
        const session = requireSession(req, res);
        if (!session) return true;
        const body = await parseJsonBody(req, 6 * 1024 * 1024);
        const cardData = cleanCardData(body.cardData);
        const quantity = normalizeQuantity(body.quantity);
        const image = normalizeImage(body.imageDataUrl);
        const settings = await getSettings();
        let order = await enqueueOrderCreation(async () => {
          const nowDate = new Date();
          const now = nowDate.toISOString();
          const id = await nextOrderId(nowDate);
          fs.mkdirSync(imageDir, { recursive: true });
          const imagePath = path.join(imageDir, `${id}.jpg`);
          fs.writeFileSync(imagePath, image, { flag: 'wx' });
          const values = {
            id,
            requester_id: session.user.id,
            requester_name: session.user.name,
            requester_department: cardData.departmentKo,
            card_data: cardData,
            image_url: `/uploads/business-card-orders/${id}.jpg`,
            image_path: imagePath,
            image_sha256: crypto.createHash('sha256').update(image).digest('hex'),
            send_mode: settings.sendMode,
            status: settings.sendMode === 'automatic' ? 'approved' : 'pending_approval',
            recipient_email: settings.recipientEmail,
            quantity,
            approved_by: settings.sendMode === 'automatic' ? 'AUTO' : null,
            approved_at: settings.sendMode === 'automatic' ? now : null,
            created_at: now,
            updated_at: now,
          };
          const result = await query({ operation: 'insert', table: ORDER_TABLE, values, filters: [], orders: [], selectColumns: '*' });
          return Array.isArray(result.data) ? result.data[0] : result.data;
        });
        if (settings.sendMode === 'automatic') {
          try { order = await sendOrder(order); } catch (_error) { order = await getOrder(order.id); }
        }
        sendJson(res, 201, { order });
        return true;
      }

      const cancelMatch = pathname.match(/^\/api\/business-card\/orders\/([^/]+)\/cancel$/);
      if (cancelMatch && req.method === 'POST') {
        const session = requireSession(req, res);
        if (!session) return true;
        const order = await getOrder(decodeURIComponent(cancelMatch[1]));
        if (!order) throw Object.assign(new Error('신청 내역을 찾을 수 없습니다.'), { statusCode: 404 });
        if (order.requester_id !== session.user.id) throw Object.assign(new Error('본인이 신청한 명함만 취소할 수 있습니다.'), { statusCode: 403 });
        if (order.status !== 'pending_approval') throw Object.assign(new Error('승인 대기 중인 신청만 취소할 수 있습니다.'), { statusCode: 409 });
        const updated = await updateOrderIfStatus(order.id, 'pending_approval', {
          status: 'cancelled', cancelled_by: session.user.id, cancelled_at: new Date().toISOString(),
        });
        if (!updated) throw Object.assign(new Error('신청 상태가 변경되어 취소할 수 없습니다. 새로고침 후 확인해 주세요.'), { statusCode: 409 });
        sendJson(res, 200, { order: updated });
        return true;
      }

      const actionMatch = pathname.match(/^\/api\/business-card\/orders\/([^/]+)\/(approve|reject|retry)$/);
      if (actionMatch && req.method === 'POST') {
        const session = requireSession(req, res, true);
        if (!session) return true;
        const order = await getOrder(decodeURIComponent(actionMatch[1]));
        if (!order) throw Object.assign(new Error('신청 내역을 찾을 수 없습니다.'), { statusCode: 404 });
        const action = actionMatch[2];
        if (order.status === 'cancelled') throw Object.assign(new Error('신청자가 취소한 명함은 처리할 수 없습니다.'), { statusCode: 409 });
        if (order.status === 'rejected' && action !== 'reject') throw Object.assign(new Error('반려된 신청은 다시 처리할 수 없습니다. 새 신청을 이용해 주세요.'), { statusCode: 409 });
        if (action === 'reject') {
          if (order.status === 'sent') throw Object.assign(new Error('이미 발송된 신청은 반려할 수 없습니다.'), { statusCode: 409 });
          if (order.status === 'rejected') {
            sendJson(res, 200, { order });
            return true;
          }
          const body = await parseJsonBody(req, 8 * 1024);
          const reason = String(body.reason || '').trim().slice(0, 1000);
          const updated = await updateOrderIfStatus(order.id, order.status, {
            status: 'rejected', rejected_by: session.user.id, rejected_at: new Date().toISOString(), rejection_reason: reason,
          });
          if (!updated) throw Object.assign(new Error('신청 상태가 변경되어 반려할 수 없습니다. 새로고침 후 확인해 주세요.'), { statusCode: 409 });
          await createApplicantNotification(
            updated,
            'BUSINESS_CARD_REJECTED',
            '명함 신청이 반려되었습니다.',
            `신청번호 ${updated.id}: ${reason || '신청 내용을 확인해 주세요.'}`,
          );
          sendJson(res, 200, { order: updated });
          return true;
        }
        if (order.status === 'sent') {
          sendJson(res, 200, { order });
          return true;
        }
        const expectedStatus = action === 'approve' ? 'pending_approval' : 'send_failed';
        if (order.status !== expectedStatus) {
          throw Object.assign(new Error(action === 'approve' ? '승인 대기 중인 신청만 승인할 수 있습니다.' : '발송 실패한 신청만 재발송할 수 있습니다.'), { statusCode: 409 });
        }
        const approved = await updateOrderIfStatus(order.id, expectedStatus, {
          status: 'approved', approved_by: session.user.id, approved_at: new Date().toISOString(), rejection_reason: '',
        });
        if (!approved) throw Object.assign(new Error('신청 상태가 변경되었습니다. 새로고침 후 다시 처리해 주세요.'), { statusCode: 409 });
        if (action === 'approve') {
          await createApplicantNotification(
            approved,
            'BUSINESS_CARD_APPROVED',
            '명함 신청이 승인되었습니다.',
            `신청번호 ${approved.id}의 명함 발주가 승인되었습니다.`,
          );
        }
        try {
          const sent = await sendOrder(approved);
          sendJson(res, 200, { order: sent });
        } catch (error) {
          sendJson(res, 502, { error: String(error?.message || error), order: await getOrder(order.id) });
        }
        return true;
      }

      sendJson(res, 404, { error: 'Not Found' });
      return true;
    } catch (error) {
      console.error('[business-card]', error instanceof Error ? error.message : error);
      sendJson(res, error?.statusCode || 500, { error: error instanceof Error ? error.message : String(error) });
      return true;
    }
  }

  return {
    handle,
    ensureSchema,
    getSession(req) {
      return currentSession(req);
    },
    issueSession(res, user) {
      const token = crypto.randomBytes(32).toString('base64url');
      sessions.set(token, {
        user: { id: String(user.id), name: String(user.name || user.id), role: user.role === 'ADMIN' ? 'ADMIN' : 'USER', department: String(user.department || ''), team: String(user.team || '') },
        expiresAt: Date.now() + SESSION_TTL_MS,
      });
      res.setHeader('Set-Cookie', `${SESSION_COOKIE}=${encodeURIComponent(token)}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${Math.floor(SESSION_TTL_MS / 1000)}`);
    },
  };
}

module.exports = { createBusinessCardOrderHandler };
