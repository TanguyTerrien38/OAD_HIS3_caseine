import pygame
import math
import copy
import json
import tkinter as tk
from tkinter import filedialog
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional
from ui_components import Button, HorizontalScrollbar

# ==================== CONFIGURATION VISUELLE ====================

ICONS = {}

POOL_COLORS = {
    "Assembleur": (255, 190, 100),
    "Contrôleur": (130, 190, 240),
    "default": (240, 240, 240)
}

ACTIVITY_COLORS = {
    0: (170, 200, 240), # Bleu
    1: (230, 170, 170), # Rose/Rouge
    2: (170, 210, 170), # Vert
    3: (190, 170, 220), # Violet
    4: (240, 210, 150), # Sable/Orange
}

# Couleur par défaut si l'ID n'est pas trouvé
DEFAULT_COLOR = (190, 190, 190)

# --- TEMPS DE REPLANIFICATION (En secondes) ---
REPLAN_TIMEOUTS = {
    "Facile": 45,
    "Moyen": 90,
    "Difficile": 150
}

@dataclass
class UIConfig:
    scale_x: float = 1.0
    scale_y: float = 1.0
    scale: float = 1.0
    day_width_timeline: int = 140
    day_width_basket: int = 85
    row_height: int = 60
    group_spacing: int = 20

# Instance globale unique qui sera mise à jour au lancement
GUI = UIConfig()

def draw_activity_pattern(surface, rect, activity_id, color=(0, 0, 0, 120)):
    pattern_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pattern_type = activity_id % 7 
    line_color = (0, 0, 0, 120) 
    spacing = 8
    
    if pattern_type == 0: 
        for i in range(-rect.height, rect.width, spacing):
            pygame.draw.line(pattern_surf, line_color, (i, rect.height), (i + rect.height, 0), 1)
    elif pattern_type == 1: 
        for x in range(0, rect.width, spacing):
            if (x // spacing) % 2 == 0:
                pygame.draw.rect(pattern_surf, (0,0,0,50), (x, 0, spacing/2, rect.height))
    elif pattern_type == 2: 
        for y in range(0, rect.height, spacing):
            for x in range(0, rect.width, spacing):
                if (x + y) % (spacing * 2) == 0:
                    pygame.draw.circle(pattern_surf, line_color, (x, y), 1)
    elif pattern_type == 3: 
        for x in range(0, rect.width, spacing*2):
            pygame.draw.line(pattern_surf, line_color, (x, 0), (x, rect.height), 1)
        for y in range(0, rect.height, spacing*2):
            pygame.draw.line(pattern_surf, line_color, (0, y), (rect.width, y), 1)
    elif pattern_type == 4: 
        sq_spacing = 12
        for y in range(0, rect.height, sq_spacing):
            for x in range(0, rect.width, sq_spacing):
                pygame.draw.rect(pattern_surf, line_color, (x, y, 3, 3))
    elif pattern_type == 5: 
        star_spacing = 14
        for y in range(0, rect.height, star_spacing):
            for x in range(0, rect.width, star_spacing):
                offset = (star_spacing // 2) if (y // star_spacing) % 2 == 0 else 0
                cx, cy = x + offset, y
                pygame.draw.line(pattern_surf, line_color, (cx - 2, cy), (cx + 2, cy), 1)
                pygame.draw.line(pattern_surf, line_color, (cx, cy - 2), (cx, cy + 2), 1)

    surface.blit(pattern_surf, rect.topleft)

def draw_task_tooltip(screen, task, scale, width, height, mouse_pos):
    # Police de l'infobulle
    font = pygame.font.SysFont("trebuchetms", int(16*scale))
    
    name = task.name
    part_index = getattr(task, 'part_index', 0)
    if part_index > 0: name = f"{name} ({part_index})"
    lines = [f"{name}", f"Activité : {task.activity_name}"]
    if task.duration/8>=2: lines.append(f"Durée : {int(task.duration)}h ({task.duration/8:g} jours)")
    else: lines.append(f"Durée : 8h (1 jour)")
    forced_op = getattr(task, 'forced_op', None)
    assigned_op = getattr(task, 'assigned_to', None)
    if forced_op:
        lines.append(f"Opérateur : {forced_op}")
        lines.append("(Opérateur désigné)")
    elif assigned_op:
        lines.append(f"Opérateur : {assigned_op}")
    else:
        lines.append("Opérateur : Non assigné")
    if assigned_op:
        lines.append(f"Planifié au Jour {int(task.week_start) + 1}")
    if getattr(task, 'is_pinned', False): lines.append("Épinglée")
    delay = getattr(task, 'delay_duration', 0)
    if delay > 0:
        lines.append(f"Retard : +{int(delay)}h")
    deadline = getattr(task, 'deadline', None)
    if deadline is not None:
        lines.append(f"Deadline : J{int(deadline)}")
    # Calcul des dimensions de la boîte
    padding = 10*scale
    line_height = font.get_linesize() + 2
    max_width = max(font.size(line)[0] for line in lines)
    
    box_w = max_width + padding * 2
    box_h = (line_height * len(lines)) + padding * 2
    
    # Positionnement (avec décalage pour ne pas être sous la souris)
    x, y = mouse_pos[0] + 15*scale, mouse_pos[1] + 15*scale
    
    # Sécurité : on empêche l'infobulle de sortir de l'écran
    if x + box_w > width:
        x = mouse_pos[0] - box_w - 5
    if y + box_h > height:
        y = mouse_pos[1] - box_h - 5
        
    # Dessin du fond et de la bordure
    tooltip_rect = pygame.Rect(x, y, box_w, box_h)
    pygame.draw.rect(screen, (30, 35, 45), tooltip_rect, border_radius=int(scale*6)) # Fond sombre
    pygame.draw.rect(screen, (100, 150, 200), tooltip_rect, 1, border_radius=int(scale*6)) # Bordure bleutée
    
    # Rendu du texte
    for i, line in enumerate(lines):
        color = (255, 255, 255) if i == 0 else (200, 200, 200)
        text_surf = font.render(line, True, color)
        screen.blit(text_surf, (x + padding, y + padding + i * line_height))

def draw_absence_pattern(surface, rect):
    overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    overlay.fill((255, 50, 50, 60)) # Rouge transparent
    # Hachures (Noires transparentes, espacées de 20)
    for x in range(-rect.height, rect.width, 20):
        pygame.draw.line(overlay, (0, 0, 0, 80), (x, rect.height), (x + rect.height, 0), 2)
    surface.blit(overlay, rect.topleft)

@dataclass
class Task:
    id: int
    name: str
    activity_name: str
    duration: int
    activity_id: int
    pool_name: str
    assigned_to: Optional[str] = None
    forced_op: Optional[str] = None
    part_index: int = 0
    week_start: int = -1
    start_half: int = 0
    description: str = ""
    solved_time: int = 0
    is_pinned: bool = False
    delay_duration: float = 0.0
    deadline: Optional[int] = None
    
    def get_weeks_span(self) -> float:
        return self.duration / 8.0

@dataclass
class Operator:
    id: int
    name: str
    color: Tuple[int, int, int] = (250, 250, 250)
    pool_name: str = ""
    tasks: List[Task] = field(default_factory=list)
    absences: List[Tuple[float, float]] = field(default_factory=list) 

    def get_total_hours(self) -> int:
        return sum(task.duration for task in self.tasks)

def draw_arrow(surface, start, end, color=(100, 100, 120)):
    pygame.draw.line(surface, color, start, end, 2)
    pygame.draw.polygon(surface, color, [
        (end[0], end[1]), (end[0]-6, end[1]-4), (end[0]-6, end[1]+4)
    ])

def wrap_text_with_hyphens(text: str, font: pygame.font.Font, max_lines: int, max_widths: List[int]) -> List[str]:
    """Découpe intelligemment un texte avec des tirets pour qu'il tienne dans des boîtes."""
    words = text.split()
    lines = []
    current_line = ""
    i = 0
    
    while i < len(words) and len(lines) < max_lines:
        current_max_w = max_widths[len(lines)] if len(lines) < len(max_widths) else max_widths[-1]
        word = words[i]
        test_line = current_line + word + " "
        
        if font.size(test_line)[0] <= current_max_w:
            current_line = test_line
            i += 1
        else:
            # --- NOUVEAUTÉ : On protège les (1), (2)... pour ne pas les couper ---
            # Si le mot est entre parenthèses, court, et qu'on n'est pas au début d'une ligne, 
            # on le bascule entier sur la ligne suivante.
            if word.startswith("(") and word.endswith(")") and len(word) <= 5 and current_line:
                lines.append(current_line.strip())
                current_line = ""
                continue # On retente de placer ce mot "(x)" sur la nouvelle ligne vide
                
            part = ""
            for char in word:
                temp_part = part + char
                temp_rem = word[len(temp_part):]
                sep = "" if (temp_part.endswith("-") or temp_rem.startswith(" ") or temp_rem.startswith("(")) else "-"
                    
                if font.size(current_line + temp_part + sep)[0] <= current_max_w:
                    part = temp_part
                else: break
                    
            if len(part) > 0:
                temp_rem = word[len(part):]
                sep = "" if (part.endswith("-") or temp_rem.startswith(" ") or temp_rem.startswith("(")) else "-"
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
        
    if i < len(words) and len(lines) == max_lines:
        last_line = lines[-1]
        if last_line.endswith("-"): last_line = last_line[:-1]
        last_max_w = max_widths[-1]
        while len(last_line) > 0 and font.size(last_line + "..")[0] > last_max_w: 
            last_line = last_line[:-1]
        lines[-1] = last_line.strip() + ".."
        
    return lines

class ActivityBox:
    def __init__(self, id: int, name: str, x: int, y: int, font: pygame.font.Font, scale_x=1.0, scale_y=1.0):
        self.id = id
        self.name = name
        text_width, _ = font.size(name)
        self.scale = min(scale_x, scale_y)
        box_width = max(int(130 * scale_x), text_width + int(30 * scale_x))
        self.rect = pygame.Rect(x, y, box_width, int(40 * scale_y))
        self.is_expanded = False
        self.color = (100, 150, 180)
        
    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        bg_color = ACTIVITY_COLORS.get(self.id, DEFAULT_COLOR)
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=int(self.scale*8))
        # draw_activity_pattern(surface, self.rect, self.id)
        if self.is_expanded: pygame.draw.rect(surface, (60, 60, 80), self.rect, 4, border_radius=int(self.scale*8))
        else: pygame.draw.rect(surface, (60, 60, 80), self.rect, 1, border_radius=int(self.scale*8))
        text_color = (255, 255, 255) if not self.is_expanded else (0,0,0)
        text = font.render(self.name, True, text_color)
        surface.blit(text, text.get_rect(center=self.rect.center))

class TaskBlock:
    RESIZE_HANDLE_WIDTH = 8
    def __init__(self, task: Task, x: int, y: int, week_width: int, row_y_factor = 1.0, scale = 1.0):
        self.task = task
        self.scale = scale
        self.week_width = week_width
        self.width = max(int(task.get_weeks_span() * week_width), 30)
        self.height = GUI.row_height * row_y_factor - 2
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.clip_rect = None
        self.is_hovered = False
        self.is_dragging = False
        self.is_resizing_left = False
        self.is_resizing_right = False
        self.drag_offset = (0, 0)
        self.resize_start_width = 0
        self.resize_start_x = 0
        self.base_color = POOL_COLORS.get(task.pool_name, POOL_COLORS["default"])

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font, highlight=None):
        if hasattr(self, 'clip_rect') and self.clip_rect:
            surface.set_clip(self.clip_rect)
        bg_color = ACTIVITY_COLORS.get(getattr(self.task, 'activity_id', 0), DEFAULT_COLOR)
        
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=int(self.scale*12))
        
        num_shifts = int(self.task.duration / 8)
        if num_shifts > 1:
            dash_length = 3
            dash_gap = 2
            y_margin = 2
            dot_color = (200, 200, 200)
            for i in range(1, num_shifts):
                sep_x = self.rect.x + int(i * self.week_width)
                if sep_x < self.rect.right - 2:
                    current_y = self.rect.y + y_margin
                    while current_y < self.rect.bottom - y_margin:
                        end_y = min(current_y + dash_length, self.rect.bottom - y_margin)
                        pygame.draw.line(surface, dot_color, (sep_x, current_y), (sep_x, end_y), 1)
                        current_y += dash_length + dash_gap

        strip_width = int(10*self.scale)
        
        pygame.draw.rect(surface, bg_color, self.rect, 2, border_radius=int(self.scale*8))
        pygame.draw.rect(surface, self.base_color, (self.rect.x, self.rect.y, strip_width, self.rect.height), border_top_left_radius=int(self.scale*8), border_bottom_left_radius=int(self.scale*8))

        # GLOW
        solved_time = getattr(self.task, 'solved_time', 0)
        if solved_time > 0:
            time_since_solved = pygame.time.get_ticks() - solved_time
            if 0 < time_since_solved < 2000:
                pulse = abs(math.sin((time_since_solved / 1000.0) * math.pi))
                r, g, b = int(200 + 55 * pulse), int(200 + 15 * pulse), int(200 - 200 * pulse)
                pygame.draw.rect(surface, (r, g, b), self.rect.inflate(6, 6), 3, border_radius=int(self.scale*12))
                pygame.draw.rect(surface, (r, g, b), self.rect.inflate(14, 14), 1, border_radius=int(self.scale*15))
        
        if self.width > 30:
            display_name = self.task.name
            part_suffix = f" ({self.task.part_index})" if getattr(self.task, 'part_index', 0) > 0 and not getattr(self, 'is_dragging', False) else ""
            if part_suffix: display_name += part_suffix
                
            max_lines = 2 if self.rect.height > GUI.row_height / 2 + 1 else 1
            last_line_width = (self.width - strip_width - int(35 * self.scale)) if max_lines == 2 else (self.width - strip_width - int(16 * self.scale))
            max_widths = [(self.width - strip_width - 10)] * max(0, max_lines - 1) + [last_line_width]
            
            lines = wrap_text_with_hyphens(display_name, small_font, max_lines, max_widths)
            
            line_height = int(small_font.get_height()) 
            for j, line in enumerate(lines):
                name_surf = small_font.render(line, True, (0, 0, 0))
                y_pos = self.rect.y + 4 + (j * line_height) 
                name_bg_rect = pygame.Rect(self.rect.x + strip_width + 4, y_pos, name_surf.get_width() + 4, name_surf.get_height() + 2)
                pygame.draw.rect(surface, (255, 255, 255), name_bg_rect, border_radius=4*int(self.scale))
                surface.blit(name_surf, (self.rect.x + strip_width + 6, y_pos + 1))

            current_right_x = self.rect.right - 6
            if self.rect.height > GUI.row_height/2 + 1:
                dur_surf = small_font.render(f"{self.task.duration}h", True, (0, 0, 0))
                dur_bg_rect = pygame.Rect(current_right_x - dur_surf.get_width() - 4, self.rect.bottom - 4 - dur_surf.get_height(), dur_surf.get_width() + 4, dur_surf.get_height() + 2)
                pygame.draw.rect(surface, (255, 255, 255), dur_bg_rect, border_radius=int(self.scale*4))
                surface.blit(dur_surf, (dur_bg_rect.x + 2, dur_bg_rect.y + 1))
                current_right_x = dur_bg_rect.x - 4

        # 2. Dessin de l'épingle (Placement dynamique au pixel près)
        if getattr(self.task, 'is_pinned', False):
            # On récupère la vraie taille de l'icône, ou 8 pixels par défaut si absente
            icon_w = ICONS['punaise'].get_width() if 'punaise' in ICONS else 8
            icon_h = ICONS['punaise'].get_height() if 'punaise' in ICONS else 8
            
            px = current_right_x - icon_w - 4
            py = self.rect.bottom - icon_h - 4
            
            if 'punaise' in ICONS: 
                surface.blit(ICONS['punaise'], (px, py))
            else: 
                pygame.draw.circle(surface, (220, 40, 40), (px+4, py+4), 4)
            
            current_right_x = px - 4

        # 3. Dessin du bonhomme worker (Placement dynamique)
        if getattr(self.task, 'forced_op', None):
            icon_w = ICONS['worker'].get_width() if 'worker' in ICONS else 8
            icon_h = ICONS['worker'].get_height() if 'worker' in ICONS else 8
            icon_x = current_right_x - icon_w - 4
            icon_y = self.rect.bottom - icon_h - 4
            if 'worker' in ICONS: 
                surface.blit(ICONS['worker'], (icon_x, icon_y))
            else: 
                pygame.draw.circle(surface, (50, 50, 150), (icon_x+4, icon_y+4), 4)
            
        delay_dur = getattr(self.task, 'delay_duration', 0)
        if delay_dur > 0 and self.task.duration > 0:
            delay_px = int((delay_dur / self.task.duration) * self.rect.width)
            if delay_px > 0:
                delay_rect = pygame.Rect(self.rect.right - delay_px, self.rect.y, delay_px, self.rect.height)
                pygame.draw.rect(surface, (220, 40, 40), delay_rect, 4, border_radius=int(self.scale*12))
                
                if 'small_font' not in locals(): small_font = pygame.font.Font(None, 18)
                warn_surf = small_font.render(f"+{delay_dur}h", True, (220, 40, 40))
                text_x = delay_rect.centerx - warn_surf.get_width() // 2
                text_y = delay_rect.centery - warn_surf.get_height() // 2
                
                bg_rect = pygame.Rect(text_x - 2, text_y - 2, warn_surf.get_width() + 4, warn_surf.get_height() + 4)
                bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                bg_surface.fill((255, 255, 255, 200))
                surface.blit(bg_surface, bg_rect.topleft)
                surface.blit(warn_surf, (text_x, text_y))

        if hasattr(self, 'clip_rect') and self.clip_rect:
            surface.set_clip(None)
    
    def handle_mouse_down(self, pos: Tuple[int, int]) -> str:
        if self.rect.collidepoint(pos):
            self.is_dragging = True; self.drag_offset = (pos[0]-self.rect.x, pos[1]-self.rect.y); return 'drag'
        return None
    
    def handle_mouse_up(self): self.is_dragging = self.is_resizing_left = self.is_resizing_right = False
    def handle_mouse_motion(self, pos: Tuple[int, int]):
        self.is_hovered = self.rect.collidepoint(pos)
        if self.is_dragging: self.rect.x, self.rect.y = pos[0]-self.drag_offset[0], pos[1]-self.drag_offset[1]

class TaskCard:
    def __init__(self, task: Task, x: int, y: int, font: pygame.font.Font, scale):
        self.task = task
        self.scale = scale
        duration_in_days = task.duration / 8.0
        base_width = duration_in_days * GUI.day_width_basket
        if task.duration == 8:base_width *= 1.2
        self.width = max(int(base_width), 40)
        self.height = GUI.row_height
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.is_hovered = self.is_dragging = False
        self.drag_offset = (0, 0)
        self.pool_color = POOL_COLORS.get(task.pool_name, POOL_COLORS["default"])
    
    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font):
        is_planned = self.task.assigned_to is not None
        
        if is_planned:
            bg_color = (235, 235, 235)
            border_color = (180, 180, 180)
            text_color = (150, 150, 150)
            bar_color = (180, 180, 180) 
        else:
            bg_color = ACTIVITY_COLORS.get(getattr(self.task, 'activity_id', 0), DEFAULT_COLOR)
            border_color = (100, 100, 120)
            text_color = (20, 20, 40)
            bar_color = self.pool_color 

        pygame.draw.rect(surface, bg_color, self.rect, border_radius=int(self.scale*6))
        
        num_shifts = int(self.task.duration / 8)
        if num_shifts > 1:
            dash_length = 3
            dash_gap = 2
            y_margin = 4
            dot_color = (0, 0, 0) if not is_planned else (50, 50, 50)
            for i in range(1, num_shifts):
                sep_x = self.rect.x + int(i * GUI.day_width_basket)
                if sep_x < self.rect.right - 2:
                    current_y = self.rect.y + y_margin
                    while current_y < self.rect.bottom - y_margin:
                        end_y = min(current_y + dash_length, self.rect.bottom - y_margin)
                        pygame.draw.line(surface, dot_color, (sep_x, current_y), (sep_x, end_y), 1)
                        current_y += dash_length + dash_gap

        pygame.draw.rect(surface, border_color, self.rect, 2, border_radius=int(self.scale*6))
        pygame.draw.rect(surface, bar_color, (self.rect.x, self.rect.y, 8, self.rect.height), border_top_left_radius=int(self.scale*6), border_bottom_left_radius=int(self.scale*6))
        
        
        dur_color = (100, 100, 100) if not is_planned else text_color
        dur_surf = small_font.render(f"{self.task.duration}h", True, dur_color)
        dur_w = dur_surf.get_width()

        display_name = self.task.name
        part_suffix = f" ({self.task.part_index})" if getattr(self.task, 'part_index', 0) > 0 and not getattr(self, 'is_dragging', False) else ""
        if part_suffix: display_name += part_suffix
            
        max_widths = [self.rect.width - 16, self.rect.width - 16, self.rect.width - dur_w - 25]
        lines = wrap_text_with_hyphens(display_name, small_font, 3, max_widths)

        # 4. Affichage final
        line_height = int(small_font.get_height() * 0.85)
        x_name = self.rect.x + 12
        for j, line in enumerate(lines):
            y_name = self.rect.y + 4 + (j * line_height)
            surface.blit(small_font.render(line, True, text_color), (x_name, y_name))
            
        # On place la durée tout en bas à droite
        dur_x = self.rect.right - dur_w - 8
        dur_y = self.rect.bottom - dur_surf.get_height() - 4
        surface.blit(dur_surf, (dur_x, dur_y))

    def handle_mouse_down(self, pos: Tuple[int, int]) -> bool:
        if self.task.assigned_to is not None:
            return False
        if self.rect.collidepoint(pos):
            self.is_dragging = True
            self.drag_offset = (pos[0]-self.rect.x, pos[1]-self.rect.y)
            return True
        return False

    def handle_mouse_up(self): self.is_dragging = False
    def handle_mouse_motion(self, pos: Tuple[int, int]):
        if self.task.assigned_to is None:
            self.is_hovered = self.rect.collidepoint(pos)
        if self.is_dragging: 
            self.rect.x, self.rect.y = pos[0]-self.drag_offset[0], pos[1]-self.drag_offset[1]

class Timeline:
    def __init__(self, x: int, y: int, width: int, height: int, operators: List[Operator], num_days: int = 15, row_y_factor = 1.0):
        self.rect = pygame.Rect(x, y, width, height) 
        self.operators = operators
        self.total_days = 20
        desktop_sizes = pygame.display.get_desktop_sizes()
        self.scale_x = desktop_sizes[0][0] / 1680.0
        self.scale_y = desktop_sizes[0][1] / 945.0
        self.label_width = int(200 * self.scale_x)
        self.header_height = int(60 * self.scale_y)
        self.row_height = GUI.row_height * row_y_factor
        self.scroll_offset = 0
        self.day_width = GUI.day_width_timeline
        self.total_content_width = self.day_width * self.total_days
        if self.operators:
            last_op_index = len(self.operators) - 1
            last_op_y = self.get_row_y_by_index(last_op_index)
            self.rect.height = (last_op_y + self.row_height) - self.rect.y + int(10 * self.scale_y) 
        else: self.rect.height = int(100 * self.scale_y)
        self.tasks = []
        self.timeline_combined = False
        self.timeline_combined = False

    def get_row_y_by_index(self, index: int) -> int:
        current_y = self.rect.y + self.header_height
        for i in range(index):
            current_y += self.row_height
            if i < len(self.operators) - 1:
                if self.operators[i].pool_name != self.operators[i+1].pool_name:
                    current_y += GUI.group_spacing
        return current_y

    def get_row_y(self, operator: Operator) -> int:
        try: return self.get_row_y_by_index(self.operators.index(operator))
        except ValueError: return 0

    def get_operator_at_position(self, y: int) -> Optional[Operator]:
        for i, op in enumerate(self.operators):
            op_y = self.get_row_y_by_index(i)
            if op_y <= y < op_y + self.row_height: return op
        return None

    def get_week_at_position(self, x: int) -> int:
        content_start_x = self.rect.x + self.label_width
        if x < content_start_x: return 0
        relative_x = (x - content_start_x) + self.scroll_offset
        day_index = relative_x // self.day_width
        return min(max(int(day_index), 0), self.total_days - 1)

    def draw_gauge(self, surface, gauge, x, y, height, max_days, small_font: pygame.font.Font):
        dw = self.day_width
        rh = self.row_height
        left = x + dw 
        right = x + 4*dw 
        top_left = (left, y + rh // 3)
        top_right = (right, y + rh // 3)
        bottom_left = (left, y + height - rh // 4)
        bottom_right = (right, y + height - rh // 4)
        day_height = (bottom_left[1] - top_left[1] - int(10 * self.scale_y)) / max_days
        pygame.draw.line(surface, (0,0,0), top_left, bottom_left, 3)
        pygame.draw.line(surface, (0,0,0), top_right, bottom_right, 3)
        pygame.draw.line(surface, (0,0,0), bottom_left, bottom_right, 3)
        activity_width = right - left - 3
        floor = bottom_left[1] - 1
        hours = 0
        for activity_id, day in gauge.items():
            if day == 0 or floor < y: continue
            color = ACTIVITY_COLORS.get(activity_id, DEFAULT_COLOR)
            activity_height = int(day * day_height) if (floor - int(day * day_height) > y) else (floor - y)
            rect = pygame.Rect(left + 2, floor - activity_height, activity_width, activity_height)
            pygame.draw.rect(surface, color, rect)
            floor -= activity_height 
            hours += day*8
        
        max_hours = max_days * 8
        hr_color = (10,10,10) if hours <= max_hours else (255,0,0)
        max_hr_color = (0,255,0) if hours <= max_hours else (255,0,0)
        hours_surf = small_font.render(f"{int(hours)}h", True, hr_color)
        max_hours_surf = small_font.render(f"{int(max_hours)}h", True, max_hr_color)
        y_max = bottom_left[1] - day_height * max_days 
        surface.blit(hours_surf, (right + int(10* self.scale_x), max((floor - hours_surf.get_height()//2), y)))
        surface.blit(max_hours_surf, (left - max_hours_surf.get_width() - int(10* self.scale_x), y_max - max_hours_surf.get_height()//2))
        
        dash_width = activity_width / 19
        for i in range(left + 2, right - 4, int(dash_width * 2)):
            pygame.draw.line(surface, max_hr_color, (i, y_max), (i + int(dash_width)+2, y_max), 2)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font, tasks: List[Task] = None):
        pygame.draw.rect(surface, (250, 250, 255), self.rect, border_radius=int(self.scale_x*10))
        
        last_op_index = len(self.operators) - 1
        last_op_y = self.get_row_y_by_index(last_op_index)
        content_bottom_y = last_op_y + self.row_height

        clip_rect = pygame.Rect(self.rect.x + self.label_width, self.rect.y, self.rect.width - self.label_width, self.rect.height)
        start_x_content = self.rect.x + self.label_width
        
        # Fond général
        pygame.draw.rect(surface, (250, 250, 255), self.rect, border_radius=int(self.scale_x*10))

        # Titre "Opérateurs" ou "Équipes"
        titre_font = pygame.font.SysFont("trebuchetms", int(28 * self.scale_x), bold=True)
        titre_surf = titre_font.render("Opérateurs", True, (100, 100, 120))
        titre_x = self.rect.x + 10
        titre_y = self.rect.y + (self.header_height - titre_surf.get_height()) // 2
        
        surface.blit(titre_surf, (titre_x, titre_y))
        ry, row_height = None, None
        total_hours = None
        op_pools = []
        for i, op in enumerate(self.operators):
            #si on est au début d'un groupe d'opérateur : on initialise les valeurs
            if not self.timeline_combined or i == 0 or op.pool_name != self.operators[i-1].pool_name:
                ry = self.get_row_y_by_index(i)
                row_height = self.row_height
                total_hours = op.get_total_hours()
                op_pools.append((op.pool_name, ry))
            #sinon on les incrémente
            else :
                row_height += self.row_height
                total_hours += op.get_total_hours()
            #si on arrive à la fin d'un groupe d'opérateurs : on déssine la ligne
            if not self.timeline_combined or i == len(self.operators)-1 or op.pool_name != self.operators[i+1].pool_name :
                op_pools[-1] = op_pools[-1] + (row_height,)
                row_rect = pygame.Rect(self.rect.x, ry, self.rect.width, row_height)
                pygame.draw.rect(surface, (245, 245, 250), row_rect)
                pygame.draw.rect(surface, op.color, (self.rect.x, ry, self.label_width, row_height))
                pool_color = POOL_COLORS.get(op.pool_name, (100, 100, 100))
                strip_width = int(10*self.scale_x)
                white_sep_width = 3
                pygame.draw.rect(surface, (255, 255, 255), (self.rect.x + self.label_width - strip_width - white_sep_width, ry, white_sep_width, row_height))
                pygame.draw.rect(surface, pool_color, (self.rect.x + self.label_width - strip_width, ry, strip_width, row_height))
                
                name_surf = font.render( f"{op.pool_name}s" if self.timeline_combined else op.name, True, (0,0,0))
                hours_surf = small_font.render(f"{total_hours}h", True, (0,0,0))
                total_text_h = name_surf.get_height() + hours_surf.get_height() + 2
                start_text_y = ry + (row_height - total_text_h) // 2
                
                surface.blit(name_surf, (self.rect.x+10, start_text_y))
                surface.blit(hours_surf, (self.rect.x+10, start_text_y + name_surf.get_height() + 2))
                
                pygame.draw.rect(surface, (200, 200, 210), row_rect, 1)

                # La grosse ligne de séparation entre deux équipes différentes
                if i < len(self.operators) - 1:
                    if op.pool_name != self.operators[i+1].pool_name:
                        sep_y = ry + row_height + (GUI.group_spacing // 2)
                        pygame.draw.line(surface, (180, 180, 200), (self.rect.x, sep_y), (self.rect.right, sep_y), 3)

        # Hachures d'absence
        surface.set_clip(clip_rect)
        start_x_content = self.rect.x + self.label_width
        for i, op in enumerate(self.operators):
            ry = self.get_row_y_by_index(i)
            for abs_start, abs_end in op.absences:
                abs_x = start_x_content + abs_start * self.day_width - self.scroll_offset
                abs_w = (abs_end - abs_start) * self.day_width
                if abs_x + abs_w > clip_rect.left and abs_x < clip_rect.right:
                    draw_absence_pattern(surface, pygame.Rect(abs_x, ry + 1, abs_w, self.row_height - 2))

        if not self.timeline_combined :
            for d in range(self.total_days):
                vx = start_x_content + d * self.day_width - self.scroll_offset
                if vx + self.day_width < clip_rect.left or vx > clip_rect.right: continue
                pygame.draw.line(surface, (230, 230, 240), (vx, self.rect.y+ self.header_height//2), (vx, content_bottom_y), 2)
                label = f"J{d+1}"
                lbl_surf = small_font.render(label, True, (60, 60, 80))
                lbl_x = vx + (self.day_width - lbl_surf.get_width()) // 2
                lbl_y = self.rect.y + self.header_height // 2 + int(3 * self.scale_y)
                surface.blit(lbl_surf, (lbl_x, lbl_y))
            pygame.draw.line(surface, (0,0,0), (self.rect.x, self.rect.y + self.header_height//2),
                             (self.rect.x + self.total_content_width, self.rect.y + self.header_height//2))

        for w in range(0, self.total_days, 5):
            vx = start_x_content + w * self.day_width - self.scroll_offset
            if vx + self.day_width < clip_rect.left or vx > clip_rect.right: continue
            pygame.draw.line(surface, (200, 200, 220), (vx, self.rect.y), (vx, content_bottom_y), 2)
            label = f"Semaine {w//5+1}"
            lbl_surf = small_font.render(label, True, (60, 60, 80))
            lbl_x = vx + 2.5 * self.day_width - lbl_surf.get_width() // 2
            lbl_y = self.rect.y  + ((self.header_height * 0.3) if self.timeline_combined else int(3 * self.scale_y))
            surface.blit(lbl_surf, (lbl_x, lbl_y))
            if self.timeline_combined :
                for op in op_pools: #on rempli la jauge pour chaque groupe d'opérateurs
                    gauge = {0:0 ,1:0 ,2:0 ,3:0}    # (identifiant de la tâche , nombre de jours sur cette tâche cette semaine)
                    for t in tasks:
                        if t.pool_name == op[0] and t.week_start != -1:
                            duration = int(t.get_weeks_span())
                            task_end = t.week_start + duration
                            if t.week_start < w and task_end > w :
                                gauge[t.activity_id] += task_end - w
                            if t.week_start >= w and task_end <= (w+5):
                                gauge[t.activity_id] += duration
                            if t.week_start < (w+5) and task_end > (w+5) :
                                gauge[t.activity_id] += (w+5) - t.week_start
                    # puis on déssine la jauge
                    self.draw_gauge(surface, gauge, vx, op[1], op[2], 15 if op[0] == "Assembleur" else 10, small_font)    
                    # je n'ai pas encore trouvé le moyen de choisir le nombre de jours max de dispo

        header_rect = pygame.Rect(self.rect.x, self.rect.y, self.rect.width, self.header_height)
        pygame.draw.rect(surface, (0, 0, 0), header_rect, 1)
        surface.set_clip(None)
        sep_x = self.rect.x + self.label_width
        pygame.draw.line(surface, (0, 0, 0), (sep_x, self.rect.y), (sep_x, content_bottom_y), 2)

class TaskBasket:
    # On ajoute scale_x et scale_y en paramètres
    def __init__(self, x: int, y: int, width: int, height: int, scale_x=1.0, scale_y=1.0):
        self.rect = pygame.Rect(x, y, width, height)
        self.scale_x = scale_x
        self.scale_y = scale_y

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, count: int, total: int):
        header_h = int(40 * self.scale_y)
        pygame.draw.rect(surface, (245, 245, 250), self.rect, border_radius=int(self.scale_x*12))
        pygame.draw.rect(surface, (100, 120, 150), self.rect, 2, border_radius=int(self.scale_x*12))
        pygame.draw.rect(surface, (100, 120, 150), (self.rect.x, self.rect.y, self.rect.width, header_h), border_top_left_radius=int(self.scale_x*12), border_top_right_radius=int(self.scale_x*12))
        
        title_font = pygame.font.SysFont("trebuchetms", int(26 * self.scale_x), bold=True)
        title = title_font.render(f"Composants - tâches ({count}/{total})", True, (255, 255, 255))
        margin_x = int(20 * self.scale_x)
        surface.blit(title, (self.rect.x + margin_x, self.rect.y + (header_h - title.get_height()) // 2))

# ==================== CLASSE PRINCIPALE ONGLET PLANIFICATION ====================

from solver_cpo import PlanningSolver

class PlanningTab:
    def __init__(self, width, height, screen, tutorial=None):
        self.tutorial = tutorial
        self.width = width
        self.height = height
        self.screen = screen
        
        # --- CALCUL DE L'ÉCHELLE ---
        self.scale_x = width / 1680.0
        self.scale_y = height / 945.0
        self.scale = min(self.scale_x, self.scale_y)

        GUI.scale_x = self.scale_x
        GUI.scale_y = self.scale_y
        GUI.scale = self.scale
        GUI.day_width_timeline = int(140 * self.scale_x)
        GUI.day_width_basket = int(85 * self.scale_x)
        GUI.row_height = int(60 * self.scale_y)
        GUI.group_spacing = int(20 * self.scale_y)

        self.font = pygame.font.SysFont("trebuchetms", int(24 * self.scale))
        self.small_font = pygame.font.SysFont("trebuchetms", int(20 * self.scale))
        
        self.notifications = [] 
        
        self.init_data()
        
        # --- ÉLÉMENTS DE L'INTERFACE DYNAMIQUES ---
        self.timeline = Timeline(int(20 * self.scale_x), int(90 * self.scale_y), self.width - int(40 * self.scale_x), 0, self.operators, num_days=20)
        self.scrollbar = HorizontalScrollbar(0, 0, 100, int(12 * self.scale_y), 0, 0)
        self.task_basket = TaskBasket(int(20 * self.scale_x), 0, self.width - int(40 * self.scale_x), 0, self.scale_x, self.scale_y)
        self.dragged_item = None
        self.drag_day_offset = 0
        self.expanded_activity_id = None
        self.activity_boxes = []
        
        self.current_day = 0.0
        self.is_replanning = False
        self.use_horizon_limit = False

        self.known_lower_bound = 0.0
        self.last_opt_day = -1
        self.last_opt_makespan = None

        # --- BOUTONS DYNAMIQUES ---
        btn_h = int(40 * self.scale_y)
        self.validate_replan_btn = Button(0, 0, int(330 * self.scale_x), int(40 * self.scale_y), "VALIDER LA REPLANIFICATION", (255, 140, 0))
        self.save_button = Button(0, 0, int(180 * self.scale_x), btn_h, "Sauvegarder")
        self.load_button = Button(0, 0, int(180 * self.scale_x), btn_h, "Charger", (100, 150, 200))
        self.reset_button = Button(0, 0, int(180 * self.scale_x), btn_h, "Reinitialiser", (180, 80, 80))
        
        self.solve_button = Button(0, 0, int(220 * self.scale_x), btn_h, "Nouvelle solution", (80, 180, 100))
        self.repair_button = Button(0, 0, int(220 * self.scale_x), btn_h, "Réparer le planning", (220, 140, 40))
        self.all_combine_button = Button(0, 0, int(255 * self.scale_x), btn_h, "Agréger le planning", (100, 150, 200))

        self.current_seed = 1

        self.history = []
        self.redo_stack = []
        self.undo_rect = pygame.Rect(0, 0, int(50 * self.scale), int(50 * self.scale))
        self.redo_rect = pygame.Rect(0, 0, int(50 * self.scale), int(50 * self.scale))
        self.cut_rect = pygame.Rect(0, 0, int(40 * self.scale), int(40 * self.scale))
        self.cut_mode = False
        self.hovered_task = None
        self.hover_start_time = 0
        self.basket_scroll = 0

        self.current_errors = []
        self.show_full_errors_popup = False
        self.error_box_rect = pygame.Rect(0, 0, 0, 0)
        self.close_error_popup_rect = pygame.Rect(0, 0, 0, 0)

        # --- AREA SELECTION (sélection rectangle sur la timeline) ---
        self._area_sel_start = None       # (x, y) pixel où le clic a démarré
        self._area_sel_current = None     # (x, y) position souris courante pendant le tracé
        self._selected_task_ids = set()   # set de task.id actuellement sélectionnés
        self._sel_action_rects = {}       # { label: pygame.Rect } des boutons d'action groupée

        # --- MULTI-DRAG (déplacement groupé) ---
        self._multi_drag_active = False        # True quand on déplace toute la sélection
        self._multi_drag_leader = None         # TaskBlock pilote (celui qu'on a saisi)
        self._multi_drag_offsets = {}          # { task.id: (day_offset, op_index) } positions relatives
        self._multi_drag_preview = {}          # { task.id: (target_week, target_op) } pendant le survol

        # --- ICONES DYNAMIQUES (Tailles ajustées) ---
        import os
        try:
            ICONS['punaise'] = pygame.transform.smoothscale(pygame.image.load(os.path.join("assets", "punaise.png")).convert_alpha(), (int(18 * self.scale), int(18 * self.scale)))
            ICONS['worker'] = pygame.transform.smoothscale(pygame.image.load(os.path.join("assets", "worker.png")).convert_alpha(), (int(18 * self.scale), int(20 * self.scale)))
            ICONS['ciseaux'] = pygame.transform.smoothscale(pygame.image.load(os.path.join("assets", "ciseaux.png")).convert_alpha(), (int(28 * self.scale), int(28 * self.scale)))
            ICONS['undo'] = pygame.transform.smoothscale(pygame.image.load(os.path.join("assets", "fleche_undo.png")).convert_alpha(), (int(32 * self.scale), int(32 * self.scale)))
            ICONS['redo'] = pygame.transform.smoothscale(pygame.image.load(os.path.join("assets", "fleche_redo.png")).convert_alpha(), (int(32 * self.scale), int(32 * self.scale)))
        except FileNotFoundError:
            pass

        self.update_layout()
    
    def init_data(self):
        self.operators = [
            Operator(1, "Assembleur A", pool_name="Assembleur"),
            Operator(2, "Assembleur B", pool_name="Assembleur"),
            Operator(3, "Assembleur C", pool_name="Assembleur"),
            Operator(4, "Contrôleur A", pool_name="Contrôleur"),
            Operator(5, "Contrôleur B", pool_name="Contrôleur")
        ]
        self.tasks = [
            Task(101, "Prépa Surface", "Panneaux Solaires", 16, 0, "Assembleur"),
            Task(102, "Ctrl Visuel", "Panneaux Solaires", 8, 0, "Contrôleur"),
            Task(103, "Couche Primaire", "Panneaux Solaires", 24, 0, "Assembleur"),
            Task(104, "Ctrl Epaisseur", "Panneaux Solaires", 8, 0, "Contrôleur"),
            Task(105, "Couche Finale", "Panneaux Solaires", 32, 0, "Assembleur"),
            Task(106, "Ctrl Final", "Panneaux Solaires", 16, 0, "Contrôleur"),

            Task(201, "Décapage", "Radiateurs", 24, 1, "Assembleur"),
            Task(202, "Ctrl Rugosité", "Radiateurs", 8, 1, "Contrôleur"),
            Task(203, "Peinture Noire", "Radiateurs", 40, 1, "Assembleur"),
            Task(204, "Ctrl Thermique", "Radiateurs", 16, 1, "Contrôleur"),

            Task(301, "Masquage", "Structure", 8, 2, "Assembleur"),
            Task(302, "Peinture Interne", "Structure", 24, 2, "Assembleur"),
            Task(303, "Ctrl Interne", "Structure", 8, 2, "Contrôleur"),
            Task(304, "Peinture Externe", "Structure", 40, 2, "Assembleur"),
            Task(305, "Ctrl Externe", "Structure", 16, 2, "Contrôleur"),
            Task(306, "Retouches", "Structure", 8, 2, "Assembleur"),

            Task(401, "Sablage", "Antennes", 16, 3, "Assembleur"),
            Task(402, "Apprêt", "Antennes", 16, 3, "Assembleur"),
            Task(403, "Ctrl Inter", "Antennes", 8, 3, "Contrôleur"),
            Task(404, "Laque Blanche", "Antennes", 24, 3, "Assembleur"),
            Task(405, "Ctrl Aspect", "Antennes", 8, 3, "Contrôleur")
        ]

        self.raw_tasks = copy.deepcopy(self.tasks)
        self.raw_operators = copy.deepcopy(self.operators)

        if hasattr(self, 'timeline'):
            self.timeline.operators = self.operators
            self.timeline.tasks = self.tasks
            self.update_layout()

    def get_state_signature(self, tasks_list):
        return {(t.id, getattr(t, 'part_index', 0)): (t.assigned_to, t.week_start, t.start_half, t.duration, t.part_index, getattr(t, 'is_pinned', False)) for t in tasks_list}

    def save_state(self):
        """Sauvegarde l'état actuel pour le Ctrl+Z, y compris les bornes du solveur."""
        if not hasattr(self, 'history'):
            self.history = []
        if not hasattr(self, 'redo_stack'):
            self.redo_stack = []
            
        # filtre anti doublons
        if self.history:
            current_sig = self.get_state_signature(self.tasks)
            last_sig = self.get_state_signature(self.history[-1]["tasks"])            
            if current_sig == last_sig:
                return
        
        snapshot = {
            "tasks": copy.deepcopy(self.tasks),
            "assignments": {op.name: [(t.id, getattr(t, 'part_index', 0)) for t in op.tasks] for op in self.operators},
            "known_lower_bound": getattr(self, 'known_lower_bound', 0.0),
            "last_opt_day": getattr(self, 'last_opt_day', -1),
            "last_opt_makespan": getattr(self, 'last_opt_makespan', None)
        }
        self.history.append(snapshot)
        
        if len(self.history) > 30:
            self.history.pop(0)

    def restore_state(self, snapshot):
        self.tasks = copy.deepcopy(snapshot["tasks"])
        if hasattr(self, 'timeline'):
            self.timeline.tasks = self.tasks
            
        for op in self.operators: 
            op.tasks.clear()
            
        task_map = {(t.id, getattr(t, 'part_index', 0)): t for t in self.tasks}
        
        saved_assignments = snapshot["assignments"]
        for op in self.operators:
            if op.name in saved_assignments:
                for task_key in saved_assignments[op.name]:
                    if task_key in task_map: 
                        op.tasks.append(task_map[task_key])
                        
        # --- NOUVEAU : On restaure la mémoire du solveur ---
        self.known_lower_bound = snapshot.get("known_lower_bound", 0.0)
        self.last_opt_day = snapshot.get("last_opt_day", -1)
        self.last_opt_makespan = snapshot.get("last_opt_makespan", None)
                        
        if hasattr(self, 'update_layout'):
            self.update_layout()
            
        self.dragged_item = None
        if hasattr(self, 'context_menu'):
            self.context_menu = None

    def undo(self):
        if not hasattr(self, 'history') or not self.history: 
            return
            
        current_sig = self.get_state_signature(self.tasks)
        state_to_restore = None
        
        while self.history:
            prev_state = self.history.pop()
            if self.get_state_signature(prev_state["tasks"]) != current_sig:
                state_to_restore = prev_state
                break                
                
        if state_to_restore:
            if not hasattr(self, 'redo_stack'):
                self.redo_stack = []
                
            current_snapshot = {
                "tasks": copy.deepcopy(self.tasks),
                "assignments": {op.name: [(t.id, getattr(t, 'part_index', 0)) for t in op.tasks] for op in self.operators}
            }
            self.redo_stack.append(current_snapshot)
            self.restore_state(state_to_restore)

    def redo(self):
        if not hasattr(self, 'redo_stack') or not self.redo_stack: 
            return
            
        current_sig = self.get_state_signature(self.tasks)
        state_to_restore = None
        
        while self.redo_stack:
            next_state = self.redo_stack.pop()
            if self.get_state_signature(next_state["tasks"]) != current_sig:
                state_to_restore = next_state
                break                
                
        if state_to_restore:
            if not hasattr(self, 'history'):
                self.history = []
                
            current_snapshot = {
                "tasks": copy.deepcopy(self.tasks),
                "assignments": {op.name: [(t.id, getattr(t, 'part_index', 0)) for t in op.tasks] for op in self.operators}
            }
            self.history.append(current_snapshot)
            self.restore_state(state_to_restore)

    def draw_undo_redo_arrows(self, surface: pygame.Surface):
        # On harmonise les bordures et les coins pour que les 3 boutons se ressemblent
        radius = int(10 * getattr(self, 'scale', 1.0))
        border_thick = max(1, int(3 * getattr(self, 'scale', 1.0)))
        
        # ==========================================
        # 1. BOUTON UNDO (Flèche Retour)
        # ==========================================
        is_undo_active = bool(self.history)
        bg_color_undo = (230, 230, 230) if is_undo_active else (245, 245, 245)
        border_color_undo = (180, 180, 180) if is_undo_active else (220, 220, 220)

        pygame.draw.rect(surface, bg_color_undo, self.undo_rect, border_radius=radius)
        pygame.draw.rect(surface, border_color_undo, self.undo_rect, border_thick, border_radius=radius)

        if 'undo' in ICONS:
            img_undo = ICONS['undo'].copy()
            if not is_undo_active:
                img_undo.set_alpha(80) # Grise l'image si on ne peut pas annuler
            img_rect = img_undo.get_rect(center=self.undo_rect.center)
            surface.blit(img_undo, img_rect)
        else:
            text_color = (0, 0, 0) if is_undo_active else (180, 180, 180)
            u_text = self.font.render("Z", True, text_color)
            surface.blit(u_text, u_text.get_rect(center=self.undo_rect.center))

        # ==========================================
        # 2. BOUTON REDO (Flèche Avant)
        # ==========================================
        is_redo_active = bool(self.redo_stack)
        bg_color_redo = (230, 230, 230) if is_redo_active else (245, 245, 245)
        border_color_redo = (180, 180, 180) if is_redo_active else (220, 220, 220)

        pygame.draw.rect(surface, bg_color_redo, self.redo_rect, border_radius=radius)
        pygame.draw.rect(surface, border_color_redo, self.redo_rect, border_thick, border_radius=radius)

        if 'redo' in ICONS:
            img_redo = ICONS['redo'].copy()
            if not is_redo_active:
                img_redo.set_alpha(80) # Grise l'image si on ne peut pas rétablir
            img_rect = img_redo.get_rect(center=self.redo_rect.center)
            surface.blit(img_redo, img_rect)
        else:
            text_color = (0, 0, 0) if is_redo_active else (180, 180, 180)
            r_text = self.font.render("Y", True, text_color)
            surface.blit(r_text, r_text.get_rect(center=self.redo_rect.center))

        # ==========================================
        # 3. BOUTON CISEAUX (Tel que tu l'as collé)
        # ==========================================
        bg_color = (255, 180, 80) if getattr(self, 'cut_mode', False) else (230, 230, 230)
        border_color = (200, 100, 0) if getattr(self, 'cut_mode', False) else (180, 180, 180)
        
        pygame.draw.rect(surface, bg_color, self.cut_rect, border_radius=radius)
        pygame.draw.rect(surface, border_color, self.cut_rect, border_thick, border_radius=radius)
        
        if 'ciseaux' in ICONS:
            img_rect = ICONS['ciseaux'].get_rect(center=self.cut_rect.center)
            surface.blit(ICONS['ciseaux'], img_rect)
        else:
            text_color = (0, 0, 0) if getattr(self, 'cut_mode', False) else (120, 120, 120)
            c_text = self.font.render("C", True, text_color)
            surface.blit(c_text, c_text.get_rect(center=self.cut_rect.center))

    def show_notification(self, text: str, color: Tuple[int, int, int] = (240, 50, 50)):
        self.notifications.append({
            "text": text,
            "time": pygame.time.get_ticks(),
            "color": color
        })
        if len(self.notifications) > 3:
            self.notifications = self.notifications[-3:]

    def draw_notifications(self, surface: pygame.Surface):
        current_time = pygame.time.get_ticks()
        y_offset = self.height - int(40 * getattr(self, 'scale_y', 1.0)) 
        
        notif_font = pygame.font.SysFont("trebuchetms", int(22 * getattr(self, 'scale', 1.0)), bold=True)
        self.notifications = [n for n in self.notifications if current_time - n["time"] < 5000]
        
        for notif in reversed(self.notifications): 
            age = current_time - notif["time"]
            alpha = 255
            if age > 4000: 
                alpha = int(255 * (1.0 - (age - 4000) / 1000.0))
                alpha = max(0, min(255, alpha))
            text_surf = notif_font.render(notif["text"], True, notif["color"])
            text_surf.set_alpha(alpha)
            
            marge_x = int(20 * getattr(self, 'scale_x', 1.0))
            marge_y = int(12 * getattr(self, 'scale_y', 1.0))
            bg_rect = pygame.Rect(
                int(20 * getattr(self, 'scale_x', 1.0)), 
                y_offset - text_surf.get_height() - marge_y * 2, 
                text_surf.get_width() + marge_x * 2, 
                text_surf.get_height() + marge_y * 2)
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg_surf.fill((255, 255, 255, alpha)) 
            pygame.draw.rect(bg_surf, (*notif["color"], alpha), bg_surf.get_rect(), 2, border_radius=int(self.scale*8))
            surface.blit(bg_surf, bg_rect.topleft)
            surface.blit(text_surf, text_surf.get_rect(center=bg_rect.center))
            y_offset -= (bg_rect.height + int(15*self.scale_y))

    def check_overlap(self, operator: Operator, task_to_move: Task, new_start_week: int) -> bool:
        # new_end = new_start_week + task_to_move.get_weeks_span()
        # for task in operator.tasks:
        #     if task.id == task_to_move.id: continue 
        #     existing_start = task.week_start
        #     existing_end = task.week_start + task.get_weeks_span()
        #     weeks_overlap = max(new_start_week, existing_start) < min(new_end, existing_end)
        #     if weeks_overlap:
        #         return True
        return False
    
    def check_absence_conflict(self, operator: Operator, task: Task, start_week: float) -> bool:
        t_start = start_week
        t_end = start_week + (task.duration / 8.0)
        if hasattr(operator, 'absences'):
            for abs_start, abs_end in operator.absences:
                if max(t_start, abs_start) < min(t_end, abs_end) - 0.01: return True
        return False
                
    def check_unavailability_conflict(self, operator: Operator, task: Task, start_week: float) -> bool:
        t_start = start_week
        t_end = start_week + (task.duration / 8.0)
        if hasattr(task, 'unavailabilities'):
            for u_start, u_end in task.unavailabilities:
                if max(t_start, u_start) < min(t_end, u_end) - 0.01: return True
        return False
                
    def get_valid_time_window(self, task_to_move):
        min_start = 0.0
        max_end = float(getattr(self.timeline, 'total_days', 100))

        for op in self.operators:
            for other_task in op.tasks:
                if getattr(other_task, 'activity_id', None) != getattr(task_to_move, 'activity_id', None): 
                    continue
                if other_task.id == task_to_move.id:
                    continue # On ignore les morceaux de la même tâche
                
                other_start = round(float(other_task.week_start), 2)
                other_end = round(other_start + (other_task.duration / 8.0), 2)
                
                if other_task.id < task_to_move.id:
                    min_start = max(min_start, other_end)
                elif other_task.id > task_to_move.id:
                    max_end = min(max_end, other_start)

        return min_start, max_end

    def check_precedence(self, task_to_move, new_start_week: float):
        new_end_week = round(new_start_week + (task_to_move.duration / 8.0), 2)
        
        for op in self.operators:
            for other_task in op.tasks:
                if getattr(other_task, 'activity_id', None) != getattr(task_to_move, 'activity_id', None): 
                    continue
                if other_task.id == task_to_move.id:
                    continue # On ignore les morceaux de la même tâche
                
                other_start_week = round(float(other_task.week_start), 2)
                other_end_week = round(other_start_week + (other_task.duration / 8.0), 2)
                
                if other_task.id < task_to_move.id:
                    if new_start_week < other_end_week:
                        return False, f"Ordre logique non respecté (doit être APRÈS '{other_task.name}')"
                elif other_task.id > task_to_move.id:
                    if new_end_week > other_start_week:
                        return False, f"Ordre logique non respecté (doit être AVANT '{other_task.name}')"
                        
        return True, ""

    def get_unassigned_tasks(self) -> List[Task]:
        assigned = [t for op in self.operators for t in op.tasks]
        return [t for t in self.tasks if t not in assigned]

    def update_activity_boxes(self):
        unique_acts = {}
        for t in sorted(self.tasks, key=lambda x: x.activity_id):
            if t.activity_id not in unique_acts:
                unique_acts[t.activity_id] = t.activity_name
                
        self.activity_boxes = []
        x = self.task_basket.rect.x + int(20 * self.scale_x)
        y = self.task_basket.rect.y + int(55 * self.scale_y)
        
        margin = int(25 * self.scale_x)
        for aid, aname in unique_acts.items():
            remaining_count = len(set(t.name for t in self.tasks if getattr(t, 'activity_id', None) == aid and t.assigned_to is None))
            total_count = len(set(t.name for t in self.tasks if getattr(t, 'activity_id', None) == aid))
            display_name = f"{aname} ({remaining_count}/{total_count})"
            box = ActivityBox(aid, display_name, x, y, self.font, getattr(self, 'scale_x', 1.0), getattr(self, 'scale_y', 1.0))
            if x + box.rect.width > self.task_basket.rect.right:
                x = self.task_basket.rect.x + 20
                y += box.rect.height + margin
                box.rect.x = x
                box.rect.y = y
            if getattr(self, 'expanded_activity_id', None) == aid: 
                box.is_expanded = True
            self.activity_boxes.append(box)
            x += box.rect.width + margin

    def create_basket_cards(self):
        cards = []
        if self.expanded_activity_id is None: 
            return cards
            
        expanded_box = None
        for box in getattr(self, 'activity_boxes', []):
            if box.id == self.expanded_activity_id:
                expanded_box = box
                break
                
        if expanded_box:
            y = expanded_box.rect.bottom + int(20 * self.scale_y)
            
        activity_tasks = [t for t in self.tasks if t.activity_id == self.expanded_activity_id]
        activity_tasks.sort(key=lambda t: (t.id, getattr(t, 'part_index', 0)))
        scroll_offset = getattr(self, 'basket_scroll', 0)
        current_x = self.task_basket.rect.x + int(40 * self.scale_x) - scroll_offset
        
        for task in activity_tasks:
            card = TaskCard(task, current_x, y, self.small_font, self.scale)
            cards.append(card)
            current_x += card.width + 20 #largeur flèche 
            
        if cards:
            max_h = max(card.rect.height for card in cards)
            for card in cards: 
                card.rect.height = max_h
        return cards

    def create_timeline_blocks(self) -> List[TaskBlock]:
        blocks = []
        content_start_x = self.timeline.rect.x + self.timeline.label_width
        visible_rect = pygame.Rect(content_start_x, self.timeline.rect.y, self.timeline.rect.width - self.timeline.label_width, self.timeline.rect.height)
        
        for op in self.operators:
            row_y = self.timeline.get_row_y(op)
            op_blocks = []
            
            for t in op.tasks:
                virtual_x = content_start_x + t.week_start * self.timeline.day_width
                screen_x = virtual_x - self.timeline.scroll_offset
                blk = TaskBlock(t, screen_x, row_y + 1, self.timeline.day_width, scale=self.scale)
                blk.clip_rect = visible_rect
                op_blocks.append(blk)
            
            for i in range(len(op_blocks)):
                for j in range(i + 1, len(op_blocks)):
                    b1 = op_blocks[i]
                    b2 = op_blocks[j]
                    b1_start = b1.task.week_start
                    b1_end = b1_start + (b1.task.duration / 8.0)
                    b2_start = b2.task.week_start
                    b2_end = b2_start + (b2.task.duration / 8.0)
                    
                    if max(b1_start, b2_start) < min(b1_end, b2_end):
                        half_height = (self.timeline.row_height - 4) // 2
                        b1.rect.height = half_height
                        b2.rect.height = half_height
                        b2.rect.y = row_y + 1 + half_height + 2
            
            blocks.extend(op_blocks)
            
        return blocks
    
    def replan_tasks_subset(self, tasks_to_replan, mode="no_conflict"):
        self.save_state() 
        
        for t in tasks_to_replan:
            t.is_pinned = False
            if t.assigned_to:
                for op in self.operators:
                    if t in op.tasks: op.tasks.remove(t)

        solver = PlanningSolver(self.tasks, self.operators)
        current_day = getattr(self, 'current_day', 0.0)
        
        try:
            # On appelle directement le solveur avec le SEUL mode demandé
            success, msg = solver.solve(time_limit=2, target_tasks=tasks_to_replan, current_day=current_day, mode=mode) 
        except Exception as e:
            success, msg = False, str(e)

        if success:
            for op in self.operators:
                op.tasks = [t for t in self.tasks if t.assigned_to == op.name]
            
            self.merge_contiguous_tasks()
            
            if mode == "no_conflict":
                self.show_notification(f"{len(tasks_to_replan)} tâche(s) placée(s) sans conflit !", color=(50, 200, 50))
            else:
                self.show_notification(f"{len(tasks_to_replan)} tâche(s) placée(s) au plus tôt !", color=(50, 200, 50))
                
            self.realign_delays()    
            self.update_layout()
        else:
            self.restore_state(self.history.pop())
            # --- MODIFICATION DU MESSAGE D'ERREUR ---
            if mode == "no_conflict":
                self.show_notification("Impossible de placer ces tâches sans conflit (précédences...)", color=(200, 50, 50))
            else:
                self.show_notification(f"Impossible de placer ces tâches au plus tôt.", color=(200, 50, 50))

    def _split_task_at_day(self, t, split_day):
        """Coupe une tâche en deux à un jour précis (logique mathématique pure). Retourne le nouveau morceau."""
        if getattr(t, 'assigned_to', None) is None:
            return None
            
        task_start = float(t.week_start)
        task_end = task_start + (t.duration / 8.0)
        
        # Sécurité : on coupe uniquement si le point de coupe est strictement à l'intérieur
        if not (task_start < split_day < task_end):
            return None
            
        past_duration = int((split_day - task_start) * 8)
        future_duration = t.duration - past_duration
        
        if past_duration <= 0 or future_duration <= 0:
            return None
            
        import copy
        # On clone la tâche à l'identique (beaucoup plus robuste que de recréer un objet)
        new_task = copy.copy(t) 
        new_task.duration = future_duration
        new_task.week_start = split_day
        new_task.part_index = 999 # Sera lissé par _reindex_tasks_parts juste après
        
        if hasattr(t, 'unavailabilities'):
            new_task.unavailabilities = copy.deepcopy(t.unavailabilities)
            
        # Le retard glisse entièrement sur la partie du futur
        if hasattr(t, 'delay_duration'):
            new_task.delay_duration = t.delay_duration
            t.delay_duration = 0 
            
        if new_task.assigned_to:
            for op in self.operators:
                if op.name == new_task.assigned_to:
                    op.tasks.append(new_task)
                    break
                    
        # On ampute la durée de la tâche d'origine
        t.duration = past_duration
        return new_task

    def load_replanning_window(self, source_tasks, source_operators, current_day):
        """Importe le planning, découpe les tâches interrompues et déplanifie les conflits."""
        self.tasks = copy.deepcopy(source_tasks)
        self.operators = copy.deepcopy(source_operators)
        
        for op in self.operators:
            op.tasks = []
            
        for t in self.tasks:
            if t.assigned_to:
                for op in self.operators:
                    if op.name == t.assigned_to:
                        op.tasks.append(t)
                        break

        tasks_to_add = []
                        
        # --- DÉCOUPAGE ET DÉPLANIFICATION INTELLIGENTE ---
        for op in self.operators:
            tasks_to_remove = []
            for t in list(op.tasks):
                t_start = int(t.week_start)
                t_end = t_start + int(t.duration / 8)
                
                # On cumule les absences ET les pannes de tâches
                blocking_intervals = getattr(op, 'absences', []).copy()
                if hasattr(t, 'unavailabilities'):
                    blocking_intervals.extend(t.unavailabilities)
                
                for b_s, b_e in blocking_intervals:
                    b_start, b_end = int(b_s), int(b_e)
                    if max(t_start, b_start) < min(t_end, b_end):
                        if t_start < b_start:
                            new_task = self._split_task_at_day(t, b_start)
                            if new_task:
                                tasks_to_add.append((self.tasks.index(t) + 1, new_task))
                        else:
                            tasks_to_remove.append(t)
                        break 
                        
            for t in tasks_to_remove:
                op.tasks.remove(t)
                t.assigned_to = None
                t.week_start = -1

        for idx, new_t in reversed(tasks_to_add):
            self.tasks.insert(idx, new_t)
        self._reindex_tasks_parts()
                    
        self.timeline.tasks = self.tasks
        self.timeline.operators = self.operators
        self.current_day = current_day
        self.update_layout()

    def realign_delays(self):
        """
        Aspire tout le retard d'une tâche et le distribue sur les morceaux 
        en partant de la fin. Un morceau ne peut pas contenir plus de retard 
        que sa propre durée.
        """
        noms_uniques = set(t.name for t in self.tasks)
        
        for nom in noms_uniques:
            morceaux = sorted([t for t in self.tasks if t.name == nom], key=lambda t: t.week_start)
            if morceaux:
                retard_total = sum(getattr(m, 'delay_duration', 0) for m in morceaux)
                for m in morceaux:
                    m.delay_duration = 0
                reste_a_distribuer = retard_total
                for m in reversed(morceaux):
                    if reste_a_distribuer <= 0:
                        break
                    capacite_bloc = m.duration
                    if reste_a_distribuer >= capacite_bloc:
                        m.delay_duration = capacite_bloc
                        reste_a_distribuer -= capacite_bloc
                    else:
                        m.delay_duration = reste_a_distribuer
                        reste_a_distribuer = 0

    def update_layout(self):
        max_end = 0.0
        for t in self.tasks:
            if t.assigned_to:
                max_end = max(max_end, t.week_start + (t.duration / 8.0))
                
        self.timeline.total_days = max(20, int(math.ceil(max_end)) + 3)
        
        if self.operators:
            last_op_index = len(self.operators) - 1
            last_op_y = self.timeline.get_row_y_by_index(last_op_index)
            self.timeline.rect.height = (last_op_y + self.timeline.row_height) - self.timeline.rect.y + 10
        
        sb_x = self.timeline.rect.x + self.timeline.label_width
        sb_w = self.timeline.rect.width - self.timeline.label_width
        self.scrollbar.rect.x = sb_x
        self.scrollbar.rect.width = sb_w
        self.scrollbar.rect.y = self.timeline.rect.y - int(15 * self.scale_y) 
        self.scrollbar.visible_width = sb_w
    
        self.timeline.day_width = GUI.day_width_timeline if not getattr(self.timeline, 'timeline_combined', False) else (GUI.day_width_timeline//2)
        self.timeline.total_content_width = self.timeline.total_days * GUI.day_width_timeline
        self.scrollbar.update_content_width(self.timeline.total_content_width)
                
        basket_y = self.timeline.rect.bottom + int(15 * self.scale_y)
        self.task_basket.rect.y = basket_y + int(40 * self.scale_y)
        
        base_height = int(110 * self.scale_y)
        content_height = base_height + int(90 * self.scale_y) if self.expanded_activity_id is not None else base_height
        self.task_basket.rect.height = content_height

        buttons_y = self.height - int(80 * self.scale_y)
        arrow_y_offset = buttons_y + int(5 * self.scale_y)
        self.undo_rect.x = int(30 * self.scale_x) 
        self.undo_rect.y = arrow_y_offset        
        self.redo_rect.x = self.undo_rect.right + int(15 * self.scale_x) 
        self.redo_rect.y = arrow_y_offset
        self.cut_rect.x = self.redo_rect.right + int(25 * self.scale_x) 
        self.cut_rect.y = arrow_y_offset
        
        # Positionnement dynamique des boutons
        margin = int(15 * self.scale_x)
        self.solve_button.rect.x = self.width - self.solve_button.rect.width - int(20 * self.scale_x)
        self.solve_button.rect.y = buttons_y
        self.all_combine_button.rect.x = int(self.width * 0.01)
        self.all_combine_button.rect.y = self.timeline.rect.bottom + int(10 * getattr(self, 'scale_y', 1.0))
        
        current_x = self.solve_button.rect.x
        
        # Le bouton réparer ne s'insère qu'en replanification
        if getattr(self, 'is_replanning', False) and getattr(self.tutorial, 'step', 0) > 15:
            self.repair_button.rect.x = current_x - self.repair_button.rect.width - margin
            self.repair_button.rect.y = buttons_y
            current_x = self.repair_button.rect.x
            
        self.save_button.rect.x = current_x - self.save_button.rect.width - margin
        self.save_button.rect.y = buttons_y
        self.load_button.rect.x = self.save_button.rect.x - self.load_button.rect.width - margin
        self.load_button.rect.y = buttons_y
        self.reset_button.rect.x = self.load_button.rect.x - self.reset_button.rect.width - margin
        self.reset_button.rect.y = buttons_y

        self._reindex_tasks_parts()
        self.current_errors = self.get_current_errors()

    def _merge_timeline_tasks(self):
        """Fusionne les blocs d'une même tâche qui se touchent sur le planning."""
        for op in self.operators:
            task_groups = {}
            for t in op.tasks:
                task_groups.setdefault(t.id, []).append(t)
                
            for t_id, group in task_groups.items():
                if len(group) > 1:
                    group.sort(key=lambda x: x.week_start)
                    i = 0
                    while i < len(group) - 1:
                        t1 = group[i]
                        t2 = group[i+1]
                        
                        # Si les deux tâches se touchent parfaitement
                        if abs(t2.week_start - (t1.week_start + (t1.duration / 8.0))) < 0.01:
                            t1.duration += t2.duration
                            
                            t1_delay = getattr(t1, 'delay_duration', 0)
                            t2_delay = getattr(t2, 'delay_duration', 0)
                            if t1_delay > 0 or t2_delay > 0:
                                t1.delay_duration = t1_delay + t2_delay
                                
                            op.tasks.remove(t2)
                            if t2 in self.tasks:
                                self.tasks.remove(t2)
                            group.pop(i+1)
                        else:
                            i += 1

    def _merge_basket_tasks(self):
        """Fusionne les morceaux d'une même tâche qui sont en attente dans le panier."""
        unassigned = [t for t in self.tasks if t.assigned_to is None]
        unassigned.sort(key=lambda x: (x.activity_id, x.id))

        i = 0
        while i < len(unassigned) - 1:
            t1 = unassigned[i]
            t2 = unassigned[i+1]
            
            if t1.activity_id == t2.activity_id and t1.id == t2.id:
                t1.duration += t2.duration
                
                t1_delay = getattr(t1, 'delay_duration', 0)
                t2_delay = getattr(t2, 'delay_duration', 0)
                if t1_delay > 0 or t2_delay > 0:
                    t1.delay_duration = t1_delay + t2_delay
                    
                if t2 in self.tasks:
                    self.tasks.remove(t2)
                unassigned.pop(i+1)
            else:
                i += 1
    
    def merge_contiguous_tasks(self):
        """Fusionne automatiquement les tâches contiguës sur la timeline ET les morceaux successifs dans le panier."""
        self._merge_timeline_tasks()
        self._merge_basket_tasks()
        self._reindex_tasks_parts()

    def _analyze_planning_state(self) -> dict:
        """Méthode centralisée qui détecte toutes les erreurs et conflits du planning."""
        errors = []
        conflict_tasks = {} # dictionnaire pour dédupliquer les objets Task par ID

        def add_error(t_list, short_msg, long_msg):
            for t in t_list:
                key = (t.id, getattr(t, 'activity_id', 0), getattr(t, 'part_index', 0))
                conflict_tasks[key] = t
            # On évite de spammer 4 fois le même message d'erreur à l'écran
            if not any(e["long"] == long_msg for e in errors):
                errors.append({"short": short_msg, "long": long_msg})

        # 1. Tâches non planifiées
        unassigned = [t for t in self.tasks if t.assigned_to is None]
        for t in unassigned:
            key = (t.id, getattr(t, 'activity_id', 0), getattr(t, 'part_index', 0))
            conflict_tasks[key] = t
            
        unassigned_names = list(set(t.name for t in unassigned))
        if unassigned_names:
            if len(unassigned_names) == 1:
                errors.append({
                    "short": f"Non planifiée : '{unassigned_names[0]}'",
                    "long": f"La tâche '{unassigned_names[0]}' doit être placée sur le planning."
                })
            else:
                errors.append({
                    "short": f"{len(unassigned_names)} tâches non planifiées",
                    "long": f"Il reste {len(unassigned_names)} tâches dans le panier qui n'ont pas encore été planifiées."
                })

        # 2. Conflits intra-opérateurs, Absences, Deadlines
        for op in self.operators:
            sorted_tasks = sorted(op.tasks, key=lambda t: t.week_start)
            for i in range(len(sorted_tasks) - 1):
                t1, t2 = sorted_tasks[i], sorted_tasks[i+1]
                t1_end = t1.week_start + (t1.duration / 8.0)
                if t2.week_start < t1_end - 0.01:
                    add_error([t1, t2], 
                              f"Superposition : {op.name}", 
                              f"Superposition sur {op.name} entre '{t1.name}' et '{t2.name}'.")
            
            for t in op.tasks:
                if self.check_absence_conflict(op, t, t.week_start):
                    add_error([t], f"Absence : {op.name}", f"La tâche '{t.name}' est planifiée pendant une absence de {op.name}.")
                if self.check_unavailability_conflict(op, t, t.week_start):
                    add_error([t], f"Indisponibilité : '{t.name}'", f"La tâche '{t.name}' est planifiée sur une période où elle est indisponible.")
                
                t_end = t.week_start + (t.duration / 8.0)
                if getattr(t, 'deadline', None) is not None and t_end > t.deadline + 0.01:
                    add_error([t], f"Deadline : '{t.name}'", f"La tâche '{t.name}' se termine après sa date limite (J{t.deadline}).")

        # 3. Conflits inter-opérateurs : Précédences et Morceaux de même tâche (LE BUG FIXÉ EST ICI)
        planned_tasks = [t for t in self.tasks if t.assigned_to is not None]
        act_groups = {}
        for t in planned_tasks:
            act_groups.setdefault(getattr(t, 'activity_id', 0), []).append(t)

        for act_id, tasks_in_act in act_groups.items():
            for i in range(len(tasks_in_act)):
                for j in range(i + 1, len(tasks_in_act)):
                    t1 = tasks_in_act[i]
                    t2 = tasks_in_act[j]
                    
                    # On ordonne t1 et t2 pour que t1 soit "avant" logiquement
                    if t1.id > t2.id or (t1.id == t2.id and t1.week_start > t2.week_start):
                        t1, t2 = t2, t1
                        
                    t1_start = round(float(t1.week_start), 2)
                    t1_end = round(t1_start + (t1.duration / 8.0), 2)
                    t2_start = round(float(t2.week_start), 2)
                    t2_end = round(t2_start + (t2.duration / 8.0), 2)

                    # Si c'est la MÊME tâche (morceaux découpés)
                    if t1.id == t2.id:
                        if max(t1_start, t2_start) < min(t1_end, t2_end) - 0.01:
                            p1 = f" (P{t1.part_index})" if getattr(t1, 'part_index', 0) > 0 else ""
                            p2 = f" (P{t2.part_index})" if getattr(t2, 'part_index', 0) > 0 else ""
                            add_error([t1, t2],
                                      f"Simultanéité : '{t1.name}'",
                                      f"Impossible d'effectuer '{t1.name}'{p1} et '{t2.name}'{p2} en même temps sur différents opérateurs.")
                    # Si ce sont des tâches différentes de la même activité (Précédence stricte)
                    else:
                        if t1_end > t2_start + 0.01:
                            p1 = f" (P{t1.part_index})" if getattr(t1, 'part_index', 0) > 0 else ""
                            p2 = f" (P{t2.part_index})" if getattr(t2, 'part_index', 0) > 0 else ""
                            add_error([t1, t2],
                                      f"Ordre : '{t1.name}' -> '{t2.name}'",
                                      f"Ordre non respecté : '{t1.name}{p1}' doit se terminer avant de commencer '{t2.name}{p2}'.")

        return {
            "errors": errors, 
            "conflict_tasks": list(conflict_tasks.values())
        }
    
    def get_conflicting_tasks(self) -> list:
        return self._analyze_planning_state()["conflict_tasks"]

    def cut_task_at_date(self, original_task, cut_date):
        """Action déclenchée par l'outil ciseaux (UI)."""
        exact_current_day = getattr(self, 'current_day', 0.0)
        task_end_week = original_task.week_start + (original_task.duration / 8.0)
        
        if task_end_week <= exact_current_day:
            self.show_notification("Action impossible : Tâche déjà terminée.", (200, 50, 50))
            return False
        if cut_date < exact_current_day:
            self.show_notification("Impossible de couper dans le passé.", (200, 50, 50))
            return False
            
        if hasattr(self, 'save_state'): self.save_state()
        
        new_task = self._split_task_at_day(original_task, cut_date)
        if not new_task:
            self.show_notification("Action impossible : Clic trop au bord.")
            return False
            
        self.tasks.append(new_task)
        self._reindex_tasks_parts()
        self.realign_delays()
        self.update_layout()
        return True

    def get_conflicting_tasks(self) -> list:
        return self._analyze_planning_state()["conflict_tasks"]

    def get_current_errors(self) -> list:
        return self._analyze_planning_state()["errors"]

    def is_valid(self) -> Tuple[bool, list]:
        """Vérifie la validité totale (Erreurs logiques + Solveur)."""
        errors = self.get_current_errors()
        if errors:
            return False, errors
            
        from solver_cpo import PlanningSolver
        solver = PlanningSolver(self.tasks, self.operators)
        try:
            success, msg = solver.solve(time_limit=2, current_day=getattr(self, 'current_day', 0.0))
        except Exception as e:
            print(e)
            return False, ["Échec interne : Bug dans le solveur."]
        
        if success: return True, []
        else: return False, ["Aucun planning réalisable ne satisfait l'ensemble de vos décisions."]

    def export_to_json(self):
        root = tk.Tk()
        root.withdraw() # Cache la fenêtre principale tk
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
            title="Sauvegarder le scénario"
        )
        root.destroy()
        if not file_path:
            return # L'utilisateur a annulé
        tasks_data = []
        for t in self.tasks:
            tasks_data.append(asdict(t)) # asdict convertit automatiquement la dataclass !
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({"tasks": tasks_data}, f, ensure_ascii=False, indent=4)
            self.show_notification(f"Scénario sauvegardé !", color=(50, 200, 50))
        except Exception as e:
            self.show_notification(f"Erreur de sauvegarde : {e}", color=(200, 50, 50))

    def import_from_json(self):
        # 1. Ouvrir la fenêtre de dialogue Windows
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
            title="Charger un scénario"
        )
        root.destroy()

        if not file_path:
            return

        # 2. Lire et appliquer les données
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Réinitialiser la timeline propre
            self.save_state() # Pour permettre un Ctrl+Z après un chargement !
            for op in self.operators:
                op.tasks.clear()
            self.tasks.clear()

            # Reconstruire les objets Task
            for t_dict in data.get("tasks", []):
                new_task = Task(**t_dict)
                new_task.solved_time = 0
                self.tasks.append(new_task)
                
                # Réaffecter aux opérateurs
                if new_task.assigned_to:
                    for op in self.operators:
                        if op.name == new_task.assigned_to:
                            op.tasks.append(new_task)
                            break
                    
            self.update_layout()
            self.show_notification("Scénario chargé avec succès !", color=(50, 200, 255))
            
        except Exception as e:
            self.show_notification(f"Fichier invalide ou corrompu.", color=(200, 50, 50))

    def handle_events(self, event):
        if event.type == pygame.QUIT:
            pass
            
    def handle_events(self, event):
        if event.type == pygame.QUIT:
            pass
            
        elif event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
            
        elif event.type == pygame.MOUSEWHEEL:
            self._handle_mousewheel(event)

        # 1. Mise à jour de la barre de défilement globale
        if self.scrollbar.handle_event(event):
            self.timeline.scroll_offset = int(self.scrollbar.scroll_x)

        # 2. Gestion des boutons d'interface (Renvoie parfois un signal spécifique)
        ui_action = self._handle_ui_buttons(event)
        if ui_action:
            return ui_action

        # 3. Gestion granulaire de la souris
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.timeline.timeline_combined and self.timeline.rect.collidepoint(event.pos): return
            if event.button == 1 : # Clic Gauche
                self._handle_left_click(event)
            elif event.button == 3: # Clic Droit
                self._handle_right_click(event.pos)
                
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1: # Relâchement Clic Gauche
                self._handle_mouse_up(event)
                
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(event)

    def _handle_keydown(self, event):
        if event.mod & pygame.KMOD_CTRL:
            if event.key == pygame.K_z: self.undo()
            elif event.key == pygame.K_y: self.redo()
        elif event.key == pygame.K_c:
            self.cut_mode = not getattr(self, 'cut_mode', False)
            pygame.mouse.set_visible(not self.cut_mode)
        elif event.key == pygame.K_DELETE and self._selected_task_ids:
            self._apply_area_selection_action("Déplanifier")

    def _handle_mousewheel(self, event):
        mouse_pos = pygame.mouse.get_pos()
        if hasattr(self, 'task_basket') and self.task_basket.rect.collidepoint(mouse_pos):
            self.basket_scroll = getattr(self, 'basket_scroll', 0) - event.y * 40 * self.scale
            self.basket_scroll = max(0, self.basket_scroll) 
        else:
            self.scrollbar.scroll_x -= event.y * 50 * self.scale
            self.scrollbar.scroll_x = max(0, min(self.scrollbar.scroll_x, self.scrollbar.max_scroll))
            self.timeline.scroll_offset = int(self.scrollbar.scroll_x)
    def _handle_mousewheel(self, event):
        mouse_pos = pygame.mouse.get_pos()
        if hasattr(self, 'task_basket') and self.task_basket.rect.collidepoint(mouse_pos):
            self.basket_scroll = getattr(self, 'basket_scroll', 0) - event.y * 40 * self.scale
            self.basket_scroll = max(0, self.basket_scroll) 
        else:
            self.scrollbar.scroll_x -= event.y * 50 * self.scale
            self.scrollbar.scroll_x = max(0, min(self.scrollbar.scroll_x, self.scrollbar.max_scroll))
            self.timeline.scroll_offset = int(self.scrollbar.scroll_x)

    def _handle_ui_buttons(self, event):
        exact_current_day = math.ceil(getattr(self, 'current_day', 0.0) - 0.06)
    def _handle_ui_buttons(self, event):
        exact_current_day = math.ceil(getattr(self, 'current_day', 0.0) - 0.06)

        if self.save_button.handle_event(event): self.export_to_json()
        if self.load_button.handle_event(event): self.import_from_json()

        if hasattr(self, 'all_combine_button') and self.all_combine_button.handle_event(event):
            self.timeline.timeline_combined = not self.timeline.timeline_combined
            self.timeline.day_width = (self.timeline.day_width // 2) if self.timeline.timeline_combined else (self.timeline.day_width * 2)
            self.timeline.total_content_width = self.timeline.day_width * self.timeline.total_days
            self.all_combine_button.text = "Désagréger le planning" if self.timeline.timeline_combined else "Agréger le planning"
            self.update_layout()
            self.dragged_item = None
        '''if hasattr(self, 'all_combine_button') and self.all_combine_button.handle_event(event):
            self.timeline.timeline_combined = not self.timeline.timeline_combined
            self.timeline.day_width = (self.timeline.day_width // 2) if self.timeline.timeline_combined else (self.timeline.day_width * 2)
            self.timeline.total_content_width = self.timeline.day_width * self.timeline.total_days
            self.all_combine_button.text = "Désagréger le planning" if self.timeline.timeline_combined else "Agréger le planning"
            self.update_layout()
            self.dragged_item = None'''
        
        if getattr(self, 'is_replanning', False) and self.validate_replan_btn.handle_event(event):
            valid, error_list = self.is_valid()
            if not valid:
                self.show_notification(f"Impossible de valider : {len(error_list)} erreur(s).", (220, 50, 50))
                self.show_full_errors_popup = True 
                self.show_full_errors_popup = True 
            else:
                self.is_replanning = False
                return "VALIDATE_REPLAN"
            
        if self.reset_button.handle_event(event):
            self.save_state()
            if exact_current_day == 0:
                self.init_data()
            else:
                split_day = math.ceil(getattr(self, 'current_day', 0.0) - 0.06)
                split_day = math.ceil(getattr(self, 'current_day', 0.0) - 0.06)
                for t in self.tasks:
                    t.is_pinned = False
                    if t.week_start >= split_day:
                        if t.assigned_to:
                            for op in self.operators:
                                if t in op.tasks: op.tasks.remove(t)
                        t.assigned_to = None
                        t.week_start = -1 # <-- Modification ici selon votre mode agrégé précédent
                        t.week_start = -1 # <-- Modification ici selon votre mode agrégé précédent
                        t.start_half = 0
            self.update_layout()
            self.show_notification("Plateau réinitialisé.", (50, 200, 255))
            
        btn_solve_clicked = self.solve_button.handle_event(event)
        btn_repair_clicked = getattr(self, 'is_replanning', False) and getattr(self, 'repair_button', None) and self.repair_button.handle_event(event)

        if btn_solve_clicked or btn_repair_clicked:
            return self._run_solver_process(is_repair=btn_repair_clicked)
            
        return None

    def _run_solver_process(self, is_repair):
        import time
        from solver_cpo import PlanningSolver # Sécurité d'import

        self.save_state()
        old_blocks = self.create_timeline_blocks()
        exact_current_day = getattr(self, 'current_day', 0.0)
        split_day = math.ceil(exact_current_day - 0.06)
        
        # 1. AUTO-DÉCOUPAGE
        tasks_to_add = []
        for t in self.tasks:
            new_task = self._split_task_at_day(t, split_day)
            if new_task:
                tasks_to_add.append((self.tasks.index(t) + 1, new_task))
        for idx, new_t in reversed(tasks_to_add): self.tasks.insert(idx, new_t)
        self._reindex_tasks_parts()
        
        # 2. SAUVEGARDE ETATS INITIAUX
        pre_solve_state = {}
        ref_state = {} 
        is_replanning = getattr(self, 'is_replanning', False)
        for t in self.tasks:
            task_key = (getattr(t, 'activity_id', 'global'), t.id, getattr(t, 'part_index', 0))
            pre_solve_state[task_key] = (t.assigned_to, t.week_start, t.duration)
            if is_replanning and t.assigned_to and t.week_start >= split_day:
                ref_state[task_key] = {"start": t.week_start, "op": t.assigned_to}
                
        lb = getattr(self, 'known_lower_bound', 0.0)
        self.current_seed = getattr(self, 'current_seed', 0) + 1 
        exact_ms = getattr(self, 'last_opt_makespan', None) if getattr(self, 'last_opt_day', -1) == split_day else None 
        solver = PlanningSolver(self.tasks, self.operators)
        success = False
        msg = ""

        # 3. RÉSOLUTION SÉPARÉE
        if is_repair:
            conflicts = self.get_conflicting_tasks()
            for t in conflicts:
                if t.assigned_to:
                    for op in self.operators:
                        if t in op.tasks: op.tasks.remove(t)
                t.assigned_to = None
                t.week_start = -1
            self.update_layout()
            
            try:
                success, msg = solver.solve(time_limit=3, seed=self.current_seed, current_day=split_day, lower_bound=lb, exact_makespan=exact_ms, replan_ref=ref_state, global_deadline=10, conflict_tasks=conflicts, mode="no_conflict", pre_solve_state=pre_solve_state)
                # Note: La logique de fallback "Essai 2 et 3" est très lourde, vous pouvez l'isoler ici si besoin, 
                # mais le fait de l'avoir packagée allège considérablement la lecture.
            except Exception as e:
                success, msg = False, "Bug dans le solveur."
                print(e)
        else:
            # Mode "Nouvelle Solution Globale"
            for t in self.tasks:
                if exact_current_day == 0 or getattr(t, 'week_start', -1) >= split_day:
                    if not getattr(t, 'is_pinned', False):
                        if t.assigned_to:
                            for op in self.operators:
                                if t in op.tasks: op.tasks.remove(t)
                        t.assigned_to = None
                        t.week_start = -1
            self.update_layout()
            
            try:
                success, msg = solver.solve(time_limit=3, seed=self.current_seed, current_day=split_day, lower_bound=lb, exact_makespan=exact_ms, global_deadline=None)
            except Exception as e:
                success, msg = False, "Bug dans le solveur."
                print(e)
                
        # 4. APPLICATION UI
        if success:
            self.merge_contiguous_tasks()
            for t in self.tasks:
                task_key = (getattr(t, 'activity_id', 'global'), t.id, getattr(t, 'part_index', 0))
                if task_key in pre_solve_state:
                    old_assigned, old_start, old_dur = pre_solve_state[task_key]
                    if t.assigned_to == old_assigned and abs(t.week_start - old_start) < 0.01 and t.duration == old_dur:
                        t.solved_time = 0
            
            if is_repair:
                self.replan_changes = msg if isinstance(msg, list) else ["Planning ajusté avec succès."]
                self.show_replan_popup = True
            else:
                if exact_ms is None and getattr(solver, 'is_optimal', False):
                    self.known_lower_bound = max(lb, getattr(solver, 'best_makespan', 0.0))
                    self.last_opt_day = split_day
                    self.last_opt_makespan = getattr(solver, 'best_makespan', 0.0)
                    self.show_notification("Solution optimale trouvée !", (50, 200, 50))
                else:
                    self.show_notification("Nouvelle solution générée !", (50, 200, 255))
                
            self.realign_delays()    
            self.update_layout()
            new_blocks = self.create_timeline_blocks()
            self.animate_transition(old_blocks, new_blocks)
        else:
            if self.history: self.restore_state(self.history.pop())
            self.show_notification(f"Échec : {msg}", (200, 50, 50))
            self.update_layout()
            
        return "SOLVED"
    
    def _handle_left_click(self, event):
        # 1. Gestion des popups prioritaires
        if self._handle_popups_click(event.pos):
            return

        # 2. Gestion des contrôles UI divers
        if getattr(self, 'basket_thumb_rect', None) and self.basket_thumb_rect.collidepoint(event.pos):
            self.is_dragging_basket_scroll = True
            self.basket_drag_offset_x = event.pos[0] - self.basket_thumb_rect.x
            return
        if self.undo_rect.collidepoint(event.pos): self.undo(); return
        if self.redo_rect.collidepoint(event.pos): self.redo(); return
        if getattr(self, 'cut_rect', pygame.Rect(0,0,0,0)).collidepoint(event.pos): 
            self.cut_mode = not getattr(self, 'cut_mode', False)
            pygame.mouse.set_visible(not self.cut_mode)
            return

        # 3. Gestion Menu Contextuel
        if getattr(self, 'context_menu', None):
            self._handle_context_menu_click(event.pos)
            return

        # 4. Mode Ciseaux
        if getattr(self, 'cut_mode', False):
            self._handle_cut_mode_click(event.pos)
            return

        # 5. Boîtes d'activités (Ouvrir / Fermer dossiers)
        self.update_activity_boxes()
        for box in self.activity_boxes:
            if box.rect.collidepoint(event.pos):
                self.expanded_activity_id = None if self.expanded_activity_id == box.id else box.id
                self.update_layout()
                return

        # 6. Clics sur Timeline et Panier
        self._handle_timeline_and_basket_click(event)

    def _handle_popups_click(self, pos):
        if getattr(self, 'show_replan_popup', False):
            self.show_replan_popup = False
            return True
        if getattr(self, 'show_full_errors_popup', False):
            if getattr(self, 'close_error_popup_rect', pygame.Rect(0,0,0,0)).collidepoint(pos) or not getattr(self, 'full_error_popup_rect', pygame.Rect(0,0,0,0)).collidepoint(pos):
                self.show_full_errors_popup = False
            return True
        if getattr(self, 'error_box_rect', pygame.Rect(0,0,0,0)).collidepoint(pos) and not getattr(self, 'show_full_errors_popup', False):
            if self.current_errors:
                self.show_full_errors_popup = True
            return True
        return False

    def _handle_cut_mode_click(self, pos):
        timeline_blocks = self.create_timeline_blocks()
        for blk in reversed(timeline_blocks):
            if blk.rect.collidepoint(pos):
                relative_x = pos[0] - blk.rect.x
                raw_days = relative_x / self.timeline.day_width 
                split_days = max(1, int(raw_days + 0.5))
                cut_date = blk.task.week_start + split_days
                
                if self.cut_task_at_date(blk.task, cut_date):
                    self.cut_mode = False
                    pygame.mouse.set_visible(True)
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                return

    def _handle_timeline_and_basket_click(self, event):
        timeline_blocks = self.create_timeline_blocks()
        
        # A. Clic avec Control (Multi-Sélection)
        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            for blk in reversed(timeline_blocks):
                if blk.rect.collidepoint(event.pos):
                    key = (blk.task.id, blk.task.part_index)
                    if key in self._selected_task_ids: self._selected_task_ids.discard(key)
                    else: self._selected_task_ids.add(key)
                    return

        # B. Préhension d'une tâche (Drag & Drop)
        for blk in reversed(timeline_blocks):
            if blk.handle_mouse_down(event.pos):
                if blk.task.week_start < math.ceil(getattr(self, 'current_day', 0.0)-0.06):
                    self.show_notification("Action impossible : Cette tâche a déjà commencé.", (200, 50, 50))
                    blk.is_dragging = False 
                    break

                # Configuration du Multi-Drag
                if (blk.task.id, blk.task.part_index) in self._selected_task_ids and len(self._selected_task_ids) > 1:
                    split_day = math.ceil(getattr(self, 'current_day', 0.0) - 0.06)
                    sel_tasks = [t for t in self.tasks if (t.id, t.part_index) in self._selected_task_ids and t.assigned_to is not None]
                    if any(t.week_start < split_day for t in sel_tasks):
                        self.show_notification("Action impossible : certaines tâches ont déjà commencé.", (200, 50, 50))
                        blk.is_dragging = False
                        break
                    
                    leader_day = blk.task.week_start
                    leader_op_idx = next((i for i, op in enumerate(self.operators) if op.name == blk.task.assigned_to), 0)
                    self._multi_drag_offsets = {}
                    for t in sel_tasks:
                        t_op_idx = next((i for i, op in enumerate(self.operators) if op.name == t.assigned_to), 0)
                        self._multi_drag_offsets[(t.id, t.part_index)] = (t.week_start - leader_day, t_op_idx - leader_op_idx)
                    self._multi_drag_leader = blk
                    self._multi_drag_active = True
                    self._multi_drag_preview = {}
                    
                self.dragged_item = blk
                rel_x = event.pos[0] - blk.rect.x
                self.drag_day_offset = int(rel_x / self.timeline.day_width)
                return

        # C. Lancement d'une Sélection par zone (Area Selection)
        if not getattr(self, 'dragged_item', None):
            content_start_x = self.timeline.rect.x + self.timeline.label_width
            in_content = self.timeline.rect.collidepoint(event.pos) and event.pos[0] >= content_start_x
            in_action_btn = any(r.collidepoint(event.pos) for r in self._sel_action_rects.values())
            
            if not in_action_btn:
                self._selected_task_ids = set()
                self._sel_action_rects = {}
            if in_content and not in_action_btn:
                self._area_sel_start = event.pos
                self._area_sel_current = event.pos

        # D. Interaction avec le Panier (Basket)
        if not getattr(self, 'dragged_item', None):
            cards = self.create_basket_cards()
            for card in reversed(cards):
                if card.rect.collidepoint(event.pos):
                    if card.task.assigned_to is not None:
                        # Auto-Scroll vers le morceau
                        for t in self.tasks:
                            if t.id == card.task.id and t.assigned_to is not None:
                                t.solved_time = pygame.time.get_ticks() 
                        planned_parts = [t for t in self.tasks if t.id == card.task.id and t.assigned_to is not None]
                        if planned_parts:
                            first_part = min(planned_parts, key=lambda x: x.week_start)
                            target_scroll = first_part.week_start * self.timeline.day_width - ((self.timeline.rect.width - self.timeline.label_width) / 2) + (self.timeline.day_width / 2)
                            max_scroll = max(0, self.timeline.total_content_width - (self.timeline.rect.width - self.timeline.label_width))
                            self.scrollbar.scroll_x = max(0, min(target_scroll, max_scroll))
                            self.timeline.scroll_offset = int(self.scrollbar.scroll_x)
                    else:
                        # Démarrer le Drag & Drop depuis le panier
                        card.is_dragging = True
                        card.drag_offset = (event.pos[0] - card.rect.x, event.pos[1] - card.rect.y)
                        self.dragged_item = card
                        self.drag_day_offset = int((event.pos[0] - card.rect.x) / card.width * (card.task.duration / 8.0))
                    break

    def _handle_context_menu_click(self, pos):
        if not self.context_menu['bg_rect'].collidepoint(pos):
            self.context_menu = None
            return

        clicked_opt = next((self.context_menu['options'][i] for i, r in enumerate(self.context_menu['rects']) if r.collidepoint(pos)), None)
        menu_type = self.context_menu.get('type', 'task')
        saved_menu = self.context_menu 
        self.context_menu = None 
        
        if not clicked_opt: return

        if menu_type == 'task':
            target_t = saved_menu['task']
            
            if clicked_opt in ["Placer au plus tôt", "Placer sans conflit"]:
                mode = "early" if clicked_opt == "Placer au plus tôt" else "no_conflict"
                if clicked_opt == "Placer au plus tôt" and self.tutorial.current()["id"] == "PLAN_EARLY": self.tutorial.trigger_validation()
                
                split_day = math.ceil(getattr(self, 'current_day', 0.0)-0.06)
                if target_t.week_start < split_day and target_t.assigned_to is not None:
                    if split_day < target_t.week_start + (target_t.duration / 8.0):
                        self.save_state()
                        new_task = self._split_task_at_day(target_t, split_day)
                        if new_task:
                            self.save_state()
                            self.tasks.insert(self.tasks.index(target_t) + 1, new_task)
                            self.realign_delays()
                            self.update_layout()
                            self.replan_tasks_subset([new_task], mode=mode)
                    else:
                        self.show_notification("Tâche déjà terminée, impossible d'optimiser.", (200, 50, 50))
                else:
                    self.replan_tasks_subset([target_t], mode=mode)
                    
            elif clicked_opt == "Désépingler":
                if self.tutorial.current()["id"] == "RIGHT_CLICK": self.tutorial.trigger_validation()
                self.save_state(); target_t.is_pinned = False; self.update_layout()
            elif clicked_opt == "Épingler":
                self.save_state(); target_t.is_pinned = True; self.update_layout()
            elif clicked_opt == "Désassigner":
                self.save_state()
                for t in self.tasks:
                    if t.id == target_t.id: t.forced_op = None
                self.update_layout()
            elif clicked_opt == "Déplanifier":
                self.save_state()
                for op in self.operators:
                    if op.name == target_t.assigned_to and target_t in op.tasks: op.tasks.remove(target_t)
                target_t.assigned_to = None; target_t.week_start = -1; target_t.is_pinned = False
                self._reindex_tasks_parts()
                self.update_layout()

        elif menu_type == 'activity':
            act_id = saved_menu['activity_id']
            if clicked_opt in ["Placer au plus tôt", "Placer sans conflit"]:
                mode = "early" if "plus tôt" in clicked_opt else "no_conflict"
                if clicked_opt == "Placer au plus tôt" and self.tutorial.current()["id"] == "PLAN_EARLY": self.tutorial.trigger_validation()
                
                split_day = math.ceil(getattr(self, 'current_day', 0.0)-0.06)
                activity_tasks = [t for t in self.tasks if getattr(t, 'activity_id', None) == act_id and not getattr(t, 'is_pinned', False) and not (t.assigned_to is not None and t.week_start < split_day)]
                
                if activity_tasks: self.replan_tasks_subset(activity_tasks, mode=mode)
                else: self.show_notification("Aucune tâche modifiable.", color=(200, 150, 50))
                    
            elif clicked_opt == "Déplanifier":
                self.save_state()
                for t in self.tasks:
                    if getattr(t, 'activity_id', None) == act_id and t.assigned_to is not None:
                        for op in self.operators:
                            if op.name == t.assigned_to and t in op.tasks: op.tasks.remove(t)
                        t.assigned_to = None; t.week_start = -1; t.start_half = 0; t.is_pinned = False
                self._reindex_tasks_parts()
                self.update_layout()

    def _handle_right_click(self, pos):
        self.context_menu = None
        target_task, target_activity_id = None, None
        
        # 1. Timeline
        for blk in reversed(self.create_timeline_blocks()):
            if blk.rect.collidepoint(pos):
                target_task = blk.task; break
                
        # 2. Basket
        if not target_task:
            for card in reversed(self.create_basket_cards()):
                if card.rect.collidepoint(pos):
                    target_task = card.task; break
                    
        # 3. Activity Boxes
        if not target_task:
            self.update_activity_boxes()
            for box in getattr(self, 'activity_boxes', []):
                if box.rect.collidepoint(pos):
                    target_activity_id = box.id; break

        menu_w, menu_h = int(190 * self.scale_x), int(40 * self.scale_y)
        if target_task:
            options = ["Placer au plus tôt", "Placer sans conflit"]
            if target_task.assigned_to is not None:
                options.append("Déplanifier")
                options.append("Désépingler" if getattr(target_task, 'is_pinned', False) else "Épingler")
            if getattr(target_task, 'forced_op', None): options.append("Désassigner")
                
            rects = [pygame.Rect(pos[0], pos[1] + i*menu_h, menu_w, menu_h) for i in range(len(options))]
            self.context_menu = {'type': 'task', 'rects': rects, 'options': options, 'task': target_task, 'bg_rect': pygame.Rect(pos[0], pos[1], menu_w, menu_h * len(options))}

        elif target_activity_id is not None:
            options = ["Placer au plus tôt", "Placer sans conflit"]               
            if any(t.assigned_to is not None for t in self.tasks if getattr(t, 'activity_id', None) == target_activity_id):
                options.append("Déplanifier")
            
            rects = [pygame.Rect(pos[0], pos[1] + i*menu_h, menu_w, menu_h) for i in range(len(options))]
            self.context_menu = {'type': 'activity', 'activity_id': target_activity_id, 'options': options, 'rects': rects, 'bg_rect': pygame.Rect(pos[0], pos[1], menu_w, menu_h * len(options))}

    def _handle_mouse_up(self, event):
        self.is_dragging_basket_scroll = False

        # Boutons de l'Area Selection
        if self._sel_action_rects and not getattr(self, 'dragged_item', None):
            for label, rect in self._sel_action_rects.items():
                if rect.collidepoint(event.pos):
                    self._apply_area_selection_action(label)
                    self._area_sel_start = None; self._area_sel_current = None
                    break

        # Fin du tracé Area Selection
        if self._area_sel_start and not getattr(self, 'dragged_item', None):
            x0, y0 = self._area_sel_start
            x1, y1 = self._area_sel_current or event.pos
            sel = pygame.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            if sel.width > 6 or sel.height > 6:
                self._selected_task_ids = {(blk.task.id, blk.task.part_index) for blk in self.create_timeline_blocks() if sel.colliderect(blk.rect)}
            self._area_sel_start = None; self._area_sel_current = None
        
        # Logique de relâchement du Drag & Drop
        if getattr(self, 'dragged_item', None):
            self._process_drag_drop(event)
            
    def _process_drag_drop(self, event):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        exact_current_day = math.ceil(getattr(self, 'current_day', 0.0) - 0.06)

        # 1. Multi-Drag Execution
        if getattr(self, '_multi_drag_active', False) and self._multi_drag_preview:
            self._execute_multi_drag(exact_current_day)
            return

        # Calcul d'aimantation (Snap)
        offset_x = (self.dragged_item.drag_offset[0] / self.dragged_item.width * (self.dragged_item.task.duration / 8.0) * self.timeline.day_width) if hasattr(self.dragged_item, 'width') else self.dragged_item.drag_offset[0]
        relative_x = (event.pos[0] - offset_x) - (self.timeline.rect.x + self.timeline.label_width) + self.timeline.scroll_offset
        
        target_week = max(float(max(0, int(round(relative_x / self.timeline.day_width)))), float(int(exact_current_day)))
        t_end_eval = round(target_week + (self.dragged_item.task.duration / 8.0), 2)
        new_op = self.timeline.get_operator_at_position(event.pos[1])

        # 2. Lâcher sur la Colonne de Gauche (Forcer Opérateur)
        colonne_gauche_rect = pygame.Rect(self.timeline.rect.x, self.timeline.rect.y, self.timeline.label_width, self.timeline.rect.height)
        if colonne_gauche_rect.collidepoint((mouse_x, mouse_y)):
            if new_op:
                if self.dragged_item.task.pool_name != new_op.pool_name:
                    self.show_notification(f"Action impossible : Réservé aux {self.dragged_item.task.pool_name}s !")
                else:
                    self.save_state()
                    if hasattr(self, 'tutorial') and self.tutorial.current()["id"] == "FORCED_OP": self.tutorial.trigger_validation()
                    
                    for t in self.tasks:
                        if t.id == self.dragged_item.task.id:
                            t.forced_op = new_op.name
                            if t.assigned_to and t.assigned_to != new_op.name:
                                for op in self.operators:
                                    if op.name == t.assigned_to and t in op.tasks: op.tasks.remove(t)
                                t.assigned_to = None; t.week_start = -1
                    self._reindex_tasks_parts()
                    self.update_layout()
            self._cleanup_drag()
            return

        # 3. Lâcher sur la Timeline Centrale
        if self.timeline.rect.collidepoint(event.pos) and new_op:
            if getattr(self.dragged_item.task, 'forced_op', None) and getattr(self.dragged_item.task, 'forced_op', None) != new_op.name:
                self.show_notification(f"Tâche réservée à {getattr(self.dragged_item.task, 'forced_op', None)} !")
            elif self.dragged_item.task.pool_name != new_op.pool_name:
                self.show_notification(f"Action impossible : Réservé aux {self.dragged_item.task.pool_name}s.")
            elif self.check_absence_conflict(new_op, self.dragged_item.task, target_week):
                self.show_notification("Cet opérateur est absent sur cette période !")
            elif any(max(target_week, u_s) < min(t_end_eval, u_e) for u_s, u_e in getattr(self.dragged_item.task, 'unavailabilities', [])):
                self.show_notification("Cette tâche est indisponible sur cette période !")
            elif self.use_horizon_limit and t_end_eval > 10:
                self.show_notification("Hors limite ! Planification max : Jour 10.")
            elif target_week < exact_current_day:
                self.show_notification("Impossible de planifier dans le passé !")
            else:
                is_valid_order, error_msg = self.check_precedence(self.dragged_item.task, target_week)
                if not is_valid_order and not getattr(self.tutorial, 'is_active', False):
                    self.show_notification("Avertissement : " + error_msg, color=(200, 150, 50))
                
                self.save_state()
                for op in self.operators:
                    if self.dragged_item.task in op.tasks: op.tasks.remove(self.dragged_item.task)
                    
                self.dragged_item.task.week_start = target_week
                self.dragged_item.task.assigned_to = new_op.name
                self.dragged_item.task.is_pinned = True
                new_op.tasks.append(self.dragged_item.task)
                
        # 4. Lâcher Ailleurs (Désassigner)
        else:
            if self.dragged_item.task.assigned_to is not None: self.save_state()
            for op in self.operators:
                if self.dragged_item.task in op.tasks: op.tasks.remove(self.dragged_item.task)
            self.dragged_item.task.assigned_to = None
            self.dragged_item.task.week_start = -1
            self.dragged_item.task.is_pinned = False

        self.merge_contiguous_tasks()
        self._reindex_tasks_parts()
        self.update_layout()
        self._cleanup_drag()

    def _execute_multi_drag(self, exact_current_day):
        self.save_state()
        errors = []
        for (task_id, part_index), (target_day, target_op_idx) in self._multi_drag_preview.items():
            t = next((x for x in self.tasks if x.id == task_id and x.part_index == part_index), None)
            if not t: continue
            target_op = self.operators[target_op_idx]
            if target_day < exact_current_day: errors.append(f"'{t.name}' dans le passé")
            elif t.pool_name != target_op.pool_name: errors.append(f"'{t.name}' : mauvais pool ({target_op.pool_name})")
            elif getattr(t, 'forced_op', None) and t.forced_op != target_op.name: errors.append(f"'{t.name}' réservée à {t.forced_op}")
            elif self.check_absence_conflict(target_op, t, target_day): errors.append(f"Absence de {target_op.name}")
        
        if errors:
            self.show_notification("Déplacement annulé : " + errors[0], (200, 50, 50))
        else:
            for (task_id, part_index), (target_day, target_op_idx) in self._multi_drag_preview.items():
                t = next((x for x in self.tasks if x.id == task_id and x.part_index == part_index), None)
                if not t: continue
                for op in self.operators:
                    if t in op.tasks: op.tasks.remove(t)
                t.week_start = target_day
                t.assigned_to = self.operators[target_op_idx].name
                self.operators[target_op_idx].tasks.append(t)
            self.merge_contiguous_tasks()
        
        self.update_layout()
        self._cleanup_drag()

    def _cleanup_drag(self):
        self._multi_drag_active = False
        self._multi_drag_leader = None
        self._multi_drag_offsets = {}
        self._multi_drag_preview = {}
        if self.dragged_item:
            self.dragged_item.handle_mouse_up()
            self.dragged_item = None

    def _reindex_tasks_parts(self):
        """Helper local pour réaligner les id (lissage)."""
        synced_tasks = [t for t in self.tasks if t.assigned_to is None]
        for op in self.operators:
            for t in op.tasks:
                if t not in synced_tasks: synced_tasks.append(t)
        self.tasks = synced_tasks

        id_groups = {}
        for t in self.tasks: id_groups.setdefault(t.id, []).append(t)
        for group in id_groups.values():
            if len(group) > 1:
                for i, t in enumerate(sorted(group, key=lambda x: (x.week_start if x.assigned_to else 9999, x.assigned_to or ""))): 
                    t.part_index = i + 1
            elif group: group[0].part_index = 0

    def _handle_mouse_motion(self, event):
        if getattr(self, 'dragged_item', None): self.dragged_item.handle_mouse_motion(event.pos)
        
        # Multi-drag Preview
        if getattr(self, '_multi_drag_active', False) and self._multi_drag_leader:
            leader = self._multi_drag_leader
            relative_x = (event.pos[0] - leader.drag_offset[0]) - (self.timeline.rect.x + self.timeline.label_width) + self.timeline.scroll_offset
            leader_day = float(max(0, int(round(relative_x / self.timeline.day_width))))
            
            leader_op_idx = next((i for i, op in enumerate(self.operators) if self.timeline.get_row_y_by_index(i) <= event.pos[1] < self.timeline.get_row_y_by_index(i) + self.timeline.row_height), None)
            if leader_op_idx is None:
                leader_op_idx = next((i for i, op in enumerate(self.operators) if op.name == self._multi_drag_leader.task.assigned_to), 0)
                
            self._multi_drag_preview = {}
            for task_key, (day_off, op_off) in self._multi_drag_offsets.items():
                self._multi_drag_preview[task_key] = (max(0, leader_day + day_off), max(0, min(len(self.operators) - 1, leader_op_idx + op_off)))
                
        # Area Selection Rectangle
        if getattr(self, '_area_sel_start', None):
            self._area_sel_current = event.pos

        # Scrollbar du Panier
        if getattr(self, 'is_dragging_basket_scroll', False):
            new_thumb_x = event.pos[0] - getattr(self, 'basket_drag_offset_x', 0)
            bar_x, visible_w = getattr(self, 'basket_bar_x', 0), getattr(self, 'basket_visible_width', 1)
            thumb_w, max_scroll = getattr(self, 'basket_thumb_width', 1), getattr(self, 'basket_max_scroll', 0)
            clamped_thumb_x = max(bar_x, min(new_thumb_x, bar_x + visible_w - thumb_w))
            if visible_w > thumb_w:
                self.basket_scroll = ((clamped_thumb_x - bar_x) / (visible_w - thumb_w)) * max_scroll

    def animate_transition(self, old_blocks, new_blocks):
        if getattr(self.timeline, 'timeline_combined', False):
            return
        frames = 45
        clock = pygame.time.Clock()
        
        old_exact = {f"{b.task.id}_{b.task.part_index}": b.rect.copy() for b in old_blocks}
        old_fallback = {}
        for b in old_blocks:
            if b.task.id not in old_fallback:
                old_fallback[b.task.id] = b
                
        basket_center = self.task_basket.rect.center
        if basket_center[1] <= 0: 
            basket_center = (self.width // 2, self.height)
            
        anim_data = []
        for nb in new_blocks:
            key_exact = f"{nb.task.id}_{nb.task.part_index}"
            
            if key_exact in old_exact:
                start_rect = old_exact[key_exact]
            elif nb.task.id in old_fallback:
                old_b = old_fallback[nb.task.id]
                day_diff = nb.task.week_start - old_b.task.week_start
                pixel_offset = day_diff * self.timeline.day_width
                start_rect = pygame.Rect(old_b.rect.x + pixel_offset, old_b.rect.y, nb.rect.width, nb.rect.height)
            else:
                start_rect = pygame.Rect(basket_center[0], basket_center[1], nb.rect.width, nb.rect.height)
                
            anim_data.append({'block': nb, 'start': start_rect, 'end': nb.rect.copy()})
            
        for i in range(1, frames + 1):
            t = i / frames
            ease = t * t * (3 - 2 * t) 
            
            self.screen.fill((230, 235, 245))
            self.scrollbar.draw(self.screen)
            
            # 1. Ajout de l'état des tâches pour les jauges de charge en mode agrégé
            self.timeline.draw(self.screen, self.font, self.small_font, self.tasks if self.timeline.timeline_combined else None)
            
            unassigned_unique = len(set((task.activity_id, task.name) for task in self.get_unassigned_tasks()))
            total_unique = len(set((task.activity_id, task.name) for task in self.tasks))
            self.task_basket.draw(self.screen, self.font, unassigned_unique, total_unique)
            self.save_button.draw(self.screen, self.font)
            self.load_button.draw(self.screen, self.font)
            self.solve_button.draw(self.screen, self.font)
            self.reset_button.draw(self.screen, self.font)
            
            # 2. Ajout du dessin du bouton d'agrégation pendant la transition
            self.all_combine_button.draw(self.screen, self.font)
            
            for data in anim_data:
                b, s, e = data['block'], data['start'], data['end']
                b.rect.x = int(s.x + (e.x - s.x) * ease)
                b.rect.y = int(s.y + (e.y - s.y) * ease)
                b.rect.width = max(10, int(s.width + (e.width - s.width) * ease))
                b.rect.height = int(s.height + (e.height - s.height) * ease)
                b.draw(self.screen, self.font, self.small_font)
            
            self.draw_replan_overlay(self.screen)
            pygame.display.flip()
            clock.tick(60)
            pygame.event.pump()

    def draw_dynamic_errors(self, screen):
        if getattr(self, 'tutorial', None) and getattr(self.tutorial, 'is_active', False):
            return

        if not self.current_errors and getattr(self, 'show_full_errors_popup', False):
            self.show_full_errors_popup = False

        def wrap_text(text, font, max_width):
            words = text.split(' ')
            lines, current_line = [], ""
            for word in words:
                test_line = current_line + word + " "
                if font.size(test_line)[0] < max_width:
                    current_line = test_line
                else:
                    if current_line: lines.append(current_line)
                    current_line = word + " "
            if current_line: lines.append(current_line)
            return lines

        if getattr(self, 'show_full_errors_popup', False):
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            
            box_w = int(1000 * getattr(self, 'scale_x', 1.0))
            max_text_w = box_w - 60 
            
            all_wrapped_lines = []
            for err in self.current_errors:
                wrapped = wrap_text("• " + err["long"], self.font, max_text_w)
                all_wrapped_lines.append(wrapped)
                
            total_lines = sum(len(lines) for lines in all_wrapped_lines)
            line_h = self.font.get_linesize()
            
            # --- NOUVEAU CALCUL : Taille et position cappées ---
            # Hauteur maximale = taille de l'écran - espace pour onglets (80) - marge en bas (40)
            max_box_h = self.height - int(120 * getattr(self, 'scale_y', 1.0)) 
            ideal_box_h = int(120 * getattr(self, 'scale_y', 1.0)) + (total_lines * line_h) + (len(self.current_errors) * 15)
            
            box_h = min(ideal_box_h, max_box_h)
            
            # On empêche le haut de la boîte de passer au-dessus des onglets
            min_y = int(80 * getattr(self, 'scale_y', 1.0))
            box_y = max(min_y, (self.height - box_h) // 2)
            
            box_rect = pygame.Rect((self.width - box_w)//2, box_y, box_w, box_h)
            self.full_error_popup_rect = box_rect
            
            # --- DESSIN DE LA BOÎTE ---
            pygame.draw.rect(screen, (245, 240, 240), box_rect, border_radius=12*int(self.scale))
            pygame.draw.rect(screen, (220, 80, 80), box_rect, 3, border_radius=12*int(self.scale))
            
            font_title = pygame.font.SysFont("trebuchetms", int(32 * getattr(self, 'scale', 1.0)), bold=True)
            title_surf = font_title.render(f"Liste des Erreurs ({len(self.current_errors)})", True, (200, 50, 50))
            screen.blit(title_surf, (box_rect.x + 20, box_rect.y + 20))

            y_offset = box_rect.y + int(80 * self.scale_y)
            erreurs_affichees = 0
            
            # --- BOUCLE D'AFFICHAGE INTELLIGENTE ---
            for lines_of_err in all_wrapped_lines:
                # Si l'ajout de ce bloc d'erreur dépasse le bas de la boîte, on arrête l'affichage
                if y_offset + (len(lines_of_err) * line_h) > box_rect.bottom - int(45 * self.scale_y):
                    break 
                    
                for line in lines_of_err:
                    err_surf = self.font.render(line, True, (60, 60, 60))
                    x_pos = box_rect.x + 30 if line.startswith("•") else box_rect.x + 45
                    screen.blit(err_surf, (x_pos, y_offset))
                    y_offset += line_h
                y_offset += 15
                erreurs_affichees += 1

            # --- INDICATION SI DES ERREURS SONT MASQUÉES ---
            if erreurs_affichees < len(self.current_errors):
                restant = len(self.current_errors) - erreurs_affichees
                pluriel = "s" if restant > 1 else ""
                msg_reste = f"... et {restant} autre{pluriel} erreur{pluriel} masquée{pluriel} par manque de place."
                reste_surf = self.small_font.render(msg_reste, True, (180, 100, 100))
                screen.blit(reste_surf, (box_rect.x + 30, box_rect.bottom - int(35 * self.scale_y)))

        else:
            box_w = int(500 * getattr(self, 'scale_x', 1.0))
            buttons_y = self.save_button.rect.y - int(10*self.scale_y)
            
            if not self.current_errors:
                box_h = int(55 * getattr(self, 'scale_y', 1.0))
                self.error_box_rect = pygame.Rect(self.width - box_w - int(20*getattr(self, 'scale_x', 1.0)), buttons_y - box_h - int(15*getattr(self, 'scale_y', 1.0)), box_w, box_h)
                
                pygame.draw.rect(screen, (240, 250, 240), self.error_box_rect, border_radius=int(self.scale*12))
                pygame.draw.rect(screen, (80, 200, 80), self.error_box_rect, 2, border_radius=int(self.scale*12))
                title_surf = self.font.render("0 erreur détectée", True, (50, 180, 50))
                screen.blit(title_surf, (self.error_box_rect.x + 15, self.error_box_rect.y + 12))
            else:
                max_err = min(3, len(self.current_errors))
                line_spacing = int(self.font.get_height() * 0.95) 
                box_h = int(50 * getattr(self, 'scale_y', 1.0)) + (max_err * line_spacing) + int(25 * getattr(self, 'scale_y', 1.0))
                
                self.error_box_rect = pygame.Rect(self.width - box_w - int(20*getattr(self, 'scale_x', 1.0)), buttons_y - box_h - int(15*getattr(self, 'scale_y', 1.0)), box_w, box_h)
                
                pygame.draw.rect(screen, (255, 240, 240), self.error_box_rect, border_radius=int(self.scale*12))
                pygame.draw.rect(screen, (220, 80, 80), self.error_box_rect, 3, border_radius=int(self.scale*12))
                
                pluriel = 's' if len(self.current_errors) > 1 else ''
                title_surf = self.font.render(f"{len(self.current_errors)} Erreur{pluriel} détectée{pluriel}", True, (200, 50, 50))
                screen.blit(title_surf, (self.error_box_rect.x + 15, self.error_box_rect.y + 12))
                
                y_offset = self.error_box_rect.y + int(40 * getattr(self, 'scale_y', 1.0))
                for i in range(max_err):
                    err_text = "• " + self.current_errors[i]["short"]
                    max_pixel_width = box_w - 20 
                    if self.font.size(err_text)[0] > max_pixel_width:
                        while len(err_text) > 2 and self.font.size(err_text + "...")[0] > max_pixel_width:
                            err_text = err_text[:-1]
                        err_text += "..."
                    err_surf = self.font.render(err_text, True, (80, 80, 80)) 
                    screen.blit(err_surf, (self.error_box_rect.x + 15, y_offset))
                    y_offset += line_spacing
                    
                txt_clic = f"+ {len(self.current_errors) - max_err} autres (cliquez)" if len(self.current_errors) > max_err else "(Cliquez pour agrandir)"
                click_surf = self.small_font.render(txt_clic, True, (150, 100, 100))
                screen.blit(click_surf, (self.error_box_rect.x + 15, y_offset))

    def _apply_area_selection_action(self, label: str):
        """Applique une action groupée sur les tâches sélectionnées par area selection."""
        if not getattr(self, '_selected_task_ids', None): return
        
        # On récupère toutes les tâches de la sélection
        selected = [t for t in self.tasks if (t.id, getattr(t, 'part_index', 0)) in self._selected_task_ids]
        if not selected: return

        self.save_state()

        if label == "Déplanifier":
            for t in selected:
                if t.assigned_to:
                    for op in self.operators:
                        if t in op.tasks: op.tasks.remove(t)
                t.assigned_to = None
                t.week_start = -1
                t.start_half = 0
                t.is_pinned = False
            self.merge_contiguous_tasks()
            self.update_layout()
            self.show_notification(f"{len(selected)} tâche(s) déplanifiée(s).", (50, 180, 255))

        elif label == "Épingler":
            for t in selected: t.is_pinned = True
            self.update_layout()
            self.show_notification(f"{len(selected)} tâche(s) épinglée(s).", (50, 200, 50))

        elif label == "Désépingler":
            for t in selected: t.is_pinned = False
            self.update_layout()
            self.show_notification(f"{len(selected)} tâche(s) désépinglée(s).", (50, 200, 50))
            
        # --- NOUVELLES ACTIONS LIAISON SOLVEUR ---
        elif label in ["Au plus tôt", "Placer sans conflit"]:
            mode = "early" if label == "Au plus tôt" else "no_conflict"
            split_day = math.ceil(getattr(self, 'current_day', 0.0) - 0.06)
            tasks_to_replan = []
            
            for t in selected:
                # On vérifie que la tâche est modifiable (pas dans le passé)
                if t.assigned_to is None or t.week_start >= split_day:
                    tasks_to_replan.append(t)
                    
            if tasks_to_replan:
                # Validation du tutoriel si actif
                if hasattr(self, 'tutorial') and getattr(self.tutorial, 'is_active', False) and getattr(self.tutorial, 'current', lambda: None)():
                    curr = self.tutorial.current()
                    if curr and curr.get("id") == "PLAN_EARLY" and label == "Au plus tôt":
                        self.tutorial.trigger_validation()
                        
                self.replan_tasks_subset(tasks_to_replan, mode=mode)
            else:
                self.show_notification("Aucune tâche modifiable (toutes passées ou épinglées).", color=(200, 150, 50))

        self._selected_task_ids = set()
        self._sel_action_rects = {}

    def draw(self, screen):
        # 1. Fond et composants de base
        # 1. Fond et composants de base
        screen.fill((230, 235, 245))
        self.scrollbar.draw(screen)
        
        # Envoi des tâches pour les jauges si le mode agrégé est activé
        tasks_to_pass = [] if self.raw_tasks == self.tasks else self.tasks
        self.timeline.draw(screen, self.font, self.small_font, tasks_to_pass if self.timeline.timeline_combined else None)
        
        # Variables géométriques et données communes
        content_start_x = self.timeline.rect.x + self.timeline.label_width
        mouse_pos = pygame.mouse.get_pos()
        timeline_rect = pygame.Rect(content_start_x, self.timeline.rect.y, self.timeline.rect.width - self.timeline.label_width, self.timeline.rect.height)
        
        # Récupération des blocs de la timeline
        timeline_blocks = self.create_timeline_blocks() if not self.timeline.timeline_combined else []
        
        # 2. Dessin des blocs de tâches individuels (si non combinés)
        constraint_markers = self._draw_timeline_blocks(screen, timeline_blocks, mouse_pos, content_start_x)
        
        # 3. Dessin des voiles, limites et contraintes de Drag & Drop
        self._draw_drag_constraints(screen, content_start_x, constraint_markers)
            
        # 4. Animation visuelle des tâches expulsées (Ghosts)
        self._draw_expelled_ghosts(screen, content_start_x)
        
        # 5. Rendu du panier de composants, des dossiers d'activités et des cartes
        self._draw_basket_and_cards(screen)
        
        # 6. Dessin de l'élément fantôme actuellement transporté à la souris
        self._draw_dragged_item(screen, mouse_pos)
        
        # 7. Boutons de contrôle de l'interface graphique
        self.save_button.draw(screen, self.font)
        self.load_button.draw(screen, self.font)
        self.reset_button.draw(screen, self.font)
        self.solve_button.draw(screen, self.font)
        if getattr(self, 'is_replanning', False):
            self.repair_button.draw(screen, self.font)
        self.draw_undo_redo_arrows(screen)
        self.all_combine_button.draw(screen, self.font)
        
        # 8. Rendu du menu contextuel (clic droit)
        self._draw_context_menu(screen, mouse_pos)
        
        # 9. Rendu de la sélection par rectangle (Area Selection) et actions groupées
        self._draw_area_selection(screen, timeline_blocks, timeline_rect, mouse_pos, content_start_x)
        
        # 10. Curseur rouge du jour présent et ombrage logique du passé
        self._draw_time_markers(screen, content_start_x)
        
        # 11. Indicateurs du mode découpage (Ciseaux)
        self._draw_cut_mode_indicator(screen, mouse_pos, content_start_x)
        
        # 12. Rendu de l'infobulle (Tooltip) dynamique au survol
        self._draw_tooltip(screen, mouse_pos, content_start_x)
        
        # 13. Système d'affichage des popups, erreurs et notifications temporelles
        self.draw_dynamic_errors(screen)
        self.draw_notifications(screen)
        if getattr(self, 'show_replan_popup', False):
            self.draw_replan_popup(screen)

    def _draw_timeline_blocks(self, screen, timeline_blocks, mouse_pos, content_start_x):
        constraint_markers = []
        if self.timeline.timeline_combined:
            return constraint_markers
            
        drag_min_start = 0.0
        drag_max_end = float(self.timeline.total_days)
        left_forbidden_rect = pygame.Rect(0, 0, 0, 0)
        right_forbidden_rect = pygame.Rect(0, 0, 0, 0)
        
        if self.dragged_item:
            drag_min_start, drag_max_end = self.get_valid_time_window(self.dragged_item.task)
            pixel_limit_left = content_start_x + (drag_min_start * self.timeline.day_width) - self.timeline.scroll_offset
            pixel_limit_right = content_start_x + (drag_max_end * self.timeline.day_width) - self.timeline.scroll_offset
            
            left_forbidden_rect = pygame.Rect(0, self.timeline.rect.y, pixel_limit_left, self.timeline.rect.height)
            right_forbidden_rect = pygame.Rect(pixel_limit_right, self.timeline.rect.y, 20000, self.timeline.rect.height)

        for blk in timeline_blocks:
            if blk.rect.collidepoint(mouse_pos):
                blk.is_hovered = True

            # Surbrillance liée au Tutoriel actif
            is_tuto_target = False
            if self.tutorial and self.tutorial.is_active:
                curr = self.tutorial.current()
                if curr and curr.get("highlight_task") == blk.task.id:
                    is_tuto_target = True

            if is_tuto_target:
                pulse = abs(math.sin(pygame.time.get_ticks() / 200.0))
                color = (255, 150 + 100 * pulse, 0)
                pygame.draw.rect(screen, color, blk.rect.inflate(8, 8), 4, border_radius=8)
            
            if not self.dragged_item or blk.task is not self.dragged_item.task:
                blk.draw(screen, self.font, self.small_font, highlight=None)

                # Gestion dynamique de l'assombrissement lors du Drag & Drop
                if self.dragged_item:
                    should_dim = True
                    if blk.task.activity_id == self.dragged_item.task.activity_id:
                        task_end = blk.task.week_start + blk.task.get_weeks_span()
                        is_blocking_pred = abs(task_end - drag_min_start) < 0.01
                        is_blocking_succ = abs(blk.task.week_start - drag_max_end) < 0.01
                        
                        if is_blocking_pred or is_blocking_succ: 
                            should_dim = False
                            marker_w = 6  
                            marker = pygame.Rect(0, blk.rect.y, marker_w, blk.rect.height)
                            marker.centerx = blk.rect.right + 1 if is_blocking_pred else blk.rect.left + 1
                            constraint_markers.append(marker)

                    if should_dim:
                        for forbidden_rect in (left_forbidden_rect, right_forbidden_rect):
                            clip = blk.rect.clip(forbidden_rect)
                            if clip.width > 0:
                                dim_surf = pygame.Surface((clip.width, clip.height), pygame.SRCALPHA)
                                dim_surf.fill((0, 0, 0, 40)) 
                                screen.blit(dim_surf, clip.topleft)
        return constraint_markers

    def _draw_drag_constraints(self, screen, content_start_x, constraint_markers):
        if not self.dragged_item:
            return
            
        drag_min_start, drag_max_end = self.get_valid_time_window(self.dragged_item.task)
        pixel_limit_left = content_start_x + (drag_min_start * self.timeline.day_width) - self.timeline.scroll_offset
        pixel_limit_right = content_start_x + (drag_max_end * self.timeline.day_width) - self.timeline.scroll_offset

        clip_rect = pygame.Rect(content_start_x, self.timeline.rect.y, self.timeline.rect.width - self.timeline.label_width, self.timeline.rect.height)
        screen.set_clip(clip_rect)
        
        overlay_color = (0, 0, 0, 15)
        line_color = (220, 80, 80)
        
        if drag_min_start > 0:
            width = pixel_limit_left - (content_start_x - self.timeline.scroll_offset)
            if width > 0:
                overlay = pygame.Surface((int(width), self.timeline.rect.height), pygame.SRCALPHA)
                overlay.fill(overlay_color)
                screen.blit(overlay, (content_start_x - self.timeline.scroll_offset, self.timeline.rect.y))
                pygame.draw.line(screen, line_color, (pixel_limit_left, self.timeline.rect.y), (pixel_limit_left, self.timeline.rect.bottom), 2)
        
        if drag_max_end < self.timeline.total_days and pixel_limit_right < self.timeline.rect.right:
            width = self.timeline.rect.right - pixel_limit_right
            if width > 0:
                overlay = pygame.Surface((int(width), self.timeline.rect.height), pygame.SRCALPHA)
                overlay.fill(overlay_color)
                screen.blit(overlay, (pixel_limit_right, self.timeline.rect.y))
                pygame.draw.line(screen, line_color, (pixel_limit_right, self.timeline.rect.y), (pixel_limit_right, self.timeline.rect.bottom), 2)

        # Visualisation de la Deadline stricte
        if getattr(self.dragged_item.task, 'deadline', None) is not None:
            deadline_x = int(content_start_x + (self.dragged_item.task.deadline * self.timeline.day_width) - self.timeline.scroll_offset)
            if deadline_x > content_start_x and deadline_x < self.timeline.rect.right:
                pygame.draw.line(screen, (255, 0, 0), (deadline_x, self.timeline.rect.y), (deadline_x, self.timeline.rect.bottom), max(2, int(4 * self.scale)))
                forbidden_w = self.timeline.rect.right - deadline_x
                if forbidden_w > 0:
                    overlay = pygame.Surface((forbidden_w, self.timeline.rect.height), pygame.SRCALPHA)
                    overlay.fill((50, 50, 50, 150)) 
                    screen.blit(overlay, (deadline_x, self.timeline.rect.y))

        # Affichage des hachures de pannes (Indisponibilités de la tâche)
        if hasattr(self.dragged_item.task, 'unavailabilities'):
            task_pool = self.dragged_item.task.pool_name
            for op in self.timeline.operators:
                if op.pool_name == task_pool: 
                    row_y = self.timeline.get_row_y(op)
                    for u_s, u_e in self.dragged_item.task.unavailabilities:
                        u_px_x = int(content_start_x + (u_s * self.timeline.day_width) - self.timeline.scroll_offset)
                        u_px_w = int((u_e - u_s) * self.timeline.day_width)
                        if u_px_x + u_px_w > content_start_x and u_px_x < self.timeline.rect.right and u_px_w > 0:
                            unav_rect = pygame.Rect(u_px_x, row_y + 1, u_px_w, self.timeline.row_height - 2)
                            if unav_rect.width > 0 and unav_rect.height > 0:
                                overlay = pygame.Surface((unav_rect.width, unav_rect.height), pygame.SRCALPHA)
                                overlay.fill((255, 50, 50, 70)) 
                                for x in range(-unav_rect.height, unav_rect.width, 20):
                                    pygame.draw.line(overlay, (0, 0, 0, 100), (x, unav_rect.height), (x + unav_rect.height, 0), 2)
                                    pygame.draw.line(overlay, (0, 0, 0, 100), (x, 0), (x + unav_rect.height, unav_rect.height), 2)
                                screen.blit(overlay, unav_rect.topleft)

        # Griser les opérateurs interdits (mauvaise équipe ou opérateur forcé différent)
        forced_op = getattr(self.dragged_item.task, 'forced_op', None)
        task_pool = self.dragged_item.task.pool_name
        for op in self.timeline.operators:
            is_allowed = True
            if forced_op and op.name != forced_op:
                is_allowed = False
                force_grisage = 130
            elif not forced_op and op.pool_name != task_pool:
                is_allowed = False
                force_grisage = 50
                
            if not is_allowed:
                row_y = self.timeline.get_row_y(op)
                dim_rect = pygame.Rect(content_start_x, row_y, self.timeline.rect.width - self.timeline.label_width, self.timeline.row_height)
                dim_overlay = pygame.Surface((dim_rect.width, dim_rect.height), pygame.SRCALPHA)
                dim_overlay.fill((0, 0, 0, force_grisage))
                screen.blit(dim_overlay, dim_rect.topleft)
        screen.set_clip(None)

        for marker_rect in constraint_markers:
            pygame.draw.rect(screen, (220, 60, 60), marker_rect, border_radius=int(self.scale*10))

    def _draw_expelled_ghosts(self, screen, content_start_x):
        for i, op in enumerate(self.timeline.operators):
            if hasattr(op, 'expelled_ghosts'):
                row_y = self.timeline.get_row_y(op) 
                for ghost in op.expelled_ghosts[:]:
                    if ghost['alpha'] <= 0:
                        op.expelled_ghosts.remove(ghost)
                        continue
                        
                    alpha = int(ghost['alpha'])
                    g_x = int(content_start_x + (ghost['start_day'] * self.timeline.day_width) - self.timeline.scroll_offset)
                    g_w = int(ghost['duration_days'] * self.timeline.day_width)
                    
                    if g_x + g_w > content_start_x and g_x < self.timeline.rect.right and g_w > 0:
                        g_rect = pygame.Rect(g_x, row_y + 1, g_w, self.timeline.row_height - 2)
                        ghost_surf = pygame.Surface((g_rect.width, g_rect.height), pygame.SRCALPHA)
                        pygame.draw.rect(ghost_surf, (220, 50, 50, max(0, alpha - 120)), ghost_surf.get_rect(), border_radius=int(self.scale*4))
                        pygame.draw.rect(ghost_surf, (255, 50, 50, alpha), ghost_surf.get_rect(), 2, border_radius=int(self.scale*4))
                        
                        task_name = ghost.get('name', 'Expulsée')
                        text_surf = self.small_font.render(task_name[:5] + ".." if len(task_name) > 6 else task_name, True, (255, 180, 180))
                        text_surf.set_alpha(alpha)
                        ghost_surf.blit(text_surf, (g_rect.width//2 - text_surf.get_width()//2, g_rect.height//2 - text_surf.get_height()//2))
                        screen.blit(ghost_surf, (g_rect.x, g_rect.y))
                        
                    ghost['alpha'] -= 1.5

    def _draw_basket_and_cards(self, screen):
        unassigned_unique = len(set((task.activity_id, task.name) for task in self.get_unassigned_tasks()))
        total_unique = len(set((task.activity_id, task.name) for task in self.tasks))
        self.task_basket.draw(screen, self.font, unassigned_unique, total_unique)
        
        self.update_activity_boxes()
        for box in self.activity_boxes:
            box.draw(screen, self.font)
            
        cards = self.create_basket_cards()
        clip_rect = pygame.Rect(
            self.task_basket.rect.x + int(15 * self.scale_x), 
            self.task_basket.rect.y + int(50 * getattr(self, 'scale_y', 1.0)),
            self.task_basket.rect.width - int(30 * self.scale_x), 
            self.task_basket.rect.height - int(55 * getattr(self, 'scale_y', 1.0))
        )
        screen.set_clip(clip_rect)
        
        for i, card in enumerate(cards):
            if i < len(cards) - 1:
                arrow_y = card.rect.y + 25
                draw_arrow(screen, (card.rect.right, arrow_y), (cards[i+1].rect.left, arrow_y))
            if not getattr(self, 'dragged_item', None) or card.task is not self.dragged_item.task:
                card.draw(screen, self.font, self.small_font)
                
        screen.set_clip(None)

        if cards:
            total_content_width = (cards[-1].rect.right + getattr(self, 'basket_scroll', 0)) - (cards[0].rect.left + getattr(self, 'basket_scroll', 0))
            visible_width = self.task_basket.rect.width - 40
            max_scroll = max(0, total_content_width - visible_width)
            self.basket_scroll = min(getattr(self, 'basket_scroll', 0), max_scroll)
            
            if total_content_width > visible_width:
                bar_bg = pygame.Rect(self.task_basket.rect.x + 20, self.task_basket.rect.bottom - 12, visible_width, 8)
                pygame.draw.rect(screen, (200, 205, 215), bar_bg, border_radius=int(self.scale*4))
                
                thumb_width = max(30, (visible_width / total_content_width) * visible_width)
                thumb_x = bar_bg.x + (self.basket_scroll / max_scroll) * (visible_width - thumb_width) if max_scroll > 0 else bar_bg.x
                
                self.basket_max_scroll = max_scroll
                self.basket_bar_x = bar_bg.x
                self.basket_visible_width = visible_width
                self.basket_thumb_width = thumb_width
                self.basket_thumb_rect = pygame.Rect(thumb_x, bar_bg.y - 4, thumb_width, 16)
                
                thumb_color = (120, 130, 150) if getattr(self, 'is_dragging_basket_scroll', False) else (150, 160, 180)
                visual_thumb = pygame.Rect(thumb_x, bar_bg.y, thumb_width, 8)
                pygame.draw.rect(screen, thumb_color, visual_thumb, border_radius=int(self.scale*4))
            else:
                self.basket_thumb_rect = None
        else:
            self.basket_thumb_rect = None

    def _draw_dragged_item(self, screen, mouse_pos):
        if self.dragged_item:
            if isinstance(self.dragged_item, TaskCard) and self.timeline.rect.collidepoint(mouse_pos):
                proportion_x = self.dragged_item.drag_offset[0] / self.dragged_item.width
                block_width = max(int((self.dragged_item.task.duration / 8.0) * self.timeline.day_width), 30)
                temp_x = mouse_pos[0] - (proportion_x * block_width)
                temp_block = TaskBlock(self.dragged_item.task, temp_x, mouse_pos[1] - self.dragged_item.drag_offset[1], self.timeline.day_width, scale=self.scale)
                temp_block.is_dragging = True
                temp_block.draw(screen, self.font, self.small_font)
            else:
                if hasattr(self.dragged_item, 'clip_rect'):
                    self.dragged_item.clip_rect = None
                self.dragged_item.draw(screen, self.font, self.small_font)

    def _draw_context_menu(self, screen, mouse_pos):
        if getattr(self, 'context_menu', None):
            pygame.draw.rect(screen, (245, 245, 250), self.context_menu['bg_rect'])
            pygame.draw.rect(screen, (150, 150, 170), self.context_menu['bg_rect'], 1)
            for i, opt in enumerate(self.context_menu['options']):
                r = self.context_menu['rects'][i]
                if r.collidepoint(mouse_pos):
                    pygame.draw.rect(screen, (200, 220, 255), r)
                text_surf = self.small_font.render(opt, True, (20, 20, 20))
                text_y = r.y + (r.height - text_surf.get_height()) // 2
                screen.blit(text_surf, (r.x + int(10 * self.scale_x), text_y))
                if i < len(self.context_menu['options']) - 1:
                    pygame.draw.line(screen, (200, 200, 200), (r.x, r.bottom - 1), (r.right, r.bottom - 1))

    def _draw_area_selection(self, screen, timeline_blocks, timeline_rect, mouse_pos, content_start_x):
        live_selected = set()
        if getattr(self, '_area_sel_start', None) and self._area_sel_current:
            x0, y0 = self._area_sel_start
            x1, y1 = self._area_sel_current
            live_rect = pygame.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            if live_rect.width > 2 and live_rect.height > 2:
                for blk in timeline_blocks:
                    if live_rect.colliderect(blk.rect):
                        live_selected.add((blk.task.id, blk.task.part_index))

        screen.set_clip(timeline_rect)
        highlighted_ids = live_selected if getattr(self, '_area_sel_start', None) else getattr(self, '_selected_task_ids', set())
        for blk in timeline_blocks:
            if (blk.task.id, blk.task.part_index) in highlighted_ids:
                pygame.draw.rect(screen, (80, 130, 255), blk.rect.inflate(6, 6), 3, border_radius=int(self.scale * 12))
        screen.set_clip(None)

        if getattr(self, '_area_sel_start', None) and self._area_sel_current:
            x0, y0 = self._area_sel_start
            x1, y1 = self._area_sel_current
            sel_rect = pygame.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            if sel_rect.width > 2 and sel_rect.height > 2:
                sel_surf = pygame.Surface((sel_rect.width, sel_rect.height), pygame.SRCALPHA)
                sel_surf.fill((100, 150, 255, 50))
                screen.blit(sel_surf, sel_rect.topleft)
                pygame.draw.rect(screen, (80, 130, 255), sel_rect, 2, border_radius=int(self.scale * 3))

        # Rendu de la barre d'actions groupées
        if getattr(self, '_selected_task_ids', set()) and not getattr(self, '_area_sel_start', None):
            nb = len(self._selected_task_ids)
            actions = ["Au plus tôt"]
            conflicts = self.get_conflicting_tasks()
            has_conflict = any((t.id, getattr(t, 'part_index', 0)) in self._selected_task_ids for t in conflicts)
            if has_conflict:
                actions.append("Placer sans conflit")
            actions.extend(["Déplanifier", "Épingler", "Désépingler"])
            
            btn_h = int(32 * getattr(self, 'scale_y', 1.0))
            padding = int(8 * getattr(self, 'scale_x', 1.0))
            
            lbl_text = f"{nb} sélectionnée(s) :"
            lbl = self.small_font.render(lbl_text, True, (10, 10, 10))
            total_btns_w = sum(int(len(action) * 10 * getattr(self, 'scale_x', 1.0)) for action in actions) + (len(actions) - 1) * padding
            total_w = lbl.get_width() + total_btns_w + int(30 * getattr(self, 'scale_x', 1.0))
            
            # Barre positionnée en overlay dans la timeline, collée en bas
            bx = self.timeline.rect.x + self.timeline.label_width + int(10 * getattr(self, 'scale_x', 1.0))
            by = self.timeline.rect.bottom + int(10 * getattr(self, 'scale_x', 1.0))

            bar_rect = pygame.Rect(bx - int(6 * getattr(self, 'scale_x', 1.0)), by - int(4 * getattr(self, 'scale_y', 1.0)), total_w, btn_h + int(8 * getattr(self, 'scale_y', 1.0)))
            pygame.draw.rect(screen, (200, 200, 255), bar_rect, border_radius=int(getattr(self, 'scale', 1.0) * 6))
            screen.blit(lbl, (bx, by + (btn_h - lbl.get_height()) // 2))

            self._sel_action_rects = {}
            btn_x = bx + lbl.get_width() + int(10 * getattr(self, 'scale_x', 1.0))
            
            for action in actions:
                btn_w = int(len(action) * 10 * getattr(self, 'scale_x', 1.0))
                btn_rect = pygame.Rect(btn_x, by, btn_w, btn_h)
                is_hovered = btn_rect.collidepoint(mouse_pos)
                
                if action == "Déplanifier":
                    btn_color = (220, 100, 100) if is_hovered else (160, 55, 55)
                elif action == "Au plus tôt":
                    btn_color = (100, 200, 100) if is_hovered else (60, 160, 60)
                elif action == "Placer sans conflit":
                    btn_color = (240, 180, 60) if is_hovered else (200, 140, 40)
                else:
                    btn_color = (100, 150, 255) if is_hovered else (60, 90, 180)
                    
                pygame.draw.rect(screen, btn_color, btn_rect, border_radius=int(getattr(self, 'scale', 1.0) * 5))
                pygame.draw.rect(screen, (150, 180, 255), btn_rect, 1, border_radius=int(getattr(self, 'scale', 1.0) * 5))
                txt = self.small_font.render(action, True, (255, 255, 255))
                screen.blit(txt, txt.get_rect(center=btn_rect.center))
                self._sel_action_rects[action] = btn_rect
                btn_x += btn_w + padding

        # Rendu Multi-Drag Ghost Preview
        if getattr(self, '_multi_drag_active', False) and getattr(self, '_multi_drag_preview', {}):
            screen.set_clip(timeline_rect)
            leader_key = (self._multi_drag_leader.task.id, self._multi_drag_leader.task.part_index) if self._multi_drag_leader else (-1, -1)
            for (task_id, part_index), (target_day, target_op_idx) in self._multi_drag_preview.items():
                if (task_id, part_index) == leader_key: continue
                t = next((x for x in self.tasks if x.id == task_id and x.part_index == part_index), None)
                if t is None: continue
                target_op = self.operators[target_op_idx]
                ghost_x = int(content_start_x + target_day * self.timeline.day_width - self.timeline.scroll_offset)
                ghost_y = self.timeline.get_row_y(target_op)
                ghost_w = max(int((t.duration / 8.0) * self.timeline.day_width), 30)
                ghost_h = int(self.timeline.row_height - 2)
                ghost_rect = pygame.Rect(ghost_x, ghost_y + 1, ghost_w, ghost_h)
                ghost_surf = pygame.Surface((ghost_w, ghost_h), pygame.SRCALPHA)
                base_col = ACTIVITY_COLORS.get(getattr(t, 'activity_id', 0), DEFAULT_COLOR)
                ghost_surf.fill((*base_col, 120))
                pygame.draw.rect(ghost_surf, (80, 130, 255, 200), ghost_surf.get_rect(), 2, border_radius=int(self.scale * 8))
                screen.blit(ghost_surf, ghost_rect.topleft)
            screen.set_clip(None)

    def _draw_time_markers(self, screen, content_start_x):
        current_day = getattr(self, 'current_day', 0.0)
        cursor_x = content_start_x + (current_day * self.timeline.day_width) - self.timeline.scroll_offset if current_day > 0 else -1

        if current_day > 0 and content_start_x <= cursor_x:
            past_end_x = min(cursor_x, self.timeline.rect.right)
            past_width = past_end_x - content_start_x
            if past_width > 0:
                veil = pygame.Surface((int(past_width), self.timeline.rect.height), pygame.SRCALPHA)
                veil.fill((50, 50, 50, 60))
                screen.blit(veil, (content_start_x, self.timeline.rect.y))
                
        if current_day > 0 and content_start_x <= cursor_x <= self.timeline.rect.right:
            pygame.draw.line(screen, (255, 0, 0), (cursor_x, self.timeline.rect.y), (cursor_x, self.timeline.rect.bottom), 2)
            points = [(cursor_x - 8, self.timeline.rect.y - 8), (cursor_x + 8, self.timeline.rect.y - 8), (cursor_x, self.timeline.rect.y + 4)]
            pygame.draw.polygon(screen, (255, 0, 0), points)

        if getattr(self, 'use_horizon_limit', False):
            horizon_limit = 10
            horizon_x = int(content_start_x + (horizon_limit * self.timeline.day_width) - self.timeline.scroll_offset)
            if horizon_x < self.timeline.rect.right:
                clip_start = max(content_start_x, horizon_x)
                dark_w = self.timeline.rect.right - clip_start
                if dark_w > 0:
                    dark_veil = pygame.Surface((int(dark_w), self.timeline.rect.height), pygame.SRCALPHA)
                    dark_veil.fill((20, 20, 25, 220))
                    screen.blit(dark_veil, (clip_start, self.timeline.rect.y))
                    pygame.draw.line(screen, (220, 40, 40), (horizon_x, self.timeline.rect.y), (horizon_x, self.timeline.rect.bottom), 3)
                    lim_surf = self.small_font.render(f"LIMITE : FIN DU JOUR {horizon_limit}", True, (255, 100, 100))
                    screen.blit(lim_surf, (horizon_x + 10, self.timeline.rect.y + 10))

    def _draw_cut_mode_indicator(self, screen, mouse_pos, content_start_x):
        if getattr(self, 'cut_mode', False):
            if self.timeline.rect.collidepoint(mouse_pos):
                op_survole = self.timeline.get_operator_at_position(mouse_pos[1])
                if op_survole and mouse_pos[0] >= content_start_x:
                    ligne_y = self.timeline.get_row_y(op_survole)
                    snapped_day = round((mouse_pos[0] - content_start_x + self.timeline.scroll_offset) / self.timeline.day_width)
                    snapped_x = content_start_x + (snapped_day * self.timeline.day_width) - self.timeline.scroll_offset
                    pygame.draw.line(screen, (255, 100, 100), (snapped_x, ligne_y), (snapped_x, ligne_y + self.timeline.row_height), 3)
            
            if 'ciseaux' in ICONS:
                screen.blit(ICONS['ciseaux'], ICONS['ciseaux'].get_rect(center=mouse_pos))
            else:
                pygame.draw.line(screen, (220, 50, 50), (mouse_pos[0] - 6, mouse_pos[1] - 6), (mouse_pos[0] + 6, mouse_pos[1] + 6), 3)
                pygame.draw.line(screen, (220, 50, 50), (mouse_pos[0] - 6, mouse_pos[1] + 6), (mouse_pos[0] + 6, mouse_pos[1] - 6), 3)
        else:
            pygame.mouse.set_visible(True)

    def _draw_tooltip(self, screen, mouse_pos, content_start_x):
        if not getattr(self, 'dragged_item', None) and not getattr(self, 'context_menu', None) and not self.timeline.timeline_combined:
            current_hovered = None
            if self.timeline.rect.collidepoint(mouse_pos):
                if mouse_pos[0] >= content_start_x:
                    timeline_blocks = self.create_timeline_blocks()
                    for blk in reversed(timeline_blocks):
                        if blk.rect.collidepoint(mouse_pos):
                            current_hovered = blk.task
                            break
            elif self.task_basket.rect.collidepoint(mouse_pos):
                if hasattr(self, 'create_basket_cards'):
                    cards = self.create_basket_cards()
                    for card in reversed(cards):
                        if card.rect.collidepoint(mouse_pos):
                            current_hovered = card.task
                            break                      
            if current_hovered != getattr(self, 'hovered_task', None):
                self.hovered_task = current_hovered
                self.hover_start_time = pygame.time.get_ticks()
                
            if self.hovered_task is not None:
                temps_ecoule = pygame.time.get_ticks() - self.hover_start_time
                if temps_ecoule > 600: 
                    draw_task_tooltip(self.screen, self.hovered_task, self.scale, self.width, self.height, mouse_pos)
        else:
            self.hovered_task = None

    def draw_replan_overlay(self, screen):
        if getattr(self, 'is_replanning', False):
            self.validate_replan_btn.rect.centerx = self.width // 2 + 150*self.scale_x
            self.validate_replan_btn.rect.y = 12*self.scale_y
            
            highlight_rect = self.validate_replan_btn.rect.inflate(12*self.scale_y, 12*self.scale_y)
            pygame.draw.rect(screen, (255, 140, 0, 100), highlight_rect, border_radius=int(self.scale*8))
            self.validate_replan_btn.draw(screen, self.font)

    def draw_replan_popup(self, screen):
        """Dessine la fenêtre résumant les modifications de réparation du solveur."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        changes = getattr(self, 'replan_changes', ["Aucune modification."])
        
        box_w = int(750 * getattr(self, 'scale_x', 1.0))
        box_h = int((150 + len(changes) * 30) * getattr(self, 'scale_y', 1.0))
        box_x = (self.width - box_w) // 2
        box_y = (self.height - box_h) // 2 + 150*self.scale_y
        popup_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        
        pygame.draw.rect(screen, (40, 45, 60), popup_rect, border_radius=12)
        pygame.draw.rect(screen, (100, 150, 255), popup_rect, 3, border_radius=12)

        font_title = pygame.font.SysFont("trebuchetms", int(28 * getattr(self, 'scale', 1.0)), bold=True)
        font_text = pygame.font.SysFont("trebuchetms", int(20 * getattr(self, 'scale', 1.0)))

        title = font_title.render("Ajustements effectués par le solveur :", True, (255, 255, 255))
        screen.blit(title, (popup_rect.x + 20, popup_rect.y + 20))

        y = popup_rect.y + 60*self.scale_y
        for change in changes:
            text_surf = font_text.render(change, True, (200, 220, 255))
            screen.blit(text_surf, (popup_rect.x + 30, y))
            y += 30*self.scale_y

        close_msg = font_text.render("Cliquez n'importe où pour fermer cette fenêtre", True, (150, 150, 150))
        screen.blit(close_msg, (popup_rect.centerx - close_msg.get_width()//2, popup_rect.bottom - 30*self.scale_y))