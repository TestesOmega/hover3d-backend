# Hover3D — Backend (preparado para IA)

Este backend fica PRONTO para quando você quiser ativar a geração com IA.
Por enquanto o app funciona 100% no modo Templates (grátis), sem precisar dele.

## Quando ativar a IA

1. Crie conta em https://console.anthropic.com e gere uma API key
2. Coloque a chave no arquivo `.env` (copie de `.env.example`)
3. Rode o backend: `python main.py`
4. No frontend, mude `AI_ENABLED = true` no `src/App.tsx`

## Modelo e custo

- Modelo: Claude Haiku 4.5 (mais barato)
- Custo por post: ~R$0,003 (menos de meio centavo)
- Sistema de créditos protege sua margem (ver MAX_CREDITS no App.tsx)
