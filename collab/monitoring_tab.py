import pygame
from ui_components import Button
from collab.planning_tab import Timeline, TaskBlock, Task, Operator, ACTIVITY_COLORS, DEFAULT_COLOR, draw_task_tooltip
import json
import os
import copy

class MonitoringTab:
    def __init__(self, width, height, screen):
        self.width = width
        self.height = height
        self.screen = screen
        
        # --- CALCUL DE L'ÉCHELLE ---
        self.scale_x = width / 1680.0
        self.scale_y = height / 945.0
        self.scale = min(self.scale_x, self.scale_y)
        
        # --- POLICES DYNAMIQUES ---
        self.font = pygame.font.SysFont("trebuchetms", int(20 * self.scale), bold=True)
        self.title_font = pygame.font.SysFont("trebuchetms", int(36 * self.scale), bold=True)
        
        self.is_playing = False
        self.current_day = 0.0
        self.speed = 0.02
        self.makespan = 30 
        
        self.aleas = []
        self.active_aléa = None
        self.tasks = []
        self.operators = []
        self.timeline = None
        
        # --- BOUTONS DYNAMIQUES ---
        btn_w = int(150 * self.scale_x)
        btn_h = int(60 * self.scale_y)
        self.play_pause_btn = Button(self.width//2 - btn_w//2, self.height - int(150 * self.scale_y), btn_w, btn_h, "Lecture", (50, 200, 50))
        
        replan_w = int(200 * self.scale_x)
        replan_h = int(40 * self.scale_y)
        self.replan_btn = Button(self.width//2 - replan_w//2, self.height//2 + int(50 * self.scale_y), replan_w, replan_h, "Aller Replanifier", (200, 100, 50))
        
        self.notifications = []
        self.hovered_task = None


    def show_notification(self, text, color = (240, 50, 50)):
        self.notifications.append({
            "text": text,
            "time": pygame.time.get_ticks(),
            "color": color
        })
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

    def load_scenario(self, fallback_planning, planning_file="planning_expe.json", aleas_file="aleas_expe.json"):
        path_planning = os.path.join("data", planning_file)
        path_aleas = os.path.join("data", aleas_file)
        if os.path.exists(path_planning):
            self.operators = [
                Operator(1, "Assembleur A", pool_name="Assembleur"),
                Operator(2, "Assembleur B", pool_name="Assembleur"),
                Operator(3, "Assembleur C", pool_name="Assembleur"),
                Operator(4, "Contrôleur A", pool_name="Contrôleur"),
                Operator(5, "Contrôleur B", pool_name="Contrôleur")
            ]
            with open(path_planning, 'r', encoding='utf-8') as f:
                p_data = json.load(f)
            self.tasks = [Task(**t) for t in p_data.get("tasks", [])]
            for t in self.tasks:
                if t.assigned_to:
                    for op in self.operators:
                        if op.name == t.assigned_to:
                            op.tasks.append(t)
        else:
            self.tasks = copy.deepcopy(fallback_planning.tasks)
            self.operators = copy.deepcopy(fallback_planning.operators)

        # --- NOUVEAU : Nettoyage total (Désépinglage et No-Glow) ---
        for t in self.tasks:
            t.solved_time = 0
            t.is_pinned = False 
        
        if os.path.exists(path_aleas):
            with open(path_aleas, 'r', encoding='utf-8') as f:
                self.aleas = json.load(f)
        else:
            self.aleas = []

        self.timeline = Timeline(20*self.scale_x, 90*self.scale_y, self.width - 40*self.scale_x, self.height - 100*self.scale_y, self.operators, num_days=20, row_y_factor=1.2)
        self.timeline.tasks = self.tasks
        if self.tasks:
            self.makespan = max([(t.week_start + (t.duration/8.0)) for t in self.tasks if t.assigned_to] + [30])

    def update(self):
        if self.is_playing and self.active_aléa is None and self.timeline:
            self.current_day += self.speed
            for alea in self.aleas:
                if not alea.get("triggered", False) and self.current_day+self.speed >= alea["day_trigger"]:
                    alea["triggered"] = True
                    self.active_aléa = alea
                    
                    # --- NOUVEAU : Moteur multi-effets (Découpage Simple, Entier et Sécurisé) ---
                    effects = alea.get("effects", [alea]) 
                    for eff in effects:
                        e_type = eff.get("type")
                        
                        # 1. On récupère le jour de déclenchement SPÉCIFIQUE à l'effet
                        trigger_day = float(eff.get("day_trigger", self.current_day))
                        
                        if e_type == "task_delay":
                            target_parts = [t for t in self.tasks if t.name.lower() == eff["target_task"].lower()]
                            if target_parts:
                                id_groups = {}
                                for t in target_parts:
                                    id_groups.setdefault(t.id, []).append(t)
                                for t_id, group in id_groups.items():
                                    last_part = max(group, key=lambda x: getattr(x, 'part_index', 0))
                                    last_part.duration += eff["added_duration"]
                                    last_part.delay_duration = getattr(last_part, 'delay_duration', 0) + eff["added_duration"]
                            else:
                                pass

                        elif e_type == "deadline":
                            target_name = eff.get("target_task", "")
                            new_deadline = float(eff.get("deadline_day", 10.0))
                            trouve = False
                            for t in self.tasks:
                                if t.name.lower() == target_name.lower():
                                    t.deadline = new_deadline
                                    trouve=True
                            if not trouve:
                                pass

                        elif e_type == "forced_op":
                            target_name = eff.get("target_task", "")
                            required_op = eff.get("target")
                            
                            for t in self.tasks:
                                if target_name.lower() == t.name.lower():
                                    t.forced_op = required_op
                                    if t.assigned_to and t.assigned_to != required_op:
                                        for op in self.operators:
                                            if t in op.tasks:
                                                op.tasks.remove(t)
                                        t.assigned_to = None

                        elif e_type in ["absence", "task_unavailable"]:
                            target_name = eff.get("target_task", "")
                                
                            # 2. On utilise bien le trigger_day pour couper au bon endroit !
                            u_start = int(trigger_day)
                            dur_days = eff["duration"] if e_type == "absence" else eff["duration"] / 8.0
                            u_end = int(u_start + dur_days)
                            
                            # Enregistrement pour l'affichage visuel (Les fameuses Croix !)
                            if e_type == "absence":
                                for op in self.operators:
                                    if op.name.lower() == eff["target"].lower():
                                        if not hasattr(op, 'absences'): op.absences = []
                                        op.absences.append((u_start, u_end))
                            elif e_type == "task_unavailable":
                                trouve = False
                                for t in self.tasks:
                                    if t.name.lower() == target_name.lower():
                                        if not hasattr(t, 'unavailabilities'): t.unavailabilities = []
                                        t.unavailabilities.append((u_start, u_end))
                                        trouve = True
                                if not trouve:
                                    pass
                                        
                            # Découpage chirurgical ENTIER
                            tasks_to_remove = []
                            tasks_to_add_info = [] 
                            
                            for t in self.tasks:
                                is_affected = False
                                if e_type == "absence" and t.assigned_to and t.assigned_to.lower() == eff["target"].lower(): is_affected = True
                                elif e_type == "task_unavailable" and t.name.lower() == target_name.lower(): is_affected = True
                                
                                if not is_affected or not t.assigned_to: continue
                                
                                t_start = int(t.week_start)
                                t_end = int(t.week_start + (t.duration / 8.0))
                                
                                ov_start = max(t_start, u_start)
                                ov_end = min(t_end, u_end)
                                
                                if ov_start < ov_end: # Si la tâche percute la zone
                                    tasks_to_remove.append(t)
                                    part_idx = t.part_index if t.part_index > 0 else 1
                                    
                                    dur_before_days = ov_start - t_start
                                    dur_during_days = ov_end - ov_start
                                    dur_after_days = t_end - ov_end
                                    
                                    pieces = []
                                    # 1. Tranche AVANT (Reste planifiée à sa place)
                                    if dur_before_days >= 1: 
                                        pieces.append({"dur": dur_before_days * 8, "start": t_start, "assign": t.assigned_to})
                                        
                                    # 2. Tranche PENDANT (Expulsée au panier !)
                                    if dur_during_days >= 1:
                                        pieces.append({"dur": dur_during_days * 8, "start": 0, "assign": None, "pinned": False})
                                        
                                        target_op = next((o for o in self.operators if o.name == t.assigned_to), None)
                                        if target_op:
                                            if not hasattr(target_op, 'expelled_ghosts'): target_op.expelled_ghosts = []
                                            target_op.expelled_ghosts.append({
                                                'name': t.name,
                                                'start_day': ov_start,
                                                'duration_days': dur_during_days,
                                                'alpha': 255.0
                                            })
                                        
                                    # 3. Tranche APRÈS (Reste planifiée à sa place)
                                    if dur_after_days >= 1:
                                        pieces.append({"dur": dur_after_days * 8, "start": ov_end, "assign": t.assigned_to})
                                        
                                    # Décalage des index pour la suite de la chronologie
                                    shift = len(pieces) - 1
                                    if shift > 0:
                                        for sibling in self.tasks:
                                            if sibling.activity_id == t.activity_id and sibling.name == t.name and sibling.id != t.id and sibling.part_index > t.part_index:
                                                sibling.part_index += shift
                                                
                                    # Création des nouvelles sous-tâches propres
                                    for i, p in enumerate(pieces):
                                        TaskClass = type(t)
                                        new_t = TaskClass(
                                            id=t.id, name=t.name, activity_name=t.activity_name,
                                            duration=p["dur"], activity_id=t.activity_id, pool_name=t.pool_name,
                                            week_start=p["start"], start_half=0, assigned_to=p["assign"],
                                            part_index=part_idx + i, description=t.description,
                                            deadline=getattr(t, 'deadline', None),
                                            is_pinned=p.get("pinned", False)
                                        )
                                        if hasattr(t, 'unavailabilities'): new_t.unavailabilities = copy.deepcopy(t.unavailabilities)
                                        if hasattr(t, 'delay_duration'): new_t.delay_duration = t.delay_duration
                                        tasks_to_add_info.append((t, new_t))
                                        
                            # Remplacement global (Mémoire)
                            for t in tasks_to_remove:
                                idx = self.tasks.index(t)
                                self.tasks.remove(t)
                                if t.assigned_to:
                                    for op in self.operators:
                                        if t in op.tasks: op.tasks.remove(t)

                                added_for_this = [nt for orig, nt in tasks_to_add_info if orig == t]
                                for i, nt in enumerate(added_for_this):
                                    self.tasks.insert(idx + i, nt)
                                    if nt.assigned_to:
                                        for op in self.operators:
                                            if op.name == nt.assigned_to: op.tasks.append(nt)

                    self.is_playing = False
                    self.play_pause_btn.text = "Lecture"
                    self.play_pause_btn.color = (50, 200, 50)
                    break
                    
            if self.current_day >= self.makespan:
                self.current_day = self.makespan
                self.is_playing = False
                
            viewport_width = self.timeline.rect.width - self.timeline.label_width
            current_time_px = self.current_day * self.timeline.day_width
            self.timeline.scroll_offset = max(0, min(current_time_px - (viewport_width / 2), max(0, self.timeline.total_content_width - viewport_width)))
            
    def apply_replanning(self, planning_tab):
        """Récupère et applique les données modifiées après validation de la replanification."""
        self.tasks = copy.deepcopy(planning_tab.tasks)
        self.operators = copy.deepcopy(planning_tab.operators)
        
        # On met à jour la timeline avec les nouvelles données
        self.timeline.tasks = self.tasks
        self.timeline.operators = self.operators
        
        # On recalcule la durée totale
        if self.tasks:
            self.makespan = max([(t.week_start + (t.duration/8.0)) for t in self.tasks if t.assigned_to] + [30])

    def handle_events(self, event):
        if self.active_aléa is not None:
            if self.replan_btn.handle_event(event):
                return "GOTO_PLANNING"
            return None

        if self.play_pause_btn.handle_event(event):
            self.is_playing = not self.is_playing
            self.play_pause_btn.text = "Pause" if self.is_playing else "Lecture"
            self.play_pause_btn.color = (200, 150, 50) if self.is_playing else (50, 200, 50)
            
        elif event.type == pygame.MOUSEWHEEL and not self.is_playing and self.timeline:
            self.timeline.scroll_offset -= event.y * 20 * self.scale
            self.timeline.scroll_offset = max(0, self.timeline.scroll_offset)
            
        return None
    
    def draw_alea_pointers(self):
        """Dessine un petit triangle sous la timeline à l'endroit où un aléa a eu lieu."""
        if not hasattr(self, 'aleas') or not hasattr(self, 'timeline'):
            return

        # Position Y : Juste en dessous de la timeline (tu peux augmenter le + 5 si ça touche la scrollbar)
        y_base = self.timeline.rect.bottom + 5*self.scale

        for alea in self.aleas:
            jour_declenchement = alea.get("day_trigger", 0)
            
            # On n'affiche le pointeur que si l'aléa a DÉJÀ eu lieu (ou est en train d'avoir lieu)
            if jour_declenchement <= self.current_day+self.speed:
                
                # Calcul de la position X (début du contenu + (jour * largeur d'un jour) - scroll)
                start_x = self.timeline.rect.x + getattr(self.timeline, 'label_width', 0)
                exact_x = int(start_x + (jour_declenchement * self.timeline.day_width) - self.timeline.scroll_offset)
                
                # On ne dessine le triangle que s'il est visible dans la zone de la timeline
                if start_x <= exact_x <= self.timeline.rect.right:
                    
                    # Coordonnées du triangle (Pointe en haut, base en bas)
                    points = [
                        (exact_x, y_base),           # Pointe supérieure
                        (exact_x - 10*self.scale, y_base + 15*self.scale), # Coin inférieur gauche
                        (exact_x + 10*self.scale, y_base + 15*self.scale)  # Coin inférieur droit
                    ]
                    est_resolu = alea.get("resolved", False)
                    # Bleu type "info" si résolu, Rouge type "alerte" sinon
                    couleur_triangle = (255, 160, 0) if est_resolu else (220, 50, 50)
                    # Remplissage Rouge vif
                    pygame.draw.polygon(self.screen, couleur_triangle, points)
                    # Contour Noir
                    pygame.draw.polygon(self.screen, (0, 0, 0), points, 2)

    

    def draw(self, screen):
        screen.fill((255, 255, 255))
        
        # En-tête
        time_text = self.title_font.render(f"Jour {self.current_day:.1f} / {self.makespan:.1f}", True, (0, 0, 0))
        screen.blit(time_text, (int(160 * self.scale_x), int(25 * self.scale_y)))
        self.play_pause_btn.draw(screen, self.font)
        
        # --- DESSIN DE LA TIMELINE DE MONITORING ---
        if self.timeline:
            self.timeline.rect.y = int(90 * self.scale_y)
            small_font = pygame.font.SysFont("trebuchetms", int(20 * self.scale), bold=True)
            self.timeline.draw(screen, self.font, small_font)
            self.draw_alea_pointers()
            
            content_start_x = self.timeline.rect.x + self.timeline.label_width
            current_time_px = self.current_day * self.timeline.day_width
            
            # Zone de dessin restreinte (Clip) pour ne pas déborder à gauche/droite
            visible_rect = pygame.Rect(content_start_x, self.timeline.rect.y, self.timeline.rect.width - self.timeline.label_width, self.timeline.rect.height)
            screen.set_clip(visible_rect)

            for op in self.timeline.operators:
                row_y = self.timeline.get_row_y(op)
                for t in op.tasks:
                    virtual_start_x = t.week_start * self.timeline.day_width
                    task_px_width = (t.duration / 8.0) * self.timeline.day_width
                    screen_x = content_start_x + virtual_start_x - self.timeline.scroll_offset
                    
                    if screen_x > self.width or screen_x + task_px_width < 0: continue

                    blk = TaskBlock(t, screen_x, row_y + 1, self.timeline.day_width, row_y_factor = 1.2)
                    
                    # =========================================================
                    # 1. FOND, TEXTURE ET BORDURE (La sous-couche)
                    # =========================================================
                    bg_color = ACTIVITY_COLORS.get(getattr(t, 'activity_id', 0), DEFAULT_COLOR)
                    pygame.draw.rect(screen, bg_color, blk.rect, border_radius=5)
                    # draw_activity_pattern(screen, blk.rect, t.activity_id)
                    pygame.draw.rect(screen, (50, 50, 70), blk.rect, 1, border_radius=5)

                    # =========================================================
                    # 2. TEXTE (Titre et Durée)
                    # =========================================================
                    if blk.width > 30*self.scale:
                        display_name = t.name
                        part_suffix = f" ({t.part_index})" if getattr(t, 'part_index', 0) > 0 else ""
                        
                        words = display_name.split()
                        if part_suffix and words:
                            words[-1] += part_suffix 
                            
                        max_lines = 2 if blk.rect.height > 30*self.scale else 1
                        
                        lines = []
                        current_line = ""
                        i = 0
                        
                        while i < len(words) and len(lines) < max_lines:
                            if len(lines) == 1 and max_lines == 2:
                                current_max_w = blk.width - 35*self.scale
                            else:
                                current_max_w = blk.width - 10*self.scale
                                
                            word = words[i]
                            test_line = current_line + word + " "
                            
                            if small_font.size(test_line)[0] <= current_max_w:
                                current_line = test_line
                                i += 1
                            else:
                                part = ""
                                for char in word:
                                    temp_part = part + char
                                    temp_rem = word[len(temp_part):]
                                    
                                    if temp_part.endswith("-") or temp_rem.startswith(" ") or "(" in temp_rem or ")" in temp_rem or temp_part.endswith("("):
                                        sep = ""
                                    else: sep = "-"
                                        
                                    if small_font.size(current_line + temp_part + sep)[0] <= current_max_w:
                                        part = temp_part
                                    else:
                                        break
                                
                                if len(part) > 0:
                                    temp_rem = word[len(part):]
                                    if part.endswith("-") or temp_rem.startswith(" ") or "(" in temp_rem or ")" in temp_rem or part.endswith("("):
                                        sep = ""
                                    else:
                                        sep = "-"
                                    lines.append((current_line + part + sep).strip())
                                    words[i] = temp_rem.strip()
                                    current_line = ""
                                else:
                                    if current_line:
                                        lines.append(current_line.strip())
                                        current_line = ""
                                    else:
                                        sep = "" if word.startswith("-") else "-"
                                        lines.append(word[:1] + sep)
                                        words[i] = word[1:]
                                        
                        if current_line and len(lines) < max_lines:
                            lines.append(current_line.strip())
                            
                        if len(lines) > 0:
                            last_idx = len(lines) - 1
                            last_max_w = (blk.width - 35*self.scale) if (last_idx == 1 and max_lines == 2) else (blk.width - 16*self.scale)
                            
                            if i < len(words) or small_font.size(lines[-1])[0] > last_max_w:
                                line_to_cut = lines[-1]
                                if line_to_cut.endswith("-"): line_to_cut = line_to_cut[:-1]
                                
                                while len(line_to_cut) > 0 and small_font.size(line_to_cut + "..")[0] > last_max_w:
                                    line_to_cut = line_to_cut[:-1]
                                    
                                lines[-1] = line_to_cut.strip() + ".."
                                
                        for j, line in enumerate(lines):
                            name_surf = small_font.render(line, True, (0, 0, 0))
                            y_pos = blk.rect.y + 4 + (j * 21*self.scale) 
                            
                            name_bg_rect = pygame.Rect(blk.rect.x + 4, y_pos, name_surf.get_width() + 4, name_surf.get_height() + 2)
                            pygame.draw.rect(screen, (255, 255, 255), name_bg_rect, border_radius=3)
                            screen.blit(name_surf, (blk.rect.x + 6, y_pos + 1))

                        # =========================================================
                        # ALIGNEMENT EN BAS À DROITE : Durée uniquement
                        # =========================================================
                        current_right_x = blk.rect.right - 6
                        
                        dur_surf = small_font.render(f"{t.duration}h", True, (0, 0, 0))
                        dur_w = dur_surf.get_width()
                        dur_h = dur_surf.get_height()
                        
                        dur_bg_rect = pygame.Rect(current_right_x - dur_w - 4, blk.rect.bottom - 4 - dur_h, dur_w + 4, dur_h + 2)
                        pygame.draw.rect(screen, (255, 255, 255), dur_bg_rect, border_radius=3)
                        screen.blit(dur_surf, (dur_bg_rect.x + 2, dur_bg_rect.y + 1))

                    # =========================================================
                    # 3. COUCHE GRISÉE (Le temps passé par-dessus la tâche)
                    # =========================================================
                    if current_time_px > virtual_start_x:
                        passed_width = current_time_px - virtual_start_x
                        gray_width = min(passed_width, task_px_width)
                        if gray_width > 0:
                            overlay = pygame.Surface((int(gray_width), blk.rect.height), pygame.SRCALPHA)
                            overlay.fill((50, 50, 50, 180)) 
                            screen.blit(overlay, (blk.rect.x, blk.rect.y))

                    # =========================================================
                    # 4. CADRE ROUGE DU RETARD (Peint EN DERNIER, tout au-dessus !)
                    # =========================================================
                    delay_dur = getattr(t, 'delay_duration', 0)
                    if delay_dur > 0 and t.duration > 0:
                        delay_px = int((delay_dur / t.duration) * blk.rect.width)
                        
                        if delay_px > 0:
                            delay_rect = pygame.Rect(blk.rect.right - delay_px, blk.rect.y, delay_px, blk.rect.height)
                            # Cadre gras
                            pygame.draw.rect(screen, (220, 40, 40), delay_rect, 3, border_radius=6)
                            
                            warn_surf = self.font.render(f"+{delay_dur}h", True, (220, 40, 40))
                            text_x = delay_rect.centerx - warn_surf.get_width() // 2
                            text_y = delay_rect.centery - warn_surf.get_height() // 2
                            
                            bg_rect = pygame.Rect(text_x - 2, text_y - 2, warn_surf.get_width() + 4, warn_surf.get_height() + 4)
                            bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                            bg_surface.fill((255, 255, 255, 200))
                            
                            screen.blit(bg_surface, bg_rect.topleft)
                            screen.blit(warn_surf, (text_x, text_y))

            screen.set_clip(None)

            # --- BARRE ROUGE DU TEMPS + TRIANGLE ---
            cursor_screen_x = content_start_x + current_time_px - self.timeline.scroll_offset
            if content_start_x <= cursor_screen_x <= content_start_x + visible_rect.width:
                # La ligne
                pygame.draw.line(screen, (255, 0, 0), (cursor_screen_x, self.timeline.rect.y), (cursor_screen_x, self.timeline.rect.bottom), 2)
                
                # Le triangle
                triangle_y = self.timeline.rect.y
                points = [
                    (cursor_screen_x - 8*self.scale, triangle_y - 8*self.scale), # Haut gauche
                    (cursor_screen_x + 8*self.scale, triangle_y - 8*self.scale), # Haut droite
                    (cursor_screen_x, triangle_y + 4*self.scale)      # Pointe en bas
                ]
                pygame.draw.polygon(screen, (255, 0, 0), points)

        if self.active_aléa is not None:
            # --- POPUP ALÉA DYNAMIQUE ---
            pop_w = int(500 * self.scale_x)
            pop_h = int(300 * self.scale_y)
            popup_rect = pygame.Rect(self.width//2 - pop_w//2, self.height//2 - pop_h//2, pop_w, pop_h)
            
            pygame.draw.rect(screen, (50, 50, 60), popup_rect, border_radius=10)
            pygame.draw.rect(screen, (255, 100, 100), popup_rect, 3, border_radius=10)
            
            alert_text = self.title_font.render(f"ALÉA ({self.active_aléa.get('diff', 'Inconnu')})", True, (255, 150, 100))
            screen.blit(alert_text, (popup_rect.x + int(20 * self.scale_x), popup_rect.y + int(20 * self.scale_y)))
            
            text_x = popup_rect.x + int(20 * self.scale_x)
            text_y = popup_rect.y + int(70 * self.scale_y)
            max_width = popup_rect.width - int(40 * self.scale_x)
            
            words = self.active_aléa.get('text', '').split(' ')
            lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + word + " "
                # On vérifie si la ligne avec le nouveau mot dépasse la largeur max
                if self.font.size(test_line)[0] < max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word + " "
            lines.append(current_line) # On n'oublie pas la dernière ligne !
            
            for line in lines:
                surf = self.font.render(line, True, (255, 255, 255))
                screen.blit(surf, (text_x, text_y))
                text_y += self.font.get_height() + 8 # Espacement entre les lignes
            
            self.replan_btn.rect.centerx = popup_rect.centerx
            self.replan_btn.rect.bottom = popup_rect.bottom - 20
            self.replan_btn.draw(screen, self.font)
        
        # À METTRE LORS DU MOUVEMENT DE LA SOURIS (pygame.MOUSEMOTION)
        mouse_pos = pygame.mouse.get_pos()
        current_hovered = None

        if self.timeline is not None and getattr(self.timeline, 'rect', None) and self.timeline.rect.collidepoint(mouse_pos):
            
            label_w = getattr(self.timeline, 'label_width', int(190 * self.scale_x))
            content_start_x = self.timeline.rect.x + label_w
            
            # Si on est bien dans la zone des tâches
            if mouse_pos[0] >= content_start_x:
                
                day_width = getattr(self.timeline, 'day_width', int(100 * self.scale_x))
                scroll_x = getattr(self.timeline, 'scroll_offset', 0)
                
                # On définit une épaisseur de ligne par défaut basée sur ton échelle
                assumed_row_height = getattr(self.timeline, 'row_height', int(55 * self.scale_y))
                
                for op in self.operators:
                    # On récupère le Y exact de cet opérateur !
                    row_y = self.timeline.get_row_y(op)
                    
                    # 1. La souris est-elle dans la hauteur de cette ligne ?
                    if row_y <= mouse_pos[1] <= row_y + assumed_row_height:
                        
                        # 2. Si oui, on regarde ses tâches
                        op_tasks = [t for t in self.tasks if t.assigned_to == op.name]
                        for t in op_tasks:
                            tx = content_start_x + (t.week_start * day_width) - scroll_x
                            tw = max(int((t.duration / 8.0) * day_width), 30)
                            
                            # 3. La souris est-elle sur cette tâche précise (en X) ?
                            if tx <= mouse_pos[0] <= tx + tw:
                                current_hovered = t
                                break
                                
                        break # Inutile de tester les opérateurs en dessous
                        
        if current_hovered != getattr(self, 'hovered_task', None):
            self.hovered_task = current_hovered
            self.hover_start_time = pygame.time.get_ticks()
        if self.hovered_task is not None:
            temps_ecoule = pygame.time.get_ticks() - self.hover_start_time
            if temps_ecoule > 600: 
                draw_task_tooltip(self.screen, self.hovered_task, self.scale, self.width, self.height, mouse_pos)
        else:
            self.hovered_task = None
        
        self.draw_notifications(screen)