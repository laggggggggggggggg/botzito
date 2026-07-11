"""
Cog de SLA Tracking — monitoriza tickets abertos sem resposta da staff.

Funcionamento:
  • Task em background corre a cada 5 minutos
  • Para cada ticket aberto, verifica quando foi a última resposta da staff
  • Se passar dos limiares configurados, envia avisos:
    - 1º aviso: no canal de SLA/logs
    - 2º aviso: dentro do ticket (pinga staff)
    - 3º aviso: escalada (pinga admin)
  • Quando a staff responde, o timer é resetado

Configuração via /editar → SLA:
  • sla_ativo (bool)
  • sla_aviso1_horas (int, default 1)
  • sla_aviso2_horas (int, default 2)
  • sla_aviso3_horas (int, default 6)
  • canal_sla (int, 0 = usa canal_logs)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, TICKETS_FILE, get_config, save_config
from utils import carregar_json, guardar_json, embed_erro, embed_sucesso, embed_aviso, e_admin, log_evento

_log = logging.getLogger("rede_tuga.sla")

# Intervalo de verificação em segundos (1 hora)
# O SLA só verifica tickets de hora em hora — não é repetitivo.
# Cada nível de aviso só é enviado UMA VEZ por ticket.
INTERVALO_VERIFICACAO = 3600


class SLACog(commands.Cog):
    """Sistema de SLA Tracking para tickets."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._sla_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def cog_load(self) -> None:
        """Inicia a task de SLA quando a cog é carregada."""
        if self._sla_task is None or self._sla_task.done():
            self._sla_task = asyncio.create_task(self._loop_sla())
            _log.info("✅ Task de SLA Tracking iniciada (verifica a cada 1h)")

    async def cog_unload(self) -> None:
        """Cancela a task quando a cog é descarregada."""
        if self._sla_task and not self._sla_task.done():
            self._sla_task.cancel()
            _log.info("🛑 Task de SLA Tracking parada")

    async def _loop_sla(self) -> None:
        """Loop principal que verifica tickets a cada 5 minutos."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._verificar_tickets()
            except Exception as e:
                _log.error("Erro no loop de SLA: %s", e)
            await asyncio.sleep(INTERVALO_VERIFICACAO)

    async def _verificar_tickets(self) -> None:
        """Verifica todos os tickets abertos e envia avisos se necessário."""
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

            # Verifica quando foi a última resposta da staff
            ultima_staff = await self._ultima_resposta_staff(canal, cfg, guild)
            criado_em = self._parse_datetime(ticket.get("criado_em"))

            if criado_em is None:
                continue

            # Se staff respondeu, usa a data da última resposta; senão usa a data de criação
            referencia = ultima_staff if ultima_staff else criado_em
            tempo_sem_resposta = (agora - referencia).total_seconds() / 3600  # em horas

            # Determina o nível de aviso atual
            nivel_aviso = ticket.get("nivel_aviso", 0)
            novo_nivel = 0

            if tempo_sem_resposta >= cfg.sla_aviso3_horas:
                novo_nivel = 3
            elif tempo_sem_resposta >= cfg.sla_aviso2_horas:
                novo_nivel = 2
            elif tempo_sem_resposta >= cfg.sla_aviso1_horas:
                novo_nivel = 1

            # Se o nível subiu, envia aviso
            if novo_nivel > nivel_aviso:
                await self._enviar_aviso(
                    canal, ticket, cfg, novo_nivel, tempo_sem_resposta, guild
                )
                ticket["nivel_aviso"] = novo_nivel
                ticket["ultima_verificacao_sla"] = agora.isoformat()
                tickets[ticket_id] = ticket
                houve_alteracao = True

            # Se a staff respondeu depois do último aviso, reset do nível
            elif ultima_staff and nivel_aviso > 0:
                ultima_verificacao = self._parse_datetime(
                    ticket.get("ultima_verificacao_sla")
                )
                if ultima_verificacao and ultima_staff > ultima_verificacao:
                    ticket["nivel_aviso"] = 0
                    ticket["ultima_verificacao_sla"] = agora.isoformat()
                    tickets[ticket_id] = ticket
                    houve_alteracao = True
                    _log.info(
                        "✅ SLA reset para ticket %s — staff respondeu",
                        ticket_id,
                    )

        if houve_alteracao:
            async with self._lock:
                guardar_json(TICKETS_FILE, estado)

    async def _ultima_resposta_staff(
        self, canal: discord.TextChannel, cfg, guild: discord.Guild
    ) -> Optional[datetime]:
        """Verifica quando foi a última mensagem da staff no canal do ticket."""
        try:
            async for msg in canal.history(limit=50, oldest_first=False):
                # Ignora mensagens do bot
                if msg.author.bot:
                    continue
                # Verifica se o autor é staff
                member = guild.get_member(msg.author.id)
                if member is None:
                    continue
                if member.guild_permissions.administrator:
                    return msg.created_at
                if cfg.cargo_staff and member.get_role(cfg.cargo_staff):
                    return msg.created_at
                if cfg.cargo_ticket_staff and member.get_role(cfg.cargo_ticket_staff):
                    return msg.created_at
        except discord.HTTPException:
            pass
        return None

    def _parse_datetime(self, valor: str) -> Optional[datetime]:
        """Faz parse de ISO datetime string."""
        if not valor:
            return None
        try:
            return datetime.fromisoformat(valor)
        except (ValueError, TypeError):
            return None

    async def _enviar_aviso(
        self,
        canal: discord.TextChannel,
        ticket: dict,
        cfg,
        nivel: int,
        horas: float,
        guild: discord.Guild,
    ) -> None:
        """Envia aviso de SLA no canal apropriado."""
        ticket_id = ticket.get("id", "?")
        categoria = ticket.get("categoria_label", "?")
        user_id = ticket.get("user_id", 0)

        if nivel == 1:
            # 1º aviso — no canal de SLA/logs
            canal_destino = self._get_canal_sla(cfg, guild)
            if canal_destino is None:
                return
            embed = discord.Embed(
                title="⏰ Ticket sem resposta da staff",
                description=(
                    f"🎫 **Ticket:** `{ticket_id}`\n"
                    f"📋 **Categoria:** {categoria}\n"
                    f"⏰ **Sem resposta há:** {horas:.1f}h\n"
                    f"🔗 {canal.mention}"
                ),
                color=Cores.AVISO,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text=f"{cfg.nome_servidor} • SLA Tracking")
            try:
                await canal_destino.send(embed=embed)
            except discord.HTTPException:
                pass
            _log.info("SLA aviso 1 enviado para ticket %s (%.1fh)", ticket_id, horas)

        elif nivel == 2:
            # 2º aviso — dentro do ticket, pinga staff
            cargo_mention = ""
            if cfg.cargo_staff:
                cargo = guild.get_role(cfg.cargo_staff)
                if cargo:
                    cargo_mention = cargo.mention

            embed = discord.Embed(
                title="⚠️ Lembrete de SLA",
                description=(
                    f"Este ticket está há **{horas:.1f}h** sem resposta da staff.\n"
                    f"{cargo_mention} — por favor verificai este ticket.\n\n"
                    f"— Tuguinha 🇵🇹"
                ),
                color=Cores.AVISO,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text=f"{cfg.nome_servidor} • SLA Tracking")
            try:
                await canal.send(
                    content=cargo_mention if cargo_mention else None,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=True),
                )
            except discord.HTTPException:
                pass
            _log.info("SLA aviso 2 enviado no ticket %s (%.1fh)", ticket_id, horas)

        elif nivel == 3:
            # 3º aviso — escalada, pinga admin
            canal_destino = self._get_canal_sla(cfg, guild)
            admin_mention = ""
            if cfg.cargo_admin:
                cargo = guild.get_role(cfg.cargo_admin)
                if cargo:
                    admin_mention = cargo.mention

            embed = discord.Embed(
                title="🚨 SLA EXCEDIDO — Escalada",
                description=(
                    f"🚫 **Ticket:** `{ticket_id}`\n"
                    f"📋 **Categoria:** {categoria}\n"
                    f"⏰ **Sem resposta há:** {horas:.1f}h\n"
                    f"🔗 {canal.mention}\n\n"
                    f"⚠️ Este ticket excedeu o SLA de {cfg.sla_aviso3_horas}h.\n"
                    f"{admin_mention} — intervenção necessária."
                ),
                color=Cores.ERRO,
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text=f"{cfg.nome_servidor} • SLA Tracking — Escalada")

            if canal_destino:
                try:
                    await canal_destino.send(
                        content=admin_mention if admin_mention else None,
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(roles=True),
                    )
                except discord.HTTPException:
                    pass

            # Também envia no ticket
            try:
                await canal.send(
                    embed=discord.Embed(
                        title="🚨 SLA Excedido",
                        description=(
                            f"Este ticket está há **{horas:.1f}h** sem resposta.\n"
                            f"A administração foi notificada.\n\n"
                            f"— Tuguinha 🇵🇹"
                        ),
                        color=Cores.ERRO,
                    )
                )
            except discord.HTTPException:
                pass
            _log.info("SLA aviso 3 (escalada) enviado para ticket %s (%.1fh)", ticket_id, horas)

    def _get_canal_sla(self, cfg, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Obtém o canal onde enviar avisos de SLA (canal_sla ou canal_logs)."""
        canal_id = cfg.canal_sla if cfg.canal_sla else cfg.canal_logs
        if not canal_id:
            return None
        return guild.get_channel(canal_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SLACog(bot))
