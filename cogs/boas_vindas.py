"""
Cog de Boas-Vindas — envia embed personalizada quando um membro entra,
envia DM com resumo das regras.

Sistema de verificação foi REMOVIDO por pedido do utilizador.
As mensagens são completamente customizáveis via /editar.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config
from utils import embed_erro, embed_sucesso, log_evento, mention_canal_regras


class BoasVindasCog(commands.Cog):
    """Sistema de boas-vindas (sem verificação)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        cfg = get_config(member.guild.id)
        if not cfg.setup_completo or not cfg.boas_vindas_ativas:
            return

        await self._enviar_boas_vindas_canal(member, cfg)
        await self._enviar_dm(member, cfg)

        await log_evento(
            self.bot,
            f"{Emojis.BEM_VINDO} Novo membro",
            f"{member.mention} entrou no servidor!\n"
            f"Conta criada em <t:{int(member.created_at.timestamp())}:R>.",
            Cores.VERDE,
            member,
            member.guild,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return
        await log_evento(
            self.bot,
            "👋 Membro saiu",
            f"**{member}** (`{member.id}`) deixou o servidor.",
            Cores.CINZA,
            member,
            member.guild,
        )

    async def _enviar_boas_vindas_canal(self, member: discord.Member, cfg) -> None:
        if not cfg.canal_bem_vindas:
            return
        canal = self.bot.get_channel(cfg.canal_bem_vindas)
        if canal is None:
            return

        guild = member.guild
        membros = guild.member_count or 0

        # Substitui placeholders na mensagem customizada
        msg = cfg.get_msg_bem_vindo()
        msg = msg.replace("{user}", member.mention)
        msg = msg.replace("{count}", str(membros))
        msg = msg.replace("{regras}", mention_canal_regras(cfg))
        msg = msg.replace("{tickets}", f"<#{cfg.canal_tickets}>" if cfg.canal_tickets else "#tickets")

        embed = discord.Embed(
            title=f"{Emojis.BEM_VINDO} Bem-vindo à {cfg.nome_servidor}!",
            description=msg,
            color=Cores.VERMELHO,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        embed.set_footer(text=f"Membro #{membros:04d} • {cfg.nome_servidor}")

        try:
            await canal.send(
                content=member.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException:
            pass

    async def _enviar_dm(self, member: discord.Member, cfg) -> None:
        embed = discord.Embed(
            title=f"{Emojis.REGRAS} Bem-vindo à {cfg.nome_servidor}! 🇵🇹",
            description=(
                f"Olá **{member.name}**! Recebeste as boas-vindas oficiais da nossa comunidade.\n\n"
                f"Antes de começares a interagir, é importante que leias as regras completas "
                f"no servidor. Aqui ficam as **regras essenciais** resumidas:"
            ),
            color=Cores.VERDE,
        )
        embed.add_field(
            name="🤝 Respeito",
            value="Trata todos com respeito. Sem insultos, bullying ou discurso de ódio.",
            inline=False,
        )
        embed.add_field(
            name="🚫 Proibido",
            value="NSFW, spam, phishing, pirataria e partilha de dados pessoais.",
            inline=False,
        )
        embed.add_field(
            name="🎮 Gaming",
            value="Sem cheating. Respeita regras dos canais de voz e jogos.",
            inline=False,
        )
        embed.add_field(
            name="🎫 Tickets",
            value="Para suporte, abre ticket em #tickets. Não abras tickets por brincadeira.",
            inline=False,
        )
        embed.add_field(
            name="⚖️ Sanções",
            value="Aviso → mute → ban temporário → ban permanente.",
            inline=False,
        )
        embed.add_field(
            name="✅ Próximo passo",
            value=(
                f"Explora o servidor e diverte-te! Se precisares de ajuda, "
                + (f"abre um ticket em <#{cfg.canal_tickets}>." if cfg.canal_tickets else "abre um ticket no canal de tickets.")
            ),
            inline=False,
        )
        embed.set_footer(text=cfg.nome_servidor)

        try:
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BoasVindasCog(bot))
