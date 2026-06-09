-- ============================================================
--  HOVER3D — Migration 001: Schema inicial
--  Rodar no Supabase: Dashboard → SQL Editor → New query → Cole e execute
-- ============================================================

-- ── Tabela: events ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.events (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title                 text NOT NULL,
    date                  date NOT NULL,
    time                  time NOT NULL,
    location              text DEFAULT '',
    description           text DEFAULT '',
    email_sent_day_before boolean DEFAULT false,
    email_sent_day_of     boolean DEFAULT false,
    created_at            timestamptz DEFAULT now()
);

-- Índice para busca por usuário e data (cron usa bastante)
CREATE INDEX IF NOT EXISTS events_user_date ON public.events (user_id, date);

-- RLS: cada usuário vê e altera apenas seus próprios eventos
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "events_select_own" ON public.events
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY IF NOT EXISTS "events_insert_own" ON public.events
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY IF NOT EXISTS "events_delete_own" ON public.events
    FOR DELETE USING (auth.uid() = user_id);

-- O backend usa a service key para o cron — não precisa de policy para UPDATE/cron
-- mas adicionamos para o backend poder marcar emails como enviados
CREATE POLICY IF NOT EXISTS "events_update_own" ON public.events
    FOR UPDATE USING (auth.uid() = user_id);


-- ── Tabela: profiles ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.profiles (
    id                    uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    ativo                 boolean DEFAULT false,
    plano                 text DEFAULT 'basico',
    vencimento            date,
    notification_email    text,
    notification_accepted boolean DEFAULT false,
    created_at            timestamptz DEFAULT now()
);

-- RLS: cada usuário acessa apenas seu próprio perfil
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "profiles_select_own" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY IF NOT EXISTS "profiles_insert_own" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

CREATE POLICY IF NOT EXISTS "profiles_update_own" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);
