# -*- coding: utf-8 -*-
"""Define os modelos de dados e funções de acesso."""

import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

DATA_FILE = "/var/data/data.json" # Caminho para disco persistente no Render

# --- Estruturas de Dados (Dataclasses) ---

@dataclass
class MatchEvent:
    id: int
    match_id: int
    team_id: int
    player_id: int
    event_type: str # "goal", "yellow_card", "red_card"
    minute: Optional[str] = None

@dataclass
class Match:
    id: int
    competition_id: int
    team1_id: int
    team2_id: int
    status: str = "scheduled" # "scheduled", "finished"
    team1_score: Optional[int] = None
    team2_score: Optional[int] = None
    group_id: Optional[int] = None
    round_number: Optional[int] = None # Para pontos corridos
    knockout_round: Optional[str] = None # "oitavas", "quartas", "semifinal", "final"
    date: Optional[str] = None
    events: List[MatchEvent] = field(default_factory=list)

@dataclass
class Standing:
    team_id: int
    competition_id: int
    group_id: Optional[int] = None
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0
    yellow_cards: int = 0 # Total do time na competição/grupo
    red_cards: int = 0 # Total do time na competição/grupo

@dataclass
class Group:
    id: int
    competition_id: int
    name: str
    teams: List[int] = field(default_factory=list)
    matches: List[int] = field(default_factory=list)
    standings: Dict[int, Standing] = field(default_factory=dict) # team_id -> Standing
    is_finished: bool = False

@dataclass
class KnockoutStage:
    competition_id: int
    rounds: Dict[str, List[int]] = field(default_factory=dict) # "oitavas" -> [match_id, ...]
    bracket: Optional[Any] = None # Poderia ser uma estrutura mais complexa para visualização

@dataclass
class Player:
    id: int
    name: str
    team_id: Optional[int] = None # Time atual na competição
    competition_stats: Dict[int, Dict[str, int]] = field(default_factory=dict) # competition_id -> {"goals": 0, ...}

@dataclass
class Team:
    id: int
    name: str
    competition_id: Optional[int] = None # Competição atual
    players: List[int] = field(default_factory=list)

@dataclass
class Competition:
    id: int
    name: str
    type: str # "futebol", "futsal", "fut7", "suico"
    format: str # "groups_knockout", "round_robin"
    teams: List[int] = field(default_factory=list)
    groups: List[int] = field(default_factory=list) # IDs dos grupos
    matches: List[int] = field(default_factory=list) # IDs das partidas (geral ou round-robin)
    standings: Dict[int, Standing] = field(default_factory=dict) # Para round-robin
    knockout_stage: Optional[KnockoutStage] = None
    status: str = "planning" # "planning", "group_stage", "knockout_stage", "finished"

# --- Armazenamento de Dados (Simulando um Banco de Dados Simples) ---

def load_data():
    """Carrega os dados do arquivo JSON."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            # Recriar objetos a partir dos dicts crus
            storage = {
                "competitions": {int(k): Competition(**v) for k, v in raw_data.get("competitions", {}).items()},
                "teams": {int(k): Team(**v) for k, v in raw_data.get("teams", {}).items()},
                "players": {int(k): Player(**v) for k, v in raw_data.get("players", {}).items()},
                "groups": {int(k): Group(**v) for k, v in raw_data.get("groups", {}).items()},
                "matches": {int(k): Match(**v) for k, v in raw_data.get("matches", {}).items()},
                "next_ids": raw_data.get("next_ids", {"competition": 1, "team": 1, "player": 1, "group": 1, "match": 1, "event": 1})
            }
            # Restaurar tipos complexos dentro dos objetos
            for comp in storage["competitions"].values():
                comp.standings = {int(k): Standing(**v) for k, v in comp.standings.items()} if isinstance(comp.standings, dict) else {}
                if comp.knockout_stage and isinstance(comp.knockout_stage, dict):
                     comp.knockout_stage = KnockoutStage(**comp.knockout_stage)
            for group in storage["groups"].values():
                 group.standings = {int(k): Standing(**v) for k, v in group.standings.items()} if isinstance(group.standings, dict) else {}
            for match in storage["matches"].values():
                 match.events = [MatchEvent(**e) for e in match.events] if isinstance(match.events, list) else []
            return storage
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"Erro ao carregar ou desserializar {DATA_FILE}: {e}. Iniciando com dados vazios.")
            # Fallback para dados vazios se o arquivo estiver corrompido ou mal formatado
            return {
                "competitions": {},
                "teams": {},
                "players": {},
                "groups": {},
                "matches": {},
                "next_ids": {"competition": 1, "team": 1, "player": 1, "group": 1, "match": 1, "event": 1}
            }
    else:
        # Retorna estrutura vazia se o arquivo não existe
        return {
            "competitions": {},
            "teams": {},
            "players": {},
            "groups": {},
            "matches": {},
            "next_ids": {"competition": 1, "team": 1, "player": 1, "group": 1, "match": 1, "event": 1}
        }

def save_data():
    """Salva os dados atuais no arquivo JSON."""
    # Converte objetos dataclass para dicts antes de salvar
    # Usa uma cópia profunda ou conversão manual para evitar modificar o data_storage original
    serializable_data = {
        "competitions": {k: v.__dict__ for k, v in data_storage["competitions"].items()},
        "teams": {k: v.__dict__ for k, v in data_storage["teams"].items()},
        "players": {k: v.__dict__ for k, v in data_storage["players"].items()},
        "groups": {k: v.__dict__ for k, v in data_storage["groups"].items()},
        "matches": {k: v.__dict__ for k, v in data_storage["matches"].items()},
        "next_ids": data_storage["next_ids"]
    }
    # Serializa sub-objetos manualmente
    for comp_dict in serializable_data["competitions"].values():
        comp_dict["standings"] = {k: v.__dict__ for k, v in comp_dict["standings"].items()}
        if comp_dict["knockout_stage"]:
             comp_dict["knockout_stage"] = comp_dict["knockout_stage"].__dict__
    for group_dict in serializable_data["groups"].values():
        group_dict["standings"] = {k: v.__dict__ for k, v in group_dict["standings"].items()}
    for match_dict in serializable_data["matches"].values():
        match_dict["events"] = [e.__dict__ for e in match_dict["events"]]

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Erro ao salvar dados em {DATA_FILE}: {e}")
    except TypeError as e:
         print(f"Erro de tipo ao serializar dados para JSON: {e}")

# Inicializa o armazenamento carregando do arquivo
data_storage = load_data()

# --- Funções de Acesso e Manipulação ---

def get_next_id(type_key):
    """Obtém o próximo ID disponível para um tipo e incrementa."""
    next_id = data_storage["next_ids"].get(type_key, 1)
    data_storage["next_ids"][type_key] = next_id + 1
    # Não salva aqui, salva quando a entidade for criada
    return next_id

# Funções get_... permanecem as mesmas (acessam data_storage)
def get_competition(id): return data_storage["competitions"].get(id)
def get_team(id): return data_storage["teams"].get(id)
def get_player(id): return data_storage["players"].get(id)
def get_group(id): return data_storage["groups"].get(id)
def get_match(id): return data_storage["matches"].get(id)

def get_team_players(team_id):
    team = get_team(team_id)
    return [get_player(p_id) for p_id in team.players if get_player(p_id)] if team else []

def get_competition_teams(competition_id):
    comp = get_competition(competition_id)
    return [get_team(t_id) for t_id in comp.teams if get_team(t_id)] if comp else []

def get_competition_matches(competition_id):
    comp = get_competition(competition_id)
    return [get_match(m_id) for m_id in comp.matches if get_match(m_id)] if comp else []

def get_group_matches(group_id):
    group = get_group(group_id)
    return [get_match(m_id) for m_id in group.matches if get_match(m_id)] if group else []

def get_group_teams(group_id):
     group = get_group(group_id)
     return [get_team(t_id) for t_id in group.teams if get_team(t_id)] if group else []

# Exemplo: Qualquer função que modifica dados agora deve chamar save_data()
# Exemplo (simplificado):
def add_team_to_competition(competition_id, team_name):
    competition = get_competition(competition_id)
    if not competition:
        return None
    team_id = get_next_id("team")
    new_team = Team(id=team_id, name=team_name, competition_id=competition_id)
    data_storage["teams"][team_id] = new_team
    competition.teams.append(team_id)
    save_data() # Salva após a modificação
    return new_team


