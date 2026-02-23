#!/bin/bash
set -e

# ─────────────────────────────────────────────
#  COULEURS
# ─────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()    { echo -e "${GREEN}[✔]${NC} $1"; }
warning() { echo -e "${YELLOW}[~]${NC} $1"; }
error()   { echo -e "${RED}[✘]${NC} $1"; exit 1; }

# ─────────────────────────────────────────────
#  1. SE PLACER DANS LE DOSSIER DU PROJET
# ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ─────────────────────────────────────────────
#  2. VÉRIFIER / INSTALLER OLLAMA
# ─────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    warning "Ollama non trouvé. Installation en cours..."
    curl -fsSL https://ollama.ai/install.sh | sh
    info "Ollama installé."
else
    info "Ollama déjà installé."
fi

# ─────────────────────────────────────────────
#  3. VÉRIFIER / DÉMARRER LE SERVEUR OLLAMA
# ─────────────────────────────────────────────
if ! curl -s http://localhost:11434 &>/dev/null; then
    warning "Serveur Ollama inactif. Démarrage en arrière-plan..."
    ollama serve &>/dev/null &
    # Attendre que le serveur soit prêt (max 15s)
    for i in $(seq 1 15); do
        if curl -s http://localhost:11434 &>/dev/null; then
            break
        fi
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
#  4. CONNEXION OLLAMA (nécessaire pour les modèles Cloud)
# ─────────────────────────────────────────────
# On détecte si on est connecté en vérifiant qu'un modèle cloud est accessible
if ! ollama list 2>/dev/null | grep -q ":cloud"; then
    warning "Connexion Ollama requise pour accéder aux modèles Cloud."
    echo ""
    echo "  Lancez la commande suivante si l'URL ne s'affiche pas automatiquement :"
    echo "  → ollama login"
    echo ""
    ollama login
    info "Connexion Ollama réussie."
else
    info "Déjà connecté à Ollama."
fi

# ─────────────────────────────────────────────
#  5. VÉRIFIER / INSTALLER LES MODÈLES
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
#  5. LANCER LE PROJET
# ─────────────────────────────────────────────
echo ""
info "Lancement de l'agent AI..."
source .venv/bin/activate
python ai-coding-agent/main.py "$@"
