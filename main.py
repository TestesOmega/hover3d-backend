# ============================================================
#  HOVER3D — Backend (FastAPI)
# ============================================================

import os
import re
import hmac
import hashlib
import json
import httpx
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

API_KEY                  = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL                    = os.environ.get("HOVER3D_MODEL", "claude-haiku-4-5-20251001").strip()
SUPABASE_URL             = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY             = os.environ.get("SUPABASE_KEY", "").strip()
BREVO_KEY                = os.environ.get("BREVO_API_KEY", "").strip()
EMAIL_DESTINO            = os.environ.get("EMAIL_DESTINO", "").strip()
CRON_SECRET              = os.environ.get("CRON_SECRET", "").strip()
BITIBRIDGE_API_KEY       = os.environ.get("BITIBRIDGE_API_KEY", "").strip()
BITIBRIDGE_WEBHOOK_SECRET = os.environ.get("BITIBRIDGE_WEBHOOK_SECRET", "").strip()
PLANO_VALOR              = int(os.environ.get("PLANO_VALOR", "3000"))  # centavos (R$ 30,00)
BITIBRIDGE_URL           = "https://api.bitibridge.com/functions/v1"

app = FastAPI(title="Hover3D Backend")

ALLOWED_ORIGINS = [
    "https://hover3d-frontend.vercel.app",
    "http://localhost:5173",
    "http://localhost:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
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

def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido.")
    token = authorization[7:]
    with httpx.Client() as client:
        res = client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}"},
        )
        if res.status_code != 200:
            raise HTTPException(status_code=401, detail="Não autenticado.")
        return res.json()


def send_confirmation(event: dict, email_destino: str):
    date_br  = datetime.strptime(event["date"], "%Y-%m-%d").strftime("%d/%m/%Y")
    time_str = event["time"][:5]
    title    = event["title"]
    location = event.get("location") or ""
    location_row = f"<p style='margin:6px 0;color:#8B82A8;font-size:14px;'>📍 {location}</p>" if location else ""

    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0D0B14;font-family:Arial,sans-serif;">
<div style="max-width:560px;margin:32px auto;background:#13101E;border-radius:12px;overflow:hidden;border:1px solid #2A2240;">
  <div style="background:linear-gradient(135deg,#8B5CF6,#6D28D9);padding:24px 32px;">
    <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">Hover3D</h1>
    <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">Evento cadastrado com sucesso</p>
  </div>
  <div style="padding:32px;">
    <div style="background:#1C1829;border:1px solid #2A2240;border-radius:10px;padding:24px;">
      <span style="background:#22c55e;color:#fff;font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;">✓ Cadastrado</span>
      <h2 style="color:#EDE9FF;font-size:20px;margin:14px 0 10px;">{title}</h2>
      <p style="margin:6px 0;color:#8B82A8;font-size:14px;">📅 {date_br}</p>
      <p style="margin:6px 0;color:#8B82A8;font-size:14px;">🕐 {time_str}</p>
      {location_row}
    </div>
    <p style="color:#8B82A8;font-size:13px;margin-top:20px;line-height:1.6;">
      Você receberá lembretes automáticos no dia anterior e no dia do evento, às 4h da manhã.
    </p>
  </div>
</div>
</body></html>"""

    with httpx.Client() as client:
        res = client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
            json={
                "sender": {"name": "Hover3D", "email": "noreply.hover3d@gmail.com"},
                "to": [{"email": email_destino}],
                "subject": f"✅ Evento cadastrado: {title}",
                "htmlContent": html,
            },
            timeout=15,
        )
        res.raise_for_status()


def send_alert(event: dict, when: str, email_destino: str):
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
    <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">Lembrete de evento</p>
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

    with httpx.Client() as client:
        res = client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
            json={
                "sender": {"name": "Hover3D", "email": "noreply.hover3d@gmail.com"},
                "to": [{"email": email_destino}],
                "subject": subject,
                "htmlContent": html,
            },
            timeout=15,
        )
        res.raise_for_status()


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
    title:       str = Field(..., min_length=1, max_length=200)
    date:        str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    time:        str = Field(..., pattern=r'^\d{2}:\d{2}$')
    location:    str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=1000)

class NotificationUpdate(BaseModel):
    notification_email:    str = Field(..., max_length=254)
    notification_accepted: bool

    @field_validator("notification_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError("E-mail inválido.")
        return v.lower()


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
def generate(req: GenerateRequest, user: dict = Depends(get_current_user)):
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


# ── Rotas: perfil ────────────────────────────────────────────

@app.get("/api/profile")
def get_profile(user: dict = Depends(get_current_user)):
    sb_check()
    uid = user["id"]
    with httpx.Client() as client:
        res = client.get(sb_url("profiles", f"?id=eq.{uid}&select=ativo,plano,vencimento"), headers=sb_headers())
        res.raise_for_status()
        rows = res.json()
        if not rows:
            return {"ativo": False, "plano": "basico", "vencimento": None}
        return rows[0]


# ── Rotas: notificações ──────────────────────────────────────

@app.get("/api/notification")
def get_notification(user: dict = Depends(get_current_user)):
    sb_check()
    uid = user["id"]
    with httpx.Client() as client:
        res = client.get(sb_url("profiles", f"?id=eq.{uid}&select=notification_email,notification_accepted"), headers=sb_headers())
        res.raise_for_status()
        rows = res.json()
        if not rows:
            return {"notification_email": "", "notification_accepted": False}
        return {
            "notification_email":    rows[0].get("notification_email") or "",
            "notification_accepted": rows[0].get("notification_accepted") or False,
        }


@app.put("/api/notification")
def update_notification(data: NotificationUpdate, user: dict = Depends(get_current_user)):
    sb_check()
    uid = user["id"]
    payload = {"id": uid, "notification_email": data.notification_email, "notification_accepted": data.notification_accepted}
    with httpx.Client() as client:
        res = client.post(
            sb_url("profiles") + "?on_conflict=id",
            headers={**sb_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json=payload,
        )
        res.raise_for_status()
        return res.json()[0]


# ── Rotas: eventos ───────────────────────────────────────────

@app.get("/api/events")
def list_events(user: dict = Depends(get_current_user)):
    sb_check()
    uid = user["id"]
    with httpx.Client() as client:
        res = client.get(sb_url("events", f"?select=*&user_id=eq.{uid}&order=date.asc,time.asc"), headers=sb_headers())
        res.raise_for_status()
        return res.json()


@app.post("/api/events", status_code=201)
def create_event(ev: EventCreate, user: dict = Depends(get_current_user)):
    sb_check()
    data = ev.model_dump()
    data["user_id"] = user["id"]
    uid = user["id"]
    with httpx.Client() as client:
        res = client.post(sb_url("events"), headers=sb_headers(), json=data)
        res.raise_for_status()
        created = res.json()[0]

        if BREVO_KEY:
            try:
                profile_res = client.get(sb_url("profiles", f"?id=eq.{uid}&select=notification_email,notification_accepted"), headers=sb_headers())
                profiles = profile_res.json()
                if profiles and profiles[0].get("notification_accepted") and profiles[0].get("notification_email"):
                    send_confirmation(created, profiles[0]["notification_email"])
            except Exception:
                pass

        return created


@app.delete("/api/events/{event_id}", status_code=204)
def delete_event(event_id: str, user: dict = Depends(get_current_user)):
    sb_check()
    uid = user["id"]
    with httpx.Client() as client:
        res = client.delete(sb_url("events", f"?id=eq.{event_id}&user_id=eq.{uid}"), headers=sb_headers())
        res.raise_for_status()


# ── Rota: cron ───────────────────────────────────────────────

@app.get("/api/cron/check-events")
def check_events(secret: str = ""):
    if not CRON_SECRET or secret != CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    if not BREVO_KEY:
        raise HTTPException(status_code=503, detail="BREVO_API_KEY não configurada.")

    sb_check()
    br_tz    = ZoneInfo("America/Sao_Paulo")
    today    = datetime.now(br_tz).date()
    tomorrow = today + timedelta(days=1)
    sent     = []
    expired  = []
    email_cache: dict = {}

    # Expirar assinaturas vencidas
    with httpx.Client() as client:
        res = client.get(
            sb_url("profiles", f"?select=id&ativo=eq.true&vencimento=lt.{today.isoformat()}"),
            headers=sb_headers(),
        )
        vencidos = res.json() if res.status_code == 200 else []
        for row in vencidos:
            uid = row["id"]
            client.patch(
                sb_url("profiles", f"?id=eq.{uid}"),
                headers=sb_headers(),
                json={"ativo": False},
            )
            expired.append(uid)
        if expired:
            print(f"[cron] {len(expired)} assinatura(s) expirada(s): {expired}")

    def get_user_email(uid: str, client: httpx.Client) -> str | None:
        if uid in email_cache:
            return email_cache[uid]
        res = client.get(sb_url("profiles", f"?id=eq.{uid}&select=notification_email,notification_accepted"), headers=sb_headers())
        rows = res.json() if res.status_code == 200 else []
        if rows and rows[0].get("notification_accepted") and rows[0].get("notification_email"):
            email_cache[uid] = rows[0]["notification_email"]
        else:
            email_cache[uid] = None
        return email_cache[uid]

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
                email = get_user_email(ev["user_id"], client)
                if not email:
                    sent.append(f"sem_email:{ev['title']}")
                    continue
                send_alert(ev, "today", email)
                client.patch(sb_url("events", f"?id=eq.{ev['id']}"), headers=sb_headers(), json={"email_sent_day_of": True})
                sent.append(f"hoje:{ev['title']}")
            except Exception:
                sent.append(f"erro:{ev['id']}")

        for ev in tomorrow_evs:
            try:
                email = get_user_email(ev["user_id"], client)
                if not email:
                    sent.append(f"sem_email:{ev['title']}")
                    continue
                send_alert(ev, "tomorrow", email)
                client.patch(sb_url("events", f"?id=eq.{ev['id']}"), headers=sb_headers(), json={"email_sent_day_before": True})
                sent.append(f"amanha:{ev['title']}")
            except Exception:
                sent.append(f"erro:{ev['id']}")

    return {"sent": sent, "total": len(sent), "expired": len(expired)}


# ── Rotas: pagamento (BitiBridge) ────────────────────────────

@app.post("/api/payment/create")
def payment_create(user: dict = Depends(get_current_user)):
    if not BITIBRIDGE_API_KEY:
        raise HTTPException(status_code=503, detail="Gateway de pagamento não configurado.")
    uid = user["id"]
    with httpx.Client() as client:
        res = client.post(
            f"{BITIBRIDGE_URL}/depix-create-pix",
            headers={"Authorization": f"Bearer {BITIBRIDGE_API_KEY}", "Content-Type": "application/json"},
            json={"amount": PLANO_VALOR, "external_ref": uid, "description": "Assinatura Hover3D — 1 mês"},
            timeout=30,
        )
        data = res.json()
        if not res.is_success or data.get("error_code"):
            detail = data.get("message") or "Erro ao criar cobrança PIX."
            raise HTTPException(status_code=502, detail=detail)
        return {
            "txid":       data["txid"],
            "qr_code":    data["qr_code"],
            "copy_paste": data["copy_paste"],
            "amount":     data["amount"],
            "expires_at": data.get("expires_at"),
        }


@app.post("/api/webhook/bitibridge")
async def webhook_bitibridge(request: Request):
    body = await request.body()

    # Validar assinatura HMAC-SHA256 enviada pelo BitiBridge
    if BITIBRIDGE_WEBHOOK_SECRET:
        sig = request.headers.get("x-bitibridge-signature", "")
        hex_part = BITIBRIDGE_WEBHOOK_SECRET.replace("whsec_", "")

        # Tenta 3 formatos possíveis da chave
        candidates = {
            "full_string":   BITIBRIDGE_WEBHOOK_SECRET.encode(),
            "hex_string":    hex_part.encode(),
        }
        try:
            candidates["hex_decoded"] = bytes.fromhex(hex_part)
        except ValueError:
            pass

        matched = None
        for fmt, key in candidates.items():
            expected = hmac.new(key, body, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected):
                matched = fmt
                break

        print(f"[webhook] sig_recebida={sig[:20]}... formato_matched={matched}")

        if not matched:
            print(f"[webhook] HMAC inválido — sig={sig}")
            raise HTTPException(status_code=401, detail="Assinatura inválida.")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Payload inválido.")

    if payload.get("event") != "payment.paid":
        return {"received": True}

    uid = payload.get("external_ref")
    if not uid:
        return {"received": True}

    sb_check()
    br_tz      = ZoneInfo("America/Sao_Paulo")
    vencimento = (datetime.now(br_tz) + timedelta(days=30)).date().isoformat()

    with httpx.Client() as client:
        client.post(
            sb_url("profiles") + "?on_conflict=id",
            headers={**sb_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json={"id": uid, "ativo": True, "vencimento": vencimento, "plano": "basico"},
        )

    return {"received": True}


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Hover3D — Backend")
    print(f"  IA:       {'online' if API_KEY else 'sem chave'}")
    print(f"  Supabase: {'ok' if SUPABASE_URL else 'sem chave'}")
    print(f"  Brevo:    {'ok' if BREVO_KEY else 'sem chave'}")
    print("  http://127.0.0.1:8000")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000)
