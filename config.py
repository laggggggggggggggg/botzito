"""
Gestor de configuração dinâmica — substitui a configuração estática por IDs.

A configuração é guardada em data/config.json e pode ser editada conversando
com o bot através do comando /setup. Isto permite que o utilizador só precise
de configurar DISCORD_TOKEN nos Secrets do Railway.

Fallback: se um ID estiver definido no ambiente, esse valor é usado (override).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
REGRAS_FILE = DATA_DIR / "regras.json"
TICKETS_FILE = DATA_DIR / "tickets_state.json"
AUTOROLES_FILE = DATA_DIR / "autoroles.json"


# ─────────────────────────────────────────────────────────────────────────────
# Identidade visual — Tema Portugal (Rede Tuga)
# ─────────────────────────────────────────────────────────────────────────────
class Cores:
    VERMELHO  = 0xFF3B3B
    VERDE     = 0x006233
    DOURADO   = 0xFFD700
    ESCURO    = 0x1A1A2E
    BRANCO    = 0xFFFFFF
    CINZA     = 0x95A5A6
    SUCESSO   = 0x2ECC71
    AVISO     = 0xF39C12
    ERRO      = 0xE74C3C
    PRIMARIA  = VERMELHO
    SECUNDARIA = VERDE


class Emojis:
    REGRAS     = "📜"
    BEM_VINDO  = "🇵🇹"
    TICKET     = "🎫"
    SUPORTE    = "🆘"
    REPORT     = "⚠️"
    RECLAMACAO = "📢"
    PARCERIA   = "🤝"
    BAN        = "🔨"
    DOACAO     = "💎"
    BUG        = "🐛"
    FECHAR     = "🔒"
    ARQUIVAR   = "📁"
    TRANSCRIPT = "📝"
    VERIFICAR  = "✅"
    SETA       = "➡️"
    COROA      = "👑"
    ESCUDO     = "🛡️"
    PRESENTE   = "🎁"
    ESTRELA    = "⭐"
    LOUD       = "🔊"
    MUDO       = "🔇"
    CANAL      = "📢"
    CARGO      = "🎭"


# ─────────────────────────────────────────────────────────────────────────────
# Configuração dinâmica
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class GuildConfig:
    """Configuração por servidor — persistida em JSON."""
    guild_id: int = 0
    nome_servidor: str = "Rede Tuga"

    # IDs de canais (0 = não configurado)
    canal_regras: int = 0
    canal_bem_vindas: int = 0
    canal_logs: int = 0
    canal_sugestoes: int = 0
    canal_tickets: int = 0  # canal onde fica o painel de tickets

    # IDs de cargos
    cargo_membro: int = 0
    cargo_verificado: int = 0
    cargo_staff: int = 0
    cargo_admin: int = 0
    cargo_ticket_staff: int = 0

    # IDs de categorias
    categoria_tickets: int = 0

    # Estado do setup
    setup_completo: bool = False

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "nome_servidor": self.nome_servidor,
            "canal_regras": self.canal_regras,
            "canal_bem_vindas": self.canal_bem_vindas,
            "canal_logs": self.canal_logs,
            "canal_sugestoes": self.canal_sugestoes,
            "canal_tickets": self.canal_tickets,
            "cargo_membro": self.cargo_membro,
            "cargo_verificado": self.cargo_verificado,
            "cargo_staff": self.cargo_staff,
            "cargo_admin": self.cargo_admin,
            "cargo_ticket_staff": self.cargo_ticket_staff,
            "categoria_tickets": self.categoria_tickets,
            "setup_completo": self.setup_completo,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GuildConfig":
        c = cls()
        for k, v in d.items():
            if hasattr(c, k):
                setattr(c, k, v)
        return c

    def estah_completo(self) -> bool:
        """Verifica se a config mínima está preenchida."""
        return all([
            self.canal_regras,
            self.canal_bem_vindas,
            self.canal_tickets,
            self.cargo_membro,
            self.cargo_staff,
            self.categoria_tickets,
        ])


# ─────────────────────────────────────────────────────────────────────────────
# Cache em memória + persistência
# ─────────────────────────────────────────────────────────────────────────────
_cache: dict[int, GuildConfig] = {}


def _carregar_tudo() -> dict:
    if not CONFIG_FILE.exists():
        return {"guilds": {}}
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"guilds": {}}


def _guardar_tudo(dados: dict) -> bool:
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def get_config(guild_id: int) -> GuildConfig:
    """Obtém a config do servidor. Usa cache em memória."""
    if guild_id in _cache:
        return _cache[guild_id]

    dados = _carregar_tudo()
    guild_data = dados.get("guilds", {}).get(str(guild_id))
    if guild_data:
        cfg = GuildConfig.from_dict(guild_data)
    else:
        cfg = GuildConfig(guild_id=guild_id)

    # Aplica overrides do ambiente (Railway Secrets) se existirem
    _aplicar_env_overrides(cfg)

    _cache[guild_id] = cfg
    return cfg


def save_config(cfg: GuildConfig) -> bool:
    """Persiste a config do servidor."""
    dados = _carregar_tudo()
    if "guilds" not in dados:
        dados["guilds"] = {}
    dados["guilds"][str(cfg.guild_id)] = cfg.to_dict()
    _cache[cfg.guild_id] = cfg
    return _guardar_tudo(dados)


def _aplicar_env_overrides(cfg: GuildConfig) -> None:
    """Aplica overrides do ambiente (opcional — para quem preferir configurar por Secrets)."""
    campos = [
        ("canal_regras", "CANAL_REGRAS"),
        ("canal_bem_vindas", "CANAL_BEM_VINDAS"),
        ("canal_logs", "CANAL_LOGS"),
        ("canal_sugestoes", "CANAL_SUGESTOES"),
        ("canal_tickets", "CANAL_TICKETS"),
        ("cargo_membro", "CARGO_MEMBRO"),
        ("cargo_verificado", "CARGO_VERIFICADO"),
        ("cargo_staff", "CARGO_STAFF"),
        ("cargo_admin", "CARGO_ADMIN"),
        ("cargo_ticket_staff", "CARGO_TICKET_STAFF"),
        ("categoria_tickets", "CATEGORIA_TICKETS"),
    ]
    for attr, env_var in campos:
        val = os.getenv(env_var, "").strip()
        if val and val.isdigit():
            setattr(cfg, attr, int(val))

    nome = os.getenv("NOME_SERVIDOR")
    if nome:
        cfg.nome_servidor = nome

    # Se todos os IDs críticos estiverem definidos via env, marca como completo
    if cfg.estah_completo() and not cfg.setup_completo:
        cfg.setup_completo = True


# ─────────────────────────────────────────────────────────────────────────────
# Token (única variável obrigatória via Secrets)
# ─────────────────────────────────────────────────────────────────────────────
def get_token() -> str:
    return os.getenv("DISCORD_TOKEN", "").strip()


def get_donos() -> list[int]:
    raw = os.getenv("DONOS_IDS", "")
    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
