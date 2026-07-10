"""
Configuração central do bot Rede Tuga.
Lê todas as variáveis sensíveis do ambiente (Railway Secrets / .env local).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Caminhos base
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

REGRAS_FILE = DATA_DIR / "regras.json"
TICKETS_FILE = DATA_DIR / "tickets_state.json"
WELCOME_FILE = DATA_DIR / "welcome_state.json"


# ─────────────────────────────────────────────────────────────────────────────
# Identidade visual — Tema Portugal (Rede Tuga)
# ─────────────────────────────────────────────────────────────────────────────
class Cores:
    """Paleta patriótica tuga — vermelho, verde e dourado."""
    VERMELHO = 0xFF3B3B      # Bandeira PT
    VERDE    = 0x006233      # Bandeira PT
    DOURADO  = 0xFFD700      # Brasão / destacado
    ESCURO   = 0x1A1A2E      # Fundo escuro
    BRANCO   = 0xFFFFFF
    CINZA    = 0x95A5A6
    SUCESSO  = 0x2ECC71
    AVISO    = 0xF39C12
    ERRO     = 0xE74C3C

    # Por defeito os embeds usam o vermelho tuga
    PRIMARIA = VERMELHO
    SECUNDARIA = VERDE


class Emojis:
    """Emojis usados em painéis e botões."""
    REGRAS       = "📜"
    BEM_VINDO    = "🇵🇹"
    TICKET       = "🎫"
    SUPORTE      = "🆘"
    REPORT       = "⚠️"
    RECLAMACAO   = "📢"
    PARCERIA     = "🤝"
    BAN          = "🔨"
    DOACAO       = "💎"
    BUG          = "🐛"
    FECHAR       = "🔒"
    ARQUIVAR     = "📁"
    TRANSCRIPT   = "📝"
    VERIFICAR    = "✅"
    SETA         = "➡️"
    COROA        = "👑"
    ESCUDO       = "🛡️"
    PRESENTE     = "🎁"
    ESTRELA      = "⭐"
    LOUD         = "🔊"
    MUDO         = "🔇"


# ─────────────────────────────────────────────────────────────────────────────
# Configuração dinâmica via environment
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Config:
    # Credenciais (lidas do ambiente / Railway Secrets)
    token: str = os.getenv("DISCORD_TOKEN", "")
    guild_id: int = int(os.getenv("GUILD_ID", "0") or 0)  # 0 = global

    # IDs de canais
    canal_regras: int = int(os.getenv("CANAL_REGRAS", "0") or 0)
    canal_bem_vindas: int = int(os.getenv("CANAL_BEM_VINDAS", "0") or 0)
    canal_logs: int = int(os.getenv("CANAL_LOGS", "0") or 0)
    canal_sugestoes: int = int(os.getenv("CANAL_SUGESTOES", "0") or 0)

    # IDs de cargos
    cargo_membro: int = int(os.getenv("CARGO_MEMBRO", "0") or 0)
    cargo_verificado: int = int(os.getenv("CARGO_VERIFICADO", "0") or 0)
    cargo_staff: int = int(os.getenv("CARGO_STAFF", "0") or 0)
    cargo_admin: int = int(os.getenv("CARGO_ADMIN", "0") or 0)
    cargo_ticket_staff: int = int(os.getenv("CARGO_TICKET_STAFF", "0") or 0)

    # Categoria onde os tickets são criados
    categoria_tickets: int = int(os.getenv("CATEGORIA_TICKETS", "0") or 0)

    # Mensagens customizáveis
    nome_servidor: str = os.getenv("NOME_SERVIDOR", "Rede Tuga")
    prefixo: str = os.getenv("PREFIXO", "!")
    cor_bot: int = int(os.getenv("COR_BOT", str(Cores.VERMELHO)), 16)

    # Dados estáticos (não-vazia quando em runtime)
    donos: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        donos_raw = os.getenv("DONOS_IDS", "")
        if donos_raw.strip():
            self.donos = [int(x.strip()) for x in donos_raw.split(",") if x.strip().isdigit()]


config = Config()
