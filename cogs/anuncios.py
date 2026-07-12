"""
Cog de Anúncios — /anunciar com modal e agendamento de data/hora.

Funcionalidades:
  • /anunciar — abre modal com título, descrição, cor, imagem, canal
  • /anunciar_agendar — abre modal para agendar anúncio para data/hora específica
  • Suporte a cores por nome ou hex
  • Validação anti-SSRF de URLs de imagem
  • Preview do anúncio antes de enviar
  • Agendamento usa asyncio task em background (não persiste após restart)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config, save_config
from utils import embed_erro, embed_sucesso, e_admin, e_staff, log_evento


# ─────────────────────────────────────────────────────────────────────────────
# Cores nomeadas
# ─────────────────────────────────────────────────────────────────────────────
CORES_NOME: dict[str, int] = {
    "vermelho": Cores.VERMELHO, "verde": Cores.VERDE, "dourado": Cores.DOURADO,
    "escuro": Cores.ESCURO, "branco": Cores.BRANCO, "cinza": Cores.CINZA,
    "sucesso": Cores.SUCESSO, "aviso": Cores.AVISO, "erro": Cores.ERRO,
    "azul": 0x3498DB, "roxo": 0x9B59B6, "rosa": 0xE91E63, "laranja": 0xE67E22,
}


def parse_cor(valor: str) -> int:
    import re
    valor = valor.strip().lower()
    if valor in CORES_NOME:
        return CORES_NOME[valor]
    hex_match = re.match(r"^#?([0-9a-fA-F]{6})$", valor)
    if hex_match:
        return int(hex_match.group(1), 16)
    return Cores.PRIMARIA


def validar_url_imagem(url: str) -> bool:
    """Valida URL de imagem — previne SSRF para IPs internos."""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    # Verifica se é IP interno usando ipaddress (preciso para 172.16/12)
    import ipaddress
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        # Não é IP — é hostname. Bloqueia hostnames conhecidos de metadata
        if host in ("localhost", "metadata.google.internal", "metadata"):
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Modal de anúncio
# ─────────────────────────────────────────────────────────────────────────────
class AnuncioModal(discord.ui.Modal):
    """Modal para criar anúncio personalizado.

    Limitações do Discord:
    • Máximo 5 campos (TextInput) por modal
    • Label máximo 45 caracteres
    """

    def __init__(self, cog: "AnunciosCog", agendar: bool = False) -> None:
        titulo_modal = "📅 Agendar Anúncio" if agendar else "📢 Criar Anúncio"
        super().__init__(title=titulo_modal, timeout=600)
        self.cog = cog
        self.agendar = agendar

        # 1. Título
        self.titulo = discord.ui.TextInput(
            label="📋 Título do anúncio",
            placeholder="Ex: Evento especial este fim de semana!",
            max_length=256,
            required=True,
        )
        self.add_item(self.titulo)

        # 2. Descrição (Markdown)
        self.descricao = discord.ui.TextInput(
            label="📝 Descrição (Markdown)",
            placeholder="Escreve aqui o conteúdo do anúncio...\n\nUsa **negrito**, *itálico*, > citação, etc.",
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=True,
        )
        self.add_item(self.descricao)

        # 3. Cor (opcional)
        self.cor = discord.ui.TextInput(
            label="🎨 Cor (nome ou hex)",
            placeholder="vermelho, verde, dourado, azul, #FF3B3B",
            default="vermelho",
            max_length=20,
            required=False,
        )
        self.add_item(self.cor)

        # 4. URL de imagem (opcional)
        self.imagem = discord.ui.TextInput(
            label="🖼️ URL imagem (opcional)",
            placeholder="https://...",
            max_length=500,
            required=False,
        )
        self.add_item(self.imagem)

        # 5. Canal destino OU data/hora (consoante modo)
        if agendar:
            # No modo agendar, o canal é o atual; pede-se data/hora
            self.data_hora = discord.ui.TextInput(
                label="📅 Data (DD/MM/AAAA HH:MM)",
                placeholder="Ex: 25/12/2025 18:00",
                max_length=20,
                required=True,
            )
            self.add_item(self.data_hora)
            self.canal = None
        else:
            # No modo normal, pede-se canal destino (vazio = canal atual)
            self.canal = discord.ui.TextInput(
                label="📢 ID do canal (vazio = atual)",
                placeholder="123456789012345678",
                max_length=20,
                required=False,
            )
            self.add_item(self.canal)
            self.data_hora = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        cor = parse_cor(self.cor.value) if self.cor.value else Cores.VERMELHO

        # Valida URL de imagem
        url_imagem = None
        if self.imagem.value:
            if validar_url_imagem(self.imagem.value):
                url_imagem = self.imagem.value
            else:
                await interaction.response.send_message(
                    embed=embed_erro(
                        "🚫 URL inválida",
                        "A URL de imagem fornecida não é válida ou aponta para um endereço interno.",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return

        # Determina canal destino
        canal_alvo = interaction.channel
        if self.canal is not None and self.canal.value and self.canal.value.isdigit():
            ch = interaction.guild.get_channel(int(self.canal.value))
            if ch is not None:
                canal_alvo = ch

        if not isinstance(canal_alvo, discord.TextChannel):
            await interaction.response.send_message(
                embed=embed_erro("🚫 Canal inválido", "O canal de destino não é um canal de texto válido.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        # Verifica permissões do bot no canal
        perms = canal_alvo.permissions_for(interaction.guild.me)
        if not perms.send_messages or not perms.embed_links:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissões",
                    f"O Tuguinha não tem permissões para enviar embeds em {canal_alvo.mention}.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Constrói embed
        embed = discord.Embed(
            title=self.titulo.value,
            description=self.descricao.value,
            color=cor,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(
            text=f"📢 {cfg.nome_servidor} • Anúncio da Staff",
            icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None,
        )
        embed.set_author(
            name=str(interaction.user),
            icon_url=interaction.user.display_avatar.url,
        )
        if url_imagem:
            embed.set_image(url=url_imagem)

        # Se for agendar
        if self.agendar:
            data_hora = self._parse_data_hora(self.data_hora.value)
            if data_hora is None:
                await interaction.response.send_message(
                    embed=embed_erro(
                        "🚫 Data inválida",
                        "Formato esperado: `DD/MM/AAAA HH:MM`\nEx: `25/12/2025 18:00`",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return
            agora = datetime.now(timezone.utc)
            if data_hora <= agora:
                await interaction.response.send_message(
                    embed=embed_erro(
                        "🚫 Data no passado",
                        "A data e hora têm de ser no futuro.",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return

            # Calcula delay em segundos
            delay = (data_hora - agora).total_seconds()
            # Agenda task em background
            task = asyncio.create_task(
                self.cog._enviar_anuncio_agendado(canal_alvo, embed, data_hora, interaction.user)
            )
            # Adiciona callback para remover a task da lista quando terminar (evita memory leak)
            task.add_done_callback(lambda t: self.cog._cleanup_task(t))
            self.cog._anuncios_agendados.append(task)

            # Preview com confirmação (deepcopy para não modificar o embed original)
            import copy as _copy
            unix_ts = int(data_hora.timestamp())
            preview_embed = _copy.deepcopy(embed)
            preview_embed.add_field(
                name="📅 Agendado para",
                value=f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)",
                inline=False,
            )
            preview_embed.add_field(
                name="📢 Canal",
                value=canal_alvo.mention,
                inline=False,
            )

            await interaction.response.send_message(
                embed=embed_sucesso(
                    "📅 Anúncio agendado!",
                    f"O anúncio será enviado em {canal_alvo.mention} a <t:{unix_ts}:F>.\n\n**Preview:**",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            await interaction.followup.send(embed=preview_embed, ephemeral=True)

            await log_evento(
                interaction.client,
                "📅 Anúncio agendado",
                f"Por {interaction.user.mention}\nCanal: {canal_alvo.mention}\nData: <t:{unix_ts}:F>",
                Cores.DOURADO,
                interaction.user,
                interaction.guild,
            )
            return

        # Envio imediato
        try:
            await canal_alvo.send(embed=embed)
        except discord.HTTPException as e:
            await interaction.response.send_message(
                embed=embed_erro("🚫 Erro", "Falha ao enviar o anúncio. Tenta novamente.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embed_sucesso(
                "📢 Anúncio publicado!",
                f"Enviado para {canal_alvo.mention}.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

        await log_evento(
            interaction.client,
            "📢 Anúncio publicado",
            f"Por {interaction.user.mention} em {canal_alvo.mention}.",
            cor,
            interaction.user,
            interaction.guild,
        )

    def _parse_data_hora(self, valor: str) -> Optional[datetime]:
        """Faz parse de 'DD/MM/AAAA HH:MM' para datetime em timezone de Portugal."""
        import re
        from zoneinfo import ZoneInfo
        valor = valor.strip()
        match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})$", valor)
        if not match:
            return None
        try:
            dia, mes, ano, hora, minuto = (int(x) for x in match.groups())
            # Timezone de Portugal (WET/WEST — UTC+0 no inverno, UTC+1 no verão)
            tz = ZoneInfo("Europe/Lisbon")
            local_dt = datetime(ano, mes, dia, hora, minuto, tzinfo=tz)
            # Converte para UTC para usar internamente
            return local_dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────────────────────────────────────────
class AnunciosCog(commands.Cog):
    """Sistema de anúncios com agendamento."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Lista de tasks de anúncios agendados (não persiste após restart)
        self._anuncios_agendados: list[asyncio.Task] = []

    def _cleanup_task(self, task: asyncio.Task) -> None:
        """Remove tasks concluídas da lista (previne memory leak)."""
        try:
            self._anuncios_agendados.remove(task)
        except ValueError:
            pass  # já foi removida

    def __del__(self) -> None:
        # Cancela tasks pendentes quando a cog é descarregada
        for task in self._anuncios_agendados:
            if not task.done():
                task.cancel()

    @app_commands.command(
        name="anunciar",
        description="📢 Cria um anúncio personalizado e envia para um canal (apenas admins).",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_anunciar(self, interaction: discord.Interaction) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas **administradores** podem usar este comando.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(AnuncioModal(self, agendar=False))

    @app_commands.command(
        name="anunciar_agendar",
        description="📅 Agenda um anúncio para uma data e hora específicas (apenas admins).",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_anunciar_agendar(self, interaction: discord.Interaction) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas **administradores** podem usar este comando.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(AnuncioModal(self, agendar=True))

    async def _enviar_anuncio_agendado(
        self,
        canal: discord.TextChannel,
        embed: discord.Embed,
        data_hora: datetime,
        quem_pediu: discord.abc.User,
    ) -> None:
        """Task em background que espera até a data/hora e envia o anúncio."""
        agora = datetime.now(timezone.utc)
        delay = (data_hora - agora).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            await canal.send(embed=embed)
            await log_evento(
                self.bot,
                "📢 Anúncio agendado enviado",
                f"Agendado por {quem_pediu.mention}\nCanal: {canal.mention}",
                Cores.SUCESSO,
                quem_pediu,
                canal.guild,
            )
        except discord.HTTPException as e:
            import logging as _logging
            _log = _logging.getLogger("rede_tuga.anuncios")
            _log.error("Falha ao enviar anúncio agendado: %s", e)
            # Tenta notificar o admin via DM
            try:
                await quem_pediu.send(
                    f"⚠️ O teu anúncio agendado para {canal.mention} falhou: `{e}`"
                )
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnunciosCog(bot))
