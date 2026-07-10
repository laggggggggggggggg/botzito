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

from config import Cores, Emojis, get_config, get_donos

log = logging.getLogger("rede_tuga")


# ─────────────────────────────────────────────────────────────────────────────
# Embeds padronizadas com a identidade visual da Rede Tuga
# ─────────────────────────────────────────────────────────────────────────────
def embed_base(
    titulo: str,
    descricao: str = "",
    cor: int = Cores.PRIMARIA,
    thumbnail: Optional[str] = None,
    nome_servidor: str = "Rede Tuga",
) -> discord.Embed:
    embed = discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text=f"{nome_servidor} • Sistema de Gestão")
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    return embed


def embed_sucesso(titulo: str, descricao: str, nome: str = "Rede Tuga") -> discord.Embed:
    return embed_base(f"{Emojis.VERIFICAR} {titulo}", descricao, Cores.SUCESSO, nome_servidor=nome)


def embed_erro(titulo: str, descricao: str, nome: str = "Rede Tuga") -> discord.Embed:
    return embed_base(f"❌ {titulo}", descricao, Cores.ERRO, nome_servidor=nome)


def embed_aviso(titulo: str, descricao: str, nome: str = "Rede Tuga") -> discord.Embed:
    return embed_base(f"⚠️ {titulo}", descricao, Cores.AVISO, nome_servidor=nome)


def embed_info(titulo: str, descricao: str, nome: str = "Rede Tuga") -> discord.Embed:
    return embed_base(f"ℹ️ {titulo}", descricao, Cores.CINZA, nome_servidor=nome)


# ─────────────────────────────────────────────────────────────────────────────
# Persistência JSON simples
# ─────────────────────────────────────────────────────────────────────────────
def carregar_json(caminho: Path, default: Any = None) -> Any:
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
    """Escrita ATÓMICA em JSON — usa ficheiro temporário + rename.

    Isto previne corrupção se o bot crashar a meio da escrita ou se
    outro coroutine ler simultaneamente.
    """
    import os
    import tempfile
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # Cria ficheiro temporário no MESMO directório (necessário para atomicidade do rename)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(caminho.parent), prefix=caminho.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            # os.replace é atómico em POSIX e Windows
            os.replace(tmp_path, str(caminho))
            # Permissões restritas (apenas owner pode ler/escrever)
            try:
                os.chmod(str(caminho), 0o600)
            except OSError:
                pass
            return True
        finally:
            # Se algo falhou antes do rename, remover o tmp
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    except OSError as e:
        log.error("Falha ao guardar %s: %s", caminho, e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Logger para o canal de logs do Discord (usa config dinâmica)
# ─────────────────────────────────────────────────────────────────────────────
async def log_evento(
    bot: discord.Client,
    titulo: str,
    descricao: str,
    cor: int = Cores.CINZA,
    user: Optional[discord.abc.User] = None,
    guild: Optional[discord.Guild] = None,
) -> None:
    """Envia uma entrada de log para o canal configurado (procura por guild)."""
    canal_logs_id = 0
    if guild is not None:
        cfg = get_config(guild.id)
        canal_logs_id = cfg.canal_logs
        nome_srv = cfg.nome_servidor
    else:
        # Tenta inferir a guild do user
        if user is not None:
            for g in bot.guilds:
                if g.get_member(user.id):
                    cfg = get_config(g.id)
                    canal_logs_id = cfg.canal_logs
                    nome_srv = cfg.nome_servidor
                    guild = g
                    break
        if canal_logs_id == 0:
            return
        nome_srv = "Rede Tuga"

    canal = bot.get_channel(canal_logs_id)
    if canal is None:
        return

    embed = embed_base(titulo, descricao, cor, nome_servidor=nome_srv)
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
# Verificações de permissão (usam config dinâmica)
# ─────────────────────────────────────────────────────────────────────────────
def e_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    cfg = get_config(member.guild.id)
    if cfg.cargo_staff and member.get_role(cfg.cargo_staff):
        return True
    if cfg.cargo_admin and member.get_role(cfg.cargo_admin):
        return True
    return False


def e_admin(member: discord.Member) -> bool:
    if member.id in get_donos():
        return True
    if member.guild_permissions.administrator:
        return True
    cfg = get_config(member.guild.id)
    if cfg.cargo_admin and member.get_role(cfg.cargo_admin):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Sanitização de input para embeds
# ─────────────────────────────────────────────────────────────────────────────
def escape_markdown_safe(text: str) -> str:
    """Escapa caracteres Markdown que poderiam quebrar embeds ou criar links disfarçados.

    Aplica escape em: *, _, `, ~, |, >, [, ]
    Não escapa emojis (unicode) nem caracteres acentuados.
    """
    if not text:
        return text
    # Discord usa estes caracteres para formatação
    chars = ("*", "_", "`", "~", "|", ">", "[", "]")
    result = text
    for c in chars:
        result = result.replace(c, "\\" + c)
    return result


def sanitize_nome_servidor(nome: str) -> str:
    """Sanitiza o nome do servidor para uso em embeds.
    Limita a 80 chars e escapa markdown injection.
    """
    if not nome:
        return "Rede Tuga"
    return escape_markdown_safe(nome[:80])
