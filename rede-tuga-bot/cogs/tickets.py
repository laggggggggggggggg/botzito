"""
Cog de Tickets — sistema completo e profissional de gestão de tickets.

Funcionalidades:
  • Painel com 7 categorias (Suporte Geral, Reportar Player, Reclamações Staff,
    Parcerias, Apelar Ban, Doações, Bugs/Sugestões)
  • Modal de motivo ao clicar num botão
  • Criação de canal privado com permissões restrictas
  • Painel de controlo dentro do ticket (fechar, reivindicar, transcript)
  • Persistência do estado em JSON (survive a restarts no Railway)
  • Logs de todas as ações
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, config, TICKETS_FILE
from utils import (
    carregar_json,
    embed_aviso,
    embed_base,
    embed_erro,
    embed_sucesso,
    e_staff,
    guardar_json,
    log_evento,
)


# ─────────────────────────────────────────────────────────────────────────────
# Definição das categorias de ticket
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIAS_TICKET: list[dict] = [
    {
        "id": "suporte",
        "label": "Suporte Geral",
        "emoji": Emojis.SUPORTE,
        "cor": Cores.VERDE,
        "descricao": "Dúvidas gerais sobre o servidor, Discord ou qualquer assunto.",
        "placeholder": "Descreve a tua dúvida...",
    },
    {
        "id": "report",
        "label": "Reportar Player",
        "emoji": Emojis.REPORT,
        "cor": Cores.ERRO,
        "descricao": "Denúncia de um jogador por comportamento inadequado.",
        "placeholder": "Indica o jogador e o motivo da denúncia...",
    },
    {
        "id": "reclamacao",
        "label": "Reclamações Staff",
        "emoji": Emojis.RECLAMACAO,
        "cor": Cores.AVISO,
        "descricao": "Queixas sobre membros da equipa de moderação.",
        "placeholder": "Descreve a tua queixa sobre a staff...",
    },
    {
        "id": "parceria",
        "label": "Parcerias",
        "emoji": Emojis.PARCERIA,
        "cor": Cores.DOURADO,
        "descricao": "Propostas de parceria com outros servidores ou criadores.",
        "placeholder": "Descreve a proposta de parceria...",
    },
    {
        "id": "apelar",
        "label": "Apelar Ban",
        "emoji": Emojis.BAN,
        "cor": Cores.VERMELHO,
        "descricao": "Recursos de bans ou mutes aplicados no servidor.",
        "placeholder": "Indica o motivo do ban e por que deves ser desbanido...",
    },
    {
        "id": "doacao",
        "label": "Doações / VIP",
        "emoji": Emojis.DOACAO,
        "cor": Cores.DOURADO,
        "descricao": "Pedidos relacionados com doações, VIP ou benefícios.",
        "placeholder": "Descreve a tua questão sobre doações/VIP...",
    },
    {
        "id": "bug",
        "label": "Bugs / Sugestões",
        "emoji": Emojis.BUG,
        "cor": Cores.CINZA,
        "descricao": "Reportar bugs ou sugerir melhorias para o servidor.",
        "placeholder": "Descreve o bug ou a sugestão...",
    },
]


def categoria_por_id(cat_id: str) -> Optional[dict]:
    for c in CATEGORIAS_TICKET:
        if c["id"] == cat_id:
            return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Modal de motivo
# ─────────────────────────────────────────────────────────────────────────────
class MotivoTicketModal(discord.ui.Modal):
    """Modal que pede o motivo/descrição ao criar um ticket."""

    def __init__(self, categoria: dict, cog: "TicketsCog") -> None:
        super().__init__(title=f"{categoria['emoji']} {categoria['label']}", timeout=300)
        self.categoria = categoria
        self.cog = cog

        self.motivo = discord.ui.TextInput(
            label="Descreve o teu problema",
            placeholder=categoria["placeholder"],
            style=discord.TextStyle.paragraph,
            min_length=10,
            max_length=1000,
            required=True,
        )
        self.add_item(self.motivo)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.criar_ticket(interaction, self.categoria, self.motivo.value)


# ─────────────────────────────────────────────────────────────────────────────
# Painel principal de tickets (botões)
# ─────────────────────────────────────────────────────────────────────────────
class PainelTicketsView(discord.ui.View):
    """Painel com 7 botões — um por categoria de ticket."""

    def __init__(self, cog: "TicketsCog") -> None:
        super().__init__(timeout=None)
        self.cog = cog
        # Adiciona um botão por categoria (Discord aceita até 25)
        for cat in CATEGORIAS_TICKET:
            self.add_item(BotaoCategoria(cat, cog))


class BotaoCategoria(discord.ui.Button):
    """Botão individual do painel de tickets."""

    def __init__(self, categoria: dict, cog: "TicketsCog") -> None:
        # Cores dos botões: estilo danger para report/ban, success para suporte, etc.
        if categoria["id"] in ("report", "apelar"):
            style = discord.ButtonStyle.danger
        elif categoria["id"] == "suporte":
            style = discord.ButtonStyle.success
        elif categoria["id"] in ("doacao", "parceria"):
            style = discord.ButtonStyle.success
        else:
            style = discord.ButtonStyle.secondary

        super().__init__(
            label=categoria["label"],
            emoji=categoria["emoji"],
            style=style,
            custom_id=f"rede_tuga:ticket:{categoria['id']}",
            row=categoria["id"] != "suporte" and 0 or 0,  # auto-layout
        )
        self.categoria = categoria
        self.cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        # Verifica se o utilizador já tem ticket aberto
        estado = carregar_json(TICKETS_FILE, {"tickets": {}})
        tickets_ativos = estado.get("tickets", {})

        for tid, t in tickets_ativos.items():
            if t.get("user_id") == interaction.user.id and t.get("aberto"):
                canal_existente = interaction.guild.get_channel(t.get("canal_id", 0))
                if canal_existente:
                    await interaction.response.send_message(
                        embed=embed_aviso(
                            "Já tens ticket aberto",
                            f"Já tens um ticket ativo: {canal_existente.mention}. "
                            f"Fecha-o antes de abrir outro.",
                        ),
                        ephemeral=True,
                    )
                    return

        # Mostra o modal
        await interaction.response.send_modal(MotivoTicketModal(self.categoria, self.cog))


# ─────────────────────────────────────────────────────────────────────────────
# Painel de controlo dentro do ticket
# ─────────────────────────────────────────────────────────────────────────────
class ControloTicketView(discord.ui.View):
    """Botões de controlo dentro do canal de ticket."""

    def __init__(self, cog: "TicketsCog", dono_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.dono_id = dono_id

    @discord.ui.button(
        label="Fechar Ticket",
        emoji=Emojis.FECHAR,
        style=discord.ButtonStyle.danger,
        custom_id="rede_tuga:ticket_fechar",
    )
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Apenas o dono ou staff pode fechar
        if interaction.user.id != self.dono_id and not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas o dono do ticket ou a staff pode fechá-lo."),
                ephemeral=True,
            )
            return
        await self.cog.fechar_ticket(interaction, confirmar=False)

    @discord.ui.button(
        label="Reivindicar",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="rede_tuga:ticket_reivindicar",
    )
    async def reivindicar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas a staff pode reivindicar tickets."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=embed_sucesso(
                "Ticket reivindicado!",
                f"{interaction.user.mention} vai tratar deste ticket. Obrigado! 🙌",
            )
        )

    @discord.ui.button(
        label="Transcript",
        emoji=Emojis.TRANSCRIPT,
        style=discord.ButtonStyle.secondary,
        custom_id="rede_tuga:ticket_transcript",
    )
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas a staff pode gerar transcripts."),
                ephemeral=True,
            )
            return
        await self.cog.gerar_transcript(interaction)


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal de Tickets
# ─────────────────────────────────────────────────────────────────────────────
class TicketsCog(commands.Cog):
    """Sistema completo de tickets para a Rede Tuga."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Regista views persistentes
        self.bot.add_view(PainelTicketsView(self))
        # Para os botões de controlo, o dono_id é dinâmico por canal — usamos uma factory
        # Discord só permite custom_id fixo, mas o handler genérico abaixo resolve

    # ─────────────────────────────────────────────────────────────────────────
    # Comando: criar painel de tickets
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="painel_tickets",
        description="Cria o painel principal de tickets no canal atual (staff).",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def painel_tickets(self, interaction: discord.Interaction) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas a staff pode usar este comando."),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"{Emojis.TICKET} Central de Tickets — {config.nome_servidor}",
            description=(
                f"Precisas de ajuda ou queres contactar a equipa? 🎫\n\n"
                f"**Clica numa das opções abaixo** que melhor se adequa ao teu pedido. "
                f"Um canal privado será criado onde podes falar com a staff com toda a confidencialidade.\n\n"
                f"⚠️ **Antes de abrires ticket:**\n"
                f"{Emojis.SETA} Lê as <#{config.canal_regras}> para garantir que a tua dúvida não é resolvida lá.\n"
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
        embed.set_thumbnail(
            url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else discord.Embed.Empty
        )
        embed.set_footer(text=f"{config.nome_servidor} • Sistema de Tickets")

        view = PainelTicketsView(self)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            embed=embed_sucesso("Painel criado!", "Painel de tickets enviado neste canal."),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            f"{Emojis.TICKET} Painel de tickets criado",
            f"Criado por {interaction.user.mention} em {interaction.channel.mention}.",
            Cores.VERDE,
            interaction.user,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Criar ticket
    # ─────────────────────────────────────────────────────────────────────────
    async def criar_ticket(
        self, interaction: discord.Interaction, categoria: dict, motivo: str
    ) -> None:
        guild = interaction.guild
        if guild is None:
            return

        # Categoria onde criar o canal
        parent = None
        if config.categoria_tickets:
            parent = guild.get_channel(config.categoria_tickets)

        # Nome do canal: ticket-{tipo}-{username}
        nome_canal = f"ticket-{categoria['id']}-{interaction.user.name}"[:50]

        # Permissões: só dono, staff e bot veem
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
        }

        # Adiciona cargo de ticket_staff se configurado
        if config.cargo_ticket_staff:
            cargo = guild.get_role(config.cargo_ticket_staff)
            if cargo:
                overwrites[cargo] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )
        # Adiciona cargo de staff geral
        if config.cargo_staff:
            cargo = guild.get_role(config.cargo_staff)
            if cargo:
                overwrites[cargo] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )

        try:
            canal = await guild.create_text_channel(
                name=nome_canal,
                topic=(
                    f"Ticket de {interaction.user} ({interaction.user.id}) • "
                    f"Categoria: {categoria['label']} • Motivo: {motivo[:200]}"
                ),
                overwrites=overwrites,
                category=parent if isinstance(parent, discord.CategoryChannel) else None,
                reason=f"Ticket aberto por {interaction.user} — {categoria['label']}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Sem permissões",
                    "O bot não tem permissão para criar canais. Verifica as permissões do bot.",
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                embed=embed_erro("Erro", f"Não foi possível criar o canal: `{e}`"),
                ephemeral=True,
            )
            return

        # Persiste o estado
        estado = carregar_json(TICKETS_FILE, {"tickets": {}, "contador": 0})
        contador = estado.get("contador", 0) + 1
        ticket_id = f"#{contador:04d}"
        estado["tickets"][ticket_id] = {
            "id": ticket_id,
            "canal_id": canal.id,
            "user_id": interaction.user.id,
            "categoria": categoria["id"],
            "categoria_label": categoria["label"],
            "motivo": motivo,
            "aberto": True,
            "criado_em": datetime.now(timezone.utc).isoformat(),
            "criado_por": str(interaction.user),
        }
        estado["contador"] = contador
        guardar_json(TICKETS_FILE, estado)

        # Mensagem de confirmação ao utilizador
        await interaction.response.send_message(
            embed=embed_sucesso(
                f"{categoria['emoji']} Ticket criado!",
                f"O teu ticket foi criado: {canal.mention}\n"
                f"**ID:** `{ticket_id}` • **Categoria:** {categoria['label']}\n"
                f"A staff responderá o mais breve possível.",
            ),
            ephemeral=True,
        )

        # Mensagem dentro do ticket
        embed_ticket = discord.Embed(
            title=f"{categoria['emoji']} {categoria['label']} — Ticket {ticket_id}",
            description=(
                f"Bem-vindo {interaction.user.mention}! 🎫\n\n"
                f"**Motivo apresentado:**\n```{motivo}```\n\n"
                f"📋 **Regras do ticket:**\n"
                f"{Emojis.SETA} Mantém o respeito com a staff.\n"
                f"{Emojis.SETA} Explica o teu problema com o máximo de detalhe.\n"
                f"{Emojis.SETA} Não marques a staff — serás atendido quando possível.\n"
                f"{Emojis.SETA} Para fechar, clica no botão **Fechar Ticket** abaixo."
            ),
            color=categoria["cor"],
            timestamp=datetime.now(timezone.utc),
        )
        embed_ticket.set_thumbnail(
            url=interaction.user.display_avatar.url if interaction.user.display_avatar else discord.Embed.Empty
        )
        embed_ticket.set_footer(text=f"{config.nome_servidor} • Ticket {ticket_id}")

        # Pinga staff se configurado
        conteudo = ""
        if config.cargo_ticket_staff:
            cargo = guild.get_role(config.cargo_ticket_staff)
            if cargo:
                conteudo = f"{cargo.mention} — novo ticket!"
        elif config.cargo_staff:
            cargo = guild.get_role(config.cargo_staff)
            if cargo:
                conteudo = f"{cargo.mention} — novo ticket!"

        view = ControloTicketView(self, interaction.user.id)
        await canal.send(content=conteudo, embed=embed_ticket, view=view, allowed_mentions=discord.AllowedMentions(roles=True))

        await log_evento(
            self.bot,
            f"{Emojis.TICKET} Ticket aberto",
            f"**{ticket_id}** • {categoria['label']}\n"
            f"Aberto por {interaction.user.mention} no canal {canal.mention}.\n"
            f"Motivo: {motivo[:200]}",
            categoria["cor"],
            interaction.user,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Fechar ticket
    # ─────────────────────────────────────────────────────────────────────────
    async def fechar_ticket(self, interaction: discord.Interaction, confirmar: bool = False) -> None:
        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel):
            return

        # Encontra o ticket no estado
        estado = carregar_json(TICKETS_FILE, {"tickets": {}})
        ticket_encontrado: Optional[dict] = None
        ticket_id_encontrado: Optional[str] = None
        for tid, t in estado.get("tickets", {}).items():
            if t.get("canal_id") == canal.id and t.get("aberto"):
                ticket_encontrado = t
                ticket_id_encontrado = tid
                break

        if ticket_encontrado is None:
            await interaction.response.send_message(
                embed=embed_erro("Não é ticket", "Este canal não é um ticket ativo."),
                ephemeral=True,
            )
            return

        # Confirmação com botões
        view_confirmar = ConfirmarFechoView()
        await interaction.response.send_message(
            embed=embed_aviso(
                f"{Emojis.FECHAR} Fechar ticket?",
                f"{interaction.user.mention}, tens a certeza que queres fechar este ticket?\n"
                f"Um transcript será gerado antes do fecho.\n\n"
                f"Clica em **Confirmar** para fechar nos próximos 30 segundos.",
            ),
            view=view_confirmar,
        )

        # Espera pela confirmação
        timed_out = await view_confirmar.wait()
        if timed_out:
            try:
                await interaction.edit_original_response(
                    content="⏱️ Confirmação expirou — ticket não fechado.",
                    view=None,
                )
            except discord.HTTPException:
                pass
            return

        if not view_confirmar.confirmado:
            try:
                await interaction.edit_original_response(
                    content="❌ Fecho cancelado.",
                    view=None,
                )
            except discord.HTTPException:
                pass
            return

        # Gera transcript antes de fechar
        await self._gerar_e_enviar_transcript(canal, interaction.user, ticket_encontrado)

        # Atualiza estado
        ticket_encontrado["aberto"] = False
        ticket_encontrado["fechado_em"] = datetime.now(timezone.utc).isoformat()
        ticket_encontrado["fechado_por"] = str(interaction.user)
        estado["tickets"][ticket_id_encontrado] = ticket_encontrado
        guardar_json(TICKETS_FILE, estado)

        await log_evento(
            self.bot,
            f"{Emojis.FECHAR} Ticket fechado",
            f"**{ticket_id_encontrado}** • {ticket_encontrado['categoria_label']}\n"
            f"Fechado por {interaction.user.mention} no canal #{canal.name}.",
            Cores.ERRO,
            interaction.user,
        )

        # Apaga o canal
        try:
            await canal.send(embed=embed_aviso("A fechar...", "Este canal será apagado em 5 segundos."))
            await asyncio_sleep(5)
            await canal.delete(reason=f"Ticket fechado por {interaction.user}")
        except discord.HTTPException:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Gerar transcript (anexo .txt)
    # ─────────────────────────────────────────────────────────────────────────
    async def gerar_transcript(self, interaction: discord.Interaction) -> None:
        canal = interaction.channel
        await self._gerar_e_enviar_transcript(canal, interaction.user, None, interaction=interaction)

    async def _gerar_e_enviar_transcript(
        self,
        canal: discord.TextChannel,
        quem_pediu: discord.abc.User,
        ticket_info: Optional[dict],
        interaction: Optional[discord.Interaction] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True) if interaction else None

        linhas: list[str] = []
        linhas.append("╔══════════════════════════════════════════════════════════════╗")
        linhas.append(f"║  TRANSCRIPT DE TICKET — {config.nome_servidor}")
        linhas.append("╚══════════════════════════════════════════════════════════════╝")
        linhas.append(f"Canal: #{canal.name}")
        linhas.append(f"Servidor: {canal.guild.name}")
        linhas.append(f"Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        linhas.append(f"Por: {quem_pediu}")
        if ticket_info:
            linhas.append(f"Ticket ID: {ticket_info.get('id', '?')}")
            linhas.append(f"Categoria: {ticket_info.get('categoria_label', '?')}")
            linhas.append(f"Aberto por: {ticket_info.get('criado_por', '?')}")
            linhas.append(f"Motivo: {ticket_info.get('motivo', '?')}")
        linhas.append("─" * 64)
        linhas.append("")

        # Lê as últimas 500 mensagens
        contador = 0
        async for msg in canal.history(limit=500, oldest_first=True):
            contador += 1
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            autor = f"{msg.author} ({msg.author.id})"
            conteudo = msg.clean_content or "[sem texto]"
            anexos = "\n  ".join(f"[ANEXO] {a.url}" for a in msg.attachments)
            linhas.append(f"[{timestamp}] {autor}:")
            linhas.append(f"  {conteudo}")
            if anexos:
                linhas.append(f"  {anexos}")
            linhas.append("")

        linhas.append("─" * 64)
        linhas.append(f"Total de mensagens: {contador}")
        linhas.append(f"Fim do transcript.")

        conteudo_final = "\n".join(linhas)
        buffer = io.BytesIO(conteudo_final.encode("utf-8"))
        ficheiro = discord.File(buffer, filename=f"transcript-{canal.name}.txt")

        # Envia para o canal (visível para staff) e resposta efêmera a quem pediu
        embed = discord.Embed(
            title=f"{Emojis.TRANSCRIPT} Transcript gerado",
            description=f"Transcript de **#{canal.name}** • {contador} mensagens.\nGerado por {quem_pediu.mention}.",
            color=Cores.CINZA,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=config.nome_servidor)

        if interaction and interaction.response.is_done():
            await interaction.followup.send(embed=embed, file=ficheiro, ephemeral=True)
        elif interaction:
            await interaction.response.send_message(embed=embed, file=ficheiro, ephemeral=True)

        # Envia para o canal de logs se existir
        if config.canal_logs:
            canal_logs = canal.guild.get_channel(config.canal_logs)
            if canal_logs:
                # Recria o buffer porque o anterior foi consumido
                buffer2 = io.BytesIO(conteudo_final.encode("utf-8"))
                ficheiro2 = discord.File(buffer2, filename=f"transcript-{canal.name}.txt")
                await canal_logs.send(embed=embed, file=ficheiro2)


# ─────────────────────────────────────────────────────────────────────────────
# View de confirmação de fecho
# ─────────────────────────────────────────────────────────────────────────────
class ConfirmarFechoView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=30)
        self.confirmado: bool = False

    @discord.ui.button(label="Confirmar", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmado = True
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Cancelar", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmado = False
        self.stop()
        await interaction.response.edit_message(view=None)


# ─────────────────────────────────────────────────────────────────────────────
# Handler de interações persistentes (depois de restart)
# ─────────────────────────────────────────────────────────────────────────────
async def asyncio_sleep(s: float) -> None:
    import asyncio as _asyncio
    await _asyncio.sleep(s)


async def setup(bot: commands.Bot) -> None:
    cog = TicketsCog(bot)
    await bot.add_cog(cog)

    # Handler custom para botões persistentes de controlo (não registados como View)
    @bot.listen("on_interaction")
    async def _handle_persistent_ticket_controls(interaction: discord.Interaction) -> None:
        if not interaction.data:
            return
        custom_id = interaction.data.get("component_id") or interaction.data.get("custom_id")
        if not isinstance(custom_id, str):
            return

        if custom_id in ("rede_tuga:ticket_fechar", "rede_tuga:ticket_transcript"):
            cog_local = bot.get_cog("TicketsCog")
            if cog_local is None:
                return
            if custom_id == "rede_tuga:ticket_fechar":
                await cog_local.fechar_ticket(interaction, confirmar=True)
            else:
                await cog_local.gerar_transcript(interaction)
