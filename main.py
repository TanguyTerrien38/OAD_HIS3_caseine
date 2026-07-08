import pygame
import os
import sys
from docplex.cp.config import context
from tutorial import TutorialManager
import ctypes
from collab.solver_cpo import PlanningSolver

try:
    # Dit à Windows : "Laisse Pygame gérer ses propres pixels, ne zoome pas !"
    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    pass

# Détermination des chemins
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Configuration CPLEX
chemin_cpoptimizer = os.path.join(base_dir, "moteur_cplex", "cpoptimizer.exe")
if os.path.exists(chemin_cpoptimizer):
    context.solver.agent = 'local'
    context.solver.local.execfile = chemin_cpoptimizer

# =========================================================================
# CONFIGURATION POUR LES ENTRETIENS (Forcé sur "collab" pour avoir l'OAD)
# =========================================================================
CONDITION = "collab" 

dossier_condition = os.path.join(base_dir, CONDITION)
sys.path.insert(0, dossier_condition)

# Imports des modules d'onglets restants
from planning_tab import PlanningTab
from monitoring_tab import MonitoringTab
from simulation_tab import SimulationTab

# Petit bouton utilitaire générique
class Button:
    def __init__(self, x, y, w, h, text, color):
        self.rect = pygame.Rect(x, y, w, h)
        self.text, self.color = text, color
    def draw(self, screen, font):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=5)
        surf = font.render(self.text, True, (255,255,255))
        screen.blit(surf, surf.get_rect(center=self.rect.center))
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)
        return False

# =========================================================================
# LA CLASSE PRINCIPALE (MAÎTRE DU JEU)
# =========================================================================
class MainApp:
    def __init__(self):
        pygame.init()
        
        os.environ['SDL_VIDEO_DISPLAY'] = '0'
        os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
        desktop_sizes = pygame.display.get_desktop_sizes()
        self.width, self.height = desktop_sizes[0]
        
        self.scale_x = self.width / 1680.0
        self.scale_y = self.height / 945.0
        self.scale = min(self.scale_x, self.scale_y)

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN | pygame.SCALED)
        pygame.display.set_caption(f"Planificateur & Simulateur - Mode Entretien")
        
        self.clock, self.running = pygame.time.Clock(), True
        
        # Polices fixes
        self.font_large = pygame.font.SysFont("trebuchetms", int(48*self.scale))
        self.font_medium = pygame.font.SysFont("trebuchetms", int(32*self.scale))
        self.tab_font = pygame.font.SysFont("trebuchetms", int(28*self.scale))
        
        # --- GESTION DU PROTOCOLE EXPÉRIMENTAL ---
        self.exp_state = "INTRO" # INTRO -> FAMIL -> EXP -> END

        # 3 Listes de difficultés
        self.scenarios = {
            "Facile": [
                {"planning": "scenarios_et_aleas/planning_S1.json", "aleas": "scenarios_et_aleas/aleas_S1.json"},
                {"planning": "scenarios_et_aleas/planning_S2.json", "aleas": "scenarios_et_aleas/aleas_S2.json"},
                {"planning": "scenarios_et_aleas/planning_S3.json", "aleas": "scenarios_et_aleas/aleas_S3.json"},
                {"planning": "scenarios_et_aleas/planning_S4.json", "aleas": "scenarios_et_aleas/aleas_S4.json"},
            ],
            "Moyen": [
                {"planning": "scenarios_et_aleas/planning_S10.json", "aleas": "scenarios_et_aleas/aleas_S10.json"},
                {"planning": "scenarios_et_aleas/planning_S12.json", "aleas": "scenarios_et_aleas/aleas_S11.json"},
                {"planning": "scenarios_et_aleas/planning_S12.json", "aleas": "scenarios_et_aleas/aleas_S12.json"}
            ],
            "Difficile": [
                {"planning": "scenarios_et_aleas/planning_S20.json", "aleas": "scenarios_et_aleas/aleas_S20.json"},
                {"planning": "scenarios_et_aleas/planning_S21.json", "aleas": "scenarios_et_aleas/aleas_S21.json"}
            ]
        }
        self.played_scenarios = {"Facile": [], "Moyen": [], "Difficile": []}
        self.is_choosing_scenario = False
        self.essais_restants = 5

        # Boutons pour le menu de choix
        btn_diff_w = int(220 * self.scale_x)
        btn_diff_h = int(60 * self.scale_y)
        self.btn_scen_facile = Button(0, 0, btn_diff_w, btn_diff_h, "Facile", (80, 200, 80))
        self.btn_scen_moyen = Button(0, 0, btn_diff_w, btn_diff_h, "Moyen", (220, 150, 50))
        self.btn_scen_difficile = Button(0, 0, btn_diff_w, btn_diff_h, "Difficile", (220, 80, 80))

        # --- BOUTONS GÉNÉRIQUES ---
        btn_start_w = int(500 * self.scale_x)
        btn_start_h = int(75 * self.scale_y)
        self.btn_start = Button(self.width//2 - btn_start_w//2, self.height - int(300 * self.scale_y), btn_start_w, btn_start_h, "Démarrer le tutoriel", (50, 200, 50))
        btn_end_w = int(400 * self.scale_x)
        btn_end_h = int(45 * self.scale_y)
        self.btn_end_famil = Button(self.width - btn_end_w - int(100*self.scale_x), int(10*self.scale_y), btn_end_w, btn_end_h, "Terminer la familiarisation", (200, 100, 50))

        # --- GESTION DES ONGLETS ---
        self.tabs_names = ["Planification", "Simulation", "Supervision"]
        self.active_tab_index = 0
        self.tab_rects = []

        self.tutorial = TutorialManager(self.screen, self.scale_x, self.scale_y)

        # --- INITIALISATION DES SOUS-APPLICATIONS ---
        self.planning_tab = PlanningTab(self.width, self.height, self.screen, self.tutorial)
        self.tab_monitoring = MonitoringTab(self.width, self.height, self.screen)
        self.simulation_tab = SimulationTab(self.width, self.height)
        
        self.show_supervision_intro = False
        self.btn_start_supervision = Button(0, 0, 400*self.scale_x, 50*self.scale_y, "Compris, démarrer la supervision !", (80, 180, 100))

        self.init_quit_dialog()
             
    def load_scenario(self, scenario):
        fichier_planning = scenario["planning"]
        fichier_aleas = scenario["aleas"]
        
        self.planning_tab.init_data() 
        self.tab_monitoring.load_scenario(self.planning_tab, fichier_planning, fichier_aleas)
        
        self.active_tab_index = 2
        self.tab_monitoring.current_day = 0.0
        self.tab_monitoring.is_playing = False
        self.tab_monitoring.active_aléa = None
        self.planning_tab.is_replanning = False
        self.supervision_locked = True
        
    def end_current_scenario(self):
        """Met en pause l'expérience et ouvre le menu de choix de scénario."""
        self.planning_tab.is_replanning = False
        self.tab_monitoring.active_aléa = None
        self.active_tab_index = 2
        
        if self.essais_restants <= 0:
            self.exp_state = "END"
            self.is_choosing_scenario = False
        else:
            self.is_choosing_scenario = True
            self.scenario_choice_error = ""
        
    def draw_tabs_header(self):
        header_h = int(65 * self.scale_y)
        pygame.draw.rect(self.screen, (40, 45, 65), (0, 0, self.width, header_h))
        
        tab_width = int(200 * self.scale_x)
        self.tab_rects = []
        for i, name in enumerate(self.tabs_names):
            x = int(20 * self.scale_x) + i * (tab_width + int(10 * self.scale_x))
            rect = pygame.Rect(x, int(10 * self.scale_y), tab_width, int(55 * self.scale_y))
            self.tab_rects.append(rect)
            
            # --- MODIFICATION : L'onglet Supervision est bloqué jusqu'à l'étape 12 (index 11) ---
            is_locked = False
            if self.exp_state == "FAMIL":
                if i == 2 and getattr(self.tutorial, 'step', 0) < 11:
                    is_locked = True
                    
            is_active = (i == self.active_tab_index)
            
            if is_active:
                color = (230, 235, 245) if i == 0 else (255, 255, 255)
                text_color = (20, 20, 40)
                pygame.draw.rect(self.screen, color, rect, border_top_left_radius=8, border_top_right_radius=8)
            else:
                color = (70, 80, 100)
                text_color = (180, 180, 180)
                if is_locked:
                    color = (40, 45, 55)
                    text_color = (80, 80, 80)
                pygame.draw.rect(self.screen, color, rect, border_radius=8)
            
            text_surf = self.tab_font.render(name, True, text_color)
            self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))

    def draw_supervision_intro(self, screen):
        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        screen.blit(overlay, (0, 0))
        
        panel_w, panel_h = 1050*self.scale, 730*self.scale
        panel_rect = pygame.Rect(
            (screen.get_width() - panel_w) // 2, 
            (screen.get_height() - panel_h) // 2, 
            panel_w, panel_h
        )
        pygame.draw.rect(screen, (245, 245, 250), panel_rect, border_radius=15)
        pygame.draw.rect(screen, (100, 120, 150), panel_rect, 3, border_radius=15)
        
        font_title = pygame.font.SysFont("trebuchetms", int(32*self.scale), bold=True)
        title_surf = font_title.render("Phase de Familiarisation Terminée !", True, (40, 40, 60))
        screen.blit(title_surf, (panel_rect.centerx - title_surf.get_width()//2, panel_rect.y + 25*self.scale))
        
        font_text = pygame.font.SysFont("trebuchetms", int(22*self.scale))
        lignes = [
            "Vous allez maintenant passer à la phase principale de l'expérience : la supervision.", 
            "",
            "ATTENTION", "Les plannings que vous allez superviser sont des scénarios entièrement pré-construits",
            "pour cet exercice. Ils sont indépendants de ceux que vous avez manipulés durant le tutoriel.",
            "", 
            "Votre rôle sera d'observer le déroulement du projet en temps réel. Si un imprévu survient, le temps",
            "s'arrêtera automatiquement et vous devrez replanifier pour rétablir un planning valide.",
            "Cinq types d'imprévus sont possibles :",
            "— Absence d'un opérateur",
            "— Indisponibilité d'une tâche",
            "— Retard (durée d'une tâche allongée)",
            "— Nouvelle deadline imposée",
            "— Opérateur imposé pour une tâche (symbolisé par un bonhomme)",
            "",
            "Lors de la replanification, trois règles sont à respecter :",
            "— Les tâches d'un même composant (même couleur) doivent être réalisées dans un ordre strict.",
            "— Un opérateur ne peut effectuer qu'une seule tâche à la fois.",
            "— Le planning doit toujours se terminer avant la fin du 10ème jour.",
            "",
            "Vous allez avoir 5 aléas à replanifier. Le premier sera facile,",
            "puis vous aurez le choix sur la difficulté pour les prochains (Facile, Moyen, Difficile)."
        ]
        
        y_text = panel_rect.y + 80*self.scale
        for ligne in lignes:
            color = (200, 50, 50) if "ATTENTION" in ligne else (60, 60, 80)
            ligne_surf = font_text.render(ligne, True, color)
            screen.blit(ligne_surf, (panel_rect.centerx - ligne_surf.get_width()//2, y_text))
            y_text += 26*self.scale
            
        self.btn_start_supervision.rect.centerx = panel_rect.centerx
        self.btn_start_supervision.rect.y = panel_rect.bottom - 70*self.scale
        self.btn_start_supervision.draw(screen, font_text)

    def draw_scenario_choice_overlay(self, screen):
        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200)) 
        screen.blit(overlay, (0, 0))
        
        panel_w, panel_h = 1000 * self.scale, 250 * self.scale
        panel_rect = pygame.Rect(
            (screen.get_width() - panel_w) // 2, 
            (screen.get_height() - panel_h) // 2, 
            panel_w, panel_h)
        pygame.draw.rect(screen, (245, 245, 250), panel_rect, border_radius=15)
        pygame.draw.rect(screen, (100, 120, 150), panel_rect, 3, border_radius=15)
        
        font_title = pygame.font.SysFont("trebuchetms", int(32 * self.scale), bold=True)
        err_font = pygame.font.SysFont("trebuchetms", int(20 * self.scale), bold=True)
        title_surf = font_title.render(f"Choisissez la difficulté du prochain aléa", True, (40, 40, 60))
        essai_restants_surf = err_font.render(f"(Résolvez encore {self.essais_restants} aléas pour que l'étude prenne fin)", True, (80, 80, 120))
        screen.blit(title_surf, (panel_rect.centerx - title_surf.get_width()//2, panel_rect.y + 30 * self.scale))
        screen.blit(essai_restants_surf, (panel_rect.centerx - essai_restants_surf.get_width()//2, panel_rect.y + 80 * self.scale))
        
        spacing = int(20 * self.scale_x)
        total_w = self.btn_scen_facile.rect.width * 3 + spacing * 2
        start_x = panel_rect.centerx - total_w // 2
        
        y_btns = panel_rect.centery + int(30 * self.scale_y)
        
        btns_data = [("Facile", self.btn_scen_facile), 
                    ("Moyen", self.btn_scen_moyen), 
                    ("Difficile", self.btn_scen_difficile)]
        font_btn = pygame.font.SysFont("trebuchetms", int(26 * self.scale), bold=True)
        
        for i, (diff, btn) in enumerate(btns_data):
            btn.rect.x = start_x + i * (btn.rect.width + spacing)
            btn.rect.centery = y_btns
            is_exhausted = len(self.played_scenarios[diff]) == len(self.scenarios[diff])
            if is_exhausted:
                btn.color = (140, 140, 145)
            btn.draw(screen, font_btn)

        if getattr(self, 'scenario_choice_error', ""):
            err_surf = err_font.render(self.scenario_choice_error, True, (220, 60, 60)) # Rouge
            screen.blit(err_surf, (panel_rect.centerx - err_surf.get_width()//2, panel_rect.bottom - int(45 * self.scale_y)))

    def draw_finish_confirm(self, screen):
        overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150)) 
        screen.blit(overlay, (0, 0))
        
        box_w, box_h = int(500 * self.scale_x), int(250 * self.scale_y)
        box_rect = pygame.Rect((screen.get_width()-box_w)//2, (screen.get_height()-box_h)//2, box_w, box_h)
        pygame.draw.rect(screen, (250, 250, 250), box_rect, border_radius=12)
        
        txt = self.font_medium.render("Souhaitez-vous terminer l'étude ?", True, (40, 40, 40))
        screen.blit(txt, (box_rect.centerx - txt.get_width()//2, box_rect.y + 50*self.scale_y))
        
        self.btn_confirm_fin_yes.rect.x = box_rect.x + 40*self.scale_x
        self.btn_confirm_fin_yes.rect.bottom = box_rect.bottom - 40*self.scale_y
        self.btn_confirm_fin_yes.draw(screen, self.tab_font)
        
        self.btn_confirm_fin_no.rect.right = box_rect.right - 40*self.scale_x
        self.btn_confirm_fin_no.rect.bottom = box_rect.bottom - 40*self.scale_y
        self.btn_confirm_fin_no.draw(screen, self.tab_font)

    def init_quit_dialog(self):
        """Initialise les variables et les boutons du menu de fermeture."""
        from ui_components import Button 
        self.show_quit_confirm = False
        
        margin_x = int(60 * self.scale_x)
        margin_y = int(10 * self.scale_y)
        size = int(50 * self.scale)
        self.close_rect = pygame.Rect(self.screen.get_width() - margin_x, margin_y, size, size) 
        
        btn_w = int(220 * self.scale_x)
        btn_h = int(60 * self.scale_y)
        self.btn_quit_yes = Button(0, 0, btn_w, btn_h, "Oui, quitter", (200, 60, 60))
        self.btn_quit_no = Button(0, 0, btn_w, btn_h, "Annuler", (100, 120, 150))

    def handle_quit_events(self, event):
        """Gère les clics de la croix et du pop-up. Retourne True si intercepté."""
        if event.type == pygame.QUIT:
            self.show_quit_confirm = True
            return True

        if getattr(self, 'show_quit_confirm', False):
            if self.btn_quit_yes.handle_event(event):
                self.running = False
            if self.btn_quit_no.handle_event(event):
                self.show_quit_confirm = False
            return True
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if getattr(self, 'close_rect', pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                self.show_quit_confirm = True
                return True

        return False

    def draw_quit_dialog(self, screen):
        """Dessine la croix en permanence, et le pop-up s'il est actif."""
        m = max(2, int(8 * self.scale_x)) 
        thickness = max(1, int(3 * self.scale_x)) 
        
        pygame.draw.rect(screen, (220, 60, 60), self.close_rect)
        pygame.draw.rect(screen, (150, 40, 40), self.close_rect, 2)
        pygame.draw.line(screen, (255, 255, 255), (self.close_rect.left + m, self.close_rect.top + m), (self.close_rect.right - m, self.close_rect.bottom - m), thickness)
        pygame.draw.line(screen, (255, 255, 255), (self.close_rect.left + m, self.close_rect.bottom - m), (self.close_rect.right - m, self.close_rect.top + m), thickness)

        if getattr(self, 'show_quit_confirm', False):
            overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180)) 
            screen.blit(overlay, (0, 0))

            box_w, box_h = int(600 * self.scale_x), int(280 * self.scale_y)
            box_x = (screen.get_width() - box_w) // 2
            box_y = (screen.get_height() - box_h) // 2
            popup_rect = pygame.Rect(box_x, box_y, box_w, box_h)
            
            pygame.draw.rect(screen, (245, 245, 250), popup_rect, border_radius=12)
            pygame.draw.rect(screen, (100, 100, 120), popup_rect, 3, border_radius=12)

            font_title = pygame.font.SysFont("trebuchetms", int(36 * self.scale), bold=True)
            txt_surf = font_title.render("Voulez-vous vraiment quitter ?", True, (40, 40, 40))
            screen.blit(txt_surf, (popup_rect.centerx - txt_surf.get_width() // 2, popup_rect.y + int(50 * self.scale_y)))

            margin_btn = int(50 * self.scale_x)
            self.btn_quit_yes.rect.x = popup_rect.left + margin_btn
            self.btn_quit_yes.rect.y = popup_rect.bottom - int(90 * self.scale_y)
            
            self.btn_quit_no.rect.x = popup_rect.right - margin_btn - self.btn_quit_no.rect.width
            self.btn_quit_no.rect.y = popup_rect.bottom - int(90 * self.scale_y)

            font_btn = pygame.font.SysFont("trebuchetms", int(26 * self.scale))
            self.btn_quit_yes.draw(screen, font_btn)
            self.btn_quit_no.draw(screen, font_btn)

    def update(self):
        self.tutorial.update()

        if self.exp_state == "FAMIL" and self.tutorial.mode == "CENTER":
            self.tutorial.baseline_set = False

        elif self.exp_state == "FAMIL" and self.tutorial.mode == "CORNER":
            tut_data = self.tutorial.current()

            if tut_data:
                if not getattr(self.tutorial, 'baseline_set', False):
                    self.tutorial.baseline_set = True
                    self.tuto_nb_tasks = len(self.planning_tab.tasks)
                    self.tuto_nb_unpinned = sum(1 for t in self.planning_tab.tasks if not getattr(t, 'is_pinned', True))
                    self.tuto_nb_assigned = sum(1 for t in self.planning_tab.tasks if t.assigned_to is not None)
                    self.tuto_has_undone = False
                    self.tuto_has_redone = False

                if not self.tutorial.is_validated:
                    if tut_data["id"] == "PLAN_TASK":
                        if sum(1 for t in self.planning_tab.tasks if t.assigned_to is not None) > getattr(self, 'tuto_nb_assigned', 0):
                            self.tutorial.trigger_validation()

                    elif tut_data["id"] == "UNPLAN_TASK":
                        if self.tuto_nb_assigned==0:
                            current_assigned = sum(1 for t in self.planning_tab.tasks if t.assigned_to is not None)
                            if current_assigned > 0:
                                self.tuto_nb_assigned = current_assigned
                        if sum(1 for t in self.planning_tab.tasks if t.assigned_to is not None) < getattr(self, 'tuto_nb_assigned', 0):
                            self.tutorial.trigger_validation()
                            
                    elif tut_data["id"] == "CUT_TASK":
                        if len(self.planning_tab.tasks) > getattr(self, 'tuto_nb_tasks', 0):
                            self.tutorial.trigger_validation()

                    elif tut_data["id"] == "HISTORY":
                        if self.tuto_has_undone and self.tuto_has_redone:
                            self.tutorial.trigger_validation()

                    elif tut_data["id"] == "GO_SUPERV":
                        if self.active_tab_index == 2:
                            self.tutorial.trigger_validation()
                    
                    elif tut_data["id"] == "PLAY_SUPERV":
                        if self.tab_monitoring.active_aléa is not None:
                            self.tutorial.trigger_validation(500)

                    elif tut_data["id"] == "CLICK_REPLAN":
                        if self.active_tab_index == 0 and self.planning_tab.is_replanning:
                            self.tutorial.trigger_validation()

                    elif tut_data["id"] == "FIX_CATAPHORESE":
                        target = next((t for t in self.planning_tab.tasks if t.id == 316), None)
                        if target and target.week_start >= 8:
                            self.tutorial.trigger_validation()
                    
                    elif tut_data["id"] == "VALIDATE_TUTO":
                        pass
                    
                    elif tut_data["id"] == "REPAIR_SOL":
                        if self.active_tab_index == 0 and self.planning_tab.is_replanning:
                            self.tutorial.trigger_validation()

        if self.exp_state == "FAMIL" and self.active_tab_index == 2:
            self.tab_monitoring.update()

        if self.exp_state == "EXP":
            if self.active_tab_index == 2:
                self.tab_monitoring.update()
                
    def handle_events(self):
        for event in pygame.event.get():
            if self.handle_quit_events(event):
                return

            if getattr(self, 'show_supervision_intro', False):
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.btn_start_supervision.handle_event(event):
                        self.show_supervision_intro = False
                        self.active_tab_index = 2
                return

            if getattr(self, 'is_choosing_scenario', False):
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    import random
                    for diff, btn in [("Facile", self.btn_scen_facile), ("Moyen", self.btn_scen_moyen), ("Difficile", self.btn_scen_difficile)]:
                        if btn.handle_event(event):
                            available = [s for s in self.scenarios[diff] if s not in self.played_scenarios[diff]]
                            if available:
                                chosen = random.choice(available)
                                self.played_scenarios[diff].append(chosen)
                                self.load_scenario(chosen)
                                self.essais_restants -= 1
                                self.is_choosing_scenario = False
                                self.scenario_choice_error = ""
                            else:
                                self.scenario_choice_error = f"Tous les aléas de niveau {diff} ont déjà été résolus."
                return
                
            # =================================================================
            # MACHINE À ÉTATS
            # =================================================================
            if self.exp_state == "INTRO":
                if self.btn_start.handle_event(event):
                    self.exp_state = "FAMIL"
                    self.active_tab_index = 0
                    
            elif self.exp_state == "FAMIL":
                tut_before = self.tutorial.current()
                if self.tutorial.handle_events(event):
                    tut_after = self.tutorial.current()                    
                    if tut_before and tut_before["id"] == "TUTO_END":
                        if tut_after is None or tut_after["id"] == "TUTO_END":
                            self.tutorial.is_active = False 
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, rect in enumerate(self.tab_rects):
                        if rect.collidepoint(event.pos):
                            if i == 2 and getattr(self.tutorial, 'step', 0) >= 11:
                                self.active_tab_index = 2
                                if not getattr(self, 'tuto_supervision_loaded', False):
                                    self.tab_monitoring.load_scenario(self.planning_tab, "planning_S8.json", "aleas_S8.json")
                                    self.tab_monitoring.current_day = 0.0
                                    self.tab_monitoring.is_playing = False
                                    self.tuto_supervision_loaded = True
                            elif i == 0:
                                self.active_tab_index = 0
                            elif i == 1:
                                self.active_tab_index = 1
                                self.simulation_tab.sync_data(self.planning_tab.tasks, self.planning_tab.operators, self.planning_tab.current_day)
                            return

                current_tut = self.tutorial.current()
                if current_tut and current_tut["id"] == "GO_PLAN":
                    self.is_planning_unlocked = True
                
                if current_tut and self.tutorial.mode == "CORNER":
                    if current_tut["id"] == "HISTORY" and event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
                            self.tuto_has_undone = True
                        elif event.key == pygame.K_y and (event.mod & pygame.KMOD_CTRL):
                            self.tuto_has_redone = True

                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.active_tab_index == 0:
                            if current_tut["id"] == "HISTORY":
                                if getattr(self.planning_tab, 'undo_rect', pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                    self.tuto_has_undone = True
                                elif getattr(self.planning_tab, 'redo_rect', pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                                    self.tuto_has_redone = True
                            if current_tut["id"] == "SOLVE" and self.planning_tab.solve_button.rect.collidepoint(event.pos):
                                self.tutorial.trigger_validation(3000) 
                            elif current_tut["id"] == "SAVE" and self.planning_tab.save_button.rect.collidepoint(event.pos):
                                self.tutorial.trigger_validation()
                            elif current_tut["id"] == "RESET" and self.planning_tab.reset_button.rect.collidepoint(event.pos):
                                self.tutorial.trigger_validation()
                            elif current_tut["id"] == "LOAD" and self.planning_tab.load_button.rect.collidepoint(event.pos):
                                self.tutorial.trigger_validation()

                if (not self.tutorial.is_active or (current_tut and current_tut["id"] == "TUTO_END")) and self.btn_end_famil.handle_event(event):
                    self.show_supervision_intro = True
                    self.exp_state = "EXP"
                    self.active_tab_index = 2
                    self.planning_tab.use_horizon_limit = True
                    
                    panel_w, panel_h = 800 * self.scale, 450 * self.scale
                    panel_rect = pygame.Rect((self.width - panel_w) // 2, (self.height - panel_h) // 2, panel_w, panel_h)
                    self.btn_start_supervision.rect.centerx = panel_rect.centerx
                    self.btn_start_supervision.rect.bottom = panel_rect.bottom - 40 * self.scale
                    
                    import random
                    if self.scenarios["Facile"]:
                        chosen = random.choice(self.scenarios["Facile"])
                        self.played_scenarios["Facile"].append(chosen)
                        self.load_scenario(chosen)
                    return
                
                if self.active_tab_index == 0:
                    action = self.planning_tab.handle_events(event)
                    if action == "VALIDATE_REPLAN":
                        current_tut = self.tutorial.current()
                        if current_tut and current_tut["id"] == "VALIDATE_TUTO":
                            self.tab_monitoring.load_scenario(self.planning_tab, "planning_S14.json", "aleas_S14.json")
                            import copy
                            self.planning_tab.tasks = copy.deepcopy(self.tab_monitoring.tasks)
                            self.planning_tab.operators = copy.deepcopy(self.tab_monitoring.operators)
                            self.planning_tab.current_day = 0.0
                            self.tab_monitoring.current_day = 0.0
                            self.tab_monitoring.is_playing = False
                            self.tab_monitoring.active_aléa = None
                            self.tutorial.trigger_validation()
                            self.active_tab_index = 2

                        if current_tut and current_tut["id"] == "VALIDATE_TUTO_BIS":
                            self.tutorial.trigger_validation()
                            self.active_aléa = None
                            self.is_playing = False
                            self.current_day = 0.0
                            self.hovered_task = None

                elif self.active_tab_index == 1:
                    action = self.simulation_tab.handle_events(event)
                    if action == "SEND_TO_PLANNING":
                        import copy
                        self.planning_tab.tasks = copy.deepcopy(self.simulation_tab.tasks)
                        for op in self.planning_tab.operators:
                            op.tasks = []
                        for t in self.planning_tab.tasks:
                            if t.assigned_to:
                                for op in self.planning_tab.operators:
                                    if op.name == t.assigned_to:
                                        op.tasks.append(t)  # On lui affecte la nouvelle tâche
                                        break

                        for op in self.planning_tab.operators:
                            op.tasks.sort(key=lambda x: getattr(x, 'week_start', 0))
                        self.active_tab_index = 0
                        return 
                    
                elif self.active_tab_index == 2:
                    action = self.tab_monitoring.handle_events(event)
                    if action == "GOTO_PLANNING":
                        self.active_tab_index = 0
                        self.planning_tab.is_replanning = True
                        self.planning_tab.current_day = self.tab_monitoring.current_day
                        self.planning_tab.load_replanning_window(self.tab_monitoring.tasks, self.tab_monitoring.operators, self.tab_monitoring.current_day)
                        if hasattr(self.tab_monitoring, 'timeline') and hasattr(self.planning_tab, 'timeline'):
                            self.planning_tab.timeline.scroll_offset = self.tab_monitoring.timeline.scroll_offset

            elif self.exp_state == "EXP":
                self.supervision_locked = True

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, rect in enumerate(self.tab_rects):
                        if rect.collidepoint(event.pos):
                            if getattr(self.planning_tab, 'is_replanning', False) and i != 0:
                                self.planning_tab.show_notification("Validez d'abord la replanification !", (220, 50, 50))
                                return
                            if getattr(self, 'supervision_locked', False) and self.active_tab_index == 2 and i != 2:
                                self.tab_monitoring.show_notification("Vous ne pouvez pas sortir de la supervision !", (200, 50, 50))
                                return
                            self.active_tab_index = i
                            if i == 0:
                                self.planning_tab.current_day = self.tab_monitoring.current_day
                            elif i == 1:
                                self.simulation_tab.sync_data(self.planning_tab.tasks, self.planning_tab.operators, self.planning_tab.current_day)
                            return
                            
                if self.active_tab_index == 0:
                    action = self.planning_tab.handle_events(event)
                    if action == "VALIDATE_REPLAN":
                        self.tab_monitoring.show_notification("Replanification validée !", (50, 200, 50))
                        self.end_current_scenario()

                elif self.active_tab_index == 1:
                    action = self.simulation_tab.handle_events(event)
                    if action == "SEND_TO_PLANNING":
                        import copy
                        self.planning_tab.tasks = copy.deepcopy(self.simulation_tab.tasks)
                        for op in self.planning_tab.operators:
                            op.tasks = []  # On vide l'ancien planning de l'opérateur
                        for t in self.planning_tab.tasks:
                            if t.assigned_to:
                                for op in self.planning_tab.operators:
                                    if op.name == t.assigned_to:
                                        op.tasks.append(t)  # On lui affecte la nouvelle tâche
                                        break
                        
                        for op in self.planning_tab.operators:
                            op.tasks.sort(key=lambda x: getattr(x, 'week_start', 0))
                        self.active_tab_index = 0
                        return 

                elif self.active_tab_index == 2:
                    action = self.tab_monitoring.handle_events(event)
                    if action == "GOTO_PLANNING":
                        self.active_tab_index = 0
                        self.planning_tab.is_replanning = True
                        self.planning_tab.current_day = self.tab_monitoring.current_day
                        self.planning_tab.load_replanning_window(self.tab_monitoring.tasks, self.tab_monitoring.operators, self.tab_monitoring.current_day)
                        if hasattr(self.tab_monitoring, 'timeline') and hasattr(self.planning_tab, 'timeline'):
                            self.planning_tab.timeline.scroll_offset = self.tab_monitoring.timeline.scroll_offset
                        diff_alea = self.tab_monitoring.active_aléa.get("diff", "Moyen")

    def draw_text_center(self, text, y_offset, font, color=(255,255,255)):
        surf = font.render(text, True, color)
        self.screen.blit(surf, (self.width//2 - surf.get_width()//2, y_offset))

    def draw(self):
        pygame.mouse.set_visible(True)
        
        # =================================================================
        # AFFICHAGE SELON L'ÉTAT EXPÉRIMENTAL
        # =================================================================
        if self.exp_state == "INTRO":
            self.screen.fill((40, 45, 60))
            start_y = self.height // 8            
            etapes = [
                "Bonjour et merci d'avoir accepté de participer à cette étude.",
                "",
                "Au cours de la session, vous allez être amenés à tester notre outil d'aide à la planification.",
                "Dans un premier temps, vous allez réaliser un tutoriel, puis une mise en situation réelle",
                "au cours de laquelle vous serez plongés dans la planification de la construction d'un satellite.",
                "À l'issue de cette mise en situation, un entretien vous sera proposé afin de recueillir vos impressions sur l'outil."
            ]
            y_offset = start_y + 100*self.scale
            for i, ligne in enumerate(etapes):
                if i == 0:
                    self.draw_text_center(ligne, y_offset, self.font_large, (255, 255, 255))
                    y_offset += 70*self.scale
                else:
                    self.draw_text_center(ligne, y_offset, self.font_medium, (205, 205, 205))
                    y_offset += 55*self.scale
                    
            self.btn_start.draw(self.screen, self.font_medium)
            
        elif self.exp_state == "FAMIL":
            if self.active_tab_index == 0: self.planning_tab.draw(self.screen)
            elif self.active_tab_index == 1: self.simulation_tab.draw(self.screen)
            elif self.active_tab_index == 2: self.tab_monitoring.draw(self.screen)
            self.draw_tabs_header()
            self.tutorial.draw(self.screen)

            if self.active_tab_index == 0 and getattr(self.planning_tab, 'is_replanning', False):
                self.planning_tab.draw_replan_overlay(self.screen)
            
            if self.tutorial.current() and self.tutorial.current()["id"] == "TUTO_END":
                self.btn_end_famil.draw(self.screen, self.font_medium)

        elif self.exp_state == "EXP":
            if self.active_tab_index == 0: self.planning_tab.draw(self.screen)
            elif self.active_tab_index == 1: self.simulation_tab.draw(self.screen)
            elif self.active_tab_index == 2: self.tab_monitoring.draw(self.screen)
            self.draw_tabs_header()
            
            if self.active_tab_index == 0 and getattr(self.planning_tab, 'is_replanning', False):
                self.planning_tab.draw_replan_overlay(self.screen)
            if getattr(self, 'is_choosing_scenario', False):
                self.draw_scenario_choice_overlay(self.screen)
                
        elif self.exp_state == "END":
            self.screen.fill((40, 45, 60))
            self.draw_text_center("La mise en situation est terminée.", self.height//3, self.font_large)
            self.draw_text_center("Merci pour votre participation !", self.height//3 + 60*self.scale, self.font_large)
            self.draw_text_center("Vous pouvez maintenant fermer l'application.", self.height//3 + 120*self.scale, self.font_large)
        
        if getattr(self, 'show_supervision_intro', False):
            self.draw_supervision_intro(self.screen)
        
        self.draw_quit_dialog(self.screen)

        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
        pygame.quit()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    MainApp().run()