-- ============================================================
--  HOVER3D — Migration 002: Colunas de notificação em profiles
--  Rodar APENAS se a tabela profiles já existia antes da migration 001
--  (se rodou a 001 do zero, essas colunas já existem — não precisa desta)
-- ============================================================

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS notification_email    text,
    ADD COLUMN IF NOT EXISTS notification_accepted boolean DEFAULT false;
