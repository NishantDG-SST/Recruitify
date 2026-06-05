-- Seed default organizations
INSERT INTO organizations (id, name) VALUES ('11111111-1111-1111-1111-111111111111', 'Demo Org 1') ON CONFLICT DO NOTHING;
INSERT INTO organizations (id, name) VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Org 2') ON CONFLICT DO NOTHING;

-- Seed default users
INSERT INTO users (id, org_id, email, full_name, status) 
VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'demo1@example.com', 'Demo User 1', 'active') 
ON CONFLICT DO NOTHING;

INSERT INTO users (id, org_id, email, full_name, status) 
VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'demo2@example.com', 'Demo User 2', 'active') 
ON CONFLICT DO NOTHING;
