# ============================================================
#  HOVER3D — Backend (FastAPI + Claude API)
# ============================================================
#  Gera posts com IA usando a API da Anthropic.
#  Protegido por sistema de créditos para garantir margem.
#
#  ATIVAÇÃO:
#    1. pip install -r requirements.txt
#    2. copie .env.example para .env e coloque sua ANTHROPIC_API_KEY
#    3. python main.py
# ============================================================

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# A lib da Anthropic só é importada se a chave existir
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL   = os.environ.get("HOVER3D_MODEL", "claude-haiku-4-5-20251001")

app = FastAPI(title="Hover3D Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    character: str
    service:   str
    category:  str
    occasion:  str
    tone:      str
    company:   str = "nossa empresa"
    region:    str = "nossa região"


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


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok", "ai": "online" if API_KEY else "no_key", "model": MODEL}


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY não configurada.")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=API_KEY)
        message = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(req)}],
        )
        text = message.content[0].text.strip()

        # Custo aproximado para log/controle
        usage = {
            "input_tokens":  message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }
        return {"success": True, "text": text, "usage": usage}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na geração: {e}")


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  Hover3D — Backend")
    print(f"  IA: {'online' if API_KEY else 'SEM CHAVE (configure .env)'}")
    print(f"  Modelo: {MODEL}")
    print("  http://127.0.0.1:8000")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000)
