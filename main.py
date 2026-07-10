"""
╔════════════════════════════════════════════════════════════════════════════╗
║                          🇵🇹  BOT REDE TUGA  🇵🇹                              ║
║                                                                            ║
║  Bot profissional para a comunidade Rede Tuga no Discord.                  ║
║  Funcionalidades:                                                          ║
║    • Painel de regras enviável por comando                                 ║
║    • Sistema de boas-vindas com DM + verify                                ║
║    • Sistema completo de tickets (7 categorias)                            ║
║    • Auto-roles reativos                                                   ║
║    • Embed builder para anúncios da staff                                  ║
║                                                                            ║
║  Deploy: Railway (free tier) com Secrets                                   ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

from config import Cores, config, REGRAS_FILE

# ─────────────────────────────────────────────────────────────────────────────
# Logging — Railway captura stdout/stderr automaticamente
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("rede_tuga.main")

# ─────────────────────────────────────────────────────────────────────────────
# Intents — necessários para membros, mensagens e conteúdo
# ─────────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True           # boas-vindas, auto-roles, verificação
intents.message_content = True   # comandos prefixados (legacy)
intents.guilds = True            # criação de canais de ticket
intents.voice_states = True

# ─────────────────────────────────────────────────────────────────────────────
# Instância do bot
# ─────────────────────────────────────────────────────────────────────────────
class RedeTugaBot(commands.Bot):
    """Bot principal da Rede Tuga."""

    def __init__(self) -> None:
        super().__init__(
            command_prefix=config.prefixo,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.start_time: discord.utils.utcnow = discord.utils.utcnow()

    async def setup_hook(self) -> None:
        """Carrega todos os cogs antes de o bot ficar online."""
        cogs_dir = Path(__file__).parent / "cogs"
        carregados, falhados = 0, 0

        for ficheiro in sorted(cogs_dir.glob("*.py")):
            if ficheiro.name.startswith("_"):
                continue
            nome_cog = f"cogs.{ficheiro.stem}"
            try:
                await self.load_extension(nome_cog)
                carregados += 1
                log.info("✅ Cog carregado: %s", nome_cog)
            except Exception as e:
                falhados += 1
                log.exception("❌ Falha ao carregar %s: %s", nome_cog, e)

        log.info("📊 Cogs: %d carregados, %d falhados", carregados, falhados)

        # Sincroniza slash commands
        # Se GUILD_ID estiver definido → sync instantâneo (guild commands)
        # Caso contrário → sync global (pode demorar até 1h)
        try:
            if config.guild_id:
                guild = discord.Object(id=config.guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info("🔄 %d slash commands sincronizados (guild %d)", len(synced), config.guild_id)
            else:
                synced = await self.tree.sync()
                log.info("🔄 %d slash commands sincronizados (global)", len(synced))
        except Exception as e:
            log.exception("⚠️ Erro ao sincronizar slash commands: %s", e)

    @property
    def uptime(self) -> str:
        delta = discord.utils.utcnow() - self.start_time
        horas, resto = divmod(int(delta.total_seconds()), 3600)
        minutos, segundos = divmod(resto, 60)
        return f"{horas}h {minutos}m {segundos}s"


bot = RedeTugaBot()


# ─────────────────────────────────────────────────────────────────────────────
# Eventos globais
# ─────────────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready() -> None:
    """Bot pronto para receber eventos."""
    log.info("═══════════════════════════════════════════════════")
    log.info("🇵🇹  BOT REDE TUGA — ONLINE")
    log.info("═══════════════════════════════════════════════════")
    log.info("👤 Conectado como: %s", bot.user)
    log.info("🆔 ID: %s", bot.user.id if bot.user else "—")
    log.info("🏠 Servidores: %d", len(bot.guilds))
    log.info("👥 Utilizadores: %d", sum(g.member_count or 0 for g in bot.guilds))
    log.info("⚡ Latência: %.0fms", round(bot.latency * 1000))
    log.info("⏱️  Uptime desde startup: %s", bot.uptime)
    log.info("═══════════════════════════════════════════════════")

    # Presença personalizada — "A servir a comunidade"
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"a comunidade 🇵🇹 • /ajuda",
            ),
        )
    except Exception as e:
        log.warning("Não foi possível definir presença: %s", e)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    """Tratamento de erros de comandos prefixados."""
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Não tens permissões para usar este comando.", delete_after=10)
        return
    if isinstance(error, commands.NotOwner):
        await ctx.send("❌ Apenas o dono do bot pode usar este comando.", delete_after=10)
        return
    log.exception("Erro em comando %s: %s", ctx.command, error)
    await ctx.send(f"❌ Ocorreu um erro: `{error}`", delete_after=15)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
) -> None:
    """Tratamento de erros de slash commands."""
    if isinstance(error, discord.app_commands.CommandInvokeError):
        error = error.original

    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "❌ Não tens permissões para usar este comando."
    elif isinstance(error, discord.app_commands.BotMissingPermissions):
        msg = "❌ O bot não tem permissões suficientes."
    else:
        log.exception("Erro em slash command: %s", error)
        msg = f"❌ Ocorreu um erro: `{error}`"

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Comandos globais simples
# ─────────────────────────────────────────────────────────────────────────────
@bot.tree.command(name="ajuda", description="Mostra os comandos disponíveis do bot")
async def cmd_ajuda(interaction: discord.Interaction) -> None:
    """Lista de comandos principais."""
    from utils import embed_base
    from config import Emojis

    embed = embed_base(
        f"{Emojis.REGRAS} Comandos do Bot {config.nome_servidor}",
        "Aqui tens a lista de comandos disponíveis. Usa-os no servidor!",
    )
    embed.add_field(
        name="📜 `/regras`",
        value="Envia o painel de regras no canal atual ou no canal configurado.",
        inline=False,
    )
    embed.add_field(
        name="🎫 `/painel_tickets`",
        value="Cria o painel de tickets com botões para todos os tipos de suporte.",
        inline=False,
    )
    embed.add_field(
        name="🎭 `/painel_cargos`",
        value="Cria o painel de auto-roles — os membros escolhem os seus cargos.",
        inline=False,
    )
    embed.add_field(
        name="📢 `/embed`",
        value="Cria um anúncio personalizado (apenas staff).",
        inline=False,
    )
    embed.add_field(
        name="ℹ️ `/info`",
        value="Informações técnicas sobre o bot (versão, ping, uptime).",
        inline=False,
    )
    embed.add_field(
        name="🏓 `/ping`",
        value="Verifica a latência do bot.",
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ping", description="Verifica a latência do bot")
async def cmd_ping(interaction: discord.Interaction) -> None:
    latency_ms = round(bot.latency * 1000)
    cor = 0x2ECC71 if latency_ms < 100 else (0xF39C12 if latency_ms < 300 else 0xE74C3C)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência da API: **{latency_ms}ms**",
        color=cor,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="info", description="Informações sobre o bot")
async def cmd_info(interaction: discord.Interaction) -> None:
    from utils import embed_base
    from config import Emojis

    embed = embed_base(
        f"{Emojis.COROA} {config.nome_servidor} — Bot",
        "Bot de gestão da comunidade Rede Tuga.",
    )
    embed.add_field(name="🤖 Utilizador", value=f"`{bot.user}`", inline=True)
    embed.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    embed.add_field(name="📅 Online desde", value=f"<t:{int(bot.start_time.timestamp())}:R>", inline=True)
    embed.add_field(name="🏠 Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="👥 Utilizadores", value=f"`{sum(g.member_count or 0 for g in bot.guilds):,}`", inline=True)
    embed.add_field(name="⚡ Ping", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(
        name="🛠️ Stack",
        value="`discord.py 2.4+` · `Python 3.11+` · `Railway`",
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Ponto de entrada
# ─────────────────────────────────────────────────────────────────────────────
async def main() -> None:
    if not config.token or config.token == "coloca_aqui_o_teu_token":
        log.error("═══════════════════════════════════════════════════")
        log.error("❌ DISCORD_TOKEN não configurado!")
        log.error("   Define a variável DISCORD_TOKEN nos Secrets do Railway")
        log.error("   ou cria um ficheiro .env local com base no .env.example")
        log.error("═══════════════════════════════════════════════════")
        sys.exit(1)

    # Garante que data/ existe
    REGRAS_FILE.parent.mkdir(parents=True, exist_ok=True)

    async with bot:
        try:
            await bot.start(config.token)
        except KeyboardInterrupt:
            log.info("Encerramento solicitado pelo utilizador.")
        except discord.LoginFailure:
            log.error("❌ Token inválido. Verifica o DISCORD_TOKEN.")
            sys.exit(1)
        except Exception as e:
            log.exception("Erro fatal: %s", e)
            sys.exit(1)
        finally:
            if not bot.is_closed():
                await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEncerrado.")
