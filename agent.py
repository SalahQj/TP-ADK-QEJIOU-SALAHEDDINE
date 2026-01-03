# Fichier: Salah_agent/agent.py

# On importe l'instance directe créée dans votre fichier de logique (agents.py)
# Notez le 'r' minuscule, car c'est une variable, pas une classe.
from .agents import root_agent

# L'ADK cherche souvent une variable nommée 'agent' ou 'root_agent'
agent = root_agent