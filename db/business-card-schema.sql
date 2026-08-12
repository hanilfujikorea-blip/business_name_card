-- 기존 포털로 병합할 때 참고하는 명함발주 전용 테이블입니다.
-- 독립 개발 서버는 이 SQL 대신 data/dev-db.json을 사용합니다.

create schema if not exists ksys;

create table if not exists ksys.hr_portal_business_card_orders (
  id varchar(64) primary key,
  requester_id varchar(100) not null,
  requester_name varchar(200) not null,
  requester_department varchar(300) not null default '',
  card_data jsonb not null default '{}'::jsonb,
  image_url text not null,
  image_path text not null,
  image_sha256 varchar(64) not null,
  send_mode varchar(24) not null default 'semi_automatic',
  status varchar(32) not null default 'pending_approval',
  recipient_email text not null default '',
  quantity integer not null default 200,
  approved_by varchar(100),
  approved_at timestamptz,
  rejected_by varchar(100),
  rejected_at timestamptz,
  rejection_reason text,
  cancelled_by varchar(100),
  cancelled_at timestamptz,
  sent_at timestamptz,
  mail_message_id text,
  mail_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint ck_hr_portal_business_card_orders_quantity check (quantity between 1 and 100000),
  constraint ck_hr_portal_business_card_orders_status check (
    status in ('pending_approval', 'approved', 'sending', 'sent', 'send_failed', 'rejected', 'cancelled')
  )
);

create index if not exists idx_hr_portal_business_card_orders_created
  on ksys.hr_portal_business_card_orders (created_at desc);

create index if not exists idx_hr_portal_business_card_orders_status
  on ksys.hr_portal_business_card_orders (status, created_at desc);
