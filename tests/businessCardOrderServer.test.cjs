const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createBusinessCardOrderHandler } = require('../businessCardOrderServer.cjs');

function createMemoryQuery() {
  const tables = { site_settings: [], business_card_orders: [], notifications: [] };
  const matches = (row, filters = []) => filters.every(filter => String(row[filter.column] ?? '') === String(filter.value ?? ''));
  return {
    tables,
    async run(payload) {
      const rows = tables[payload.table] || (tables[payload.table] = []);
      if (payload.operation === 'select') {
        let data = rows.filter(row => matches(row, payload.filters));
        for (const order of payload.orders || []) {
          data = [...data].sort((left, right) => String(left[order.column]).localeCompare(String(right[order.column])) * (order.ascending ? 1 : -1));
        }
        if (payload.singleMode) return { data: data[0] || null };
        return { data };
      }
      if (payload.operation === 'insert') {
        const inserted = { ...payload.values };
        rows.push(inserted);
        return { data: [inserted] };
      }
      if (payload.operation === 'update') {
        const index = rows.findIndex(row => matches(row, payload.filters));
        if (index < 0) return { data: null };
        rows[index] = { ...rows[index], ...payload.values, updated_at: new Date().toISOString() };
        return { data: rows[index] };
      }
      if (payload.operation === 'upsert') {
        const index = rows.findIndex(row => row.setting_key === payload.values.setting_key);
        if (index < 0) rows.push({ ...payload.values });
        else rows[index] = { ...rows[index], ...payload.values };
        return { data: index < 0 ? rows[rows.length - 1] : rows[index] };
      }
      throw new Error(`Unsupported operation: ${payload.operation}`);
    },
  };
}

function createResponse() {
  return {
    statusCode: 0,
    headers: {},
    payload: null,
    setHeader(name, value) { this.headers[name.toLowerCase()] = value; },
    writeHead(statusCode, headers = {}) { this.statusCode = statusCode; Object.assign(this.headers, headers); },
    end(body) { this.payload = body ? JSON.parse(body) : null; },
  };
}

function request(method, url, cookie = '', body = {}) {
  return { method, url, headers: { cookie }, body };
}

test('semi-automatic orders persist and failed mail remains retryable', async () => {
  const previousProvider = process.env.DB_PROVIDER;
  const previousMailEnabled = process.env.BUSINESS_CARD_MAIL_ENABLED;
  process.env.DB_PROVIDER = 'local';
  process.env.BUSINESS_CARD_MAIL_ENABLED = 'false';
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'hfk-business-card-test-'));
  const memory = createMemoryQuery();
  const sendJson = (res, statusCode, payload) => {
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(payload));
  };
  const handler = createBusinessCardOrderHandler({
    runQuery: payload => memory.run(payload),
    withPostgresTransaction: async callback => callback({ query: async () => ({ rows: [] }) }),
    parseJsonBody: async req => req.body,
    sendJson,
    uploadsDir: tempRoot,
  });

  try {
    const userLogin = createResponse();
    handler.issueSession(userLogin, { id: 'USER1', name: '테스트직원', role: 'USER', department: '영업부', team: '영업1팀' });
    const userCookie = String(userLogin.headers['set-cookie']).split(';')[0];
    const adminLogin = createResponse();
    handler.issueSession(adminLogin, { id: 'ADMIN1', name: '관리자', role: 'ADMIN', department: '전산팀' });
    const adminCookie = String(adminLogin.headers['set-cookie']).split(';')[0];
    const otherUserLogin = createResponse();
    handler.issueSession(otherUserLogin, { id: 'USER2', name: '다른 직원', role: 'USER', department: '영업부' });
    const otherUserCookie = String(otherUserLogin.headers['set-cookie']).split(';')[0];

    const settingsResponse = createResponse();
    await handler.handle(request('POST', '/api/business-card/settings', adminCookie, {
      sendMode: 'semi_automatic', recipientEmail: 'vendor@example.com',
    }), settingsResponse);
    assert.equal(settingsResponse.statusCode, 200);
    assert.equal(settingsResponse.payload.sendMode, 'semi_automatic');

    const jpeg = Buffer.from([0xff, 0xd8, 0xff, 0xd9]).toString('base64');
    const createResponseValue = createResponse();
    await handler.handle(request('POST', '/api/business-card/orders', userCookie, {
      cardData: {
        koreanName: '테스트직원', englishName: 'TEST USER', companyKo: '한일후지코리아(주)',
        companyEn: 'WRONG COMPANY NAME',
        departmentKo: '영업1팀', mobilePhone: '010-0000-0000', email: 'user@example.com',
        addressKo: 'CUSTOM KOREAN ADDRESS 123',
        addressEn: '123, Custom Applicant Address, Busan, Korea',
        postalCode: '12345',
        website: 'wrong.example.com',
      },
      imageDataUrl: `data:image/jpeg;base64,${jpeg}`,
    }), createResponseValue);
    assert.equal(createResponseValue.statusCode, 201);
    assert.equal(createResponseValue.payload.order.status, 'pending_approval');
    assert.equal(createResponseValue.payload.order.quantity, 200);
    assert.equal(createResponseValue.payload.order.card_data.companyEn, 'HANIL-FUJI(Korea) CO., LTD.');
    assert.equal(createResponseValue.payload.order.card_data.addressKo, 'CUSTOM KOREAN ADDRESS 123');
    assert.equal(createResponseValue.payload.order.card_data.addressEn, '123, Custom Applicant Address, Busan, Korea');
    assert.equal(createResponseValue.payload.order.card_data.postalCode, '12345');
    assert.equal(createResponseValue.payload.order.card_data.website, 'www.hanil-fuji.com');
    const koreaDate = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(new Date()).replaceAll('-', '');
    assert.equal(createResponseValue.payload.order.id, `${koreaDate}-1`);
    assert.equal(memory.tables.business_card_orders.length, 1);
    assert.ok(fs.existsSync(memory.tables.business_card_orders[0].image_path));

    const secondCreateResponse = createResponse();
    await handler.handle(request('POST', '/api/business-card/orders', userCookie, {
      cardData: {
        koreanName: 'SECOND USER', englishName: 'SECOND USER', companyKo: '(주)후지글로벌로지스틱',
        companyEn: 'WRONG COMPANY NAME',
        departmentKo: 'SALES', mobilePhone: '010-1111-1111', email: 'second@example.com',
        addressKo: 'CUSTOM KOREAN ADDRESS 456',
        addressEn: '456, Another Custom Address, Changwon, Korea',
        postalCode: '67890',
        website: 'wrong.example.com',
      },
      quantity: 400,
      imageDataUrl: `data:image/jpeg;base64,${jpeg}`,
    }), secondCreateResponse);
    assert.equal(secondCreateResponse.statusCode, 201);
    assert.equal(secondCreateResponse.payload.order.id, `${koreaDate}-2`);
    assert.equal(secondCreateResponse.payload.order.card_data.companyEn, 'Fuji Global Logistics Co., Ltd.');
    assert.equal(secondCreateResponse.payload.order.card_data.addressKo, 'CUSTOM KOREAN ADDRESS 456');
    assert.equal(secondCreateResponse.payload.order.card_data.addressEn, '456, Another Custom Address, Changwon, Korea');
    assert.equal(secondCreateResponse.payload.order.card_data.postalCode, '67890');
    assert.equal(secondCreateResponse.payload.order.card_data.website, 'www.fujiglobal.co.kr');
    assert.equal(secondCreateResponse.payload.order.quantity, 400);
    assert.equal(memory.tables.business_card_orders.length, 2);

    const thirdCreateResponse = createResponse();
    await handler.handle(request('POST', '/api/business-card/orders', userCookie, {
      cardData: {
        koreanName: 'CANCEL USER', englishName: 'CANCEL USER', companyKo: '한일후지코리아(주)',
        companyEn: 'HANIL-FUJI(Korea) CO., LTD.', departmentKo: 'SALES', mobilePhone: '010-3333-3333', email: 'cancel@example.com',
      },
      imageDataUrl: `data:image/jpeg;base64,${jpeg}`,
    }), thirdCreateResponse);
    assert.equal(thirdCreateResponse.statusCode, 201);
    assert.equal(thirdCreateResponse.payload.order.id, `${koreaDate}-3`);
    assert.equal(memory.tables.business_card_orders.length, 3);

    const invalidQuantityResponse = createResponse();
    await handler.handle(request('POST', '/api/business-card/orders', userCookie, {
      cardData: {
        koreanName: 'INVALID QUANTITY', englishName: 'INVALID QUANTITY', companyKo: '한일후지코리아(주)',
        companyEn: 'HANIL-FUJI(Korea) CO., LTD.', departmentKo: 'SALES', mobilePhone: '010-4444-4444', email: 'quantity@example.com',
      },
      quantity: 300,
      imageDataUrl: `data:image/jpeg;base64,${jpeg}`,
    }), invalidQuantityResponse);
    assert.equal(invalidQuantityResponse.statusCode, 400);
    assert.match(invalidQuantityResponse.payload.error, /수량/);
    assert.equal(memory.tables.business_card_orders.length, 3);

    const unsupportedCompanyResponse = createResponse();
    await handler.handle(request('POST', '/api/business-card/orders', userCookie, {
      cardData: {
        koreanName: 'BLOCKED USER', englishName: 'BLOCKED USER', companyKo: '(주)키토스',
        companyEn: 'KITOS CO., LTD.', departmentKo: 'TEAM', mobilePhone: '010-2222-2222', email: 'blocked@example.com',
      },
      imageDataUrl: `data:image/jpeg;base64,${jpeg}`,
    }), unsupportedCompanyResponse);
    assert.equal(unsupportedCompanyResponse.statusCode, 400);
    assert.match(unsupportedCompanyResponse.payload.error, /한일후지코리아|후지글로벌로지스틱/);
    assert.equal(memory.tables.business_card_orders.length, 3);

    const otherUserCancelResponse = createResponse();
    await handler.handle(request('POST', `/api/business-card/orders/${thirdCreateResponse.payload.order.id}/cancel`, otherUserCookie), otherUserCancelResponse);
    assert.equal(otherUserCancelResponse.statusCode, 403);
    assert.equal(memory.tables.business_card_orders[2].status, 'pending_approval');

    const cancelResponse = createResponse();
    await handler.handle(request('POST', `/api/business-card/orders/${thirdCreateResponse.payload.order.id}/cancel`, userCookie), cancelResponse);
    assert.equal(cancelResponse.statusCode, 200);
    assert.equal(cancelResponse.payload.order.status, 'cancelled');
    assert.equal(cancelResponse.payload.order.cancelled_by, 'USER1');
    assert.ok(cancelResponse.payload.order.cancelled_at);

    const approveCancelledResponse = createResponse();
    await handler.handle(request('POST', `/api/business-card/orders/${thirdCreateResponse.payload.order.id}/approve`, adminCookie), approveCancelledResponse);
    assert.equal(approveCancelledResponse.statusCode, 409);

    const approveResponse = createResponse();
    await handler.handle(request('POST', `/api/business-card/orders/${createResponseValue.payload.order.id}/approve`, adminCookie), approveResponse);
    assert.equal(approveResponse.statusCode, 502);
    assert.equal(memory.tables.business_card_orders[0].status, 'send_failed');
    assert.match(memory.tables.business_card_orders[0].mail_error, /SMTP/);
    assert.equal(memory.tables.notifications.length, 1);
    assert.equal(memory.tables.notifications[0].type, 'BUSINESS_CARD_APPROVED');
    assert.equal(memory.tables.notifications[0].recipient_id, 'USER1');

    const rejectResponse = createResponse();
    await handler.handle(request('POST', `/api/business-card/orders/${secondCreateResponse.payload.order.id}/reject`, adminCookie, {
      reason: '전화번호를 확인해 주세요.',
    }), rejectResponse);
    assert.equal(rejectResponse.statusCode, 200);
    assert.equal(rejectResponse.payload.order.status, 'rejected');
    assert.equal(memory.tables.notifications.length, 2);
    assert.equal(memory.tables.notifications[1].type, 'BUSINESS_CARD_REJECTED');
    assert.match(memory.tables.notifications[1].message, /전화번호/);

    const userListResponse = createResponse();
    await handler.handle(request('GET', '/api/business-card/orders', userCookie), userListResponse);
    assert.equal(userListResponse.statusCode, 200);
    assert.equal(userListResponse.payload.orders.length, 3);
  } finally {
    const resolvedTemp = path.resolve(tempRoot);
    if (!resolvedTemp.startsWith(path.resolve(os.tmpdir()))) throw new Error('Unsafe temp cleanup target.');
    fs.rmSync(resolvedTemp, { recursive: true, force: true });
    if (previousProvider === undefined) delete process.env.DB_PROVIDER; else process.env.DB_PROVIDER = previousProvider;
    if (previousMailEnabled === undefined) delete process.env.BUSINESS_CARD_MAIL_ENABLED; else process.env.BUSINESS_CARD_MAIL_ENABLED = previousMailEnabled;
  }
});
