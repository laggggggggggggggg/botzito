"""
Utils partilhadas — helpers de embeds, persistência JSON e logging.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import discord

from config import Cores, Emojis, config

log = logging.getLogger("rede_tuga")


# ─────────────────────────────────────────────────────────────────────────────
# Embeds padronizadas com a identidade visual da Rede Tuga
# ─────────────────────────────────────────────────────────────────────────────
def embed_base(
    titulo: str,
    descricao: str = "",
    cor: int = Cores.PRIMARIA,
    thumbnail: Optional[str] = None,
) -> discord.Embed:
    """Cria embed com footer e timestamp automáticos."""
    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(
        text=f"{config.nome_servidor} • Sistema de Gestão",
        icon_url=discord.Embed.Empty if not thumbnail else thumbnail,
    )
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    return embed


def embed_sucesso(titulo: str, descricao: str) -> discord.Embed:
    return embed_base(f"{Emojis.VERIFICAR} {titulo}", descricao, Cores.SUCESSO)


def embed_erro(titulo: str, descricao: str) -> discord.Embed:
    return embed_base(f"❌ {titulo}", descricao, Cores.ERRO)


def embed_aviso(titulo: str, descricao: str) -> discord.Embed:
    return embed_base(f"⚠️ {titulo}", descricao, Cores.AVISO)


def embed_info(titulo: str, descricao: str) -> discord.Embed:
    return embed_base(f"ℹ️ {titulo}", descricao, Cores.CINZA)


# ─────────────────────────────────────────────────────────────────────────────
# Persistência JSON simples — sem dependências externas
# ─────────────────────────────────────────────────────────────────────────────
def carregar_json(caminho: Path, default: Any = None) -> Any:
    """Carrega JSON de ficheiro. Retorna default se não existir."""
    if default is None:
        default = {}
    if not caminho.exists():
        return default
    try:
        with caminho.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Falha ao ler %s: %s — usando default", caminho, e)
        return default


def guardar_json(caminho: Path, dados: Any) -> bool:
    """Persiste dados em JSON. Retorna False em caso de erro."""
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        log.error("Falha ao guardar %s: %s", caminho, e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Logger para o canal de logs do Discord
# ─────────────────────────────────────────────────────────────────────────────
async def log_evento(
    bot: discord.Client,
    titulo: str,
    descricao: str,
    cor: int = Cores.CINZA,
    user: Optional[discord.abc.User] = None,
) -> None:
    """Envia uma entrada de log para o canal configurado."""
    if not config.canal_logs:
        return
    canal = bot.get_channel(config.canal_logs)
    if canal is None:
        return
    embed = embed_base(titulo, descricao, cor)
    if user is not None:
        embed.set_author(
            name=f"{user} ({user.id})",
            icon_url=user.display_avatar.url if user.display_avatar else discord.Embed.Empty,
        )
    try:
        await canal.send(embed=embed)
    except discord.HTTPException as e:
        log.warning("Não foi possível enviar log: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Verificações de permissão
# ─────────────────────────────────────────────────────────────────────────────
def e_staff(member: discord.Member) -> bool:
    """Verifica se o membro pertence à staff (cargo configurado ou admin)."""
    if member.guild_permissions.administrator:
        return True
    if config.cargo_staff and member.get_role(config.cargo_staff):
        return True
    if config.cargo_admin and member.get_role(config.cargo_admin):
        return True
    return False


def e_admin(member: discord.Member) -> bool:
    """Verifica se o membro é admin do bot."""
    if member.id in config.donos:
        return True
    if member.guild_permissions.administrator:
        return True
    if config.cargo_admin and member.get_role(config.cargo_admin):
        return True
    return False
