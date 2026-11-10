# WhatsFlow AI — PoC

PoC de terminal que lê uma lista de contatos e uma mensagem, abre cada conversa
no WhatsApp Web, valida o destinatário pelo telefone e envia automaticamente,
sem pedir aprovação por contato.

## Atenção

A aprovação manual por mensagem foi removida a pedido do usuário. Isso sai do
escopo original do spec (que previa aprovação humana antes de cada envio) e
aumenta o risco de a conta ser bloqueada pelo WhatsApp por automação sem
supervisão. Use com poucos contatos e por sua conta e risco.

## O que isso NÃO faz

- Não usa IA para validar o destinatário — a comparação é por telefone (string
  exata), que é determinística; ver `src/agent.py`.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Arquivos de entrada

- `data/contacts.csv`: colunas `name` e `phone` (não versionado — contém dados
  pessoais; copie `data/contacts.example.csv` como ponto de partida).
- `data/message.txt`: texto da mensagem a ser enviada a todos os contatos.
- `data/attachments/`: opcional — qualquer arquivo colocado aqui é enviado logo
  após a mensagem de texto, para todos os contatos. Imagens (`.jpg`, `.png`,
  etc.) são enviadas como foto (bolha de imagem, com preview); outros tipos
  são enviados como documento. Pasta vazia = nenhum anexo é enviado.

## Painel web (opcional)

Interface local para editar contatos, mensagem e anexos sem mexer nos arquivos
na mão, com um botão para disparar o envio e acompanhar o log em tempo real:

```bash
python -m src.web
```

Abra `http://127.0.0.1:5000` no navegador. Roda só em `localhost` — não exponha
essa porta na rede, já que não tem autenticação e o botão "Executar" dispara
envios reais de WhatsApp.

## Execução (linha de comando)

```bash
python -m src.main
```

Na primeira execução, uma janela do Chromium abre o WhatsApp Web — escaneie o
QR code com o celular. A sessão é mantida em `browser_profile/` (ignorado pelo
git), então não é necessário escanear novamente nas próximas execuções — até
o fim da lista (veja abaixo).

Ao terminar de processar todos os contatos (sem ser interrompido), o script
faz logout automático do WhatsApp Web, para que a próxima execução possa
escanear o QR code de **outro número** — útil para rodar listas de números
diferentes em sequência. Se a execução for interrompida (`Ctrl+C`) ou falhar
antes de concluir a lista, o logout não acontece e a sessão permanece ativa.

Para cada contato, o script valida o telefone, prepara a mensagem e envia
direto, sem pedir confirmação. Contatos com status `SENT` ou `SKIPPED` nos
últimos 30 dias (`REPROCESS_COOLDOWN` em `src/logs.py`) não são reprocessados;
depois desse prazo, voltam a ficar elegíveis automaticamente, sem precisar
mexer no log.

Para forçar um reprocessamento imediato (ex.: novo teste), esvazie o log:

```bash
> logs/results.jsonl
```

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
