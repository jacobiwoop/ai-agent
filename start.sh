#!/bin/bash
set -e

# ─────────────────────────────────────────────
#  COULEURS
# ─────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${GREEN}[✔]${NC} $1"; }
warning() { echo -e "${YELLOW}[~]${NC} $1"; }
error()   { echo -e "${RED}[✘]${NC} $1"; exit 1; }
ask()     { echo -e "${CYAN}[?]${NC} $1"; }

# ─────────────────────────────────────────────
#  1. SE PLACER DANS LE DOSSIER DU PROJET
# ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
ENV_FILE="ai-coding-agent/.env"

# ─────────────────────────────────────────────
#  2. SETUP WIZARD — créer le .env si absent
# ─────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo -e "${BOLD}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║       🛠  Configuration initiale           ║${NC}"
    echo -e "${BOLD}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    warning "Fichier .env absent. Lancement de l'assistant de configuration..."
    echo ""

    # --- LLM Backend ---
    ask "URL du backend LLM (défaut: http://localhost:11434/v1 pour Ollama local) :"
    read -r INPUT_BASE_URL
    BASE_URL="${INPUT_BASE_URL:-http://localhost:11434/v1}"

    ask "Clé API du backend LLM (défaut: ollama) :"
    read -r INPUT_API_KEY
    API_KEY="${INPUT_API_KEY:-ollama}"

    # --- Telegram ---
    echo ""
    ask "Token du bot Telegram (depuis @BotFather, laissez vide pour ignorer) :"
    read -r TELEGRAM_BOT_TOKEN

    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        ask "Votre Chat ID Telegram personnel (depuis @userinfobot) :"
        read -r TELEGRAM_AUTHORIZED_CHAT_ID
    fi

    # --- Groq Whisper ---
    echo ""
    ask "Clé API Groq pour la transcription vocale Whisper (console.groq.com, laissez vide pour ignorer) :"
    read -r GROQ_API_KEY

    # --- Écriture du .env ---
    cat > "$ENV_FILE" <<EOF
# Agent Configuration
API_KEY=${API_KEY}
BASE_URL=${BASE_URL}

# Telegram Bot Integration
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_AUTHORIZED_CHAT_ID=${TELEGRAM_AUTHORIZED_CHAT_ID}

# Groq Whisper - Transcription vocale
GROQ_API_KEY=${GROQ_API_KEY}
EOF

    echo ""
    info "Fichier .env créé avec succès → $ENV_FILE"
    echo ""
else
    info "Fichier .env trouvé."
fi

# ─────────────────────────────────────────────
#  3. VÉRIFIER / INSTALLER OLLAMA
# ─────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    warning "Ollama non trouvé. Installation en cours..."
    curl -fsSL https://ollama.ai/install.sh | sh
    info "Ollama installé."
else
    info "Ollama déjà installé."
fi

# ─────────────────────────────────────────────
#  4. VÉRIFIER / DÉMARRER LE SERVEUR OLLAMA
# ─────────────────────────────────────────────
if ! curl -s http://localhost:11434 &>/dev/null; then
    warning "Serveur Ollama inactif. Démarrage en arrière-plan..."
    ollama serve &>/dev/null &
    for i in $(seq 1 15); do
        if curl -s http://localhost:11434 &>/dev/null; then break; fi
        sleep 1
    done
    if ! curl -s http://localhost:11434 &>/dev/null; then
        error "Le serveur Ollama n'a pas pu démarrer."
    fi
    info "Serveur Ollama démarré."
else
    info "Serveur Ollama déjà actif."
fi

# ─────────────────────────────────────────────
#  5. CONNEXION OLLAMA (modèles Cloud)
# ─────────────────────────────────────────────
if ! ollama list 2>/dev/null | grep -q ":cloud"; then
    warning "Connexion Ollama requise pour les modèles Cloud."
    echo ""
    ollama login
    info "Connexion Ollama réussie."
else
    info "Déjà connecté à Ollama."
fi

# ─────────────────────────────────────────────
#  6. VÉRIFIER / INSTALLER LES MODÈLES
# ─────────────────────────────────────────────
MODELS=(
    "gemma3:27b-cloud"
    "kimi-k2.5:cloud"
    "deepseek-v3.2:cloud"
    "glm-4.6:cloud"
    "qwen3-coder-next:cloud"
    "qwen3-coder:480b-cloud"
)

INSTALLED=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')

for MODEL in "${MODELS[@]}"; do
    if echo "$INSTALLED" | grep -q "^$MODEL$"; then
        info "Modèle déjà présent : $MODEL"
    else
        warning "Installation du modèle : $MODEL"
        ollama pull "$MODEL"
        info "Modèle installé : $MODEL"
    fi
done

# ─────────────────────────────────────────────
#  7. LANCER LE PROJET
# ─────────────────────────────────────────────
echo ""
info "Lancement de l'agent AI..."
source .venv/bin/activate
python ai-coding-agent/main.py "$@"
