const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { createBusinessCardOrderHandler } = require('./businessCardOrderServer.cjs');

const ROOT = __dirname;
const DIST_DIR = path.join(ROOT, 'dist');
const DATA_DIR = path.join(ROOT, 'data');
const DATA_FILE = path.join(DATA_DIR, 'dev-db.json');
const UPLOADS_DIR = path.join(ROOT, 'uploads');
const API_ONLY = process.argv.includes('--api-only');

function loadEnv(filePath) {
  if (!fs.existsSync(filePath)) return;
  for (const line of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const separator = trimmed.indexOf('=');
    if (separator < 1) continue;
    const key = trimmed.slice(0, separator).trim();
    if (!(key in process.env)) process.env[key] = trimmed.slice(separator + 1).trim();
  }
}

loadEnv(path.join(ROOT, '.env'));
process.env.DB_PROVIDER = process.env.DB_PROVIDER || 'local';
process.env.BUSINESS_CARD_MAIL_ENABLED = process.env.BUSINESS_CARD_MAIL_ENABLED || 'false';

const PORT = Number(process.env.BUSINESS_CARD_STANDALONE_PORT || 3101);
const DEFAULT_DB = { site_settings: [], business_card_orders: [], notifications: [] };

function ensureData() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
  if (!fs.existsSync(DATA_FILE)) fs.writeFileSync(DATA_FILE, JSON.stringify(DEFAULT_DB, null, 2), 'utf8');
}

function readDb() {
  ensureData();
  return { ...DEFAULT_DB, ...JSON.parse(fs.readFileSync(DATA_FILE, 'utf8').replace(/^\uFEFF/, '')) };
}

function writeDb(database) {
  ensureData();
  const temporary = `${DATA_FILE}.tmp`;
  fs.writeFileSync(temporary, JSON.stringify(database, null, 2), 'utf8');
  fs.renameSync(temporary, DATA_FILE);
}

function matches(row, filters = []) {
  return filters.every(filter => filter.type !== 'eq' || String(row[filter.column] ?? '') === String(filter.value ?? ''));
}

async function runQuery(payload) {
  const database = readDb();
  const rows = database[payload.table] || (database[payload.table] = []);

  if (payload.operation === 'select') {
    let selected = rows.filter(row => matches(row, payload.filters));
    for (const order of payload.orders || []) {
      selected = [...selected].sort((left, right) => String(left[order.column] ?? '').localeCompare(String(right[order.column] ?? '')) * (order.ascending ? 1 : -1));
    }
    if (payload.limitCount) selected = selected.slice(0, payload.limitCount);
    return { data: payload.singleMode ? (selected[0] || null) : selected };
  }

  if (payload.operation === 'insert') {
    const values = Array.isArray(payload.values) ? payload.values : [payload.values];
    const inserted = values.map(value => ({ ...value }));
    rows.push(...inserted);
    writeDb(database);
    return { data: inserted };
  }

  if (payload.operation === 'update') {
    const updated = [];
    for (let index = 0; index < rows.length; index += 1) {
      if (!matches(rows[index], payload.filters)) continue;
      rows[index] = { ...rows[index], ...payload.values, updated_at: new Date().toISOString() };
      updated.push(rows[index]);
    }
    writeDb(database);
    return { data: payload.singleMode ? (updated[0] || null) : updated };
  }

  if (payload.operation === 'upsert') {
    const conflictKey = payload.options?.onConflict || 'id';
    const index = rows.findIndex(row => String(row[conflictKey] ?? '') === String(payload.values[conflictKey] ?? ''));
    if (index < 0) rows.push({ ...payload.values });
    else rows[index] = { ...rows[index], ...payload.values };
    writeDb(database);
    const saved = index < 0 ? rows[rows.length - 1] : rows[index];
    return { data: payload.singleMode ? saved : [saved] };
  }

  return { error: `Unsupported operation: ${payload.operation}` };
}

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

function parseJsonBody(req, maximumBytes = 16 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', chunk => {
      size += chunk.length;
      if (size > maximumBytes) {
        reject(Object.assign(new Error('요청 데이터가 너무 큽니다.'), { statusCode: 413 }));
        req.destroy();
        return;
      }
      chunks.push(Buffer.from(chunk));
    });
    req.on('end', () => {
      try {
        const body = Buffer.concat(chunks).toString('utf8');
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(Object.assign(error, { statusCode: 400 }));
      }
    });
    req.on('error', reject);
  });
}

function safePath(base, requestPath) {
  const resolvedBase = path.resolve(base);
  const resolved = path.resolve(base, requestPath.replace(/^[/\\]+/, ''));
  return resolved === resolvedBase || resolved.startsWith(`${resolvedBase}${path.sep}`) ? resolved : null;
}

function serveFile(res, filePath) {
  if (!filePath || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) return false;
  const extension = path.extname(filePath).toLowerCase();
  const contentTypes = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.woff2': 'font/woff2',
  };
  res.writeHead(200, { 'Content-Type': contentTypes[extension] || 'application/octet-stream' });
  fs.createReadStream(filePath).pipe(res);
  return true;
}

const orders = createBusinessCardOrderHandler({
  runQuery,
  withPostgresTransaction: async callback => callback({ query: async () => ({ rows: [] }) }),
  parseJsonBody,
  sendJson,
  uploadsDir: UPLOADS_DIR,
});

const server = http.createServer(async (req, res) => {
  const pathname = new URL(req.url || '/', 'http://localhost').pathname;

  if (pathname === '/api/dev/session' && req.method === 'POST') {
    try {
      const body = await parseJsonBody(req, 8 * 1024);
      const isAdmin = body.role === 'ADMIN';
      const user = {
        id: isAdmin ? 'TEAM_ADMIN' : 'TEAM_USER',
        name: isAdmin ? '관리자' : '홍길동',
        role: isAdmin ? 'ADMIN' : 'USER',
        department: isAdmin ? '전산팀' : '재무관리사업부',
        team: isAdmin ? '' : '인사총무팀',
      };
      orders.issueSession(res, user);
      sendJson(res, 200, { user });
    } catch (error) {
      sendJson(res, error.statusCode || 400, { error: error.message || String(error) });
    }
    return;
  }

  if (pathname === '/api/health' && req.method === 'GET') {
    sendJson(res, 200, { status: 'ok', mode: 'standalone-development' });
    return;
  }

  if (await orders.handle(req, res)) return;

  if (pathname.startsWith('/uploads/')) {
    const filePath = safePath(UPLOADS_DIR, decodeURIComponent(pathname.slice('/uploads/'.length)));
    if (!serveFile(res, filePath)) sendJson(res, 404, { error: 'File not found' });
    return;
  }

  if (pathname.startsWith('/api/') || API_ONLY) {
    sendJson(res, 404, { error: 'Not Found' });
    return;
  }

  const requested = pathname === '/' ? 'index.html' : decodeURIComponent(pathname.slice(1));
  const filePath = safePath(DIST_DIR, requested);
  if (serveFile(res, filePath)) return;
  if (serveFile(res, path.join(DIST_DIR, 'index.html'))) return;
  res.writeHead(503, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('먼저 npm run build를 실행해 주세요.');
});

server.listen(PORT, '127.0.0.1', () => {
  ensureData();
  console.log(`명함발주 개발 API: http://127.0.0.1:${PORT}`);
});
