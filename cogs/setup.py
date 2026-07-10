"""
Cog de Setup — assistente interativo que configura o bot conversando.

O utilizador só precisa de:
  1. Configurar DISCORD_TOKEN nos Secrets do Railway
  2. Convidar o bot para o servidor
  3. Executar /setup — o bot cria canais, cargos e painéis automaticamente

Nada de IDs manuais! 🎉
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config as cfg_module
from config import Cores, Emojis, get_config, save_config
from utils import embed_aviso, embed_erro, embed_sucesso, log_evento


# ─────────────────────────────────────────────────────────────────────────────
# Estrutura de canais a criar
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIA_INFO = {
    "nome": "📡 Informações",
    "canais": [
        ("regras", "📜 Regras", "text"),
        ("anuncios", "📢 Anúncios", "text"),
        ("boas-vindas", "👋 Boas-vindas", "text"),
    ],
}

CATEGORIA_COMUNIDADE = {
    "nome": "💬 Comunidade",
    "canais": [
        ("geral", "💬 Geral", "text"),
        ("off-topic", "🌀 Off-topic", "text"),
        ("sugestoes", "💡 Sugestões", "text"),
        ("media", "🖼️ Mídia", "text"),
    ],
}

CATEGORIA_SUPORTE = {
    "nome": "🎫 Suporte",
    "canais": [
        ("tickets", "🎫 Abrir Ticket", "text"),
        ("logs", "📋 Logs do Servidor", "text"),
    ],
}

CATEGORIA_STAFF = {
    "nome": "🛡️ Staff",
    "canais": [
        ("staff-chat", "🔒 Staff Chat", "text"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Cargos a criar
# ─────────────────────────────────────────────────────────────────────────────
CARGOS_PADRAO = [
    {"nome": "👑 Admin", "cor": Cores.VERMELHO, "permissoes": "admin"},
    {"nome": "🛡️ Staff", "cor": Cores.DOURADO, "permissoes": "staff"},
    {"nome": "🎫 Ticket Staff", "cor": Cores.VERDE, "permissoes": "ticket"},
    {"nome": "✅ Verificado", "cor": Cores.SUCESSO, "permissoes": "verificado"},
    {"nome": "🇵🇹 Membro", "cor": Cores.VERDE, "permissoes": "membro"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Modal para escolher o nome do servidor
# ─────────────────────────────────────────────────────────────────────────────
class NomeServidorModal(discord.ui.Modal):
    def __init__(self, cog: "SetupCog", guild: discord.Guild) -> None:
        super().__init__(title="🇵🇹 Configurar Rede Tuga", timeout=300)
        self.cog = cog
        self.guild = guild

        self.nome = discord.ui.TextInput(
            label="Nome do servidor no bot",
            placeholder="Ex: Rede Tuga, Comunidade Tuga, etc.",
            default=guild.name,
            max_length=80,
            required=True,
        )
        self.add_item(self.nome)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.iniciar_setup(interaction, self.nome.value)


# ─────────────────────────────────────────────────────────────────────────────
# Botões de confirmação do setup
# ─────────────────────────────────────────────────────────────────────────────
class ConfirmarSetupView(discord.ui.View):
    def __init__(self, cog: "SetupCog", nome_servidor: str, guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.nome_servidor = nome_servidor
        self.guild = guild

    @discord.ui.button(label="🚀 Começar Setup", style=discord.ButtonStyle.success)
    async def comecar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Precisas de permissões de administrador para fazer o setup.",
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(view=None)
        await self.cog.executar_setup(interaction, self.nome_servidor)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            content="❌ Setup cancelado. Podes executar `/setup` outra vez quando quiseres.",
            embed=None,
            view=None,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────────────────────────────────────────
class SetupCog(commands.Cog):
    """Assistente de configuração do bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="🚀 Configura o bot automaticamente — cria canais, cargos e painéis.",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_setup(self, interaction: discord.Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Sem permissão",
                    "Precisas de ser **administrador** do servidor para executar o setup.",
                ),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)
        if cfg.setup_completo:
            view = ConfirmarSetupView(self, cfg.nome_servidor or interaction.guild.name, interaction.guild)
            await interaction.response.send_message(
                embed=embed_aviso(
                    "⚠️ Setup já foi feito",
                    f"O bot já está configurado para este servidor ({cfg.nome_servidor}).\n\n"
                    f"Se quiseres **reconfigurar tudo**, clica em **Começar Setup**.\n"
                    f"Isto vai recriar canais e cargos em falta (não apaga os existentes).",
                ),
                view=view,
            )
            return

        await interaction.response.send_modal(NomeServidorModal(self, interaction.guild))

    # ─────────────────────────────────────────────────────────────────────────
    # Fluxo principal
    # ─────────────────────────────────────────────────────────────────────────
    async def iniciar_setup(self, interaction: discord.Interaction, nome_servidor: str) -> None:
        """Etapa 1 — mostra preview e pede confirmação."""
        embed = discord.Embed(
            title=f"{Emojis.COROA} Configurar {nome_servidor}",
            description=(
                f"Vou configurar o bot para o servidor **{interaction.guild.name}** "
                f"com o nome **{nome_servidor}**.\n\n"
                f"📋 **O que vou criar:**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📂 **4 categorias** com canais:\n"
                f"   • 📡 Informações — #regras, #anuncios, #boas-vindas\n"
                f"   • 💬 Comunidade — #geral, #off-topic, #sugestoes, #media\n"
                f"   • 🎫 Suporte — #tickets, #logs\n"
                f"   • 🛡️ Staff — #staff-chat (privado)\n\n"
                f"🎭 **5 cargos:**\n"
                f"   • 👑 Admin  • 🛡️ Staff  • 🎫 Ticket Staff\n"
                f"   • ✅ Verificado  • 🇵🇹 Membro\n\n"
                f"🎨 **Painéis automáticos:**\n"
                f"   • Painel de regras no #regras\n"
                f"   • Painel de boas-vindas + botão de verificação\n"
                f"   • Painel de tickets no #tickets\n"
                f"   • Painel de auto-roles\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ **Atenção:**\n"
                f"• O bot precisa de permissões de **Administrador** para isto funcionar.\n"
                f"• Não vou apagar nada que já exista — apenas crio o que estiver em falta.\n"
                f"• O processo demora ~30 segundos."
            ),
            color=Cores.VERMELHO,
        )
        embed.set_footer(text="Rede Tuga • Setup Automático")

        view = ConfirmarSetupView(self, nome_servidor, interaction.guild)
        await interaction.response.send_message(embed=embed, view=view)

    async def executar_setup(self, interaction: discord.Interaction, nome_servidor: str) -> None:
        """Etapa 2 — executa o setup de facto."""
        guild = interaction.guild
        cfg = get_config(guild.id)
        cfg.nome_servidor = nome_servidor

        # Mensagem de progresso
        progresso_embed = discord.Embed(
            title=f"{Emojis.COROA} Setup em curso...",
            description=(
                f"Olá {interaction.user.mention}! Vou configurar tudo para ti. "
                f"Acompanha o progresso abaixo 👇"
            ),
            color=Cores.DOURADO,
        )
        progresso_embed.add_field(name="📋 Tarefas", value="A iniciar...", inline=False)
        msg = await interaction.channel.send(embed=progresso_embed)

        log_passos: list[str] = []

        async def atualizar(passo: str) -> None:
            log_passos.append(passo)
            embed = discord.Embed(
                title=f"{Emojis.COROA} Setup em curso...",
                description=f"Olá {interaction.user.mention}! Acompanha o progresso 👇",
                color=Cores.DOURADO,
            )
            embed.add_field(
                name="📋 Progresso",
                value="\n".join(f"{'✅' if i < len(log_passos) - 1 else '⏳'} {p}"
                                for i, p in enumerate(log_passos)),
                inline=False,
            )
            try:
                await msg.edit(embed=embed)
            except discord.HTTPException:
                pass

        try:
            # 1. Cria categorias e canais
            await atualizar("A criar categorias e canais...")
            canais_criados = await self._criar_estrutura_canais(guild, cfg)
            await save_config(cfg)

            # 2. Cria cargos
            await atualizar("A criar cargos...")
            cargos_criados = await self._criar_cargos(guild, cfg)
            await save_config(cfg)

            # 3. Configura permissões dos canais
            await atualizar("A configurar permissões...")
            await self._configurar_permissoes(guild, cfg)

            # 4. Publica painel de regras
            await atualizar("A publicar painel de regras...")
            await self._publicar_regras(guild, cfg)

            # 5. Publica painel de boas-vindas
            await atualizar("A publicar painel de boas-vindas...")
            await self._publicar_boas_vindas(guild, cfg)

            # 6. Publica painel de tickets
            await atualizar("A publicar painel de tickets...")
            await self._publicar_tickets(guild, cfg)

            # 7. Publica painel de auto-roles
            await atualizar("A publicar painel de auto-roles...")
            await self._publicar_autoroles(guild, cfg)

            # 8. Marca como completo
            cfg.setup_completo = True
            await save_config(cfg)

            await atualizar("Setup concluído! 🎉")

            # Mensagem final
            embed_final = discord.Embed(
                title=f"{Emojis.VERIFICAR} Setup concluído!",
                description=(
                    f"O bot **{cfg.nome_servidor}** está pronto a usar! 🇵🇹\n\n"
                    f"✅ **{canais_criados}** canais criados/configurados\n"
                    f"✅ **{cargos_criados}** cargos criados/configurados\n"
                    f"✅ Painéis publicados: regras, boas-vindas, tickets, auto-roles\n\n"
                    f"🎯 **Próximos passos sugeridos:**\n"
                    f"• Atribui o cargo **👑 Admin** a ti próprio\n"
                    f"• Personaliza as regras em `data/regras.json` se quiseres\n"
                    f"• Configura cargos do auto-roles com `/config_autoroles`\n\n"
                    f"Para ver todos os comandos: `/ajuda`"
                ),
                color=Cores.SUCESSO,
            )
            await interaction.channel.send(embed=embed_final, content=interaction.user.mention)

            await log_evento(
                self.bot,
                f"{Emojis.VERIFICAR} Setup concluído",
                f"Servidor **{guild.name}** configurado com sucesso.\n"
                f"Canais: {canais_criados} • Cargos: {cargos_criados}",
                Cores.SUCESSO,
                interaction.user,
            )

        except discord.Forbidden as e:
            await interaction.channel.send(
                embed=embed_erro(
                    "Sem permissões",
                    f"O bot não tem permissões suficientes. Verifica que o cargo do bot tem "
                    f"**Administrador** ativo e tenta novamente.\n\nErro: `{e}`",
                )
            )
        except Exception as e:
            await interaction.channel.send(
                embed=embed_erro(
                    "Erro no setup",
                    f"Algo correu mal: `{e}`\n\n"
                    f"O que já foi configurado ficou guardado. Podes executar `/setup` novamente.",
                )
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Criação de canais
    # ─────────────────────────────────────────────────────────────────────────
    async def _criar_estrutura_canais(self, guild: discord.Guild, cfg) -> int:
        """Cria as categorias e canais. Retorna o número de canais configurados."""
        canais_map = {
            "regras": "canal_regras",
            "boas-vindas": "canal_bem_vindas",
            "sugestoes": "canal_sugestoes",
            "tickets": "canal_tickets",
            "logs": "canal_logs",
        }
        contador = 0

        for categoria_def in [CATEGORIA_INFO, CATEGORIA_COMUNIDADE, CATEGORIA_SUPORTE, CATEGORIA_STAFF]:
            # Encontra ou cria categoria
            categoria = discord.utils.get(guild.categories, name=categoria_def["nome"])
            if categoria is None:
                categoria = await guild.create_category(categoria_def["nome"])

            # Se for a de suporte, guarda como categoria de tickets
            if categoria_def["nome"] == "🎫 Suporte":
                cfg.categoria_tickets = categoria.id

            for slug, nome_canal, _tipo in categoria_def["canais"]:
                # Procura canal existente
                canal = discord.utils.get(guild.text_channels, name=slug)
                if canal is None:
                    # Cria canal novo
                    overwrites = {}
                    if categoria_def["nome"] == "🛡️ Staff":
                        # Staff chat é privado para todos exceto staff
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        }
                    canal = await guild.create_text_channel(
                        name=slug,
                        topic=f"{nome_canal} • {cfg.nome_servidor}",
                        category=categoria,
                        overwrites=overwrites or None,
                    )

                # Atualiza config
                if slug in canais_map:
                    setattr(cfg, canais_map[slug], canal.id)
                contador += 1

        return contador

    # ─────────────────────────────────────────────────────────────────────────
    # Criação de cargos
    # ─────────────────────────────────────────────────────────────────────────
    async def _criar_cargos(self, guild: discord.Guild, cfg) -> int:
        """Cria os cargos padrão. Retorna o número de cargos configurados."""
        mapeamento = {
            "👑 Admin": "cargo_admin",
            "🛡️ Staff": "cargo_staff",
            "🎫 Ticket Staff": "cargo_ticket_staff",
            "✅ Verificado": "cargo_verificado",
            "🇵🇹 Membro": "cargo_membro",
        }

        contador = 0
        for cargo_def in CARGOS_PADRAO:
            nome = cargo_def["nome"]
            # Procura cargo existente pelo nome
            cargo = discord.utils.get(guild.roles, name=nome)
            if cargo is None:
                # Cria novo cargo
                permissoes = discord.Permissions()
                if cargo_def["permissoes"] == "admin":
                    permissoes = discord.Permissions(administrator=True)
                elif cargo_def["permissoes"] == "staff":
                    permissoes = discord.Permissions(
                        kick_members=True,
                        ban_members=True,
                        manage_messages=True,
                        mute_members=True,
                        deafen_members=True,
                        move_members=True,
                        manage_nicknames=True,
                        view_audit_log=True,
                        moderate_members=True,
                    )
                elif cargo_def["permissoes"] == "ticket":
                    permissoes = discord.Permissions(
                        manage_channels=True,
                        manage_messages=True,
                        view_audit_log=True,
                    )
                else:
                    permissoes = discord.Permissions(send_messages=True, view_channel=True, read_message_history=True)

                cargo = await guild.create_role(
                    name=nome,
                    color=discord.Color(cargo_def["cor"]),
                    permissions=permissoes,
                    reason=f"Setup automático — {cfg.nome_servidor}",
                )

            attr = mapeamento.get(nome)
            if attr:
                setattr(cfg, attr, cargo.id)
            contador += 1

        return contador

    # ─────────────────────────────────────────────────────────────────────────
    # Configura permissões dos canais críticos
    # ─────────────────────────────────────────────────────────────────────────
    async def _configurar_permissoes(self, guild: discord.Guild, cfg) -> None:
        """Ajusta permissões para que os canais de regras/tickets sejam read-only."""
        # Canal de regras: apenas staff pode escrever
        if cfg.canal_regras:
            canal = guild.get_channel(cfg.canal_regras)
            if canal and cfg.cargo_staff:
                cargo_staff = guild.get_role(cfg.cargo_staff)
                if cargo_staff:
                    await canal.set_permissions(
                        guild.default_role,
                        send_messages=False,
                        add_reactions=False,
                        view_channel=True,
                        read_message_history=True,
                    )
                    await canal.set_permissions(
                        cargo_staff,
                        send_messages=True,
                        manage_messages=True,
                    )

        # Canal de tickets: read-only (só painel)
        if cfg.canal_tickets:
            canal = guild.get_channel(cfg.canal_tickets)
            if canal:
                await canal.set_permissions(
                    guild.default_role,
                    send_messages=False,
                    add_reactions=False,
                    view_channel=True,
                    read_message_history=True,
                )

        # Canal de logs: privado (só staff)
        if cfg.canal_logs and cfg.cargo_staff:
            canal = guild.get_channel(cfg.canal_logs)
            cargo_staff = guild.get_role(cfg.cargo_staff)
            if canal and cargo_staff:
                await canal.set_permissions(
                    guild.default_role,
                    view_channel=False,
                )
                await canal.set_permissions(
                    cargo_staff,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

        # Canal de boas-vindas: read-only (só embeds)
        if cfg.canal_bem_vindas:
            canal = guild.get_channel(cfg.canal_bem_vindas)
            if canal:
                await canal.set_permissions(
                    guild.default_role,
                    send_messages=False,
                    add_reactions=False,
                    view_channel=True,
                    read_message_history=True,
                )

    # ─────────────────────────────────────────────────────────────────────────
    # Publicação dos painéis
    # ─────────────────────────────────────────────────────────────────────────
    async def _publicar_regras(self, guild: discord.Guild, cfg) -> None:
        canal = guild.get_channel(cfg.canal_regras)
        if canal is None:
            return
        # Importa localmente para evitar circular import
        from cogs.regras import construir_embeds_regras
        guild_icon = guild.icon.url if guild.icon else None
        embeds = construir_embeds_regras(guild_icon)
        # Limpa mensagens anteriores do bot neste canal (opcional — últimas 20)
        try:
            async for m in canal.history(limit=20):
                if m.author == guild.me:
                    await m.delete()
        except discord.HTTPException:
            pass
        for i in range(0, len(embeds), 10):
            await canal.send(embeds=embeds[i:i + 10])

    async def _publicar_boas_vindas(self, guild: discord.Guild, cfg) -> None:
        canal = guild.get_channel(cfg.canal_bem_vindas)
        if canal is None:
            return
        from cogs.boas_vindas import VerificacaoView
        embed = discord.Embed(
            title=f"{Emojis.VERIFICAR} Verificação de Membro",
            description=(
                f"Olá! Para teres acesso a todos os canais da **{cfg.nome_servidor}**, "
                f"precisas de te verificar.\n\n"
                f"**Como te verificas?**\n"
                f"{Emojis.SETA} Clica no botão verde **Verificar-me** abaixo\n"
                f"{Emojis.SETA} Receberás automaticamente o cargo de membro\n"
                f"{Emojis.SETA} Já podes explorar o servidor à vontade!\n\n"
                f"Se tiveres problemas, abre um ticket em <#{cfg.canal_tickets}>."
            ),
            color=Cores.VERDE,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Sistema de Verificação")
        await canal.send(embed=embed, view=VerificacaoView())

    async def _publicar_tickets(self, guild: discord.Guild, cfg) -> None:
        canal = guild.get_channel(cfg.canal_tickets)
        if canal is None:
            return
        from cogs.tickets import PainelTicketsView, TicketsCog, CATEGORIAS_TICKET
        cog_tickets = self.bot.get_cog("TicketsCog")
        if cog_tickets is None:
            # Cria instância temporária só para a view
            cog_tickets = TicketsCog(self.bot)

        embed = discord.Embed(
            title=f"{Emojis.TICKET} Central de Tickets — {cfg.nome_servidor}",
            description=(
                f"Precisas de ajuda ou queres contactar a equipa? 🎫\n\n"
                f"**Clica numa das opções abaixo** que melhor se adequa ao teu pedido. "
                f"Um canal privado será criado onde podes falar com a staff com toda a confidencialidade.\n\n"
                f"⚠️ **Antes de abrires ticket:**\n"
                f"{Emojis.SETA} Lê as <#{cfg.canal_regras}> para garantir que a tua dúvida não é resolvida lá.\n"
                f"{Emojis.SETA} Não abras tickets por brincadeira — pode resultar em sanção.\n"
                f"{Emojis.SETA} Mantém o respeito com a staff — são voluntários a ajudar-te.\n\n"
                f"🎫 **Escolhe a categoria:**"
            ),
            color=Cores.VERMELHO,
        )
        for cat in CATEGORIAS_TICKET:
            embed.add_field(
                name=f"{cat['emoji']} {cat['label']}",
                value=cat["descricao"],
                inline=True,
            )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Sistema de Tickets")

        view = PainelTicketsView(cog_tickets)
        await canal.send(embed=embed, view=view)

    async def _publicar_autoroles(self, guild: discord.Guild, cfg) -> None:
        canal = guild.get_channel(cfg.canal_tickets)  # usa canal de tickets se auto-roles não tiver canal próprio
        # Melhor: cria um canal específico para auto-roles na categoria de info
        categoria_info = discord.utils.get(guild.categories, name="📡 Informações")
        canal_ar = discord.utils.get(guild.text_channels, name="auto-roles")
        if canal_ar is None and categoria_info:
            canal_ar = await guild.create_text_channel(
                name="auto-roles",
                topic="🎭 Escolhe os teus cargos",
                category=categoria_info,
            )
            # Read-only
            await canal_ar.set_permissions(
                guild.default_role,
                send_messages=False,
                add_reactions=False,
                view_channel=True,
                read_message_history=True,
            )

        if canal_ar is None:
            return

        from cogs.auto_roles import AutoRolesView, carregar_autoroles
        opcoes = carregar_autoroles()

        embed = discord.Embed(
            title=f"🎭 Escolhe os teus Cargos — {cfg.nome_servidor}",
            description=(
                f"Seleciona no menu abaixo os cargos que queres atribuir-te! 🎭\n\n"
                f"Podes escolher **vários ao mesmo tempo** — clica novamente para remover.\n\n"
                f"**Categorias disponíveis:**\n"
                f"{Emojis.SETA} 🔔 Notificações\n"
                f"{Emojis.SETA} 🎮 Interesses (gaming, música, arte)\n"
                f"{Emojis.SETA} 🌍 Região de Portugal\n\n"
                f"*Os cargos são opcionais e não afetam o teu acesso ao servidor.*"
            ),
            color=Cores.DOURADO,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Auto-Roles")

        view = AutoRolesView(opcoes)
        await canal_ar.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCog(bot))
