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
# Mensagens padrão (usadas se o utilizador não customizar no /setup)
# ─────────────────────────────────────────────────────────────────────────────
MENSAGEM_BEM_VINDO_DEFAULT = (
    "Olá {user}! 🎉\n\n"
    "És o membro número **{count}** desta comunidade tuga. 🇵🇹\n\n"
    "Antes de começares a explorar o servidor:\n"
    "➡️ Lê as regras em {regras}\n"
    "➡️ Se precisares de ajuda, abre um ticket em {tickets}\n\n"
    "Bom jogo e diverte-te! 💪"
)

MENSAGEM_TICKET_PANEL_DEFAULT = (
    "Escolhe uma categoria e um formulário vai abrir para descreveres o teu caso. "
    "A staff vai responder dentro do ticket correspondente.\n\n"
    "**Categorias disponíveis:**\n{categorias}\n\n"
    "⚠️ **Antes de abrires ticket:**\n"
    "➡️ Lê as {regras} para garantir que a tua dúvida não é resolvida lá.\n"
    "➡️ Não abras tickets por brincadeira — pode resultar em sanção.\n"
    "➡️ Mantém o respeito com a staff — são voluntários a ajudar-te.\n\n"
    "Usa o menu abaixo para abrir o ticket certo."
)

MENSAGEM_TICKET_CRIADO_DEFAULT = (
    "Bem-vindo {user}! 🎫\n\n"
    "**Motivo apresentado:**\n```{motivo}```\n\n"
    "📋 **Regras do ticket:**\n"
    "➡️ Mantém o respeito com a staff.\n"
    "➡️ Explica o teu problema com o máximo de detalhe.\n"
    "➡️ Não marques a staff — serás atendido quando possível.\n"
    "➡️ Para fechar, clica no botão **Fechar Ticket** abaixo."
)


# ─────────────────────────────────────────────────────────────────────────────
# Categorias de ticket padrão (admin pode personalizar via /editar)
#
# Cada categoria pode ter "campos" — uma lista de campos customizados que aparecem
# no modal de criação de ticket. O Discord permite máximo 5 TextInput por modal.
# O primeiro campo é sempre o "nome do jogador" (adicionado automaticamente).
#
# Estrutura de cada campo:
#   {
#     "label": str (máx 45 chars),
#     "placeholder": str (máx 100 chars, opcional),
#     "style": "short" | "paragraph",
#     "required": bool,
#     "max_length": int,
#     "key": str (chave para guardar no ticket — ex: "membro_acusado")
#   }
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIAS_TICKET_DEFAULT = [
    {
        "id": "suporte_discord",
        "nome": "Problema no Discord",
        "emoji": "🆘",
        "descricao": "Tens algum problema com o nosso servidor de Discord?",
        "cor": 0x3498DB,
        "placeholder": "Descreve o problema que tens no Discord...",
        "campos": [
            {
                "label": "📋 Descreve o problema",
                "placeholder": "Ex: Não consigo ver o canal #geral...",
                "style": "paragraph",
                "required": True,
                "max_length": 1000,
                "key": "descricao",
            },
        ],
    },
    {
        "id": "claims",
        "nome": "Problemas com Claims",
        "emoji": "🏰",
        "descricao": "Problemas com claims dentro do jogo?",
        "cor": 0xFFD700,
        "placeholder": "Descreve o problema com a tua claim...",
        "campos": [
            {
                "label": "📍 Localização da claim",
                "placeholder": "Ex: Coordenadas X:123 Y:456 Z:789",
                "style": "short",
                "required": True,
                "max_length": 200,
                "key": "localizacao",
            },
            {
                "label": "📋 Descreve o problema",
                "placeholder": "Ex: A minha claim foi griefada...",
                "style": "paragraph",
                "required": True,
                "max_length": 1000,
                "key": "descricao",
            },
        ],
    },
    {
        "id": "vip",
        "nome": "Compra de VIPs",
        "emoji": "💎",
        "descricao": "Queres comprar VIP ou saber quais são os benefícios?",
        "cor": 0x9B59B6,
        "placeholder": "Indica qual o VIP que queres comprar ou a tua dúvida...",
        "campos": [
            {
                "label": "💎 Qual o VIP que queres?",
                "placeholder": "Ex: VIP Bronze, VIP Ouro...",
                "style": "short",
                "required": True,
                "max_length": 100,
                "key": "vip_desejado",
            },
            {
                "label": "📋 Dúvida ou pedido",
                "placeholder": "Descreve a tua dúvida sobre VIPs...",
                "style": "paragraph",
                "required": False,
                "max_length": 1000,
                "key": "descricao",
            },
        ],
    },
    {
        "id": "denuncia_cheat",
        "nome": "Denúncia de Cheat",
        "emoji": "🚫",
        "descricao": "Queres denunciar um cheater que viste no jogo?",
        "cor": 0xE74C3C,
        "placeholder": "Denuncia um cheater com provas se possível...",
        "campos": [
            {
                "label": "👤 Membro que vais acusar",
                "placeholder": "Ex: JoãoPT (ou ID do jogador)",
                "style": "short",
                "required": True,
                "max_length": 200,
                "key": "membro_acusado",
            },
            {
                "label": "📋 Descrição do cheat",
                "placeholder": "Descreve o que viste (kill aura, fly, x-ray...). Anexa provas se possível.",
                "style": "paragraph",
                "required": True,
                "max_length": 1000,
                "key": "descricao_cheat",
            },
        ],
    },
    {
        "id": "reportar_bug",
        "nome": "Reportar Bug",
        "emoji": "🐛",
        "descricao": "Encontraste um bug no jogo ou servidor?",
        "cor": 0xE67E22,
        "placeholder": "Reporta o bug com o máximo de detalhe possível...",
        "campos": [
            {
                "label": "📍 Onde aconteceu o bug?",
                "placeholder": "Ex: No spawn, no /warp survival...",
                "style": "short",
                "required": True,
                "max_length": 200,
                "key": "local_bug",
            },
            {
                "label": "📋 Descrição do bug",
                "placeholder": "Descreve o bug: o que aconteceu, como reproduzir, etc.",
                "style": "paragraph",
                "required": True,
                "max_length": 1000,
                "key": "descricao_bug",
            },
        ],
    },
    {
        "id": "suporte_geral",
        "nome": "Suporte Geral",
        "emoji": "💬",
        "descricao": "Dúvidas gerais que não se encaixam nas outras categorias?",
        "cor": 0x2ECC71,
        "placeholder": "Descreve a tua dúvida ou pedido...",
        "campos": [
            {
                "label": "📋 Descreve a tua dúvida",
                "placeholder": "Ex: Como funciona o sistema de economies?",
                "style": "paragraph",
                "required": True,
                "max_length": 1000,
                "key": "descricao",
            },
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Configuração dinâmica por servidor
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class GuildConfig:
    guild_id: int = 0
    nome_servidor: str = "Rede Tuga"

    # IDs de canais (0 = não configurado)
    canal_regras: int = 0
    canal_bem_vindas: int = 0
    canal_logs: int = 0
    canal_sugestoes: int = 0
    canal_tickets: int = 0
    canal_autoroles: int = 0
    canal_transcript: int = 0  # Canal onde os transcripts são enviados após fecho

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
    boas_vindas_ativas: bool = True
    logs_ativos: bool = True

    # SLA Tracking
    sla_ativo: bool = True
    sla_aviso1_horas: int = 1   # 1ª notificação (logs)
    sla_aviso2_horas: int = 2   # 2ª notificação (no ticket)
    sla_aviso3_horas: int = 6   # 3ª notificação (escalada)
    canal_sla: int = 0          # Canal onde avisos de SLA são enviados (0 = canal_logs)

    # Mensagens customizadas (vazias = usar default)
    msg_bem_vindo: str = ""
    msg_ticket_panel: str = ""
    msg_ticket_criado: str = ""

    # Categorias de ticket customizadas (vazias = usar defaults)
    categorias_ticket: list = None

    def __post_init__(self) -> None:
        if self.categorias_ticket is None:
            self.categorias_ticket = []

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "nome_servidor": self.nome_servidor,
            "canal_regras": self.canal_regras,
            "canal_bem_vindas": self.canal_bem_vindas,
            "canal_logs": self.canal_logs,
            "canal_sugestoes": self.canal_sugestoes,
            "canal_tickets": self.canal_tickets,
            "canal_autoroles": self.canal_autoroles,
            "canal_transcript": self.canal_transcript,
            "cargo_membro": self.cargo_membro,
            "cargo_verificado": self.cargo_verificado,
            "cargo_staff": self.cargo_staff,
            "cargo_admin": self.cargo_admin,
            "cargo_ticket_staff": self.cargo_ticket_staff,
            "categoria_tickets": self.categoria_tickets,
            "setup_completo": self.setup_completo,
            "boas_vindas_ativas": self.boas_vindas_ativas,
            "logs_ativos": self.logs_ativos,
            "sla_ativo": self.sla_ativo,
            "sla_aviso1_horas": self.sla_aviso1_horas,
            "sla_aviso2_horas": self.sla_aviso2_horas,
            "sla_aviso3_horas": self.sla_aviso3_horas,
            "canal_sla": self.canal_sla,
            "msg_bem_vindo": self.msg_bem_vindo,
            "msg_ticket_panel": self.msg_ticket_panel,
            "msg_ticket_criado": self.msg_ticket_criado,
            "categorias_ticket": self.categorias_ticket,
        }

    # Campos que devem ser inteiros (IDs do Discord)
    CAMPOS_INT = frozenset({
        "guild_id", "canal_regras", "canal_bem_vindas", "canal_logs",
        "canal_sugestoes", "canal_tickets", "canal_autoroles", "canal_transcript",
        "canal_sla",
        "cargo_membro", "cargo_verificado", "cargo_staff", "cargo_admin",
        "cargo_ticket_staff", "categoria_tickets",
        "sla_aviso1_horas", "sla_aviso2_horas", "sla_aviso3_horas",
    })
    # Campos que devem ser bool
    CAMPOS_BOOL = frozenset({
        "setup_completo", "boas_vindas_ativas", "logs_ativos", "sla_ativo",
    })
    # Campos que devem ser str
    CAMPOS_STR = frozenset({"nome_servidor", "msg_bem_vindo", "msg_ticket_panel", "msg_ticket_criado"})

    @classmethod
    def from_dict(cls, d: dict) -> "GuildConfig":
        c = cls()
        for k, v in d.items():
            if not hasattr(c, k):
                continue
            # Validação de tipos — converte se possível, senão usa default
            if k in cls.CAMPOS_INT:
                if isinstance(v, bool):
                    v = int(v)
                elif isinstance(v, str):
                    v = int(v) if v.isdigit() else 0
                elif not isinstance(v, int):
                    v = 0
            elif k in cls.CAMPOS_BOOL:
                if not isinstance(v, bool):
                    v = bool(v)
            elif k in cls.CAMPOS_STR:
                if not isinstance(v, str):
                    v = str(v) if v is not None else ""
            elif k == "categorias_ticket":
                if not isinstance(v, list):
                    v = []
            setattr(c, k, v)
        return c

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers para obter mensagens (com fallback para default)
    # ─────────────────────────────────────────────────────────────────────────
    def get_msg_bem_vindo(self) -> str:
        return self.msg_bem_vindo or MENSAGEM_BEM_VINDO_DEFAULT

    def get_msg_ticket_panel(self) -> str:
        return self.msg_ticket_panel or MENSAGEM_TICKET_PANEL_DEFAULT

    def get_msg_ticket_criado(self) -> str:
        return self.msg_ticket_criado or MENSAGEM_TICKET_CRIADO_DEFAULT

    def get_categorias_ticket(self) -> list:
        """Retorna as categorias customizadas se existirem, senão os defaults."""
        if self.categorias_ticket:
            return self.categorias_ticket
        return CATEGORIAS_TICKET_DEFAULT

    def estah_completo(self) -> bool:
        """Verifica se a config mínima está preenchida.

        Nota: cargos são opcionais (admin pode não configurar cargo_staff).
        Se não houver cargo_staff, apenas admins do Discord acedem aos comandos.
        """
        return all([
            self.canal_regras,
            self.canal_tickets,
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
    """Escrita ATÓMICA — previne corrupção em crashes/restarts."""
    import os as _os
    import tempfile as _tempfile
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = _tempfile.mkstemp(
            dir=str(CONFIG_FILE.parent), prefix=CONFIG_FILE.name + ".", suffix=".tmp"
        )
        try:
            with _os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            _os.replace(tmp_path, str(CONFIG_FILE))
            try:
                _os.chmod(str(CONFIG_FILE), 0o600)
            except OSError:
                pass
            return True
        finally:
            if _os.path.exists(tmp_path):
                try:
                    _os.unlink(tmp_path)
                except OSError:
                    pass
    except OSError:
        return False


def get_config(guild_id: int) -> GuildConfig:
    if guild_id in _cache:
        return _cache[guild_id]

    dados = _carregar_tudo()
    guild_data = dados.get("guilds", {}).get(str(guild_id))
    if guild_data:
        cfg = GuildConfig.from_dict(guild_data)
    else:
        cfg = GuildConfig(guild_id=guild_id)

    _aplicar_env_overrides(cfg)
    _cache[guild_id] = cfg
    return cfg


import threading

# Lock global para proteger o read-modify-write do config.json
_config_lock = threading.Lock()


def save_config(cfg: GuildConfig) -> bool:
    """Persiste a config do servidor de forma thread-safe."""
    with _config_lock:
        dados = _carregar_tudo()
        if "guilds" not in dados:
            dados["guilds"] = {}
        dados["guilds"][str(cfg.guild_id)] = cfg.to_dict()
        _cache[cfg.guild_id] = cfg
        return _guardar_tudo(dados)


def _aplicar_env_overrides(cfg: GuildConfig) -> None:
    campos = [
        ("canal_regras", "CANAL_REGRAS"),
        ("canal_bem_vindas", "CANAL_BEM_VINDAS"),
        ("canal_logs", "CANAL_LOGS"),
        ("canal_sugestoes", "CANAL_SUGESTOES"),
        ("canal_tickets", "CANAL_TICKETS"),
        ("canal_autoroles", "CANAL_AUTOROLES"),
        ("canal_transcript", "CANAL_TRANSCRIPT"),
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
