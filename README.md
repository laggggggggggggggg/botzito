# 🇵🇹 Bot Rede Tuga

Bot profissional de Discord para a comunidade **Rede Tuga**, com sistema completo de:

- 📜 **Painel de regras** — comando `/regras` publica embeds completas no canal
- 👋 **Boas-vindas automáticas** — embed no canal + DM ao membro + botão de verificação
- 🎫 **Sistema de tickets profissional** — 7 categorias, modais, transcripts, painel de controlo
- 🎭 **Auto-roles reativos** — select menu onde os membros escolhem cargos
- 📢 **Embed builder** — `/embed` para staff criar anúncios personalizados
- 💡 **Sugestões** — `/sugerir` cria votação no canal de sugestões
- 📊 **Logs** — registo de eventos no canal de logs

Construído em **Python 3.11+** com **discord.py 2.4+**, pronto para deploy no **Railway** (free tier).

---

## 📂 Estrutura do projeto

```
rede-tuga-bot/
├── main.py                  # Ponto de entrada — startup, intents, comandos globais
├── config.py                # Configuração (lê environment / Secrets)
├── requirements.txt         # Dependências Python
├── railway.json             # Configuração de deploy Railway
├── railway.toml             # Configuração alternativa Railway
├── Procfile                 # Comando de arranque (Railway/Heroku)
├── .env.example             # Template de variáveis de ambiente
│
├── cogs/                    # Módulos do bot (extensões)
│   ├── regras.py            # Comando /regras
│   ├── boas_vindas.py       # on_member_join + botão de verificação
│   ├── tickets.py           # Sistema completo de tickets
│   ├── auto_roles.py        # /painel_cargos + select menu
│   ├── embed_builder.py     # /embed para anúncios
│   └── sugestoes.py         # /sugerir
│
├── utils/
│   ├── __init__.py
│   └── helpers.py           # Embeds, persistência JSON, logging, permissões
│
└── data/
    └── regras.json          # Conteúdo das regras (editável)
```

---

## 🚀 Setup rápido — Discord Developer Portal

### 1. Criar a aplicação

1. Vai a <https://discord.com/developers/applications>
2. Clica em **New Application** → dá o nome `Rede Tuga Bot`
3. Vai a **Bot** no menu lateral:
   - **Reset Token** e copia o token → guarda num sitio seguro
   - Liga **Privileged Gateway Intents**:
     - ✅ Presence Intent
     - ✅ Server Members Intent
     - ✅ Message Content Intent
4. Vai a **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator` (ou usa o set abaixo, mais restrito)
   - Copia o URL gerado e abre no browser para convidar o bot

### Permissões recomendadas (em vez de Administrator)

```
Manage Channels, Manage Roles, Manage Messages,
Kick Members, Ban Members, View Audit Log,
Send Messages, Embed Links, Attach Files,
Read Message History, Add Reactions, Use Slash Commands,
Moderate Members
```

### 2. Configurar o Discord (IDs)

Para cada passo, ativa **Modo de Programador** em:
`Definições > Avançadas > Modo de Programador` (Discord)

Depois clica com o botão direito > **Copiar ID** em:

| O que copiar | Onde | Variable |
|---|---|---|
| Servidor (guild) | botão direito no ícone do servidor | `GUILD_ID` |
| Canal de regras | botão direito no canal | `CANAL_REGRAS` |
| Canal de boas-vindas | botão direito no canal | `CANAL_BEM_VINDAS` |
| Canal de logs | botão direito no canal | `CANAL_LOGS` |
| Canal de sugestões | botão direito no canal | `CANAL_SUGESTOES` |
| Categoria de tickets | botão direito na categoria | `CATEGORIA_TICKETS` |
| Cargo de membro | botão direito no cargo | `CARGO_MEMBRO` |
| Cargo de verificado | botão direito no cargo | `CARGO_VERIFICADO` |
| Cargo de staff | botão direito no cargo | `CARGO_STAFF` |
| Cargo de admin | botão direito no cargo | `CARGO_ADMIN` |
| Cargo de ticket staff | botão direito no cargo | `CARGO_TICKET_STAFF` |

---

## 🚂 Deploy no Railway (free tier)

### Passo a passo

1. **Cria conta** em <https://railway.app> (podes fazer login com GitHub)

2. **Sobe o código para o GitHub**:
   ```bash
   cd rede-tuga-bot
   git init
   git add .
   git commit -m "🇵🇹 Bot Rede Tuga — versão inicial"
   git branch -M main
   git remote add origin https://github.com/TEU_USER/rede-tuga-bot.git
   git push -u origin main
   ```

3. **Cria um novo projeto no Railway**:
   - Clica em **New Project** > **Deploy from GitHub repo**
   - Selecionalo repositório que acabaste de criar

4. **Configura os Secrets**:
   - No painel do projeto, clica no **service** que foi criado
   - Vai ao separador **Variables**
   - Clica em **Raw Editor** e cola o seguinte (preenchendo os teus IDs):

   ```env
   DISCORD_TOKEN=coloca_aqui_o_teu_token
   GUILD_ID=123456789012345678
   CANAL_REGRAS=123456789012345678
   CANAL_BEM_VINDAS=123456789012345678
   CANAL_LOGS=123456789012345678
   CANAL_SUGESTOES=123456789012345678
   CATEGORIA_TICKETS=123456789012345678
   CARGO_MEMBRO=123456789012345678
   CARGO_VERIFICADO=123456789012345678
   CARGO_STAFF=123456789012345678
   CARGO_ADMIN=123456789012345678
   CARGO_TICKET_STAFF=123456789012345678
   NOME_SERVIDOR=Rede Tuga
   PREFIXO=!
   COR_BOT=FF3B3B
   ```

   - Clica em **Update Variables**

5. **Deploy!**
   - O Railway detecta automaticamente Python + `requirements.txt`
   - O comando de arranque (`python main.py`) está definido em `railway.json`
   - Acompanha os logs no separador **Deployments**

6. **Verifica que está online**:
   - Os logs devem mostrar `🇵🇹 BOT REDE TUGA — ONLINE`
   - No Discord, o bot deve aparecer como online
   - Testa com `/ajuda`

> ⚠️ **Importante sobre o free tier do Railway**: o plano gratuito tem 500 horas/mês e o serviço **adormece após inatividade**. Para bots de Discord isto raramente é problema porque o bot mantém a websocket aberta, mas se acontecer reinícios automáticos estão configurados (`restartPolicyMaxRetries: 10`).

---

## 🧪 Testar localmente

```bash
# 1. Instala dependências
pip install -r requirements.txt

# 2. Cria ficheiro .env (copia do .env.example e preenche)
cp .env.example .env
nano .env

# 3. Corre o bot
python main.py
```

---

## 🎮 Comandos disponíveis

### Globais (todos os membros)

| Comando | Descrição |
|---|---|
| `/ajuda` | Lista de comandos disponíveis |
| `/ping` | Latência do bot |
| `/info` | Informações técnicas do bot |
| `/sugerir` | Envia sugestão para o canal de sugestões |

### Staff (`manage_messages` ou superior)

| Comando | Descrição |
|---|---|
| `/regras` | Publica painel de regras no canal atual ou configurado |
| `/recarregar_regras` | Recarrega regras do `data/regras.json` |
| `/painel_tickets` | Cria painel principal de tickets |
| `/painel_boas_vindas` | Cria painel com botão de verificação |
| `/painel_cargos` | Cria painel de auto-roles com select menu |
| `/embed` | Construtor de embeds (anúncios) |

### Admin (`administrator`)

| Comando | Descrição |
|---|---|
| `/config_autoroles` | Configura cargo para cada opção do auto-roles |

---

## 🎫 Sistema de tickets — detalhe

O painel de tickets tem **7 categorias** profissionais:

| Categoria | Emoji | Cor | Descrição |
|---|---|---|---|
| Suporte Geral | 🆘 | Verde | Dúvidas gerais sobre o servidor |
| Reportar Player | ⚠️ | Vermelho | Denúncias de jogadores |
| Reclamações Staff | 📢 | Laranja | Queixas sobre a equipa de moderação |
| Parcerias | 🤝 | Dourado | Propostas de parceria |
| Apelar Ban | 🔨 | Vermelho | Recursos de bans/mutes |
| Doações / VIP | 💎 | Dourado | Questões sobre doações |
| Bugs / Sugestões | 🐛 | Cinza | Reportar bugs ou sugerir melhorias |

### Funcionalidades dos tickets

- ✅ **Modal de motivo** ao clicar (mínimo 10 caracteres)
- ✅ **Canal privado** com permissões restrictas (só dono + staff veem)
- ✅ **Painel de controlo** dentro do ticket:
  - 🔒 Fechar Ticket (com confirmação)
  - 🙋 Reivindicar (staff marca-se como responsável)
  - 📝 Transcript (gera .txt com todas as mensagens)
- ✅ **Transcript automático** antes do fecho, enviado ao canal de logs
- ✅ **Anti-duplicados** — não permite abrir 2 tickets simultâneos
- ✅ **Persistência** em JSON — sobrevive a restarts do Railway

---

## 🎨 Personalizar a temática

### Cores

Edita `config.py` → classe `Cores`:

```python
class Cores:
    VERMELHO = 0xFF3B3B   # Cor da bandeira PT
    VERDE    = 0x006233   # Cor da bandeira PT
    DOURADO  = 0xFFD700   # Destaques
```

### Regras

Edita `data/regras.json` — adiciona/remove secções, itens e emojis à vontade.
Depois corre `/recarregar_regras` no Discord para aplicar.

### Auto-roles

Por defeito, o painel tem 8 opções (Notificações, Gaming, Música, Arte, Norte, Centro, Sul, Ilhas).

Para configurar cargos reais:
1. Cria os cargos no Discord
2. Usa `/config_autoroles opcao_id:gaming cargo:@Gamer` para cada um
3. Recria o painel com `/painel_cargos`

### Nome do servidor

Define `NOME_SERVIDOR` nos Secrets do Railway. Aparece em todos os embeds e painéis.

---

## 🔧 Resolução de problemas

### O bot não fica online

- Verifica que `DISCORD_TOKEN` está correto nos Secrets
- Verifica os logs no Railway — deve mostrar mensagens de erro
- Confirma que ativaste os 3 Privileged Intents no Discord Developer Portal

### Slash commands não aparecem

- Se `GUILD_ID=0`, os comandos são **globais** e podem demorar até 1h a aparecer
- Para sync instantâneo, define `GUILD_ID` com o ID do teu servidor
- Podes também usar `Ctrl+R` no Discord para refrescar

### Bot não consegue criar canais de ticket

- Verifica que `CATEGORIA_TICKETS` está definido e aponta para uma categoria real
- Verifica que o bot tem a permissão **Manage Channels**
- A categoria não pode ter permissões que bloqueiem o bot

### Auto-roles não funcionam

- Usa `/config_autoroles` para cada opção antes de criar o painel
- Os cargos não podem ser **bot-managed** (cargos de bots) nem `@everyone`
- O bot precisa da permissão **Manage Roles** e o cargo do bot tem de estar **acima** dos cargos que atribui

### Erros de permissões no canal de regras

- Verifica que `CANAL_REGRAS` aponta para um canal de texto real
- O bot precisa de `Send Messages` e `Embed Links` nesse canal

---

## 📝 Licença

Projeto open-source para a comunidade Rede Tuga. Sente-te à vontade para adaptar ao teu servidor.

## 🤝 Contribuições

Encontraste um bug ou queres adicionar uma feature? Abre um issue ou PR no GitHub.

---

**Bom divertimento e boa comunidade! 🇵🇹**
