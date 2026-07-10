"""
Cog de Embed Builder — comando /embed para a staff criar anúncios personalizados.

Inclui:
  • Modal com campos: título, descrição, cor, thumbnail, imagem
  • Atalhos de cor por nome (vermelho, verde, dourado, etc.)
  • Pré-visualização antes de publicar (opcional via flags)
"""
from __future__ import annotations

import re

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, config
from utils import embed_erro, embed_sucesso, e_staff, log_evento


CORES_NOME: dict[str, int] = {
    "vermelho": Cores.VERMELHO,
    "verde": Cores.VERDE,
    "dourado": Cores.DOURADO,
    "escuro": Cores.ESCURO,
    "branco": Cores.BRANCO,
    "cinza": Cores.CINZA,
    "sucesso": Cores.SUCESSO,
    "aviso": Cores.AVISO,
    "erro": Cores.ERRO,
    "azul": 0x3498DB,
    "roxo": 0x9B59B6,
    "rosa": 0xE91E63,
    "laranja": 0xE67E22,
}


def parse_cor(valor: str) -> int:
    """Converte nome de cor ou hex em inteiro."""
    valor = valor.strip().lower()
    if valor in CORES_NOME:
        return CORES_NOME[valor]
    # Hex com ou sem #
    hex_match = re.match(r"^#?([0-9a-fA-F]{6})$", valor)
    if hex_match:
        return int(hex_match.group(1), 16)
    return Cores.PRIMARIA


class EmbedModal(discord.ui.Modal):
    """Modal para construir o embed."""

    def __init__(self, cog: "EmbedBuilderCog") -> None:
        super().__init__(title=f"{Emojis.REGRAS} Construtor de Embed", timeout=600)
        self.cog = cog

        self.titulo = discord.ui.TextInput(
            label="Título",
            placeholder="Título do anúncio (vazio = sem título)",
            max_length=256,
            required=False,
        )
        self.add_item(self.titulo)

        self.descricao = discord.ui.TextInput(
            label="Descrição (suporta Markdown)",
            placeholder="Escreve aqui o conteúdo do anúncio...\n\nUsa **negrito**, *itálico*, > citação, código ``` etc.",
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True,
        )
        self.add_item(self.descricao)

        self.cor = discord.ui.TextInput(
            label="Cor (nome ou hex)",
            placeholder="vermelho, verde, dourado, azul, #FF3B3B...",
            max_length=20,
            required=False,
        )
        self.add_item(self.cor)

        self.imagem = discord.ui.TextInput(
            label="URL de imagem (opcional)",
            placeholder="https://...",
            max_length=500,
            required=False,
        )
        self.add_item(self.imagem)

        self.canal = discord.ui.TextInput(
            label="ID do canal (opcional — vazio = canal atual)",
            placeholder="123456789012345678",
            max_length=20,
            required=False,
        )
        self.add_item(self.canal)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cor = parse_cor(self.cor.value) if self.cor.value else Cores.PRIMARIA

        embed = discord.Embed(
            title=self.titulo.value or None,
            description=self.descricao.value,
            color=cor,
        )
        embed.set_footer(
            text=f"{config.nome_servidor} • Anúncio da Staff",
            icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else discord.Embed.Empty,
        )
        embed.set_author(
            name=str(interaction.user),
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else discord.Embed.Empty,
        )

        if self.imagem.value:
            if self.imagem.value.startswith("http"):
                embed.set_image(url=self.imagem.value)

        # Canal destino
        canal_alvo = interaction.channel
        if self.canal.value and self.canal.value.isdigit():
            ch = interaction.guild.get_channel(int(self.canal.value))
            if ch is not None:
                canal_alvo = ch

        if not isinstance(canal_alvo, discord.TextChannel):
            await interaction.response.send_message(
                embed=embed_erro("Canal inválido", "O canal de destino não é um canal de texto."),
                ephemeral=True,
            )
            return

        # Verifica permissões
        perms = canal_alvo.permissions_for(interaction.guild.me)
        if not perms.send_messages or not perms.embed_links:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Sem permissões",
                    f"O bot não tem permissões em {canal_alvo.mention}.",
                ),
                ephemeral=True,
            )
            return

        try:
            await canal_alvo.send(embed=embed)
        except discord.HTTPException as e:
            await interaction.response.send_message(
                embed=embed_erro("Erro", f"Falha ao enviar: `{e}`"),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embed_sucesso(
                "Anúncio publicado!",
                f"Embed enviado para {canal_alvo.mention}.",
            ),
            ephemeral=True,
        )

        await log_evento(
            interaction.client,
            "📢 Embed criado",
            f"Por {interaction.user.mention} em {canal_alvo.mention}.",
            cor,
            interaction.user,
        )


class EmbedBuilderCog(commands.Cog):
    """Construtor de embeds para a staff publicar anúncios."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="embed",
        description="Cria um anúncio personalizado com embed (apenas staff).",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def embed(self, interaction: discord.Interaction) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas a staff pode usar este comando."),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(EmbedModal(self))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EmbedBuilderCog(bot))
