# ============================================================
#  HOVER3D — Backend (FastAPI)
# ============================================================

import os
import httpx
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

API_KEY       = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL         = os.environ.get("HOVER3D_MODEL", "claude-haiku-4-5-20251001").strip()
SUPABASE_URL  = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "").strip()
RESEND_KEY    = os.environ.get("RESEND_API_KEY", "").strip()
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", "").strip()

app = FastAPI(title="Hover3D Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers Supabase (REST direto) ───────────────────────────

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def sb_url(table: str, qs: str = "") -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}{qs}"

def sb_check():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=503, detail="Supabase não configurado.")


def send_alert(event: dict, when: str):
    import resend
    resend.api_key = RESEND_KEY

    date_obj  = datetime.strptime(event["date"], "%Y-%m-%d")
    date_br   = date_obj.strftime("%d/%m/%Y")
    time_str  = event["time"][:5]
    title     = event["title"]
    location  = event.get("location") or ""
    desc      = event.get("description") or ""

    if when == "today":
        subject      = f"🔔 HOJE: {title} às {time_str}"
        badge        = "Hoje"
        badge_color  = "#8B5CF6"
    else:
        subject      = f"📅 Amanhã: {title}"
        badge        = "Amanhã"
        badge_color  = "#6D28D9"

    location_row = f"<p style='margin:6px 0;color:#8B82A8;font-size:14px;'>📍 {location}</p>" if location else ""
    desc_row     = f"<p style='margin:12px 0 0;color:#8B82A8;font-size:13px;'>{desc}</p>" if desc else ""

    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0D0B14;font-family:Arial,sans-serif;">
<div style="max-width:560px;margin:32px auto;background:#13101E;border-radius:12px;overflow:hidden;border:1px solid #2A2240;">
  <div style="background:linear-gradient(135deg,#8B5CF6,#6D28D9);padding:24px 32px;">
    <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">Hover3D</h1>
    <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">Lembrete de evento — Artemis</p>
  </div>
  <div style="padding:32px;">
    <div style="background:#1C1829;border:1px solid #2A2240;border-radius:10px;padding:24px;">
      <span style="background:{badge_color};color:#fff;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;">{badge}</span>
      <h2 style="color:#EDE9FF;font-size:20px;margin:14px 0 10px;">{title}</h2>
      <p style="margin:6px 0;color:#8B82A8;font-size:14px;">📅 {date_br}</p>
      <p style="margin:6px 0;color:#8B82A8;font-size:14px;">🕐 {time_str}</p>
      {location_row}
      {desc_row}
    </div>
  </div>
</div>
</body></html>"""

    resend.Emails.send({
        "from": "Hover3D <onboarding@resend.dev>",
        "to": [EMAIL_DESTINO],
        "subject": subject,
        "html": html,
    })


# ── Models ───────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    character: str
    service:   str
    category:  str
    occasion:  str
    tone:      str
    company:   str = "nossa empresa"
    region:    str = "nossa região"


class EventCreate(BaseModel):
    title:       str
    date:        str
    time:        str
    location:    str = ""
    description: str = ""


# ── Rotas: saúde ─────────────────────────────────────────────

@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok", "ai": "online" if API_KEY else "no_key", "model": MODEL}


# ── Rotas: IA ────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é um especialista em marketing para redes sociais, focado em \
empresas de personagens vivos e animação de eventos no Brasil.

Crie um post de Instagram seguindo estas regras:
- Texto em português brasileiro, natural e envolvente
- Use emojis com moderação e bom gosto
- Inclua uma chamada para ação (CTA) clara
- Tom adequado ao solicitado
- Entre 3 e 6 linhas
- NÃO inclua hashtags no corpo (serão adicionadas separadamente)
- Responda APENAS com o texto do post, sem comentários"""


def build_prompt(req: GenerateRequest) -> str:
    return f"""Crie um post de Instagram:
- Personagem: {req.character}
- Serviço: {req.service}
- Tipo de post: {req.category}
- Ocasião: {req.occasion}
- Tom de voz: {req.tone}
- Empresa: {req.company}
- Região de atuação: {req.region}"""


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY não configurada.")
    try:
        import anthropic
        client  = anthropic.Anthropic(api_key=API_KEY)
        message = client.messages.create(
            model=MODEL, max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(req)}],
        )
        text  = message.content[0].text.strip()
        usage = {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens}
        return {"success": True, "text": text, "usage": usage}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na geração: {e}")


# ── Rotas: eventos ───────────────────────────────────────────

@app.get("/api/events")
def list_events():
    sb_check()
    with httpx.Client() as client:
        res = client.get(sb_url("events", "?select=*&order=date.asc,time.asc"), headers=sb_headers())
        res.raise_for_status()
        return res.json()


@app.post("/api/events", status_code=201)
def create_event(ev: EventCreate):
    sb_check()
    with httpx.Client() as client:
        res = client.post(sb_url("events"), headers=sb_headers(), json=ev.model_dump())
        res.raise_for_status()
        return res.json()[0]


@app.delete("/api/events/{event_id}", status_code=204)
def delete_event(event_id: str):
    sb_check()
    with httpx.Client() as client:
        res = client.delete(sb_url("events", f"?id=eq.{event_id}"), headers=sb_headers())
        res.raise_for_status()


# ── Rota: cron ───────────────────────────────────────────────

@app.get("/api/cron/check-events")
def check_events():
    if not RESEND_KEY or not EMAIL_DESTINO:
        raise HTTPException(status_code=503, detail="Resend ou EMAIL_DESTINO não configurados.")

    sb_check()
    br_tz    = ZoneInfo("America/Sao_Paulo")
    today    = datetime.now(br_tz).date()
    tomorrow = today + timedelta(days=1)
    sent     = []

    with httpx.Client() as client:
        today_evs = client.get(
            sb_url("events", f"?select=*&date=eq.{today.isoformat()}&email_sent_day_of=eq.false"),
            headers=sb_headers()
        ).json()

        tomorrow_evs = client.get(
            sb_url("events", f"?select=*&date=eq.{tomorrow.isoformat()}&email_sent_day_before=eq.false"),
            headers=sb_headers()
        ).json()

        for ev in today_evs:
            try:
                send_alert(ev, "today")
                client.patch(sb_url("events", f"?id=eq.{ev['id']}"), headers=sb_headers(), json={"email_sent_day_of": True})
                sent.append(f"hoje:{ev['title']}")
            except Exception as e:
                sent.append(f"erro:{ev['title']}:{e}")

        for ev in tomorrow_evs:
            try:
                send_alert(ev, "tomorrow")
                client.patch(sb_url("events", f"?id=eq.{ev['id']}"), headers=sb_headers(), json={"email_sent_day_before": True})
                sent.append(f"amanha:{ev['title']}")
            except Exception as e:
                sent.append(f"erro:{ev['title']}:{e}")

    return {"sent": sent, "total": len(sent)}


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Hover3D — Backend")
    print(f"  IA:       {'online' if API_KEY else 'sem chave'}")
    print(f"  Supabase: {'ok' if SUPABASE_URL else 'sem chave'}")
    print(f"  Resend:   {'ok' if RESEND_KEY else 'sem chave'}")
    print("  http://127.0.0.1:8000")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000)
