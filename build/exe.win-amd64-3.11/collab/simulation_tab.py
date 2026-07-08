import pygame
import math
import json
import copy
import tkinter as tk
from tkinter import filedialog
from dataclasses import asdict
from typing import List, Tuple, Dict
from ui_components import Button, HorizontalScrollbar
from solver_cpo import PlanningSolver
from collab.planning_tab import ACTIVITY_COLORS, DEFAULT_COLOR, POOL_COLORS, PlanningTab

from simulation_radar import RadarWidget

class SimulationTab:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        
        self.scale_x = width / 1600.0
        self.scale_y = height / 900.0
        self.scale = min(self.scale_x, self.scale_y)

        self.planning_tab = PlanningTab(width,height,None)
        
        self.font = pygame.font.SysFont("trebuchetms", int(24 * self.scale))
        self.small_font = pygame.font.SysFont("trebuchetms", int(16 * self.scale))
        self.tiny_font = pygame.font.SysFont("trebuchetms", int(20 * self.scale))
        self.title_font = pygame.font.SysFont("trebuchetms", int(32 * self.scale))
        self.button_font = pygame.font.SysFont("trebuchetms", int(28 * self.scale))
        
        criteria = ['Makespan (jours)', 'Déséquilibre\n(heures)', 'Jobflow (heures)', 'Idle time\n(heures)']
        
        radar_cx = int(250 * self.scale_x)
        radar_cy = int(350 * self.scale_y)
        radar_radius = int(115 * self.scale)
        
        self.radar = RadarWidget(radar_cx, radar_cy, radar_radius, criteria)
        
        # (La suite de l'init avec set_criterion_range reste identique)
        self.radar.set_criterion_range(0, 10, 40)
        self.radar.set_criterion_range(1, 0, 100)
        self.radar.set_criterion_range(2, 0, 15)
        self.radar.set_criterion_range(3, 0, 200)

        self.show_info_popup = False
        
        self.info_rect = pygame.Rect(int(40 * self.scale_x), int(80 * self.scale_y), int(26 * self.scale), int(26 * self.scale))

        self.button_color = [(50,100,200),(100,200,50),(200,100,50)]

        btn_w = int(300 * self.scale_x)
        btn_h = int(40 * self.scale_y)
        
        gen_y = radar_cy + self.radar.radius + int(90 * self.scale_y)
        self.generate_button = Button(radar_cx - (btn_w * 0.6)//2, gen_y, btn_w * 0.6, btn_h, "Générer", self.button_color[1])
        self.reset_font = pygame.font.Font(None, int(22 * self.scale))
        self.reset_text = "Réinitialiser"
        self.reset_rect = pygame.Rect(self.generate_button.rect.left - int(100 * self.scale_x), gen_y + int(14 * self.scale_y), int(90 * self.scale_x), int(20 * self.scale_y))

        self.plan_w = width * 0.55
        self.plan_x = width * 0.99 - self.plan_w
        self.plan_y_compare = int(570 * self.scale_y)

        sav_w = int(180 * self.scale_x)
        env_w = int(320 * self.scale_x)
        
        bottom_y = self.height - int(60 * self.scale_y)
        espacement = int(30 * self.scale_x)
        largeur_totale_boutons = sav_w + espacement + env_w
        start_x = self.plan_x + (self.plan_w - largeur_totale_boutons) // 2
        
        self.compare_mode = 0
        self.compare_button = Button(self.plan_x + self.plan_w // 2 -sav_w // 2, height*0.65, sav_w, btn_h, "Comparer", self.button_color[0])
        self.back_to_generate_button = Button(width * 0.08, height*0.3, sav_w, btn_h * 2, "Génération", self.button_color[0]) #nom à changer mais jsp comment faire des boutons avec des retours à la ligne
        
        self.save_button = Button(start_x, bottom_y, sav_w, btn_h, "Sauvegarder", self.button_color[0])
        self.send_button = Button(self.save_button.rect.right + espacement, bottom_y, env_w, btn_h, "Envoyer vers le Planning", self.button_color[0])

        # Caractéristiques des planning en comparaison
        self.color_slot1 = (220, 100, 120)
        self.color_slot2 = (0, 190, 170)
        # SLOT1 : le planning qu'on affiche quand il y a qu'un planning de visible ou alors le premier lorsqu'il y en a plusieurs (le bleu)
        self.compare_slot1 = pygame.Rect(0, 0, int(200 * self.scale_x), int(190 * self.scale_y))
        self.compare_slot1.center = (self.plan_x - int(120 * self.scale_x), int(200 * self.scale_y))
        # SLOT2 : le deuxième planning qu'on affiche quand il y en deux d'affichés (le rose)
        self.compare_slot2 = pygame.Rect(0, 0, int(200 * self.scale_x), int(190 * self.scale_y))
        self.compare_slot2.center = (self.plan_x - int(120 * self.scale_x), int(400 * self.scale_y))
        self.comparison_history_index = -1

        self.operators = []
        self.current_day = 0.0
        self.status_message = ""

        self.tasks_slot1 = []       # liste des tâches de correspondant au planning bleu
        self.task_slot1_btn = {}    # dictionnaire((id, part_index): rect) 

        self.tasks_slot2 = []       # liste des tâches de correspondant au planning rose
        self.task_slot2_btn = {}

        self.tasks_blended = []     # liste des tâches de correspondant au planning en construction en bas
        self.task_blended_btn = {}

        self.tasks = []             # utilisé uniquement lors des tâches vers le planning
        
        self.has_solution = False
        self.preview_scroll_x = 0
        self.scrollbar = HorizontalScrollbar(0, 0, 100, 12, 0, 0)
        
        self.history_solutions = [] 
        self.active_history_index = -1
        self.history_scroll_x = 0
        self.history_rect = pygame.Rect(width * 0.01, height * 0.68, width * 0.28, height * 0.28)
        self.history_scrollbar = HorizontalScrollbar(self.history_rect.x, self.history_rect.bottom + int(5 * self.scale_y), self.history_rect.w, int(12 * self.scale_y), 0, 0)

        self.last_metrics = None
        self.notifications = []

        # --- Hover / Tooltip ---
        self._hover_task = None         # La tâche actuellement survolée
        self._hover_task_rect = None    # Son rect pygame (pour positionner le tooltip)
        self._hover_start_time = None   # Timestamp (ms) du début du survol
        self._hover_pos = None          # Position souris au moment du survol
        self.HOVER_DELAY_MS = 600       # Délai avant apparition (ms)

        # --- Drag & Drop mini radar ---
        self._drag_radar_index = None   # Index dans history_solutions du radar en cours de drag
        self._drag_pos = None           # Position courante de la souris pendant le drag
        self._drag_target_slot = None   # 1 ou 2 : slot survolé pendant le drag (pour highlight)
        self._drag_origin = None        # Position souris au moment du MOUSEDOWN (pour détecter clic vs drag)
        self._drag_started = False      # True seulement si la souris a bougé assez (drag réel)

        # --- Historique : hover / renommage / suppression ---
        self._hist_hovered_index  = None   # index de la carte survolée
        self._hist_renaming_index = None   # index en cours de renommage
        self._hist_rename_text    = ""     # texte en cours de saisie
        self._hist_delete_confirm = None   # index en attente de confirmation de suppression

        # --- Surbrillance tâche équivalente ---
        self._highlighted_task_key = None   # (id, part_index) de la tâche mise en surbrillance
        self._highlight_start_time = None   # timestamp du début (pour animation de fondu)

        # --- Path selection : maintien clic gauche pour ajouter des tâches en survol ---
        self._drag_adding = False           # True quand le clic gauche est maintenu sur le planning
        self._drag_added_keys = set()       # Clés (id, part_index) déjà ajoutées durant ce geste

        # --- Autocomplétion du solveur avec les tâches sélectionnées ---
        self.view_sol = False
        self.view_sol_button = Button(self.compare_slot1.x + int(30* self.scale), int(650 * self.scale_y), int(140 * self.scale), int(70 * self.scale), "", self.button_color[2])
        self.solver_completion = None
        self.task_completion_btn = {}
        self.unview_sol_button = Button(self.compare_slot1.x , int(750 * self.scale_y), int(105 * self.scale), int(50 * self.scale), "", self.button_color[2])
        self.save_solution = Button(self.compare_slot1.x + int(115* self.scale), int(750 * self.scale_y), int(90 * self.scale), int(30 * self.scale), "Enregistrer", self.button_color[2])
        
        self.reset_planning_btn = Button(self.view_sol_button.rect.x - int(25*self.scale), self.view_sol_button.rect.bottom + int(10*self.scale), 
                                         self.view_sol_button.rect.w + int(50*self.scale), self.view_sol_button.rect.h//2, "Réinitialiser le planning", self.button_color[2])
        
        # --- Filtrage par activités ---
        self.activities = []
        self.activ_activity = None
        

    def get_state_signature(self, tasks_list):
        return {(t.id, getattr(t, 'part_index', 0)): (t.assigned_to, t.week_start, t.duration, t.part_index) for t in tasks_list}

    def sync_data(self, raw_tasks, raw_operators, current_day=0.0):
        new_signature = self.get_state_signature(raw_tasks)
        if getattr(self, 'last_sync_signature', None) == new_signature:
            self.current_day = current_day
            return
            
        self.last_sync_signature = new_signature
        self.raw_tasks = copy.deepcopy(raw_tasks)
        self.raw_operators = copy.deepcopy(raw_operators)
        
        self.tasks = copy.deepcopy(self.raw_tasks)
        self.tasks_slot1 = copy.deepcopy(self.raw_tasks)
        self.operators = copy.deepcopy(self.raw_operators)
        self.current_day = current_day 
        
        self.status_message = "Simulation prête."
        self.has_solution = False
        self.preview_scroll_x = 0
        self.last_metrics = None
        self.scrollbar.scroll_x = 0
        
        self.history_solutions = []
        self.active_history_index = -1

        self.compare_mode = 0

        self.metrics_hypothetical_sol = {'makespan': 0, 'balance': 0, 'wip': 0, 'idle_time': 0}

        id_seen = []
        space = 180
        for t in self.tasks:
            if t.activity_id not in id_seen:
                # tuple pour chaque activités : son id, son nom, son boutton et si elle est active ou non (affichée ou non à l'écran)
                color = ACTIVITY_COLORS.get(t.activity_id)
                dark_color = tuple(int(c * 0.9) for c in color)
                self.activities.append((t.activity_id,
                                        t.activity_name, 
                                        Button(self.plan_x + int((space)* self.scale), self.height * 0.5, 
                                                int((len(t.activity_name)* 9 + 20)* self.scale), int(35 * self.scale), 
                                                t.activity_name, dark_color, 2, (120, 120, 120)),
                                        True))
                dark_dark_color = tuple(int(c * 0.7) for c in color)
                self.activities[-1][2].color_pressed = dark_dark_color
                id_seen.append(t.activity_id)
                space += len(t.activity_name)* 8 + 80
                

    def export_solution_to_json(self):
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) 
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Fichiers JSON", "*.json")])
        if file_path:
            try:
                if self.compare_mode < 1 :
                    data = {"tasks": [asdict(t) for t in self.tasks_slot1], "assignments": {op.name: [t.id for t in op.tasks] for op in self.operators}}
                else : 
                    data = {"tasks": [asdict(t) for t in self.tasks_blended], "assignments": {op.name: [t.id for t in op.tasks] for op in self.operators}}
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                self.show_notification("Sauvegardé avec succès !", color=(50, 200, 50))
            except Exception as e:
                self.show_notification(f"Erreur de sauvegarde.", color=(200, 50, 50))

    def _draw_single_mini_radar(self, surface, cx, cy, radius, metrics, title_text, is_active=False):
        metrics_keys = ["makespan", "balance", "wip", "idle_time"]
        normalized_vals = []
        
        for i, key in enumerate(metrics_keys):
            if i < len(self.radar.min_values):
                val = metrics.get(key, 0)
                min_v = self.radar.min_values[i]
                max_v = self.radar.max_values[i]
                norm = (val - min_v) / (max_v - min_v) if max_v > min_v else 0
                normalized_vals.append(min(max(norm, 0.0), 1.0))
            else:
                normalized_vals.append(0)
        
        grid_color = (60, 60, 80)
        axis_color = (100, 100, 120)
        
        if is_active:
            poly_color = (100, 150, 255, 140)
            poly_border = (150, 200, 255)
            title_color = (255, 255, 255)
        else:
            poly_color = (50, 200, 100, 100) 
            poly_border = (50, 200, 100)
            title_color = (150, 150, 170)
        
        title_surf = self.small_font.render(title_text, True, title_color)
        
        # --- MODIFIÉ : Marge du titre au-dessus du radar mise à l'échelle ---
        marge_titre = int(60 * getattr(self, 'scale_y', 1.0))
        surface.blit(title_surf, (cx - title_surf.get_width()//2, cy - radius - marge_titre))

        for i in range(1, 4):
            r = int(radius * i / 3)
            pygame.draw.circle(surface, grid_color, (cx, cy), r, 1)
            
        points = []
        for i in range(len(metrics_keys)):
            angle = -math.pi / 2 + (2 * math.pi * i / len(metrics_keys))
            end_x = cx + radius * math.cos(angle)
            end_y = cy + radius * math.sin(angle)
            pygame.draw.line(surface, axis_color, (cx, cy), (end_x, end_y), 1)
            
            dist = radius * normalized_vals[i]
            px = cx + dist * math.cos(angle)
            py = cy + dist * math.sin(angle)
            points.append((px, py))
            
        poly_surf = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        pygame.draw.polygon(poly_surf, poly_color, points)
        surface.blit(poly_surf, (0, 0))
        pygame.draw.polygon(surface, poly_border, points, 2)
        
        for i, key in enumerate(metrics_keys):
            val = metrics.get(key, 0)
            angle = -math.pi / 2 + (2 * math.pi * i / len(metrics_keys))
            
            dist_texte = radius + int(10 * getattr(self, 'scale', 1.0))
            label_x = cx + dist_texte * math.cos(angle)
            label_y = cy + dist_texte * math.sin(angle)
            
            val_surf = self.tiny_font.render(str(int(val)), True, poly_border)
            val_rect = val_surf.get_rect()
            
            if math.cos(angle) > 0.1: val_rect.left = int(label_x)
            elif math.cos(angle) < -0.1: val_rect.right = int(label_x)
            else: val_rect.centerx = int(label_x)
            
            if math.sin(angle) > 0.1: val_rect.top = int(label_y)
            elif math.sin(angle) < -0.1: val_rect.bottom = int(label_y)
            else: val_rect.centery = int(label_y)
            
            surface.blit(val_surf, val_rect)

    def draw_history_panel(self, surface):
        pygame.draw.rect(surface, (40, 40, 50), self.history_rect, border_radius=8)
        pygame.draw.rect(surface, (80, 80, 100), self.history_rect, 2, border_radius=8)
        
        title = self.tiny_font.render("Historique des Plannings Générés", True, (200, 200, 220))
        surface.blit(title, (self.history_rect.x + 15, self.history_rect.y + 10))

        if not self.history_solutions:
            msg = self.small_font.render("Aucune solution générée pour le moment.", True, (100, 100, 120))
            surface.blit(msg, (self.history_rect.centerx - msg.get_width()//2, self.history_rect.centery))
            return

        item_w = int(200 * self.scale_x)
        item_h = int(180 * self.scale_y)
        total_content_width = len(self.history_solutions) * item_w
        
        self.history_scrollbar.update_content_width(total_content_width)
        self.history_scrollbar.visible_width = self.history_rect.width
        self.history_scroll_x = int(self.history_scrollbar.scroll_x)

        offset_y = int(35 * self.scale_y)
        clip_rect = pygame.Rect(self.history_rect.x, self.history_rect.y + offset_y, self.history_rect.width, self.history_rect.height - offset_y)
        surface.set_clip(clip_rect)

        btn_w  = int(28 * self.scale)
        btn_h  = int(22 * self.scale)

        self._hist_rename_btn_rects  = {}
        self._hist_delete_btn_rects  = {}
        self._hist_cancel_rename_rects = {}

        for i, sol in enumerate(self.history_solutions):
            x = self.history_rect.x + i * item_w - self.history_scroll_x
            if x + item_w > self.history_rect.x and x < self.history_rect.right:
                cy = self.history_rect.y + int(40 * self.scale_y) + (item_h // 2) + int(25 * self.scale_y)
                cx = x + item_w // 2
                
                is_active   = (i == self.active_history_index or i == self.comparison_history_index)
                is_hovered  = (i == self._hist_hovered_index)
                is_renaming = (i == self._hist_renaming_index)
                is_deleting = (i == self._hist_delete_confirm)

                card_y = self.history_rect.y + int(55 * self.scale_y) + int(15 * self.scale)
                bg_rect = pygame.Rect(x + 5, card_y, item_w - 10, item_h - 5)

                if is_active or is_hovered:
                    pygame.draw.rect(surface, (60, 70, 90), bg_rect, border_radius=8)
                    border_col = (100, 150, 255) if is_active else (90, 90, 120)
                    pygame.draw.rect(surface, border_col, bg_rect, 2, border_radius=8)

                radar_radius = int(50 * self.scale)
                self._draw_single_mini_radar(surface, cx, cy, radar_radius, sol["metrics"], sol["name"], is_active)

                # --- Boutons Edit et X visibles uniquement au hover ---
                if is_hovered and not is_renaming and not is_deleting:
                    # Bouton renommer Edit
                    rename_rect = pygame.Rect(x + item_w - btn_w * 2 - int(12*self.scale) - 3, card_y + int(4*self.scale), btn_w + 3, btn_h)
                    pygame.draw.rect(surface, (60, 100, 160), rename_rect, border_radius=4)
                    r_lbl = self.small_font.render("Edit", True, (200, 220, 255))
                    surface.blit(r_lbl, (rename_rect.centerx - r_lbl.get_width()//2, rename_rect.centery - r_lbl.get_height()//2))
                    self._hist_rename_btn_rects[i]  = rename_rect

                    # Bouton supprimer X
                    delete_rect = pygame.Rect(x + item_w - btn_w - int(8*self.scale), card_y + int(4*self.scale), btn_w, btn_h)
                    pygame.draw.rect(surface, (160, 60, 60), delete_rect, border_radius=4)
                    d_lbl = self.small_font.render("X", True, (255, 180, 180))
                    surface.blit(d_lbl, (delete_rect.centerx - d_lbl.get_width()//2, delete_rect.centery - d_lbl.get_height()//2))
                    self._hist_delete_btn_rects[i]  = delete_rect

                # --- Champ de renommage inline ---
                if is_renaming:
                    cancel_lbl = self.small_font.render("Annuler", True, (255, 180, 180))
                    field_rect = pygame.Rect(x + int(8*self.scale), card_y + int(4*self.scale), item_w - int(12*self.scale) - cancel_lbl.get_width() - int(8*self.scale), btn_h)
                    # Champ de saisie
                    pygame.draw.rect(surface, (20, 20, 35), field_rect, border_radius=4)
                    pygame.draw.rect(surface, (100, 160, 255), field_rect, 2, border_radius=4)
                    txt = self.small_font.render(self._hist_rename_text + "_", True, (220, 220, 255))
                    surface.blit(txt, (field_rect.x + int(6*self.scale), field_rect.centery - txt.get_height()//2))
                    hint = self.small_font.render("Entrée : valider", True, (120, 120, 140))
                    surface.blit(hint, (field_rect.x, field_rect.bottom + int(3*self.scale)))
                    # Croix annuler
                    cancel_rect = pygame.Rect(field_rect.right + int(4*self.scale), field_rect.y, cancel_lbl.get_width(), btn_h)
                    pygame.draw.rect(surface, (140, 50, 50), cancel_rect, border_radius=4)
                    surface.blit(cancel_lbl, (cancel_rect.centerx - cancel_lbl.get_width()//2, cancel_rect.centery - cancel_lbl.get_height()//2))
                    self._hist_cancel_rename_rects[i] = cancel_rect

                # --- Confirmation suppression ---
                if is_deleting:
                    conf_rect = pygame.Rect(x + int(10*self.scale), card_y + int(6*self.scale), item_w - int(20*self.scale), btn_h * 2 + int(10*self.scale))
                    pygame.draw.rect(surface, (80, 20, 20), conf_rect, border_radius=4)
                    pygame.draw.rect(surface, (220, 80, 80), conf_rect, 2, border_radius=4)
                    lbl = self.small_font.render("Supprimer ?", True, (255, 180, 180))
                    surface.blit(lbl, (conf_rect.centerx - lbl.get_width()//2, conf_rect.y + int(3*self.scale)))
                    yes_rect = pygame.Rect(conf_rect.x + int(6*self.scale), conf_rect.y + btn_h + int(4*self.scale), int((conf_rect.w - int(16*self.scale))//2), btn_h)
                    no_rect  = pygame.Rect(conf_rect.right - int(6*self.scale) - yes_rect.w, yes_rect.y, yes_rect.w, btn_h)
                    pygame.draw.rect(surface, (180, 50, 50), yes_rect, border_radius=4)
                    pygame.draw.rect(surface, (50, 100, 50), no_rect,  border_radius=4)
                    y_lbl = self.small_font.render("Oui", True, (255,255,255))
                    n_lbl = self.small_font.render("Non", True, (255,255,255))
                    surface.blit(y_lbl, (yes_rect.centerx - y_lbl.get_width()//2, yes_rect.centery - y_lbl.get_height()//2))
                    surface.blit(n_lbl, (no_rect.centerx  - n_lbl.get_width()//2,  no_rect.centery  - n_lbl.get_height()//2))
                    self._hist_confirm_yes_rect = yes_rect
                    self._hist_confirm_no_rect = no_rect

        surface.set_clip(None)
        self.history_scrollbar.draw(surface)

    def draw_info_popup(self, surface, title, lines_data):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        # --- NOUVEAU : Calcul dynamique de la hauteur avec Word Wrap ---
        box_w = int(900 * self.scale_x)
        padding = int(40 * self.scale_x)
        text_w = box_w - (padding * 2)
        
        wrapped_content = []
        total_h = int(80 * self.scale_y)
        
        for name, desc in lines_data:
            name_surf = self.font.render(name, True, (100, 200, 255))
            words = desc.split(' ')
            lines = []
            current_line = []
            
            # On décale la première ligne après le titre
            offset_x = name_surf.get_width() + 10
            
            for word in words:
                test_str = ' '.join(current_line + [word])
                test_surf = self.tiny_font.render(test_str, True, (200, 200, 220))
                
                # Si ça dépasse, on valide la ligne actuelle et on passe en dessous
                if offset_x + test_surf.get_width() > text_w and current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    offset_x = 0 # Les lignes suivantes commencent tout à gauche
                else:
                    current_line.append(word)
            if current_line:
                lines.append(' '.join(current_line))
                
            block_h = max(name_surf.get_height(), len(lines) * 25) + 15
            total_h += block_h
            wrapped_content.append((name_surf, lines, block_h))

        total_h += 50 # Marge bas
        
        box_x = (self.width - box_w) // 2
        box_y = (self.height - total_h) // 2
        popup_rect = pygame.Rect(box_x, box_y, box_w, total_h)
        
        pygame.draw.rect(surface, (40, 40, 50), popup_rect, border_radius=12)
        pygame.draw.rect(surface, (100, 150, 200), popup_rect, 3, border_radius=12)

        title = self.title_font.render(title, True, (255, 255, 255))
        surface.blit(title, (popup_rect.centerx - title.get_width()//2, popup_rect.y + 20))

        y = popup_rect.y + 80
        for name_surf, lines, block_h in wrapped_content:
            surface.blit(name_surf, (popup_rect.x + padding, y))
            
            offset_x = name_surf.get_width() + 10
            curr_y = y + 2
            for i, line in enumerate(lines):
                l_surf = self.tiny_font.render(line, True, (200, 200, 220))
                # La première ligne est décalée, les autres reviennent à la marge
                x_pos = popup_rect.x + padding + (offset_x if i == 0 else 0)
                surface.blit(l_surf, (x_pos, curr_y))
                curr_y += 25
                
            y += block_h

        close_msg = self.tiny_font.render("Cliquez n'importe où pour fermer", True, (150, 150, 150))
        surface.blit(close_msg, (popup_rect.centerx - close_msg.get_width()//2, popup_rect.bottom - 30))

    def show_notification(self, text: str, color: Tuple[int, int, int] = (240, 50, 50)):
        self.notifications.append({"text": text, "time": pygame.time.get_ticks(), "color": color})
        if len(self.notifications) > 3:
            self.notifications = self.notifications[-3:]

    def draw_notifications(self, surface: pygame.Surface):
        current_time = pygame.time.get_ticks()
        y_offset = self.height - 40 
        notif_font = pygame.font.SysFont("trebuchetms", 24)
        self.notifications = [n for n in self.notifications if current_time - n["time"] < 5000]
        for notif in reversed(self.notifications): 
            age = current_time - notif["time"]
            alpha = 255
            if age > 4000: 
                alpha = int(255 * (1.0 - (age - 4000) / 1000.0))
                alpha = max(0, min(255, alpha))
            text_surf = notif_font.render(notif["text"], True, notif["color"])
            text_surf.set_alpha(alpha)
            bg_rect = pygame.Rect(15, y_offset - text_surf.get_height() - 10, text_surf.get_width() + 20, text_surf.get_height() + 15)
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg_surf.fill((255, 255, 255, alpha))
            pygame.draw.rect(bg_surf, (*notif["color"], alpha), bg_surf.get_rect(), 2, border_radius=5)
            surface.blit(bg_surf, bg_rect.topleft)
            surface.blit(text_surf, (25, y_offset - text_surf.get_height() - 2))
            y_offset -= (bg_rect.height + 10)

    def draw_text_centered(self, surface, text, rect, font, color=(255, 255, 255)):
        x, y, w, h = rect
        x = 1.01 * x
        w = 0.97 * w
        # Découpage en lignes
        lines, line = [], ""
        for word in text.split():
            if font.size(line + word)[0] > w and line:
                lines.append(line.rstrip())
                line = ""
            line += word + " "
        if line: lines.append(line.rstrip())
        # Dessin centré
        lh = font.get_height() + 2
        cy = y + (h - len(lines) * lh) // 2
        for l in lines:
            surface.blit(font.render(l, True, color), (x + (w - font.size(l)[0]) // 2, cy))
            cy += lh

    def add_solution(self, solution, view_sol=False):
        self.history_solutions.append(solution)

        if view_sol :
            self.active_history_index = len(self.history_solutions) - 1
            self.tasks_slot1 = self.history_solutions[self.active_history_index]["tasks"]
            self.operators = self.history_solutions[self.active_history_index]["operators"]
        
        self.preview_scroll_x = 0
        
        item_w = int(200 * self.scale_x)
        total_w = len(self.history_solutions) * item_w
        self.history_scrollbar.update_content_width(total_w)
        self.history_scrollbar.scroll_x = max(0, total_w - self.history_rect.width)

    def fill_tasks(self, tasks_not_fill):
        """Rempli une liste de tâches si elle ne contient pas toutes les tâches"""
        tasks_to_fill = []
        for task in self.tasks:
            if task.id not in [t.id for t in tasks_not_fill]:
                task.is_pinned = False
                tasks_to_fill.append(copy.deepcopy(task))
            else:
                for t in tasks_not_fill:
                    if t.id == task.id:
                        t.is_pinned = True
                        tasks_to_fill.append(copy.deepcopy(t))

                sum_duration = sum(t.duration for t in tasks_not_fill if t.id == task.id)
                if task.duration > sum_duration:
                    insertion_index = max(t.part_index for t in tasks_not_fill if t.id == task.id) + 1
                    TaskClass = type(task)
                    new_task = TaskClass(
                        id=task.id, name=task.name, activity_name=task.activity_name,
                        duration=task.duration - sum_duration, activity_id=task.activity_id,
                        pool_name=task.pool_name, week_start=0,
                        start_half=0, assigned_to=None,
                        part_index=insertion_index, description=task.description,
                        is_pinned=False)
                    tasks_to_fill.append(new_task)

        return tasks_to_fill

    def _calcul_height_planning(self, header_h, row_height, group_spacing, mode):
        total_h = header_h
        for i in range(len(self.operators)):
            total_h += row_height
            total_h += int(4 * self.scale) if mode in ["COMPARE_SLOT1", "COMPARE_SLOT2"] and i < len(self.operators) -1 else 1
            # Si l'opérateur actuel n'a pas le même métier que le suivant, on ajoute une marge
            if i < len(self.operators) - 1 and self.operators[i].pool_name != self.operators[i+1].pool_name:
                total_h += group_spacing

        return total_h 

    def scrollbar_management(self, plan_x, plan_w, plan_y, day_width, label_width):
        max_day = max([t.week_start + (t.duration/8.0) for t in self.tasks_slot1 if t.assigned_to], default=0) if self.tasks_slot1 else 20
        max_day2 = max([t.week_start + (t.duration/8.0) for t in self.tasks_slot2 if t.assigned_to], default=0) if self.tasks_slot2 else 20
        max_day = max(int(math.ceil(max_day2)) + 2, int(math.ceil(max_day)) + 2) # On force minimum 20 jours, et on ajoute 2 jours de marge visuelle à droite
        
        # Positionnement de la scrollbar juste au-dessus du planning
        sb_x = plan_x + label_width # Elle commence après la colonne des noms
        sb_w = plan_w - label_width
        self.scrollbar.rect.x = sb_x
        self.scrollbar.rect.y = plan_y - int(25 * self.scale_y)  
        self.scrollbar.rect.width = sb_w
        self.scrollbar.rect.height = int(15 * self.scale_y)
        self.scrollbar.visible_width = sb_w
        
        # On dit à la scrollbar combien de pixels font le contenu total (Nb jours * largeur d'un jour)
        total_content_width = max_day * day_width
        self.scrollbar.update_content_width(total_content_width)
        
        # Sécurité pour éviter de scroller dans le vide à droite
        max_scroll = max(0, total_content_width - sb_w)
        self.preview_scroll_x = max(0, min(self.preview_scroll_x, max_scroll))
        self.scrollbar.scroll_x = self.preview_scroll_x 

        return max_day

    def _draw_day_grid(self, surface, clip_rect, max_day, plan_x, label_width, day_width, plan_w, plan_y, current_y):
        surface.set_clip(clip_rect)
        
        # On dessine une ligne verticale pour chaque jour
        for d in range(max_day):
            vx = plan_x + label_width + d * day_width - self.preview_scroll_x
            if vx > plan_x + label_width - day_width and vx < plan_x + plan_w:
                _line_surf = pygame.Surface((1, current_y - plan_y), pygame.SRCALPHA)
                _line_surf.fill((180, 180, 220, 40))
                surface.blit(_line_surf, (vx, plan_y))
                surface.blit(self.tiny_font.render(f"J{d+1}", True, (60, 60, 80)), (vx + 10*self.scale, plan_y + 2)) # Le texte "J1", "J2", ...

        # Le curseur rouge qui indique où on en est (Seulement pertinent en phase de supervision)
        exact_current_day = getattr(self, 'current_day', 0.0)
        if exact_current_day > 0:
            content_start_x = plan_x + label_width
            cursor_x = content_start_x + (exact_current_day * day_width) - self.preview_scroll_x
            
            if content_start_x <= cursor_x <= plan_x + plan_w:
                # La ligne rouge verticale
                pygame.draw.line(surface, (255, 0, 0), (cursor_x, plan_y), (cursor_x, current_y), 2)
                
                # Le voile gris transparent sur toute la zone "Passée" (à gauche du curseur)
                past_width = cursor_x - content_start_x
                if past_width > 0:
                    overlay = pygame.Surface((int(past_width), current_y - plan_y), pygame.SRCALPHA)
                    overlay.fill((50, 50, 50, 60))
                    surface.blit(overlay, (content_start_x, plan_y))
                
                # Le petit triangle rouge tout en haut du curseur
                triangle_y = plan_y
                points = [(cursor_x - 8, triangle_y - 8), (cursor_x + 8, triangle_y - 8), (cursor_x, triangle_y + 4)]
                pygame.draw.polygon(surface, (255, 0, 0), points)

        surface.set_clip(None)

    def draw_outlined_text(self, surface, pos, font, text, color=(0, 0, 0), outline_color=(255,255,255), outline_width=2):
        x, y = pos

        # Surface du contour
        outline = font.render(text, True, outline_color)

        # Dessine autour
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    surface.blit(outline, (x + dx, y + dy))

        # Texte principal
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, (x, y))

    def text_cesura(self, surface, task, task_h, task_w, task_x, task_y, yellow = False):
        display_name = task.name
        if getattr(task, 'part_index', 0) > 0: 
            display_name += f" ({task.part_index})" # Ajoute (1), (2) si la tâche est découpée
            
        max_lines = 2 if task_h > int(40 * self.scale_y) else 1
        strip_width = int(8 * self.scale_x)
        words = display_name.split()
        lines, current_line, word_idx = [], "", 0 
        
        while word_idx < len(words) and len(lines) < max_lines:
            marge_1 = int(35 * self.scale_x)
            marge_2 = int(6 * self.scale_x)
            current_max_w = (task_w - strip_width - marge_1) if (len(lines) == 1 and max_lines == 2) else (task_w - strip_width - marge_2)
            word = words[word_idx]
            test_line = current_line + word + " "
            
            if self.small_font.size(test_line)[0] <= current_max_w:
                current_line = test_line
                word_idx += 1
            else:
                part = ""
                for char in word:
                    if self.small_font.size(current_line + part + char + "-")[0] <= current_max_w: part += char
                    else: break
                        
                if len(part) > 0:
                    lines.append((current_line + part + "-").strip())
                    words[word_idx] = word[len(part):] 
                    current_line = ""
                else:
                    if current_line: lines.append(current_line.strip()); current_line = ""
                    else: lines.append(word[:1] + "-"); words[word_idx] = word[1:]
                        
        if current_line and len(lines) < max_lines:
            lines.append(current_line.strip())
            
        if len(lines) > 0:
            marge_1 = int(35 * self.scale_x)
            marge_2 = int(6 * self.scale_x)
            last_max_w = (task_w - strip_width - marge_1) if (len(lines) - 1 == 1 and max_lines == 2) else (task_w - strip_width - marge_2)
            if word_idx < len(words) or self.small_font.size(lines[-1])[0] > last_max_w:
                line_to_cut = lines[-1]
                if line_to_cut.endswith("-"): line_to_cut = line_to_cut[:-1]
                while len(line_to_cut) > 0 and self.small_font.size(line_to_cut + "..")[0] > last_max_w:
                    line_to_cut = line_to_cut[:-1]
                lines[-1] = line_to_cut.strip() + ".."
                
        # Affichage effectif des lignes de texte sur le bloc
        for j, line in enumerate(lines):
            y_pos = task_y + 4 + (j * 19*self.scale)
            text_color = (0, 0, 0)
            outline_color = (255, 255, 0) if yellow else (255,255,255)
            self.draw_outlined_text(surface, (task_x + strip_width + 3, y_pos + 1), self.small_font, line, text_color, outline_color,2)

        """# Affichage de la durée ("8h") figé en bas à droite
        current_right_x = task_rect.right - 6
        dur_surf = self.small_font.render(f"{task.duration}h", True, (0, 0, 0))
        dur_w, dur_h = dur_surf.get_width(), dur_surf.get_height()
        dur_bg_rect = pygame.Rect(current_right_x - dur_w - 4, task_rect.bottom - 4 - dur_h, dur_w + 4, dur_h + 2)
        
        pygame.draw.rect(surface, (255, 255, 255), dur_bg_rect, border_radius=3)
        surface.blit(dur_surf, (dur_bg_rect.x + 2, dur_bg_rect.y + 1))"""

    def draw_task_tooltip(self, surface, task, anchor_rect):
        """Affiche une bulle d'info détaillée pour une tâche survolée."""
        PADDING       = int(12 * self.scale)
        LINE_SPACING  = int(6 * self.scale)
        CORNER_RADIUS = int(8 * self.scale)
        BG_COLOR      = (25, 25, 40, 230)
        BORDER_COLOR  = (120, 180, 255)
        TITLE_COLOR   = (255, 255, 255)
        LABEL_COLOR   = (160, 200, 255)
        VALUE_COLOR   = (220, 220, 220)
        ACCENT_COLOR  = ACTIVITY_COLORS.get(getattr(task, 'activity_id', 0), DEFAULT_COLOR)

        tooltip_font       = pygame.font.SysFont("trebuchetms", int(15 * self.scale))
        tooltip_font_bold  = pygame.font.SysFont("trebuchetms", int(16 * self.scale), bold=True)
        tooltip_font_title = pygame.font.SysFont("trebuchetms", int(17 * self.scale), bold=True)

        # --- Construction des lignes à afficher ---
        title = task.name
        if getattr(task, 'part_index', 0) > 0:
            title += f"  (partie {task.part_index})"

        rows = []   # liste de (label, valeur) ou (None, texte_simple)

        if task.activity_name:
            rows.append(("Activité",   task.activity_name))
        if task.pool_name:
            rows.append(("Métier",     task.pool_name))

        rows.append(("Durée",      f"{task.duration} h"))

        if task.assigned_to:
            rows.append(("Assigné à", task.assigned_to))

        week_day = task.week_start + 1
        half = "matin" if getattr(task, 'start_half', 0) == 0 else "après-midi"
        rows.append(("Début",      f"Jour {week_day} – {half}"))

        end_day = task.week_start + task.duration / 8.0
        rows.append(("Fin",        f"Jour {end_day:.1f}"))

        if getattr(task, 'deadline', None) is not None:
            rows.append(("Deadline",  f"Jour {task.deadline}"))

        if getattr(task, 'is_pinned', False):
            rows.append((None, "📌 Tâche épinglée"))

        if task.description:
            rows.append(("Note",      task.description[:60] + ("…" if len(task.description) > 60 else "")))

        # --- Calcul de la taille du tooltip ---
        title_surf  = tooltip_font_title.render(title, True, TITLE_COLOR)
        max_label_w = 0
        max_value_w = 0
        row_surfs   = []

        for label, value in rows:
            if label is None:
                s = tooltip_font.render(value, True, VALUE_COLOR)
                row_surfs.append((None, s))
                max_value_w = max(max_value_w, s.get_width())
            else:
                ls = tooltip_font_bold.render(label + " :", True, LABEL_COLOR)
                vs = tooltip_font.render(value, True, VALUE_COLOR)
                row_surfs.append((ls, vs))
                max_label_w = max(max_label_w, ls.get_width())
                max_value_w = max(max_value_w, vs.get_width())

        col_gap = int(8 * self.scale)
        content_w = max(title_surf.get_width(), max_label_w + col_gap + max_value_w)
        row_h = tooltip_font.get_height() + LINE_SPACING
        content_h = (title_surf.get_height() + int(8 * self.scale)      # titre
                       + int(2 * self.scale)                            # séparateur
                       + int(6 * self.scale)                            # marge après séparateur
                       + len(row_surfs) * row_h)

        tip_w = content_w + PADDING * 2
        tip_h = content_h + PADDING * 2

        # --- Positionnement : préférer au-dessus du bloc, aligné à droite du curseur ---
        mouse_x, mouse_y = pygame.mouse.get_pos()

        # Horizontal : on part du curseur souris, décalé à gauche si ça déborde
        tip_x = mouse_x + int(14 * self.scale)
        if tip_x + tip_w > self.width - int(4 * self.scale):
            tip_x = mouse_x - tip_w - int(14 * self.scale)
        tip_x = max(int(4 * self.scale), tip_x)

        # Vertical : au-dessus du bloc ; si pas de place, en dessous
        tip_y = anchor_rect.y - tip_h - int(6 * self.scale)
        if tip_y < int(50 * self.scale):
            tip_y = anchor_rect.bottom + int(6 * self.scale)
        # Dernier recours : coller en bas d'écran
        if tip_y + tip_h > self.height - int(4 * self.scale):
            tip_y = self.height - tip_h - int(4 * self.scale)
        tip_y = max(int(4 * self.scale), tip_y)

        # --- Dessin du fond semi-transparent ---
        tip_surf = pygame.Surface((tip_w, tip_h), pygame.SRCALPHA)
        pygame.draw.rect(tip_surf, BG_COLOR, tip_surf.get_rect(), border_radius=CORNER_RADIUS)
        # Bande de couleur de l'activité en haut
        accent_bar = pygame.Rect(0, 0, tip_w, int(4 * self.scale))
        pygame.draw.rect(tip_surf, (*ACCENT_COLOR[:3], 255), accent_bar,
                         border_top_left_radius=CORNER_RADIUS, border_top_right_radius=CORNER_RADIUS)
        # Bordure
        pygame.draw.rect(tip_surf, (*BORDER_COLOR, 200), tip_surf.get_rect(), 1, border_radius=CORNER_RADIUS)

        # --- Titre ---
        cy = PADDING + int(4 * self.scale)
        tip_surf.blit(title_surf, (PADDING, cy))
        cy += title_surf.get_height() + int(6 * self.scale)

        # Ligne séparatrice
        pygame.draw.line(tip_surf, (*BORDER_COLOR, 120),
                         (PADDING, cy), (tip_w - PADDING, cy), 1)
        cy += int(6 * self.scale)

        # --- Lignes label / valeur ---
        for label_s, value_s in row_surfs:
            if label_s is None:
                tip_surf.blit(value_s, (PADDING, cy))
            else:
                tip_surf.blit(label_s, (PADDING, cy))
                tip_surf.blit(value_s, (PADDING + max_label_w + col_gap, cy))
            cy += row_h

        surface.blit(tip_surf, (tip_x, tip_y))

    def draw_task_overlay(self, surface, rect, color=(150, 150, 150), opacity=160, effet="DEFAULT", gris=False):
        x, y, w, h = rect
        c = (*color, opacity)  # couleur précalculée

        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        if gris:
            surf.fill((*color, 200))
            c = (*color, 230)

        match effet:
            case "HACHURE_1" | "HACHURE_2" | "HACHURE_CROISEE": 
                epaisseur = 2 if effet == "HACHURE_CROISEE" else 5
                do_1 = effet in ("HACHURE_1", "HACHURE_CROISEE")
                do_2 = effet in ("HACHURE_2", "HACHURE_CROISEE")
                for i in range(-h, w, 10):
                    if do_1: pygame.draw.line(surf, c, (i, 0), (i + h, h), epaisseur)
                    if do_2: pygame.draw.line(surf, c, (i + h, 0), (i, h), epaisseur)

            case "VAGUES":
                amplitude, frequence, espacement, epaisseur = 2, 0.3, int(14 * self.scale), int(7 * self.scale)
                for row in range(espacement // 2, h, espacement):
                    points = [(dx, row + int(amplitude * math.sin(dx * frequence)))
                            for dx in range(w)]
                    if len(points) >= 2:
                        pygame.draw.lines(surf, c, False, points, epaisseur)

            case "VAGUES_V":
                amplitude, frequence, espacement, epaisseur = 2, 0.3, int(28 * self.scale), int(14 * self.scale)
                for col in range(espacement // 2, w, espacement):
                    points = [(col + int(amplitude * math.sin(dy * frequence)), dy)
                            for dy in range(h)]
                    if len(points) >= 2:
                        pygame.draw.lines(surf, c, False, points, epaisseur)

            case "RONDS":
                espacement, epaisseur = 10, 5
                for r in range(espacement, max(w, h) * 2, espacement):
                    pygame.draw.circle(surf, (*color, opacity//2), (w // 2, h // 2), r, epaisseur)

            case "PLUIE":
                espacement_x, longueur, inclinaison = 8, 6, 2
                for col in range(0, w, espacement_x):
                    for row in range(0, h, longueur * 2):
                        pygame.draw.line(surf, c, (col, row), (col + inclinaison, row + longueur), 2)

            case "ZIGZAG":
                espacement, amplitude, periode, epaisseur = 13 , 4, 16, 6
                for row in range(4, h + espacement, espacement):
                    points = []
                    for dx in range(w):
                        phase = (dx % periode) / periode
                        dy = row + int(amplitude * (1 - abs(phase * 2 - 1) * 2 + 1) - amplitude)
                        points.append((dx, dy))
                    for i in range(len(points) - 1):
                        pygame.draw.line(surf, c,points[i], points[i + 1], epaisseur)
            
            case "POINTS":
                epaisseur = 3
                for dy in range(3, h, 10):
                    for dx in range(3, w, 10):
                        pygame.draw.circle(surf, c, (dx, dy), epaisseur)

        surface.blit(surf, (x, y))

    def _register_task_rect(self, t, t_rect, mode, default_color=(180, 180, 180)):
        """Enregistre le rect d'une tâche dans le bon dictionnaire et retourne la border_color."""
        match mode:
            case "COMPARE_SLOT1":
                self.task_slot1_btn[(t.id, t.part_index)] = t_rect
                default_color = self.color_slot1
            case "COMPARE_SLOT2":
                self.task_slot2_btn[(t.id, t.part_index)] = t_rect
                default_color = self.color_slot2
            case "BLENDED":
                self.task_blended_btn[(t.id, t.part_index)] = t_rect
            case "COMPLETION":
                self.task_completion_btn[(t.id, t.part_index)] = t_rect
        return default_color

    def _draw_task_highlight(self, surface, t, tx, ty, tw, th):
        """Dessine l'effet de surbrillance pulsé si la tâche est la cible active."""
        if self._highlighted_task_key != (t.id, t.part_index) or self._highlight_start_time is None:
            return
        elapsed = pygame.time.get_ticks() - self._highlight_start_time
        if elapsed < 1800:
            progress = elapsed / 1800
            alpha = int(220 * abs(math.sin(progress * math.pi * 3)) * (1.0 - progress))
            glow = pygame.Surface((tw + 8, th + 8), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 255, 100, alpha), glow.get_rect(), border_radius=7)
            pygame.draw.rect(glow, (255, 255, 100, min(255, alpha + 60)), glow.get_rect(), 3, border_radius=7)
            surface.blit(glow, (tx - 4, ty - 4))
        else:
            self._highlighted_task_key = None
            self._highlight_start_time = None

    def _draw_task_block(self, surface, t, tx, ty, tw, th, mode):
        """Dessine un bloc de tâche : fond, bordure, highlight, hover, overlays."""
        t_rect = pygame.Rect(tx, ty, tw, th)
        if mode == "UNAVAILABLE": 
            self.draw_task_overlay(surface, (tx, ty, tw, th), color=(20, 20, 20), gris=True)
            return
        bg_color = ACTIVITY_COLORS.get(getattr(t, 'activity_id', 0), DEFAULT_COLOR)
        border_color = self._register_task_rect(t, t_rect, mode, bg_color)

        pygame.draw.rect(surface, border_color, t_rect, border_radius=5)
        pygame.draw.rect(surface, bg_color, (tx, ty, tw, th - 5), border_radius=5)

        self._draw_task_highlight(surface, t, tx, ty, tw, th)

        if mode in ["COMPARE_SLOT1", "COMPARE_SLOT2"]:
            pygame.draw.rect(surface, border_color, (tx, ty, 8, th), border_top_left_radius=5, border_bottom_left_radius=5)

        # Hover tooltip
        mouse_pos = pygame.mouse.get_pos()
        if t_rect.collidepoint(mouse_pos):
            self._hover_found = True
            if self._hover_task is not t:
                self._hover_task = t
                self._hover_task_rect = pygame.Rect(tx, ty, tw, th)
                self._hover_start_time = pygame.time.get_ticks()
                self._hover_pos = mouse_pos

        # Texte
        if tw > 30:
            self.text_cesura(surface, t, th, tw, tx, ty)

        # --- Overlays ---
        # Effet transparent pour les tâches générées par l'auto-complétion du solveur
        if mode == "COMPLETION":
            self.draw_task_overlay(surface, (tx, ty, tw, th), color=(150, 150, 150), gris=True)
        # Effet très grisé quand une tâche chevauche une autre tâche du planning blended
        if not self.time_slot_available(t) and mode not in ["BLENDED", "COMPLETION"] and self.compare_mode > 0:
            self.draw_task_overlay(surface, (tx, ty, tw, th), color=(20, 20, 20), gris=True)
        # Effet grisé et hachuré quand une tâche est déjà dans le planning blended
        if not self.task_available(t) and mode not in ["BLENDED", "COMPLETION"] and self.compare_mode != 0:
            self.draw_task_overlay(surface, (tx, ty, tw, th), color=(40, 40, 40), effet="HACHURE_2", gris=True)

    def _draw_tasks(self, surface, clip_rect, op_tasks, plan_x, plan_w, day_width, row_height, label_width, row_y, mode):
        surface.set_clip(clip_rect)

        for t in op_tasks:
            if self.activ_activity not in [t.activity_id, None]: continue
            tx = plan_x + label_width + (t.week_start * day_width) - self.preview_scroll_x
            ty = row_y + 1
            tw = max(int((t.duration / 8.0) * day_width), 30)
            th = row_height - 2

            if self.compare_mode == 2 and mode not in ["BLENDED", "COMPLETION", "UNAVAILABLE"]:
                th = th // 2
                if mode in ["COMPARE_SLOT2", "TEXT_ONLY2"]:
                    ty = ty + th

            if tw > 30 and mode in ["TEXT_ONLY1", "TEXT_ONLY2"] and self.task_available(t):
                self.text_cesura(surface, t, th, tw, tx, ty, yellow=(not self.time_slot_available(t)))

            if tx + tw > plan_x + label_width and tx < plan_x + plan_w and mode not in ["TEXT_ONLY1", "TEXT_ONLY2"]:
                self._draw_task_block(surface, t, tx, ty, tw, th, mode)

        surface.set_clip(None)

    def _draw_planning_lines(self, surface, tasks, clip_rect, plan_x, plan_w, day_width, row_height, label_width, group_spacing, current_y, mode, background):
        max_hour_color = (0,0,0)
        if self.compare_mode == 2 and mode != "BLENDED":
            max_hour_color = self.color_slot1
            if mode == "COMPARE_SLOT2":
                max_hour_color = self.color_slot2        

        for i, op in enumerate(self.operators):
            row_y = current_y

            op_tasks = [t for t in tasks if t.assigned_to == op.name] if len(tasks) != 0 else []
            
            if background:
                # --- Colonne de gauche (Gris) : Nom et Infos ---
                row_rect = pygame.Rect(plan_x, row_y, plan_w, row_height)
                pygame.draw.rect(surface, (245, 245, 250), row_rect)

                # Dessin de la petite bande verticale colorée selon le métier
                pool_color = POOL_COLORS.get(op.pool_name, (100, 100, 100))
                pygame.draw.rect(surface, pool_color, (plan_x , row_y, 12, row_height))

                color_line = ((200, 200, 210) if mode in  ["BLENDED", "COMPLETION"] else (0,0,0))
                pygame.draw.rect(surface, color_line, row_rect, 1) # Bordure de la ligne

            # --- Zone de droite : Dessin des Tâches ---
            self._draw_tasks(surface, clip_rect, op_tasks, plan_x, plan_w, day_width, row_height, label_width, row_y, mode)

            if mode not in  ["TEXT_ONLY1", "TEXT_ONLY2", "COMPLETION", "UNAVAILABLE"] :
                total_h_op = sum(t.duration for t in op_tasks)
                name_surf = self.font.render(op.name, True, (0,0,0))
                hours_surf = self.small_font.render(f"{total_h_op}h", True, max_hour_color)
                compact = (3 if mode in  ["BLENDED", "COMPLETION"] else 0)

                # Centrage vertical des textes dans la ligne
                start_text_y = row_y + (row_height - (name_surf.get_height() + hours_surf.get_height() + 2)) // 2
                surface.blit(name_surf, (plan_x + int(16 * self.scale), start_text_y + compact))
                surface.blit(hours_surf, (plan_x + (label_width // 2 if mode == "COMPARE_SLOT2" else int(16 * self.scale)), start_text_y + name_surf.get_height() - compact))

            current_y += row_height

            split_h = int(4 * self.scale) if mode in ["COMPARE_SLOT1", "COMPARE_SLOT2", "TEXT_ONLY1","TEXT_ONLY2","UNAVAILABLE"] else 1
            if i < len(self.operators) - 1 and op.pool_name != self.operators[i+1].pool_name:
                split_h += group_spacing
            
            if i < len(self.operators) - 1 : 
                pygame.draw.rect(surface, (10, 10, 20), (plan_x, current_y, plan_w, split_h))
                current_y += split_h   

        return current_y

    def find_equivalent_task(self, task_key, clicked_mode):
        """
        Cherche la tâche équivalente (même id, même part_index) dans l'autre slot ou blended.
        Retourne (task, source) ou (None, None).
        clicked_mode : "COMPARE_SLOT1" | "COMPARE_SLOT2" | "BLENDED"
        """
        tid, pidx = task_key
        if clicked_mode == "COMPARE_SLOT1":
            # Chercher dans slot2 puis blended
            for t in self.tasks_slot2:
                if t.id == tid and t.part_index == pidx:
                    return t, "COMPARE_SLOT2"
            for t in self.tasks_blended:
                if t.id == tid and t.part_index == pidx:
                    return t, "BLENDED"
        elif clicked_mode == "COMPARE_SLOT2":
            for t in self.tasks_slot1:
                if t.id == tid and t.part_index == pidx:
                    return t, "COMPARE_SLOT1"
            for t in self.tasks_blended:
                if t.id == tid and t.part_index == pidx:
                    return t, "BLENDED"
        elif clicked_mode == "BLENDED":
            for t in self.tasks_slot1:
                if t.id == tid and t.part_index == pidx:
                    return t, "COMPARE_SLOT1"
            for t in self.tasks_slot2:
                if t.id == tid and t.part_index == pidx:
                    return t, "COMPARE_SLOT2"
        return None, None

    def scroll_to_task(self, task, day_width=None, plan_w=None, label_width=None):
        """Scrolle pour centrer horizontalement la tâche dans la vue."""
        day_width   = day_width   or int(100 * self.scale_x)
        plan_w      = plan_w      or self.plan_w
        label_width = label_width or int(160 * self.scale_x)
        visible_w   = plan_w - label_width
        task_center_x = (task.week_start + task.duration / 16.0) * day_width
        target_scroll = task_center_x - visible_w / 2
        # max_scroll recalculé comme dans scrollbar_management
        max_day = max(
            max((t.week_start + t.duration / 8.0) for t in self.tasks_slot1 if t.assigned_to) if self.tasks_slot1 else 20,
            max((t.week_start + t.duration / 8.0) for t in self.tasks_slot2 if t.assigned_to) if self.tasks_slot2 else 20,
        )
        max_scroll = max(0, int(math.ceil(max_day) + 2) * day_width - visible_w)
        self.preview_scroll_x = max(0, min(target_scroll, max_scroll))
        self.scrollbar.scroll_x = self.preview_scroll_x

    def draw_planning(self, surface, tasks, plan_x=None, plan_y=None, plan_w=None, day_width=None, row_height=None, label_width=None, mode="READ_ONLY", background=False):
        """Dessine le planning généré par CPLEX.       
        Paramètres modifiables :
        - plan_x, plan_y : Coordonnées du coin en haut à gauche.
        - plan_w : La largeur totale allouée au planning.
        - day_width : L'espacement en pixels entre le Jour 1 et le Jour 2 (Définit le "zoom" horizontal).
        - row_height : L'épaisseur d'une ligne d'opérateur (Définit le "zoom" vertical).
        - label_width : La largeur de la colonne de gauche (celle qui contient les noms).
        - mode : "READ_ONLY", "COMPARE_SLOT1", "COMPARE_SLOT2", "TEXT_ONLY1","TEXT_ONLY2", "UNAVAILABLE", "BLENDED" et "COMPLETION" """
        # 1. DÉFINITION DES DIMENSIONS (Récupération des arguments ou valeurs par défaut)
        # Si un argument n'est pas fourni (None), on utilise les variables de self (celles de l'onglet complet)
        plan_x = plan_x if plan_x is not None else self.plan_x
        plan_y = plan_y if plan_y is not None else int(100 * self.scale_y)
        plan_w = plan_w if plan_w is not None else self.plan_w
        
        # Dimensions internes du tableau
        day_width = day_width if day_width is not None else int(100 * self.scale_x)
        row_height = row_height if row_height is not None else int(55 * self.scale_y)
        label_width = label_width if label_width is not None else int(160 * self.scale_x)

        header_h = int(25 * self.scale_y)         # Hauteur de la barre grise en haut ("J1, J2...")
        group_spacing = int(5 * self.scale_y)    # Espace quand on change de métier (ex: Assembleur -> Contrôleur)

        # 2. CALCUL DE LA HAUTEUR GLOBALE DU FOND
        # Avant de dessiner quoi que ce soit, on doit savoir quelle sera la hauteur totale du fond blanc.
        plan_h = self._calcul_height_planning(header_h, row_height, group_spacing, mode)

        if background:
            # Dessin du grand rectangle blanc/bleuté de fond
            border_color = ((200, 200, 210) if mode == "BLENDED" else (0,0,0))
            pygame.draw.rect(surface, (250, 250, 255), (plan_x, plan_y, plan_w, plan_h), border_top_left_radius=10, border_top_right_radius=10)
            pygame.draw.rect(surface, border_color, (plan_x, plan_y, plan_w, plan_h), 2 , border_top_left_radius=10, border_top_right_radius=10)

        # 3. GESTION DU DÉFILEMENT (Scrollbar Horizontale)
        # On cherche à quel jour se termine la toute dernière tâche du planning
        max_day = self.scrollbar_management(plan_x, plan_w, plan_y, day_width, label_width)

        # On définit une zone "fenêtre" (clip_rect) qui correspond uniquement à la partie droite du tableau.
        # En activant `surface.set_clip`, Pygame devient incapable de dessiner en dehors de cette zone pour ne pas "déborder".
        clip_rect = pygame.Rect(plan_x + label_width , plan_y , plan_w - label_width -2, plan_h + header_h)
        
        current_y = plan_y + header_h

        #traitement différent en fonction du mode
        match mode :
            case "COMPARE_SLOT1":
                self.task_slot1_btn = {}
            case "COMPARE_SLOT2":
                self.task_slot2_btn = {}
            case "BLENDED" :
                self.task_blended_btn = {}
            case "COMPLETION" :
                self.task_completion_btn = {}

        # 4. DESSIN DES LIGNES (Opérateurs + Tâches)
        current_y = self._draw_planning_lines(surface, tasks, clip_rect, plan_x+1, plan_w-2, day_width, row_height, label_width, group_spacing, current_y, mode, background)

        if mode in ["TEXT_ONLY1","TEXT_ONLY2"] : return
        # 5. DESSIN DE LA GRILLE DES JOURS ET DU CURSEUR ROUGE (Le temps)
        self._draw_day_grid(surface, clip_rect, max_day, plan_x, label_width, day_width, plan_w, plan_y, current_y)

        # Ligne noire verticale qui sépare les noms de la zone de timeline
        pygame.draw.line(surface, (0, 0, 0), (plan_x + label_width, plan_y), (plan_x + label_width, current_y), 1)
        
        surface.set_clip(None)  # au cas où

    def reindexing(self, tasks):
        # Réindexation des morceaux
        families = {}
        for t in tasks:
            families.setdefault(t.id, []).append(t)
        for family in families.values():
            family.sort(key=lambda x: x.week_start)
            if len(family) == 1:
                family[0].part_index = 0
            else:
                for idx, t in enumerate(family, start=1):
                    t.part_index = idx
        return tasks

    def merge_contiguous_tasks(self, tasks):
        """Fusionne les tâches ayant le même id, le même opérateur, et qui sont contiguës dans le temps."""
        changed = True
        while changed:
            changed = False
            tasks.sort(key=lambda t: (t.assigned_to or "",t.id,t.week_start))
            i = 0
            while i < len(tasks) - 1:
                t1 = tasks[i]
                t2 = tasks[i + 1]
                if (t1 in self.tasks_blended and t2 not in self.tasks_blended) or (
                    t1 not in self.tasks_blended and t2 in self.tasks_blended) :
                    i += 1
                    continue
                same_task = t1.id == t2.id
                same_operator = t1.assigned_to == t2.assigned_to
                end_t1 = t1.week_start + (t1.duration / 8.0)
                contiguous = abs(t2.week_start - end_t1) < 0.01
                if same_task and same_operator and contiguous:
                    t1.duration += t2.duration
                    tasks.pop(i + 1)
                    changed = True
                else:
                    i += 1

        return self.reindexing(tasks)
    
    def cut_task(self, new_task, tasks):
        """ new_task: la tâche qui vient d'être ajoutée
            tasks   : la liste de tâches possiblement impactée par l'ajout de new_task, à modifier"""
        overlapped_tasks = []
        for task in tasks :
            if task.assigned_to == new_task.assigned_to and (
                task.week_start <= new_task.week_start < task.week_start + task.duration//8 
                or new_task.week_start <= task.week_start < new_task.week_start + new_task.duration//8):
                overlapped_tasks.append(task)

        # Boucle tarpin compliquée 
        nw_t_end = new_task.week_start + new_task.duration // 8
        for ov_task in overlapped_tasks:
            ov_t_end = ov_task.week_start + ov_task.duration // 8
            if (ov_task.week_start >= new_task.week_start and ov_t_end <= nw_t_end) : continue
            
            insertion_index = ov_task.part_index if ov_task.part_index > 0 else 1

            task_before = None
            if ov_task.week_start < new_task.week_start :
                task_before = copy.deepcopy(ov_task)
                duration = (new_task.week_start - ov_task.week_start) * 8
                task_before.duration = duration
                task_before.part_index = insertion_index
                insertion_index += 1
                tasks.append(task_before)
            
            task_during = copy.deepcopy(ov_task)
            if task_before == None:
                duration = (nw_t_end - ov_task.week_start) * 8
            else : 
                duration = new_task.duration if ov_t_end >= nw_t_end else (ov_t_end - new_task.week_start) *8
            task_during.duration = duration
            task_during.week_start = max([new_task.week_start, ov_task.week_start])
            task_during.part_index = insertion_index
            insertion_index += 1
            tasks.append(task_during)
            
            if ov_t_end > nw_t_end :
                task_after = copy.deepcopy(ov_task)
                duration = (ov_t_end - nw_t_end) * 8
                task_after.duration = duration
                task_after.week_start = nw_t_end
                task_after.part_index = insertion_index
                tasks.append(task_after)

            tasks.remove(ov_task)

        return self.reindexing(tasks)

    def time_slot_available(self, new_task):
        for task in self.tasks_blended:
            if task.assigned_to == new_task.assigned_to and (
                task.week_start <= new_task.week_start < task.week_start + task.duration//8 
                or new_task.week_start <= task.week_start < new_task.week_start + new_task.duration//8):
                return False
        return True

    def task_available(self, new_task):
        max_duration = sum(t.duration for t in self.tasks if t.id == new_task.id)
        current_task_duration = sum(t.duration for t in self.tasks_blended if t.id == new_task.id)
        return (current_task_duration + new_task.duration) <= max_duration

    def add_task(self, pos, task_btn_list, task_list):
        """ Renvoie un tuple: ((id, part_index), boolean)
            (id, part_index): la tâche sur laquelle l'utilisateur a cliqué
            boolean         : si la tâche a pu être ajoutée ou non"""
        for key, rect_task in task_btn_list.items():
            if rect_task.collidepoint(pos):
                # on récupère la tâche sur laquelle on vient de cliquer (faire le lien entre le rect et la tâche)
                new_task = next((t for t in task_list if (t.id, t.part_index) == key), None)    
                if self.task_available(new_task) and self.time_slot_available(new_task):
                    self.tasks_blended.append(copy.deepcopy(new_task))
                    return (new_task, True)
                return (new_task, False)
        return (None, False)

    def _handle_history_rename_key(self, event):
        """Gère la saisie clavier lors du renommage d'une solution."""
        if self._hist_renaming_index is None:
            return False
        if event.key == pygame.K_RETURN:
            name = self._hist_rename_text.strip()
            if name:
                self.history_solutions[self._hist_renaming_index]["name"] = name
            self._hist_renaming_index = None
            self._hist_rename_text    = ""
        elif event.key == pygame.K_ESCAPE:
            self._hist_renaming_index = None
            self._hist_rename_text    = ""
        elif event.key == pygame.K_BACKSPACE:
            self._hist_rename_text = self._hist_rename_text[:-1]
        elif len(self._hist_rename_text) < 30:
            self._hist_rename_text += event.unicode
        return True

    def _handle_history_click(self, event):
        """Gère les clics dans le panneau historique (sélection, renommage, suppression, drag)."""
        if not self.history_rect.collidepoint(event.pos):
            return False
        if self.history_scrollbar.rect.collidepoint(event.pos):
            return False

        relative_x = event.pos[0] - self.history_rect.x + self.history_scrollbar.scroll_x
        item_w = int(200 * self.scale_x)
        clicked_index = int(relative_x // item_w)

        if self._hist_delete_confirm is not None:
            if getattr(self, '_hist_confirm_yes_rect', None) and self._hist_confirm_yes_rect.collidepoint(event.pos):
                del self.history_solutions[self._hist_delete_confirm]
                if self.active_history_index >= len(self.history_solutions):
                    self.active_history_index = len(self.history_solutions) - 1
                if self.comparison_history_index >= len(self.history_solutions):
                    self.comparison_history_index = -1
                self.tasks_slot1 = [] if self.active_history_index == -1 else self.history_solutions[self.active_history_index]["tasks"]
                self._hist_delete_confirm = None
                if len(self.history_solutions) == 1 : 
                    self.compare_mode = 1
                    self.tasks_slot1 = self.tasks_slot2 if self.tasks_slot2 != [] else []
                if len(self.history_solutions) == 0 : self.compare_mode = 0
                return True
            elif getattr(self, '_hist_confirm_no_rect', None) and self._hist_confirm_no_rect.collidepoint(event.pos):
                self._hist_delete_confirm = None
                return True

        if any(r.collidepoint(event.pos) for r in getattr(self, '_hist_rename_btn_rects', {}).values()):
            i = next(i for i, r in self._hist_rename_btn_rects.items() if r.collidepoint(event.pos))
            self._hist_renaming_index = i
            self._hist_rename_text    = self.history_solutions[i]["name"]
            return True
        if any(r.collidepoint(event.pos) for r in getattr(self, '_hist_delete_btn_rects', {}).values()):
            i = next(i for i, r in self._hist_delete_btn_rects.items() if r.collidepoint(event.pos))
            self._hist_delete_confirm = i
            return True
        if any(r.collidepoint(event.pos) for r in getattr(self, '_hist_cancel_rename_rects', {}).values()):
            self._hist_renaming_index = None
            self._hist_rename_text    = ""
            return True

        if 0 <= clicked_index < len(self.history_solutions):
            if self.compare_mode < 1:
                self.active_history_index = clicked_index
                solution = self.history_solutions[clicked_index]
                self.tasks_slot1  = solution["tasks"]
                self.last_metrics = solution["metrics"]
                self.status_message = f"Affichage de la Solution #{clicked_index + 1}"
            elif clicked_index != self.active_history_index:
                self._drag_radar_index = clicked_index
                self._drag_origin      = event.pos
                self._drag_pos         = event.pos
                self._drag_started     = False
            return True
        return False

    def _handle_drag_radar(self, event):
        """Gère MOUSEBUTTONUP et MOUSEMOTION pour le drag & drop des mini radars."""
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.radar.handle_mouse_up()
            if self._drag_radar_index is not None:
                idx = self._drag_radar_index
                sol = self.history_solutions[idx]
                if not self._drag_started:
                    self.comparison_history_index = idx
                    self.compare_mode = 2
                    self.tasks_slot2 = sol["tasks"]
                else:
                    if self.compare_slot1.collidepoint(event.pos) and idx != self.comparison_history_index:
                        self.active_history_index = idx
                        self.tasks_slot1 = sol["tasks"]
                        self.last_metrics = sol["metrics"]
                        name = sol["name"]
                        self.show_notification(f"Solution #{name} chargée dans l'emplacement 1", color=self.color_slot1)
                    elif self.compare_slot2.collidepoint(event.pos) and idx != self.active_history_index:
                        self.comparison_history_index = idx
                        self.compare_mode = 2
                        self.tasks_slot2 = sol["tasks"]
                        name = sol["name"]
                        self.show_notification(f"{name} chargée dans l'emplacement 2", color=self.color_slot2)
                self._drag_radar_index = self._drag_pos = self._drag_origin = self._drag_target_slot = None
                self._drag_started = False

        elif event.type == pygame.MOUSEMOTION:
            self.radar.handle_mouse_motion(event.pos)
            if self.history_rect.collidepoint(event.pos):
                item_w = int(200 * self.scale_x)
                rel_x = event.pos[0] - self.history_rect.x + self.history_scrollbar.scroll_x
                idx = int(rel_x // item_w)
                self._hist_hovered_index = idx if 0 <= idx < len(self.history_solutions) else None
            else:
                self._hist_hovered_index = None
            if self._drag_radar_index is not None:
                self._drag_pos = event.pos
                if not self._drag_started and self._drag_origin is not None:
                    dx = event.pos[0] - self._drag_origin[0]
                    dy = event.pos[1] - self._drag_origin[1]
                    if dx * dx + dy * dy > 36:
                        self._drag_started = True
                if self._drag_started:
                    if   self.compare_slot1.collidepoint(event.pos): self._drag_target_slot = 1
                    elif self.compare_slot2.collidepoint(event.pos): self._drag_target_slot = 2
                    else:                                             self._drag_target_slot = None

    def _handle_buttons(self, event):
        """Gère les boutons principaux : générer, retour, envoyer, sauvegarder, comparer, view_sol."""
        if self.generate_button.handle_event(event)  and self.compare_mode == 0:
            if not getattr(self, 'raw_tasks', None):
                self.status_message = "Planning vide !"
                return None
            self.status_message = "Génération en cours (CPLEX)..."
            self.pending_solve   = True
            return None

        if self.back_to_generate_button.handle_event(event) and self.compare_mode != 0:
            self.compare_mode = 0
            self.active_history_index = self.comparison_history_index = -1
            self.tasks_slot1 = self.tasks_slot2 = []
            self.task_slot1_btn = self.task_slot2_btn = {}
            self.view_sol = False
            self.solver_completion = None

        if self.has_solution:
            if self.send_button.handle_event(event):
                self.tasks = self.tasks_slot1 if self.compare_mode < 1 else self.fill_tasks(self.tasks_blended)
                return "SEND_TO_PLANNING"
            if self.save_button.handle_event(event):
                self.export_solution_to_json()
            if self.compare_button.handle_event(event) and self.active_history_index > -1 and self.compare_mode == 0:
                self.activ_activity = None
                self.compare_mode = 1
            if  self.compare_mode == 0 :
                for activity in self.activities:
                    if activity[2].handle_event(event) :
                        self.activ_activity = None if self.activ_activity == activity[0] else activity[0]

        if not self.view_sol :
            if self.view_sol_button.handle_event(event):
                self.radar.reset()
                self.view_sol = True
                self._run_solver(time_limit=1)
                if self.solver_completion is None:
                    self.view_sol = False
            if self.reset_planning_btn.handle_event(event):
                self.tasks_blended = []
                self.task_blended_btn = {}
                self.tasks_slot1 = self.merge_contiguous_tasks(self.tasks_slot1)
                self.tasks_slot2 = self.merge_contiguous_tasks(self.tasks_slot2)
        else :
            if self.unview_sol_button.handle_event(event):
                self.view_sol = False
            if self.save_solution.handle_event(event):
                self.add_solution(self.solver_completion, view_sol=False)
        return None

    def _try_add_task_at_pos(self, pos, allow_redirect=True):
        """
        Tente d'ajouter la tâche sous `pos` au planning blended.
        allow_redirect : si False, on ne scrolle/surbrille pas en cas d'échec (utilisé en path selection).
        Retourne task_added = (bool_success, task_or_None, slot_index).
        """
        if self.compare_mode < 1:
            return (False, None, 0)

        add1 = self.add_task(pos, self.task_slot1_btn, self.tasks_slot1)
        add2 = self.add_task(pos, self.task_slot2_btn, self.tasks_slot2)
        add3 = (None, False)
        if self.view_sol:
            add3 = self.add_task(pos, self.task_completion_btn, self.solver_completion["tasks"])

        task_added = (False, None, 0)
        if add1[0] is not None: task_added = (add1[1], add1[0], 1)
        if add2[0] is not None: task_added = (add2[1], add2[0], 2)
        if self.view_sol and add3[0] is not None: task_added = (add3[1], add3[0], 3)

        if task_added[0]:
            self.tasks_blended = self.merge_contiguous_tasks(self.tasks_blended)

        # Redirection seulement si autorisée (pas en path selection)
        if allow_redirect and task_added[1] is not None and not task_added[0]:
            equiv = next((t for t in self.tasks_blended if t.id == task_added[1].id), None)
            if equiv is not None:
                self._highlighted_task_key = (equiv.id, equiv.part_index)
                self._highlight_start_time = pygame.time.get_ticks()
                self.scroll_to_task(equiv)

        if task_added[0]:
            if task_added[2] == 1:
                self.tasks_slot2 = self.cut_task(task_added[1], self.tasks_slot2)
            if task_added[2] == 2:
                self.tasks_slot1 = self.cut_task(task_added[1], self.tasks_slot1)

        return task_added

    def _handle_task_click(self, event):
        """Gère les clics sur les tâches en mode comparaison (ajout blended + surbrillance)."""
        # On ne traite que les clics gauche en mode comparaison
        if event.type != pygame.MOUSEBUTTONDOWN or self.compare_mode < 1:
            return
        pos = pygame.mouse.get_pos()

        # Suppression d'une tâche du blended si on clique dessus
        for key, rect_task in self.task_blended_btn.items():
            if rect_task.collidepoint(pos):
                self.tasks_blended.remove(next((t for t in self.tasks_blended if (t.id, t.part_index) == key), None))
                self.tasks_slot1 = self.merge_contiguous_tasks(self.tasks_slot1)
                self.tasks_slot2 = self.merge_contiguous_tasks(self.tasks_slot2)
                for t in self.tasks_blended:
                    if t.assigned_to:
                        self.tasks_slot1 = self.cut_task(t, self.tasks_slot1)
                        self.tasks_slot2 = self.cut_task(t, self.tasks_slot2)
                return  # clic consommé par la suppression

        # Ajout normal avec redirection activée
        task_added = self._try_add_task_at_pos(pos, allow_redirect=True)

        # Démarrage du path selection dès qu'on clique dans la zone planning (à droite de plan_x).
        # La zone des radars/slots drag est à gauche de plan_x, donc automatiquement exclue.
        if pos[0] >= self.plan_x:
            self._drag_adding = True
            self._drag_added_keys = set()
            if task_added[0] and task_added[1] is not None:
                self._drag_added_keys.add((task_added[1].id, task_added[1].part_index))

    def _handle_path_selection_motion(self, event):
        """Appelé sur MOUSEMOTION quand le bouton gauche est maintenu : ajoute les tâches survolées."""
        if not self._drag_adding or self.compare_mode < 1:
            return
        pos = event.pos

        # On parcourt les tâches de slot1 et slot2 (et completion si actif)
        sources = [(self.task_slot1_btn, self.tasks_slot1), (self.task_slot2_btn, self.tasks_slot2),]
        if self.view_sol and self.solver_completion:
            sources.append((self.task_completion_btn, self.solver_completion["tasks"]))

        for btn_dict, task_list in sources:
            for key, rect_task in btn_dict.items():
                if rect_task.collidepoint(pos) and key not in self._drag_added_keys:
                    # On appelle add_task directement, sans redirection
                    new_task = next((t for t in task_list if (t.id, t.part_index) == key), None)
                    if new_task is None:
                        continue
                    if self.task_available(new_task) and self.time_slot_available(new_task):
                        self.tasks_blended.append(copy.deepcopy(new_task))
                        self.tasks_blended = self.merge_contiguous_tasks(self.tasks_blended)
                        # Couper les slots impactés
                        slot_index = 1 if btn_dict is self.task_slot1_btn else 2
                        if slot_index == 1:
                            self.tasks_slot2 = self.cut_task(new_task, self.tasks_slot2)
                        elif slot_index == 2:
                            self.tasks_slot1 = self.cut_task(new_task, self.tasks_slot1)
                    # Marquer comme traité pour ce geste (qu'elle ait été ajoutée ou non)
                    self._drag_added_keys.add(key)

    def handle_events(self, event):
        if getattr(self, 'show_info_popup', False):
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.show_info_popup = False
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.info_rect.collidepoint(event.pos):
                self.show_info_popup = True
                return True

        if event.type == pygame.KEYDOWN:
            if self._handle_history_rename_key(event):
                return None
            if self.radar.handle_event(event):
                return None

        is_wheel = event.type == pygame.MOUSEWHEEL or (event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5))

        if is_wheel and self.has_solution:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            y_scroll = event.y if event.type == pygame.MOUSEWHEEL else (1 if event.button == 4 else -1)
            if self.history_rect.collidepoint((mouse_x, mouse_y)):
                self.history_scrollbar.scroll_x -= y_scroll * 40
                self.history_scrollbar.scroll_x = max(0, min(self.history_scrollbar.scroll_x, self.history_scrollbar.max_scroll))
                return None
            elif mouse_x > self.plan_x:
                self.scrollbar.scroll_x -= y_scroll * 30
                self.scrollbar.scroll_x = max(0, min(self.scrollbar.scroll_x, self.scrollbar.max_scroll))
                self.preview_scroll_x = int(self.scrollbar.scroll_x)
                return None

        if self.has_solution and not is_wheel:
            if self.scrollbar.handle_event(event):
                self.preview_scroll_x = int(self.scrollbar.scroll_x)
            if getattr(self, 'history_scrollbar', None) and self.history_scrollbar.handle_event(event):
                self.history_scroll_x = int(self.history_scrollbar.scroll_x)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._handle_history_click(event):
                return True
            if self.reset_rect.collidepoint(event.pos):
                self.radar.reset()
                self.status_message = "Cibles du radar réinitialisées."
                return None
            self.radar.handle_mouse_down(event.pos, event.button)

        # Arrêt du path selection au relâchement du bouton gauche
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_adding = False
            self._drag_added_keys = set()

        self._handle_drag_radar(event)

        # Path selection : survol avec clic gauche maintenu
        if event.type == pygame.MOUSEMOTION and self._drag_adding:
            self._handle_path_selection_motion(event)

        if not is_wheel:
            result = self._handle_buttons(event)
            if result is not None:
                return result
            self._handle_task_click(event)

        return None

    def draw(self, screen):
        screen.fill((30, 30, 40))
        r = int(13 * self.scale)
        pygame.draw.circle(screen, (100, 150, 255), self.info_rect.center, r)
        pygame.draw.circle(screen, (255, 255, 255), self.info_rect.center, r, 2)
        i_surf = self.tiny_font.render("i", True, (255, 255, 255))
        screen.blit(i_surf, (self.info_rect.centerx - i_surf.get_width()//2, self.info_rect.centery - i_surf.get_height()//2))
        
        title = self.title_font.render("Radar de Simulation", True, (255, 255, 255))
        screen.blit(title, (self.info_rect.right + 15, self.info_rect.y - 4))

        self._hover_found = False   # sera mis à True par _draw_tasks si la souris survole une tâche

        row_height = int(40 * self.scale_y)

        if self.compare_mode > 0 :
            self.draw_planning(screen, self.tasks_slot1, mode = "COMPARE_SLOT1", row_height=row_height*2, background=True)
            self.scrollbar.draw(screen) 
            self.draw_history_panel(screen)
            self.save_button.draw(screen, self.button_font)
            self.send_button.draw(screen, self.button_font)
            self.draw_notifications(screen)
            self.back_to_generate_button.draw(screen, self.button_font)

            pygame.draw.rect(screen, self.color_slot1, self.compare_slot1, 5, border_radius=15)
            self._draw_single_mini_radar(screen, self.compare_slot1.x + self.compare_slot1.w //2,
                                        self.compare_slot1.y + self.compare_slot1.h //2, int(50 * self.scale), 
                                        self.history_solutions[self.active_history_index]["metrics"], "", False)
            
            pygame.draw.rect(screen, self.color_slot2, self.compare_slot2, 5, border_radius=15)

            if self.view_sol:
                self.draw_planning(screen, self.solver_completion["tasks"], plan_y = self.plan_y_compare, 
                                   mode = "COMPLETION", row_height=row_height, background=True)
                self._draw_single_mini_radar(screen, self.compare_slot1.x + self.compare_slot1.w //2,
                                        int(650 * self.scale_y), int(55 * self.scale), 
                                        self.solver_completion["metrics"], "", False)
                self.unview_sol_button.draw(screen, self.button_font)
                self.draw_text_centered(screen, "Cacher cette solution", self.unview_sol_button.rect, self.small_font)
                self.save_solution.draw(screen, self.small_font)
            else:
                self.view_sol_button.draw(screen,self.button_font)
                self.draw_text_centered(screen, "Voir une solution avec ces tâches", self.view_sol_button.rect, self.small_font)
                self.reset_planning_btn.draw(screen, self.small_font)

            self.draw_planning(screen, self.tasks_blended, plan_y = self.plan_y_compare, 
                               mode = "BLENDED", row_height=row_height, background=not self.view_sol)

            if self.compare_mode == 2:
                self._draw_single_mini_radar(screen, self.compare_slot2.x + self.compare_slot2.w // 2,
                                            self.compare_slot2.y + self.compare_slot2.h // 2, int(50 * self.scale), 
                                            self.history_solutions[self.comparison_history_index]["metrics"], "", False)
                self.draw_planning(screen, self.tasks_slot2, mode = "COMPARE_SLOT2", row_height=row_height*2)
            else : 
                self.draw_text_centered(screen, "Cliquez sur une solution pour comparer son planning", self.compare_slot2, self.small_font)
            self.draw_planning(screen, self.tasks_blended, mode = "UNAVAILABLE", row_height=row_height*2, background=False)
            self.draw_planning(screen, self.tasks_slot1, mode = "TEXT_ONLY1", row_height=row_height*2, background=False)
            self.draw_planning(screen, self.tasks_slot2, mode = "TEXT_ONLY2", row_height=row_height*2, background=False)

            # --- Highlight des slots pendant un drag ---
            if self._drag_radar_index is not None and self._drag_started:
                for slot, color in [(self.compare_slot1, self.color_slot1), (self.compare_slot2, self.color_slot2)]:
                    hl = pygame.Surface((slot.w, slot.h), pygame.SRCALPHA)
                    hl.fill((*color, 50))
                    screen.blit(hl, slot.topleft)
                    pygame.draw.rect(screen, color, slot, 3, border_radius=8)
                    self.draw_outlined_text(screen, (slot.center[0] - int(60* self.scale), slot.center[1] - int(15 * self.scale)), 
                                            self.font, "Déposer ici", color, (0,0,0), 5)

        else :        
            status = self.font.render(self.status_message, True, (150, 200, 255))
            screen.blit(status, (self.info_rect.x, self.info_rect.bottom + int(8 * self.scale_x)))   

            self.radar.draw(screen, self.font)
            self.generate_button.draw(screen, self.button_font)
            
            reset_surf = self.reset_font.render(self.reset_text, True, (200, 80, 80))
            pygame.draw.line(reset_surf, (200, 80, 80), (0, reset_surf.get_height() - 2), (reset_surf.get_width(), reset_surf.get_height() - 2))
            screen.blit(reset_surf, self.reset_rect.topleft)
            
            if self.has_solution:
                self.draw_planning(screen, self.tasks_slot1, mode = "READ_ONLY", row_height=int(row_height*1.5), background=True)
                self.scrollbar.draw(screen) 
                self.draw_history_panel(screen)
                self.save_button.draw(screen, self.button_font)
                self.send_button.draw(screen, self.button_font)
                if len(self.history_solutions) > 0  and self.active_history_index > -1: 
                    self.compare_button.draw(screen, self.button_font)
                for activity in self.activities:
                    activity[2].draw(screen, self.tiny_font)
                    activity[2].border_color = (120, 120, 120)
                    activity[2].text_color = (255,255,255)
                if self.activ_activity != None :
                    self.activities[self.activ_activity][2].is_pressed = True
                    self.activities[self.activ_activity][2].border_color = (50, 50, 50)
                    self.activities[self.activ_activity][2].text_color = (0,0,0)

            self.draw_notifications(screen)
                
            if getattr(self, 'pending_solve', False):
                pygame.display.flip()
                self.pending_solve = False
                self._run_solver()

        if getattr(self, 'show_info_popup', False):
            title = "Signification des Métriques" if self.compare_mode == 0 else "Mode comparaison"
            lines_data = [
                ("Makespan :", "Durée globale (en jours) pour achever la totalité du planning."),
                ("Déséquilibre :", "Indice de répartition inégale du travail (en heures) en moyenne entre les différents opérateurs."),
                ("Jobflow (WIP) :", "Temps moyen d'inactivité (en heures) sur une tâche commencée mais non terminée."),
                ("Idle time :", "Temps d'inactivité cumulé de tous les opérateurs (en heures).")
            ] if self.compare_mode == 0 else [
                ("Deux plannings peuvent être affichés en parallèle.", ""),
                ("Comparaison : ","Cliquez sur un radar de l'historique pour comparer son planning avec celui du radar dans l'emplacement du haut. Vous pouvez aussi déposer un radar dans l'emplacement de votre choix"),
                ("Selection de tâche :","Cliquez sur les tâches pour construire votre planning dans la zone du bas."),
                ("Suppression de tâche :","Cliquez sur les tâches du bas pour les enlever du planning en construction."),
                ("Tâche hachurée :", "La tâche est déjà sélectionnée dans votre planning en construction."),
                ("Tâche grisée :", "Le créneau est occupé par une autre tâche déjà choisie. Cliquer dessus vous redirige vers la tâche qui bloque ce créneau."),
                ("Voir une solution :", "Une fois votre sélection faite, le solveur complète automatiquement les tâches restantes pour former un planning complet.")
            ]
            self.draw_info_popup(screen, title, lines_data)

        # --- Radar fantôme pendant le drag (dessiné au-dessus de tout sauf le tooltip) ---
        if self._drag_radar_index is not None and self._drag_started and self._drag_pos is not None:
            gx, gy = self._drag_pos
            ghost = pygame.Surface((120, 120), pygame.SRCALPHA)
            ghost.fill((0, 0, 0, 0))
            # Fond semi-transparent
            pygame.draw.circle(ghost, (40, 40, 60, 180), (60, 60), 58)
            pygame.draw.circle(ghost, (150, 150, 200, 200), (60, 60), 58, 2)
            # Mini radar centré dans le ghost
            self._draw_single_mini_radar(ghost, 60, 60, 44, self.history_solutions[self._drag_radar_index]["metrics"], "", False)
            screen.blit(ghost, (gx - 60, gy - 60))

        # --- Tooltip de survol (dessiné EN DERNIER pour être par-dessus tout) ---
        # Si aucune tâche n'a été survolée cette frame, on remet le state à zéro
        if not self._hover_found:
            self._hover_task = None
            self._hover_task_rect = None
            self._hover_start_time = None
            self._hover_pos = None

        if (self._hover_task is not None
                and self._hover_start_time is not None
                and self._hover_task_rect is not None):
            elapsed = pygame.time.get_ticks() - self._hover_start_time
            if elapsed >= self.HOVER_DELAY_MS:
                self.draw_task_tooltip(screen, self._hover_task, self._hover_task_rect)

    def _run_solver(self, time_limit=2):
        # 1. On clone les données de base
        temp_tasks = copy.deepcopy(self.raw_tasks) if self.compare_mode < 1 else self.fill_tasks(self.tasks_blended)
        temp_operators = copy.deepcopy(self.raw_operators)
        
        # 2. On s'assure que les opérateurs pointent vers les MÊMES instances de tâches
        task_dict = {t.id: t for t in temp_tasks}
        for op in temp_operators:
            op.tasks = [task_dict[t.id] for t in op.tasks if t.id in task_dict]

        exact_current_day = getattr(self, 'current_day', 0.0)
        split_day = int(math.ceil(exact_current_day - 0.05))

        # 3. Nettoyage pour le solveur
        for t in temp_tasks:
            if not self.view_sol or (not t.is_pinned and self.view_sol): 
                if exact_current_day == 0 or t.week_start >= split_day:
                    if t.assigned_to :
                        for op in temp_operators:
                            if t in op.tasks: 
                                op.tasks.remove(t)
                    t.assigned_to = None
                    t.week_start = 0
                    t.start_half = 0
                    t.is_pinned = False

        # 4. Appel direct au solveur
        solver = PlanningSolver(temp_tasks, temp_operators)
        
        # On récupère les cibles du radar
        targets = self.radar.get_targets_for_solver()

        try:
            success, msg = solver.solve(time_limit=time_limit, current_day=split_day, radar_targets=targets)
        except Exception as e:
            print(f"CRASH ÉVITÉ DANS LE SOLVEUR : {e}")
            success = False
            msg = "Erreur de communication avec CPLEX."

        # 5. Traitement de la réponse
        if success:
            self.last_metrics = getattr(solver, 'solution_metrics', {})

            snapshot = {
                "id": len(self.history_solutions),
                "name": "Solution "+str(len(self.history_solutions)),
                "tasks": copy.deepcopy(temp_tasks),
                "operators": copy.deepcopy(temp_operators),
                "metrics": copy.deepcopy(self.last_metrics)
            }

            if self.view_sol :
                self.solver_completion = snapshot
                return 

            self.add_solution(snapshot, view_sol=(not self.view_sol))

            self.status_message = "Solution trouvée !"
            self.has_solution = True
            
        else:
            self.status_message = f"Échec : {msg}"
            self.show_notification("Aucune solution trouvée avec ces contraintes.", (200, 50, 50))