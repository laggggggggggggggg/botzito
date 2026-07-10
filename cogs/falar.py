"""
Cog de Falar — /falar #canal "mensagem" para o Tuguinha enviar mensagens em nome da staff.

Funcionalidades:
  • /falar — envia mensagem simples como o Tuguinha em canal específico
  • /falar_embed — envia mensagem com embed formatada
  • Suporte a Markdown
  • Log de quem usou o comando
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config
from utils import embed_erro, embed_sucesso, e_admin, log_evento


class FalarCog(commands.Cog):
    """Sistema para staff falar como o Tuguinha."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="falar",
        description="💬 Faz o Tuguinha enviar uma mensagem num canal (apenas admins).",
    )
    @app_commands.describe(
        canal="Canal onde enviar a mensagem",
        mensagem="Texto da mensagem (suporta Markdown)",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_falar(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        mensagem: str,
    ) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas **administradores** podem usar este comando.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Verifica permissões do bot no canal
        perms = canal.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissões",
                    f"O Tuguinha não tem permissão para enviar mensagens em {canal.mention}.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        try:
            await canal.send(content=mensagem)
        except discord.HTTPException as e:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Erro",
                    "Falha ao enviar a mensagem. Verifica se o conteúdo é válido.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Confirmação efêmera
        await interaction.response.send_message(
            embed=embed_sucesso(
                "💬 Mensagem enviada!",
                f"Enviada para {canal.mention} pelo Tuguinha.",
                get_config(interaction.guild.id).nome_servidor,
            ),
            ephemeral=True,
        )

        # Log
        await log_evento(
            self.bot,
            "💬 Tuguinha falou",
            f"Por {interaction.user.mention} em {canal.mention}.\n\n**Conteúdo:**\n```\n{mensagem[:500]}\n```",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )

    @app_commands.command(
        name="falar_embed",
        description="🎨 Faz o Tuguinha enviar uma mensagem com embed (apenas admins).",
    )
    @app_commands.describe(
        canal="Canal onde enviar a embed",
        titulo="Título da embed",
        descricao="Descrição da embed (suporta Markdown)",
        cor="Cor (nome ou hex, ex: vermelho, #FF3B3B)",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_falar_embed(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        titulo: str,
        descricao: str,
        cor: str = "vermelho",
    ) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas **administradores** podem usar este comando.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Parse da cor
        from cogs.anuncios import parse_cor
        cor_int = parse_cor(cor)

        # Verifica permissões
        perms = canal.permissions_for(interaction.guild.me)
        if not perms.send_messages or not perms.embed_links:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissões",
                    f"O Tuguinha não tem permissão para enviar embeds em {canal.mention}.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=titulo[:256],
            description=descricao[:4000],
            color=cor_int,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(
            text=f"🎨 {get_config(interaction.guild.id).nome_servidor} • Tuguinha",
            icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else discord.Embed.Empty,
        )

        try:
            await canal.send(embed=embed)
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Erro",
                    "Falha ao enviar a embed.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embed_sucesso(
                "🎨 Embed enviada!",
                f"Enviada para {canal.mention}.",
                get_config(interaction.guild.id).nome_servidor,
            ),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            "🎨 Tuguinha enviou embed",
            f"Por {interaction.user.mention} em {canal.mention}.",
            cor_int,
            interaction.user,
            interaction.guild,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FalarCog(bot))
