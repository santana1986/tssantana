# -*- coding: utf-8 -*-
"""Define as rotas e a lógica de visualização do aplicativo."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
# Importar todos os modelos e funções auxiliares de models.py
from .models import (
    data_storage, get_next_id, save_data, # Adicionado save_data
    Competition, Team, Player, Group, Match, Standing, KnockoutStage, MatchEvent,
    get_competition, get_team, get_player, get_group, get_match, 
    get_team_players, get_competition_teams, get_competition_matches, 
    get_group_matches, get_group_teams
)
import itertools
import operator # Para ordenação complexa
from collections import defaultdict # Para estatísticas
from fpdf import FPDF
import datetime
import os # Para path de fontes
import random # Para sorteio e chaveamento

bp = Blueprint("routes", __name__)

# --- Constantes ---
APP_NAME = "TS Sant'ana Gerenciador de Competições"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" 

# --- Funções Auxiliares de Lógica (Cálculos, etc.) ---

def calculate_standings(competition_id, group_id=None):
    """Recalcula a classificação de um grupo ou geral (round-robin)."""
    competition = get_competition(competition_id)
    if not competition:
        return

    target_standings = None
    relevant_matches = []
    relevant_teams = []
    should_save = False # Flag para salvar apenas se houver cálculo

    if competition.format == "groups_knockout" and group_id:
        group = get_group(group_id)
        if not group: return
        target_standings = group.standings
        relevant_matches = get_group_matches(group_id)
        relevant_teams = group.teams
        # Reset group standings
        group.standings = {}
        for team_id in relevant_teams:
            if get_team(team_id):
                group.standings[team_id] = Standing(team_id, competition_id, group_id=group_id)
            else:
                print(f"Aviso: Time ID {team_id} não encontrado ao inicializar standings para o grupo {group_id}.")
        target_standings = group.standings # Aponta para o dict recém-criado
        should_save = True
    
    elif competition.format == "round_robin":
        target_standings = competition.standings
        relevant_matches = get_competition_matches(competition_id)
        relevant_teams = competition.teams
        # Reset competition standings
        competition.standings = {}
        for team_id in relevant_teams:
             if get_team(team_id):
                competition.standings[team_id] = Standing(team_id, competition_id)
             else:
                 print(f"Aviso: Time ID {team_id} não encontrado ao inicializar standings gerais para a competição {competition_id}.")
        target_standings = competition.standings # Aponta para o dict recém-criado
        should_save = True
    else:
        return # Formato inválido ou grupo não especificado quando necessário

    if not target_standings: return # Sai se não conseguiu inicializar

    # Recalcular cartões totais do time varrendo todas as partidas finalizadas relevantes
    team_yellow_cards = defaultdict(int)
    team_red_cards = defaultdict(int)
    for match in relevant_matches:
         if match.status == "finished":
            for event in match.events:
                # Verifica se o jogador pertence a um time relevante para esta classificação
                player = get_player(event.player_id)
                if player and player.team_id in relevant_teams:
                    if event.event_type == "yellow_card":
                        team_yellow_cards[event.team_id] += 1
                    elif event.event_type == "red_card":
                        team_red_cards[event.team_id] += 1

    # Processar partidas finalizadas para calcular pontos, gols, etc.
    for match in relevant_matches:
        # Verifica se os times da partida ainda existem e estão nos standings sendo calculados
        if match.status == "finished" and match.team1_score is not None and match.team2_score is not None and \
           match.team1_id in target_standings and match.team2_id in target_standings:
            
            s1 = target_standings[match.team1_id]
            s2 = target_standings[match.team2_id]

            s1.played += 1
            s2.played += 1
            s1.goals_for += match.team1_score
            s1.goals_against += match.team2_score
            s2.goals_for += match.team2_score
            s2.goals_against += match.team1_score
            s1.goal_difference = s1.goals_for - s1.goals_against
            s2.goal_difference = s2.goals_for - s2.goals_against

            if match.team1_score > match.team2_score:
                s1.points += 3; s1.wins += 1; s2.losses += 1
            elif match.team1_score < match.team2_score:
                s2.points += 3; s2.wins += 1; s1.losses += 1
            else:
                s1.points += 1; s2.points += 1; s1.draws += 1; s2.draws += 1
                
            # Atribui o total de cartões recalculado (baseado em todos os jogos)
            s1.yellow_cards = team_yellow_cards.get(match.team1_id, 0)
            s1.red_cards = team_red_cards.get(match.team1_id, 0)
            s2.yellow_cards = team_yellow_cards.get(match.team2_id, 0)
            s2.red_cards = team_red_cards.get(match.team2_id, 0)

        elif match.status == "finished":
             print(f"Aviso: Partida {match.id} finalizada mas um dos times ({match.team1_id} ou {match.team2_id}) não está nos standings relevantes.")
    
    if should_save:
        save_data() # Salva os standings atualizados

def sort_standings(standings_dict, competition_id, group_id=None):
    """Ordena a classificação (de grupo ou geral) usando critérios de desempate."""
    standings_list = list(standings_dict.values())
    
    # Função de comparação para sort
    def compare_teams(s1, s2):
        # 1. Pontos
        if s1.points != s2.points: return s2.points - s1.points
        # TODO: Implementar confronto direto (requer filtrar partidas entre os times empatados)
        # 2. Saldo de Gols (Geral)
        if s1.goal_difference != s2.goal_difference: return s2.goal_difference - s1.goal_difference
        # 3. Gols Pró (Geral)
        if s1.goals_for != s2.goals_for: return s2.goals_for - s1.goals_for
        # 4. Menos Cartões Vermelhos (Geral)
        if s1.red_cards != s2.red_cards: return s1.red_cards - s2.red_cards
        # 5. Menos Cartões Amarelos (Geral)
        if s1.yellow_cards != s2.yellow_cards: return s1.yellow_cards - s2.yellow_cards
        # 6. Sorteio (não implementado)
        return 0

    from functools import cmp_to_key
    standings_list.sort(key=cmp_to_key(compare_teams))
    return standings_list

def calculate_stats(competition_id):
    """Calcula estatísticas gerais da competição (artilharia, cartões, goleiros)."""
    competition = get_competition(competition_id)
    if not competition: return {"top_scorers": [], "discipline": [], "goalkeepers": []}

    player_stats = defaultdict(lambda: {"name": "Desconhecido", "team_id": None, "team_name": "Desconhecido", "goals": 0, "yellow_cards": 0, "red_cards": 0})
    team_goals_conceded = defaultdict(int)
    team_matches_played = defaultdict(int)
    matches = get_competition_matches(competition_id)

    for match in matches:
        if match.status == "finished":
            if match.team1_id:
                team_goals_conceded[match.team1_id] += match.team2_score
                team_matches_played[match.team1_id] += 1
            if match.team2_id:
                team_goals_conceded[match.team2_id] += match.team1_score
                team_matches_played[match.team2_id] += 1
            for event in match.events:
                player_id = event.player_id
                if player_id not in player_stats:
                    player = get_player(player_id)
                    if player:
                        team = get_team(player.team_id)
                        player_stats[player_id]["name"] = player.name
                        player_stats[player_id]["team_id"] = player.team_id
                        player_stats[player_id]["team_name"] = team.name if team else "Desconhecido"
                    else: continue
                if event.event_type == "goal": player_stats[player_id]["goals"] += 1
                elif event.event_type == "yellow_card": player_stats[player_id]["yellow_cards"] += 1
                elif event.event_type == "red_card": player_stats[player_id]["red_cards"] += 1

    top_scorers = sorted([s for s in player_stats.values() if s["goals"] > 0], key=lambda x: x["goals"], reverse=True)
    discipline = sorted([s for s in player_stats.values() if s["yellow_cards"] > 0 or s["red_cards"] > 0], key=lambda x: (x["red_cards"], x["yellow_cards"]), reverse=True)
    goalkeepers_stats = []
    for team in get_competition_teams(competition_id):
        matches_played = team_matches_played.get(team.id, 0)
        if matches_played > 0:
            goals_conceded = team_goals_conceded.get(team.id, 0)
            avg_conceded = goals_conceded / matches_played
            goalkeepers_stats.append({"team_name": team.name, "goals_conceded": goals_conceded, "matches_played": matches_played, "avg_conceded": avg_conceded})
    goalkeepers_stats.sort(key=lambda x: (x["avg_conceded"], x["goals_conceded"]))
    return {"top_scorers": top_scorers, "discipline": discipline, "goalkeepers": goalkeepers_stats}

# --- Função para Gerar Súmula PDF (sem alterações) ---
class PDF(FPDF):
    def header(self):
        try: self.add_font("DejaVu", "", FONT_PATH, uni=True); self.set_font("DejaVu", "B", 12)
        except RuntimeError: print(f"Aviso: Fonte DejaVu não encontrada em {FONT_PATH}. Usando Arial."); self.set_font("Arial", "B", 12)
        self.cell(0, 10, APP_NAME, 0, 1, "C")
        self.set_font(self.font_family, "", 10)
        self.cell(0, 10, "Súmula da Partida", 0, 1, "C")
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        try: self.set_font("DejaVu", "I", 8)
        except RuntimeError: self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", 0, 0, "C")

def generate_sumula_pdf(match_id):
    match = get_match(match_id)
    if not match or match.status != "finished": return None
    competition = get_competition(match.competition_id)
    team1 = get_team(match.team1_id); team2 = get_team(match.team2_id)
    if not competition or not team1 or not team2: return None # Verifica se tudo existe
    players1 = get_team_players(match.team1_id); players2 = get_team_players(match.team2_id)
    pdf = PDF(); pdf.alias_nb_pages(); pdf.add_page()
    try: pdf.add_font("DejaVu", "", FONT_PATH, uni=True); pdf.set_font("DejaVu", "", 10)
    except RuntimeError: pdf.set_font("Arial", "", 10)
    pdf.set_font(pdf.font_family, "B", 11)
    pdf.cell(0, 7, f"Competição: {competition.name} ({competition.type.capitalize()}) - Formato: {"Pontos Corridos" if competition.format == "round_robin" else "Grupos + Mata-Mata"}", 0, 1)
    phase = ""
    if match.group_id: group = get_group(match.group_id); phase = f"Fase de Grupos - {group.name}" if group else "Grupo Desconhecido"
    elif match.knockout_round: phase = f"Fase Eliminatória - {match.knockout_round}"
    elif match.round_number: phase = f"Rodada {match.round_number}"
    pdf.cell(0, 7, f"Fase/Rodada: {phase}", 0, 1)
    pdf.cell(0, 7, f"Data: {match.date if match.date else "Não informada"}", 0, 1); pdf.ln(5)
    pdf.set_font(pdf.font_family, "B", 14)
    pdf.cell(0, 10, f"{team1.name}  {match.team1_score}  x  {match.team2_score}  {team2.name}", 0, 1, "C"); pdf.ln(5)
    pdf.set_font(pdf.font_family, "B", 11); pdf.cell(0, 7, "Jogadores Relacionados", 0, 1)
    col_width = pdf.w / 2 - 15
    pdf.set_font(pdf.font_family, "B", 10)
    pdf.cell(col_width, 6, team1.name, border=1, ln=0, align="C")
    pdf.cell(10, 6, "", border=0, ln=0)
    pdf.cell(col_width, 6, team2.name, border=1, ln=1, align="C")
    pdf.set_font(pdf.font_family, "", 9)
    max_players = max(len(players1), len(players2))
    for i in range(max_players):
        player1_name = players1[i].name if i < len(players1) else ""
        player2_name = players2[i].name if i < len(players2) else ""
        pdf.cell(col_width, 5, player1_name, border=1, ln=0)
        pdf.cell(10, 5, "", border=0, ln=0)
        pdf.cell(col_width, 5, player2_name, border=1, ln=1)
    pdf.ln(5)
    pdf.set_font(pdf.font_family, "B", 11); pdf.cell(0, 7, "Eventos da Partida", 0, 1)
    pdf.set_font(pdf.font_family, "B", 9)
    pdf.cell(20, 6, "Minuto", border=1, ln=0, align="C"); pdf.cell(25, 6, "Tipo", border=1, ln=0, align="C")
    pdf.cell(70, 6, "Jogador", border=1, ln=0, align="C"); pdf.cell(70, 6, "Time", border=1, ln=1, align="C")
    pdf.set_font(pdf.font_family, "", 9)
    sorted_events = sorted(match.events, key=lambda e: (int(e.minute) if e.minute and e.minute.isdigit() else 999, e.event_type))
    event_type_map = {"goal": "Gol", "yellow_card": "Cartão Amarelo", "red_card": "Cartão Vermelho"}
    for event in sorted_events:
        player = get_player(event.player_id); team = get_team(event.team_id)
        pdf.cell(20, 5, str(event.minute) if event.minute else "-", border=1, ln=0, align="C")
        pdf.cell(25, 5, event_type_map.get(event.event_type, event.event_type), border=1, ln=0, align="C")
        pdf.cell(70, 5, player.name if player else f"ID {event.player_id}", border=1, ln=0)
        pdf.cell(70, 5, team.name if team else f"ID {event.team_id}", border=1, ln=1)
    pdf.ln(10)
    pdf.set_font(pdf.font_family, "", 10)
    pdf.cell(pdf.w / 3, 10, "_________________________", 0, 0, "C"); pdf.cell(pdf.w / 3, 10, "_________________________", 0, 0, "C"); pdf.cell(pdf.w / 3, 10, "_________________________", 0, 1, "C")
    pdf.cell(pdf.w / 3, 5, "Árbitro", 0, 0, "C"); pdf.cell(pdf.w / 3, 5, "Representante Time 1", 0, 0, "C"); pdf.cell(pdf.w / 3, 5, "Representante Time 2", 0, 1, "C")
    pdf_bytes = pdf.output(dest="S")
    # Tenta decodificar como latin-1, se falhar, usa utf-8 com replace
    try:
        return pdf_bytes.decode("latin-1")
    except UnicodeDecodeError:
        print("Aviso: Erro ao decodificar PDF como latin-1, tentando utf-8 com replace.")
        return pdf_bytes.decode("utf-8", errors="replace")

# --- Rotas Principais ---

@bp.route("/")
def index():
    competitions = list(data_storage["competitions"].values())
    return render_template("index.html", competitions=competitions, app_name=APP_NAME)

@bp.route("/competition/new", methods=["GET", "POST"])
def create_competition():
    if request.method == "POST":
        name = request.form.get("name")
        type = request.form.get("type")
        format = request.form.get("format")
        allowed_types = ["futebol", "futsal", "fut7", "suico"]
        allowed_formats = ["groups_knockout", "round_robin"]
        if not name or not type or type not in allowed_types or not format or format not in allowed_formats:
            flash("Nome, modalidade válida e formato válido são obrigatórios.", "error")
            return render_template("create_competition.html", app_name=APP_NAME)
        competition_id = get_next_id("competition")
        new_competition = Competition(id=competition_id, name=name, type=type, format=format)
        data_storage["competitions"][competition_id] = new_competition
        save_data() # Salva a nova competição
        format_text = "Pontos Corridos" if format == "round_robin" else "Grupos + Mata-Mata"
        flash(f"Competição 	'{name}' ({type.capitalize()} - {format_text}) criada com sucesso!", "success")
        return redirect(url_for("routes.view_competition", competition_id=competition_id))
    return render_template("create_competition.html", app_name=APP_NAME)

@bp.route("/competition/<int:competition_id>")
def view_competition(competition_id):
    competition = get_competition(competition_id)
    if not competition: flash("Competição não encontrada.", "error"); return redirect(url_for("routes.index"))
    teams = get_competition_teams(competition_id)
    groups_data = []
    knockout_matches = []
    round_robin_standings = []
    all_matches = sorted(get_competition_matches(competition_id), key=lambda m: (m.group_id or 999, m.knockout_round or "", m.round_number or 999, m.id))

    if competition.format == "groups_knockout":
        if competition.groups:
            for group_id in competition.groups:
                group = get_group(group_id)
                if group:
                    calculate_standings(competition_id, group_id=group_id) # Recalcula antes de exibir
                    sorted_standings_list = sort_standings(group.standings, competition_id, group_id=group_id)
                    group_matches = get_group_matches(group_id)
                    groups_data.append({"group": group, "standings": sorted_standings_list, "matches": group_matches})
        if competition.knockout_stage:
             for round_name, match_ids in competition.knockout_stage.rounds.items():
                 round_matches = [get_match(m_id) for m_id in match_ids if get_match(m_id)]
                 knockout_matches.append({"round_name": round_name, "matches": round_matches})
    
    elif competition.format == "round_robin":
        calculate_standings(competition_id) # Recalcula antes de exibir
        round_robin_standings = sort_standings(competition.standings, competition_id)

    stats = calculate_stats(competition_id)

    return render_template("view_competition.html", 
                           competition=competition, 
                           teams=teams, 
                           groups_data=groups_data, 
                           knockout_matches=knockout_matches,
                           round_robin_standings=round_robin_standings,
                           all_matches=all_matches,
                           stats=stats,
                           app_name=APP_NAME)

@bp.route("/competition/<int:competition_id>/add_team", methods=["GET", "POST"])
def add_team(competition_id):
    competition = get_competition(competition_id)
    if not competition: flash("Competição não encontrada.", "error"); return redirect(url_for("routes.index"))
    if request.method == "POST":
        team_name = request.form.get("team_name")
        if not team_name:
            flash("Nome do time é obrigatório.", "error")
        else:
            team_id = get_next_id("team")
            new_team = Team(id=team_id, name=team_name, competition_id=competition_id)
            data_storage["teams"][team_id] = new_team
            competition.teams.append(team_id)
            save_data() # Salva após adicionar time
            flash(f"Time '{team_name}' adicionado à competição '{competition.name}'.", "success")
            return redirect(url_for("routes.view_competition", competition_id=competition_id))
    return render_template("add_team.html", competition=competition, app_name=APP_NAME)

@bp.route("/competition/<int:competition_id>/team/<int:team_id>")
def view_team(competition_id, team_id):
    competition = get_competition(competition_id); team = get_team(team_id)
    if not competition or not team: flash("Competição ou Time não encontrado.", "error"); return redirect(url_for("routes.index"))
    players = get_team_players(team_id)
    return render_template("view_team.html", competition=competition, team=team, players=players, app_name=APP_NAME)

@bp.route("/competition/<int:competition_id>/team/<int:team_id>/add_player", methods=["GET", "POST"])
def add_player(competition_id, team_id):
    competition = get_competition(competition_id); team = get_team(team_id)
    if not competition or not team: flash("Competição ou Time não encontrado.", "error"); return redirect(url_for("routes.index"))
    if request.method == "POST":
        player_name = request.form.get("player_name")
        if not player_name:
            flash("Nome do jogador é obrigatório.", "error")
        else:
            player_id = get_next_id("player")
            new_player = Player(id=player_id, name=player_name, team_id=team_id)
            data_storage["players"][player_id] = new_player
            team.players.append(player_id)
            save_data() # Salva após adicionar jogador
            flash(f"Jogador '{player_name}' adicionado ao time '{team.name}'.", "success")
            return redirect(url_for("routes.view_team", competition_id=competition_id, team_id=team_id))
    return render_template("add_player.html", competition=competition, team=team, app_name=APP_NAME)

@bp.route("/competition/<int:competition_id>/setup_groups", methods=["GET", "POST"])
def setup_groups(competition_id):
    competition = get_competition(competition_id)
    if not competition or competition.format != "groups_knockout": 
        flash("Competição não encontrada ou formato inválido para grupos.", "error")
        return redirect(url_for("routes.index"))
    
    teams = get_competition_teams(competition_id)
    if request.method == "POST":
        num_groups = int(request.form.get("num_groups", 0))
        teams_per_group = int(request.form.get("teams_per_group", 0))
        if num_groups <= 0 or num_groups > 16 or teams_per_group <= 1 or teams_per_group > 16 or num_groups * teams_per_group > len(teams):
            flash("Número inválido de grupos ou times por grupo.", "error")
            return render_template("setup_groups.html", competition=competition, teams=teams, app_name=APP_NAME)
        
        # Limpa grupos e partidas existentes da fase de grupos
        for group_id in list(competition.groups): # Itera sobre cópia
            if group_id in data_storage["groups"]:
                for match_id in data_storage["groups"][group_id].matches:
                    if match_id in data_storage["matches"]:
                        del data_storage["matches"][match_id]
                        if match_id in competition.matches: competition.matches.remove(match_id)
                del data_storage["groups"][group_id]
        competition.groups = []
        competition.standings = {} # Limpa standings gerais se houver
        competition.knockout_stage = None # Reseta mata-mata
        competition.status = "group_stage"

        # Sorteia times nos grupos (simples)
        shuffled_teams = random.sample(teams, len(teams))
        group_teams_assignment = [[] for _ in range(num_groups)]
        team_idx = 0
        for i in range(teams_per_group):
            for g in range(num_groups):
                if team_idx < len(shuffled_teams):
                    group_teams_assignment[g].append(shuffled_teams[team_idx].id)
                    team_idx += 1

        # Cria grupos e gera partidas
        for i, team_ids in enumerate(group_teams_assignment):
            if not team_ids: continue # Pula se grupo ficou vazio
            group_id = get_next_id("group")
            group_name = f"Grupo {chr(ord('A') + i)}"
            new_group = Group(id=group_id, competition_id=competition_id, name=group_name, teams=team_ids)
            data_storage["groups"][group_id] = new_group
            competition.groups.append(group_id)
            
            # Gera partidas (todos contra todos)
            for team1_id, team2_id in itertools.combinations(team_ids, 2):
                match_id = get_next_id("match")
                new_match = Match(id=match_id, competition_id=competition_id, team1_id=team1_id, team2_id=team2_id, group_id=group_id)
                data_storage["matches"][match_id] = new_match
                new_group.matches.append(match_id)
                competition.matches.append(match_id)
        
        save_data() # Salva após criar grupos e partidas
        flash(f"{num_groups} grupos criados e partidas geradas.", "success")
        return redirect(url_for("routes.view_competition", competition_id=competition_id))

    return render_template("setup_groups.html", competition=competition, teams=teams, app_name=APP_NAME)

@bp.route("/competition/<int:competition_id>/generate_rr_matches", methods=["POST"])
def generate_round_robin_matches(competition_id):
    competition = get_competition(competition_id)
    if not competition or competition.format != "round_robin":
        flash("Competição não encontrada ou formato inválido.", "error")
        return redirect(url_for("routes.index"))
    
    teams = get_competition_teams(competition_id)
    if len(teams) < 2:
        flash("É necessário pelo menos 2 times para gerar partidas.", "error")
        return redirect(url_for("routes.view_competition", competition_id=competition_id))

    # Limpa partidas existentes
    for match_id in list(competition.matches): # Itera sobre cópia
        if match_id in data_storage["matches"]:
            del data_storage["matches"][match_id]
    competition.matches = []
    competition.standings = {} # Reseta standings
    competition.status = "round_robin_stage" # Ou um status apropriado

    # Gera partidas (todos contra todos - turno único)
    round_num = 1
    for team1_id, team2_id in itertools.combinations([t.id for t in teams], 2):
        match_id = get_next_id("match")
        new_match = Match(id=match_id, competition_id=competition_id, team1_id=team1_id, team2_id=team2_id, round_number=round_num)
        data_storage["matches"][match_id] = new_match
        competition.matches.append(match_id)
        # Simplesmente incrementa rodada, pode ser melhorado com algoritmos de tabela
        # round_num += 1 

    save_data() # Salva após gerar partidas
    flash("Partidas do formato Pontos Corridos geradas.", "success")
    return redirect(url_for("routes.view_competition", competition_id=competition_id))

@bp.route("/match/<int:match_id>/record_result", methods=["GET", "POST"])
def record_result(match_id):
    match = get_match(match_id)
    if not match: flash("Partida não encontrada.", "error"); return redirect(url_for("routes.index"))
    competition = get_competition(match.competition_id)
    team1 = get_team(match.team1_id); team2 = get_team(match.team2_id)
    if not competition or not team1 or not team2: flash("Erro ao carregar dados da partida.", "error"); return redirect(url_for("routes.index"))
    players1 = get_team_players(match.team1_id); players2 = get_team_players(match.team2_id)

    if request.method == "POST":
        try:
            score1 = int(request.form.get("score1"))
            score2 = int(request.form.get("score2"))
            match_date = request.form.get("match_date")
        except (ValueError, TypeError):
            flash("Placar inválido.", "error")
            return render_template("record_result.html", match=match, competition=competition, team1=team1, team2=team2, players1=players1, players2=players2, app_name=APP_NAME)

        match.team1_score = score1
        match.team2_score = score2
        match.status = "finished"
        match.date = match_date if match_date else match.date # Atualiza data se fornecida
        match.events = [] # Limpa eventos antigos antes de adicionar novos

        # Processar eventos
        event_count = int(request.form.get("event_count", 0))
        for i in range(event_count):
            event_type = request.form.get(f"event_type_{i}")
            player_id = int(request.form.get(f"player_id_{i}", 0))
            minute = request.form.get(f"minute_{i}")
            player = get_player(player_id)
            if event_type and player_id and player:
                event_id = get_next_id("event")
                team_id = player.team_id
                new_event = MatchEvent(id=event_id, match_id=match_id, team_id=team_id, player_id=player_id, event_type=event_type, minute=minute)
                match.events.append(new_event)
            else:
                 print(f"Aviso: Evento {i} ignorado por dados inválidos (tipo={event_type}, player_id={player_id})")

        save_data() # Salva o resultado e eventos da partida
        flash(f"Resultado da partida {team1.name} x {team2.name} registrado.", "success")
        # Recalcular standings após registrar resultado
        if match.group_id:
            calculate_standings(competition.id, group_id=match.group_id)
        elif competition.format == "round_robin":
             calculate_standings(competition.id)
        # Não salva aqui de novo, calculate_standings já salva
        return redirect(url_for("routes.view_competition", competition_id=competition.id))

    return render_template("record_result.html", match=match, competition=competition, team1=team1, team2=team2, players1=players1, players2=players2, app_name=APP_NAME)

@bp.route("/match/<int:match_id>/generate_sumula")
def generate_sumula(match_id):
    pdf_content = generate_sumula_pdf(match_id)
    if pdf_content:
        response = make_response(pdf_content)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"inline; filename=sumula_partida_{match_id}.pdf"
        return response
    else:
        flash("Não foi possível gerar a súmula. Verifique se a partida está finalizada.", "error")
        match = get_match(match_id)
        return redirect(url_for("routes.view_competition", competition_id=match.competition_id if match else 0))

@bp.route("/competition/<int:competition_id>/setup_knockout", methods=["GET", "POST"])
def setup_knockout(competition_id):
    competition = get_competition(competition_id)
    if not competition or competition.format != "groups_knockout":
        flash("Competição inválida para fase eliminatória.", "error")
        return redirect(url_for("routes.index"))

    # Verifica se a fase de grupos terminou
    all_groups_finished = True
    qualified_teams_map = {} # group_id -> [team_id, ...]
    if not competition.groups:
         flash("Nenhum grupo configurado para esta competição.", "error")
         return redirect(url_for("routes.view_competition", competition_id=competition_id))
         
    for group_id in competition.groups:
        group = get_group(group_id)
        if not group: continue
        group_finished = all(m.status == "finished" for m in get_group_matches(group_id))
        group.is_finished = group_finished
        if not group_finished:
            all_groups_finished = False
        else:
            # Pega os classificados (ex: 2 primeiros)
            num_qualify = 2 # TODO: Tornar configurável
            calculate_standings(competition_id, group_id=group_id)
            sorted_standings = sort_standings(group.standings, competition_id, group_id=group_id)
            qualified_teams_map[group_id] = [s.team_id for s in sorted_standings[:num_qualify]]

    if not all_groups_finished:
        flash("A fase de grupos ainda não terminou. Finalize todas as partidas.", "warning")
        # Salva o status de finalização dos grupos
        save_data()
        return redirect(url_for("routes.view_competition", competition_id=competition_id))

    qualified_teams_flat = [team_id for teams in qualified_teams_map.values() for team_id in teams]
    num_qualified = len(qualified_teams_flat)

    if request.method == "POST":
        num_teams_knockout = int(request.form.get("num_teams_knockout", 0))
        if num_teams_knockout not in [2, 4, 8, 16, 32] or num_teams_knockout > num_qualified:
            flash("Número inválido de times para o mata-mata.", "error")
        else:
            # Seleciona os times para o mata-mata (pode precisar de lógica mais complexa se num_teams < num_qualified)
            teams_for_knockout = qualified_teams_flat[:num_teams_knockout]
            random.shuffle(teams_for_knockout) # Sorteio simples

            # Limpa partidas de mata-mata existentes
            if competition.knockout_stage:
                 for round_name, match_ids in competition.knockout_stage.rounds.items():
                     for match_id in match_ids:
                         if match_id in data_storage["matches"]:
                             del data_storage["matches"][match_id]
                             if match_id in competition.matches: competition.matches.remove(match_id)
            
            competition.knockout_stage = KnockoutStage(competition_id=competition_id)
            competition.status = "knockout_stage"
            
            round_map = {32: "16 avos", 16: "Oitavas", 8: "Quartas", 4: "Semifinal", 2: "Final"}
            current_round_name = round_map.get(num_teams_knockout, "Fase Desconhecida")
            competition.knockout_stage.rounds[current_round_name] = []

            # Gera partidas da primeira fase do mata-mata
            for i in range(0, num_teams_knockout, 2):
                team1_id = teams_for_knockout[i]
                team2_id = teams_for_knockout[i+1]
                match_id = get_next_id("match")
                new_match = Match(id=match_id, competition_id=competition_id, team1_id=team1_id, team2_id=team2_id, knockout_round=current_round_name)
                data_storage["matches"][match_id] = new_match
                competition.matches.append(match_id)
                competition.knockout_stage.rounds[current_round_name].append(match_id)
            
            save_data() # Salva o mata-mata configurado
            flash(f"Fase eliminatória ({current_round_name}) configurada com {num_teams_knockout} times.", "success")
            return redirect(url_for("routes.view_competition", competition_id=competition_id))

    return render_template("setup_knockout.html", 
                           competition=competition, 
                           qualified_teams_map=qualified_teams_map,
                           num_qualified=num_qualified,
                           app_name=APP_NAME)

# TODO: Adicionar rota para avançar no mata-mata após registrar resultados

