from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
from copy import deepcopy

# =========================================================
# IMPORTS ADK
# =========================================================
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import SequentialAgent
from google.adk.tools import ToolContext
from google.adk.runners import Runner
from google.genai import types 
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse, LlmRequest
from google.adk.tools.base_tool import BaseTool

# (Supposons que vos outils existent dans un module .tools, 
# sinon je les mocke ici pour que le code soit exécutable et autonome comme l'exemple)
# from .tools import get_weather, search_scholarships, search_city_info, get_public_holidays

# Config placeholders (pour respecter le style sans dépendance externe)
ROOT_MODEL_NAME = "ollama_chat/qwen2.5:7b-instruct"
TOOL_MODEL_NAME = "ollama_chat/qwen2.5:7b-instruct" 

logging.basicConfig(level=logging.INFO)

# =========================================================
# 1. SERVICES
# =========================================================
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# =========================================================
# 2. CALLBACKS
# =========================================================

# --- CALLBACK 1: LOGGING & STATE CHECK (Before Agent) ---
def check_and_log_agent_entry(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    Log l'entrée dans l'agent et met à jour les stats utilisateur en session.
    Peut aussi skipper un agent si une condition est remplie.
    """
    agent_name = callback_context.agent_name
    timestamp = datetime.now().strftime("%H:%M:%S")
    current_state = callback_context.state.to_dict()

    print(f"\n{'🟡'*25}")
    print(f"[⏰ {timestamp}] Callback: Entering agent '{agent_name}'")
    
    # Mise à jour des compteurs (State Management)
    call_count = current_state.get("user:agent_call_count", 0) + 1
    callback_context.state["user:agent_call_count"] = call_count
    callback_context.state["temp:current_agent"] = agent_name
    
    print(f"📊 State: call_count={call_count}")

    # Exemple de logique de skip (similaire au code Hotel)
    if current_state.get("skip_processing", False):
        print(f"[Callback] Skipping agent {agent_name} due to skip_processing=True")
        return types.Content(
            parts=[types.Part(text=f"Agent {agent_name} skipped.")],
            role="model"
        )
    
    return None

# --- CALLBACK 2: PROMPT MODIFIER (Before Model) ---
def simple_before_model_modifier(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Inspecte ou modifie la requête LLM avant envoi."""
    agent_name = callback_context.agent_name
    timestamp = datetime.now().strftime("%H:%M:%S")

    # Récupération du dernier message utilisateur pour logging
    last_user_msg = ""
    if llm_request.contents and llm_request.contents[-1].role == 'user':
         if llm_request.contents[-1].parts:
            last_user_msg = llm_request.contents[-1].parts[0].text

    print(f"\n{'🔵'*25}")
    print(f"[⏰ {timestamp}] Before Model ({agent_name})")
    print(f"📝 User Input: {last_user_msg[:50]}..." if last_user_msg else "📝 User Input: Empty")
    
    return None # On laisse passer la requête

# --- CALLBACK 3: TOOL INSPECTOR (After Tool) ---
def simple_after_tool_modifier(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict
) -> Optional[Dict]:
    """Inspecte le résultat des outils."""
    print(f"[Callback] After tool '{tool.name}' executed.")
    # On pourrait modifier la réponse ici si besoin, comme dans l'exemple Hotel
    return None

# =========================================================
# 3. TOOLS (Wrappers pour standardisation)
# =========================================================

# Ici je définis des wrappers pour que l'architecture soit autonome
# Dans votre vrai code, remplacez le contenu par vos appels réels

def get_weather_tool(city: str) -> dict:
    """Mock weather tool."""
    return {"city": city, "temp": "25C", "condition": "Sunny", "status": "success"}

def get_public_holidays_tool(country_code: str, year: int = 2025) -> dict:
    """Mock holiday tool."""
    return {"country": country_code, "holidays": ["New Year", "Independence Day"], "status": "success"}

def search_scholarships_tool(country: str, field: str, level: str) -> dict:
    """Mock scholarship search."""
    # Simulation de retour API
    return {
        "status": "success", 
        "data": [
            {"name": "Gov Grant A", "amount": "5000$", "deadline": "2025-12-01", "req": "GPA 3.0"},
            {"name": "Tech Future B", "amount": "2000$", "deadline": "2025-06-01", "req": "GPA 3.5"},
            {"name": "Research Fell C", "amount": "10000$", "deadline": "2025-09-01", "req": "PhD Only"}
        ]
    }

# =========================================================
# 4. AGENTS
# =========================================================

# --- 4.1 UTILITY AGENTS ---

weather_agent = Agent(
    name="weather_agent",
    model=LiteLlm(model=TOOL_MODEL_NAME),
    description="Donne la météo et suggère des activités.",
    tools=[get_weather_tool],
    before_model_callback=simple_before_model_modifier,
    instruction="""
    Tu es un expert météo.
    1. Utilise `get_weather_tool` avec la ville demandée.
    2. Donne la météo actuelle.
    3. Suggère une activité adaptée (ex: 'Plage' si soleil, 'Musée' si pluie).
    """
)

holiday_agent = Agent(
    name="holiday_agent",
    model=LiteLlm(model=TOOL_MODEL_NAME),
    description="Donne les jours fériés.",
    tools=[get_public_holidays_tool],
    instruction="""
    1. Extrais le pays de la demande.
    2. Convertis-le en code ISO 2 lettres (ex: Maroc -> MA, France -> FR).
    3. Appelle `get_public_holidays_tool`.
    4. Affiche la liste des jours fériés de manière claire.
    """
)

city_info_agent = Agent(
    name="city_info_agent",
    model=LiteLlm(model=ROOT_MODEL_NAME), # Modèle plus 'bavard' pour le texte
    description="Donne des infos sur une ville.",
    instruction="""
    Tu es un guide touristique.
    Donne 3 faits intéressants et culturels sur la ville demandée par l'utilisateur.
    """
)

# --- 4.2 SCHOLARSHIP WORKFLOW ---

# Étape 1 : Recherche
scholarship_search_agent = Agent(
    name="scholarship_search_agent",
    model=LiteLlm(model=TOOL_MODEL_NAME),
    description="Recherche bourses.",
    tools=[search_scholarships_tool],
    after_tool_callback=simple_after_tool_modifier, # Check results
    instruction="""
    Analyse la demande (Pays, Domaine, Niveau d'étude).
    Appelle `search_scholarships_tool`.
    
    IMPORTANT :
    Récupère la liste des bourses retournée par l'outil.
    Écris cette liste brute dans `session.state.scholarship_results`.
    """
)

# Étape 2 : Ranking
scholarship_ranking_agent = Agent(
    name="scholarship_ranking_agent",
    model=LiteLlm(model=TOOL_MODEL_NAME),
    description="Classement bourses.",
    instruction="""
    Lis `session.state.scholarship_results`.
    
    Tâche :
    1. Trie les bourses par Montant (du plus gros au plus petit).
    2. Sélectionne le Top 3.
    3. Formate une liste propre.
    
    Écris ce Top 3 formaté dans `session.state.ranked_scholarships`.
    """
)

# Étape 3 : Résumé / Conseil
scholarship_summary_agent = Agent(
    name="scholarship_summary_agent",
    model=LiteLlm(model=ROOT_MODEL_NAME),
    description="Conseiller final.",
    instruction="""
    Tu es un conseiller d'orientation bienveillant.
    Lis `session.state.ranked_scholarships`.
    
    Présente ces opportunités à l'étudiant avec un ton encourageant.
    Explique pourquoi c'est une bonne opportunité pour lui.
    Ne mentionne pas "JSON", "Outils" ou "session state". Parle naturellement.
    """
)

# Workflow Séquentiel
scholarship_pipeline = SequentialAgent(
    name="scholarship_pipeline",
    sub_agents=[
        scholarship_search_agent,
        scholarship_ranking_agent,
        scholarship_summary_agent
    ],
    description="Workflow complet : Recherche -> Classement -> Conseil pour bourses d'études."
)

# =========================================================
# 5. ROOT AGENT (ORCHESTRATEUR)
# =========================================================

root_agent = Agent(
    name="root_agent",
    model=LiteLlm(model=ROOT_MODEL_NAME),
    description="Routeur Principal Salah Travel System.",
    sub_agents=[weather_agent, holiday_agent, city_info_agent, scholarship_pipeline],
    before_agent_callback=check_and_log_agent_entry, # Global logging entry point
    instruction="""
    Tu es l'assistant principal du système "Salah Travel & Study".

    RÈGLES DE ROUTAGE :
    
    1. Si l'utilisateur cherche des financements, bourses, master, phd ou études à l'étranger :
       -> Appelle `scholarship_pipeline`. STOP.
       
    2. Si l'utilisateur demande la météo ou des activités liées au temps :
       -> Appelle `weather_agent`. STOP.
       
    3. Si l'utilisateur demande les jours fériés ou vacances :
       -> Appelle `holiday_agent`. STOP.
       
    4. Si l'utilisateur demande des infos générales sur une ville (culture, histoire) :
       -> Appelle `city_info_agent`. STOP.
       
    5. Sinon, réponds poliment que tu es spécialisé dans le voyage et les études.
    """
)

# Export pour l'exécution
agent = root_agent