"""
Cog de SLA Tracking — sistema inteligente de avisos de tickets.

Lógica nova:
  • A cada 1h, verifica tickets abertos
  • Para cada ticket, lê a última mensagem NÃO-BOT
  • Se a última mensagem foi da STAFF (cargo 1489030726954385533 ou admin):
    → O ticket está à espera do DONO → pinga o dono do ticket
  • Se a última mensagem foi do DONO do ticket (ou ninguém respondeu):
    → O ticket está à espera da STAFF → pinga o cargo 1489030726954385533
  • Só pings UMA VEZ por "espera" (rastreia em JSON para não spammar)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from config import Cores, Emojis, TICKETS_FILE, get_config
from utils import carregar_json, guardar_json

_log = logging.getLogger("rede_tuga.sla")

INTERVALO_VERIFICACAO = 3600  # 1 hora
CARGO_SUPORTE_ID = 1489030726954385533
TEMPO_ESPERA_HORAS = 1  # Quantas horas sem resposta antes de pingar


class SLACog(commands.Cog):
    """Sistema de SLA Tracking inteligente para tickets."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._sla_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def cog_load(self) -> None:
        if self._sla_task is None or self._sla_task.done():
            self._sla_task = asyncio.create_task(self._loop_sla())
            _log.info("✅ Task de SLA Tracking iniciada (verifica a cada 1h)")

    async def cog_unload(self) -> None:
        if self._sla_task and not self._sla_task.done():
            self._sla_task.cancel()

    async def _loop_sla(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._verificar_tickets()
            except Exception as e:
                _log.error("Erro no loop de SLA: %s", e)
            await asyncio.sleep(INTERVALO_VERIFICACAO)

    async def _verificar_tickets(self) -> None:
        """Verifica todos os tickets abertos."""
        estado = carregar_json(TICKETS_FILE, {"tickets": {}})
        tickets = estado.get("tickets", {})
        agora = datetime.now(timezone.utc)
        houve_alteracao = False

        for ticket_id, ticket in tickets.items():
            if not ticket.get("aberto"):
                continue

            guild_id = ticket.get("guild_id", 0)
            if not guild_id:
                continue

            cfg = get_config(guild_id)
            if not cfg.sla_ativo:
                continue

            canal_id = ticket.get("canal_id", 0)
            if not canal_id:
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue

            canal = guild.get_channel(canal_id)
            if canal is None:
                continue

            dono_id = ticket.get("user_id", 0)
            if not dono_id:
                continue

            # Lê as últimas mensagens para determinar quem respondeu por último
            ultima_msg_info = await self._ultima_mensagem_nao_bot(canal, guild, dono_id, cfg)
            if ultima_msg_info is None:
                continue

            ultimo_autor_id, ultimo_autor_e_staff, data_ultima = ultima_msg_info
            criado_em = self._parse_dt(ticket.get("criado_em"))
            if criado_em is None:
                continue

            # Tempo desde a última mensagem (ou criação se ninguém respondeu)
            referencia = data_ultima if data_ultima else criado_em
            tempo_espera = (agora - referencia).total_seconds() / 3600

            if tempo_espera < TEMPO_ESPERA_HORAS:
                continue  # Ainda não passou tempo suficiente

            # Determina quem precisa ser pingado
            # tracking_key: "staff" = staff foi último, precisa dono | "dono" = dono foi último, precisa staff
            if ultimo_autor_e_staff:
                # Staff respondeu por último → dono precisa responder
                tracking_key = "espera_dono"
                ja_pingado = ticket.get("sla_ping_espera_dono", False)
            else:
                # Dono respondeu por último (ou ninguém respondeu) → staff precisa responder
                tracking_key = "espera_staff"
                ja_pingado = ticket.get("sla_ping_espera_staff", False)

            if ja_pingado:
                # Já pingamos para esta "espera" — não repete
                # Reset se a situação mudou
                if tracking_key == "espera_dono":
                    # Se antes estávamos à espera de staff e agora de dono, reset
                    ticket["sla_ping_espera_staff"] = False
                else:
                    ticket["sla_ping_espera_dono"] = False
                tickets[ticket_id] = ticket
                houve_alteracao = True
                continue

            # Envia o ping
            if tracking_key == "espera_dono":
                # Staff foi último → pinga o DONO
                await self._ping_dono(canal, ticket, cfg, guild, dono_id, tempo_espera)
                ticket["sla_ping_espera_dono"] = True
                ticket["sla_ping_espera_staff"] = False  # reset oposto
            else:
                # Dono foi último → pinga a STAFF
                await self._ping_staff(canal, ticket, cfg, guild, tempo_espera)
                ticket["sla_ping_espera_staff"] = True
                ticket["sla_ping_espera_dono"] = False  # reset oposto

            ticket["ultima_verificacao_sla"] = agora.isoformat()
            tickets[ticket_id] = ticket
            houve_alteracao = True

        if houve_alteracao:
            async with self._lock:
                guardar_json(TICKETS_FILE, estado)

    async def _ultima_mensagem_nao_bot(
        self, canal: discord.TextChannel, guild: discord.Guild, dono_id: int, cfg
    ) -> Optional[tuple]:
        """Retorna (user_id, e_staff, datetime) da última mensagem não-bot.
        
        Se ninguém respondeu (só bot), retorna (dono_id, False, None) — dono "precisa" de staff.
        """
        try:
            async for msg in canal.history(limit=50, oldest_first=False):
                if msg.author.bot:
                    continue

                # Verifica se é staff
                member = guild.get_member(msg.author.id)
                e_staff = False
                if member:
                    if member.guild_permissions.administrator:
                        e_staff = True
                    elif member.get_role(CARGO_SUPORTE_ID):
                        e_staff = True
                    elif cfg.cargo_staff and member.get_role(cfg.cargo_staff):
                        e_staff = True
                    elif cfg.cargo_ticket_staff and member.get_role(cfg.cargo_ticket_staff):
                        e_staff = True

                return (msg.author.id, e_staff, msg.created_at)
        except discord.HTTPException:
            pass

        # Nenhuma mensagem não-bot encontrada → dono abriu mas ninguém respondeu
        return (dono_id, False, None)

    async def _ping_dono(
        self, canal: discord.TextChannel, ticket: dict, cfg, guild: discord.Guild,
        dono_id: int, horas: float
    ) -> None:
        """Pinga o dono do ticket para responder."""
        dono_mention = f"<@{dono_id}>"
        ticket_id = ticket.get("id", "?")

        embed = discord.Embed(
            title="⏰ Precisamos da tua resposta!",
            description=(
                f"Olá {dono_mention}! A staff respondeu ao teu ticket há **{horas:.0f}h**.\n"
                f"Por favor responde para que possamos ajudar-te.\n\n"
                f"Se já não precisas de ajuda, fecha o ticket com o botão **Fechar Ticket**.\n\n"
                f"— Tuguinha 🇵🇹"
            ),
            color=Cores.AVISO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"{cfg.nome_servidor} • Ticket {ticket_id}")

        try:
            await canal.send(
                content=dono_mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException:
            pass

        _log.info("SLA: Ping ao dono %d do ticket %s (%.0fh sem resposta do dono)", dono_id, ticket_id, horas)

    async def _ping_staff(
        self, canal: discord.TextChannel, ticket: dict, cfg, guild: discord.Guild,
        horas: float
    ) -> None:
        """Pinga o cargo de staff para responder ao ticket."""
        cargo_mention = f"<@&{CARGO_SUPORTE_ID}>"
        ticket_id = ticket.get("id", "?")
        categoria = ticket.get("categoria_label", "?")

        embed = discord.Embed(
            title="⏰ Ticket à espera de resposta da staff",
            description=(
                f"🎫 **Ticket:** `{ticket_id}`\n"
                f"📋 **Categoria:** {categoria}\n"
                f"⏰ **À espera de resposta há:** {horas:.0f}h\n\n"
                f"Por favor, alguém da staff precisa de responder a este ticket.\n\n"
                f"— Tuguinha 🇵🇹"
            ),
            color=Cores.ERRO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"{cfg.nome_servidor} • SLA Tracking")

        try:
            await canal.send(
                content=cargo_mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except discord.HTTPException:
            pass

        # Também envia no canal de logs
        canal_logs = guild.get_channel(cfg.canal_logs) if cfg.canal_logs else None
        if canal_logs:
            try:
                await canal_logs.send(
                    content=cargo_mention,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=True),
                )
            except discord.HTTPException:
                pass

        _log.info("SLA: Ping à staff do ticket %s (%.0fh sem resposta da staff)", ticket_id, horas)

    def _parse_dt(self, valor: str) -> Optional[datetime]:
        if not valor:
            return None
        try:
            return datetime.fromisoformat(valor)
        except (ValueError, TypeError):
            return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SLACog(bot))
