# WhatsFlow AI — PoC

PoC de terminal que lê uma lista de contatos e uma mensagem, abre cada conversa
no WhatsApp Web, valida o destinatário pelo telefone e só envia após aprovação
humana explícita por contato.

## O que isso NÃO faz

- Não envia mensagens em massa nem contorna controles do WhatsApp.
- Não usa IA para validar o destinatário — a comparação é por telefone (string
  exata), que é determinística; ver `src/agent.py`.
- Não envia nada sem uma confirmação manual (`s`/`N`) no terminal, por contato.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Arquivos de entrada

- `data/contacts.csv`: colunas `name` e `phone` (já vem com um exemplo).
- `data/message.txt`: texto da mensagem a ser enviada a todos os contatos.

## Execução

```bash
python -m src.main
```

Na primeira execução, uma janela do Chromium abre o WhatsApp Web — escaneie o
QR code com o celular. A sessão é mantida em `browser_profile/` (ignorado pelo
git), então não é necessário escanear novamente nas próximas execuções.

Para cada contato, o terminal mostra o nome, telefone e mensagem, e pede
confirmação antes de enviar. Contatos já processados com sucesso (`SENT`) ou
pulados (`SKIPPED`) em execuções anteriores não são reprocessados.

Para interromper, use `Ctrl+C`: a execução para de forma limpa e o navegador é
encerrado.

## Logs

Cada contato processado gera uma linha JSON em `logs/results.jsonl` com nome,
telefone, data/hora, mensagem, status (`PENDING`, `CONTACT_FOUND`,
`AWAITING_APPROVAL`, `SENT`, `FAILED`, `SKIPPED`) e, quando aplicável, o motivo
da falha.

## Testes

```bash
pytest
```

Os testes cobrem carregamento/validação de contatos, deduplicação, a lógica de
validação do operador e a persistência do log — nenhum deles abre navegador.

## Limitações conhecidas

- O WhatsApp Web muda o DOM com frequência; os seletores em `src/whatsapp.py`
  podem precisar de ajuste.
- O nome exibido no cabeçalho da conversa é o nome de perfil definido pelo
  próprio contato no WhatsApp, não necessariamente o nome da planilha — por
  isso ele só gera aviso (`warning`), nunca bloqueia o envio.
- "SENT" no log significa que a mensagem apareceu na conversa pela interface,
  não uma confirmação de entrega/leitura pela plataforma.
- Para envio automatizado real em produção, use a WhatsApp Business Cloud API
  (fora do escopo deste PoC).
