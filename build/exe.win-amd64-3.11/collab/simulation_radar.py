import pygame
import math
from typing import List, Tuple

class RadarWidget:
    def __init__(self, x: int, y: int, radius: int, criteria: List[str]):
        self.center_x = x
        self.center_y = y
        self.radius = radius
        self.criteria = criteria
        self.num_criteria = len(criteria)
        self.rect = pygame.Rect(self.center_x - self.radius, self.center_y - self.radius, self.radius*2, self.radius*2)
        
        self.values = [1.0] * self.num_criteria
        self.min_values = [0.0] * self.num_criteria
        self.max_values = [100.0] * self.num_criteria
        self.constraint_type = ['max'] * self.num_criteria
        self.is_constrainable = [True] * self.num_criteria
        
        self.dragging_handle = None
        self.drag_start_pos = (0, 0)
        self.has_dragged = False
        self.handle_radius = int(12 * getattr(pygame.display.get_surface(), 'scale', 1.0)) if hasattr(pygame.display.get_surface(), 'scale') else 12
        
        self.bg_color = (20, 20, 30)
        self.grid_color = (60, 60, 80)
        self.axis_color = (100, 100, 120)
        self.polygon_color = (100, 150, 255, 100)
        self.polygon_border = (150, 200, 255)
        
        self.handle_max = (255, 200, 100)   
        self.handle_exact = (100, 255, 100) 
        self.text_color = (200, 200, 220)
        self.grid_levels = 5

        self.value_rects = [pygame.Rect(0,0,0,0) for _ in range(self.num_criteria)]
        self.editing_index = None
        self.input_text = ""

    def reset(self):
        self.values = [1.0] * self.num_criteria
        self.constraint_type = ['max'] * self.num_criteria
        self.editing_index = None
        
    def get_axis_angle(self, index: int) -> float: return -math.pi / 2 + (2 * math.pi * index / self.num_criteria)
    def get_handle_position(self, index: int) -> Tuple[int, int]:
        angle = self.get_axis_angle(index)
        dist = self.radius * self.values[index]
        return (int(self.center_x + dist * math.cos(angle)), int(self.center_y + dist * math.sin(angle)))
    def get_axis_end(self, index: int) -> Tuple[int, int]:
        angle = self.get_axis_angle(index)
        return (int(self.center_x + self.radius * math.cos(angle)), int(self.center_y + self.radius * math.sin(angle)))
    
    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        for i in range(1, self.grid_levels + 1):
            r = int(self.radius * i / self.grid_levels)
            pygame.draw.circle(surface, self.grid_color, (self.center_x, self.center_y), r, 1)
            
        for i in range(self.num_criteria):
            pygame.draw.line(surface, self.axis_color, (self.center_x, self.center_y), self.get_axis_end(i), 1)
        
        points = [self.get_handle_position(i) for i in range(self.num_criteria)]
        poly_surf = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        pygame.draw.polygon(poly_surf, self.polygon_color, points)
        surface.blit(poly_surf, (0, 0))
        pygame.draw.polygon(surface, self.polygon_border, points, 2)
        
        for i in range(self.num_criteria):
            pos = self.get_handle_position(i)
            if self.is_constrainable[i]:
                color = self.handle_exact if self.constraint_type[i] == 'exact' else self.handle_max
                pygame.draw.circle(surface, color, pos, self.handle_radius)
                pygame.draw.circle(surface, (255, 255, 255), pos, self.handle_radius, 2)
        
            angle = self.get_axis_angle(i)
            label_dist = self.radius + 10
            label_x = self.center_x + label_dist * math.cos(angle)
            label_y = self.center_y + label_dist * math.sin(angle)
            
            if self.is_constrainable[i]:
                actual_value = self.min_values[i] + self.values[i] * (self.max_values[i] - self.min_values[i])
                sym_text = "=" if self.constraint_type[i] == 'exact' else "<="
                if self.editing_index == i:
                    cursor = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
                    val_str = f"{sym_text} {self.input_text}{cursor}"
                    text_color_val = (255, 255, 255) 
                else:
                    val_str = f"{sym_text} {int(round(actual_value))}"
                    text_color_val = color
            else:
                val_str = "" 
                text_color_val = self.text_color

            words = self.criteria[i].split('\n')
            line_surfaces = [font.render(w, True, self.text_color) for w in words]
            value_surf = font.render(val_str, True, text_color_val)
            
            total_text_height = sum(s.get_height() + 2 for s in line_surfaces) + value_surf.get_height() + 4
            
            marge_x = 15
            marge_y = 15
            
            if math.sin(angle) > 0.1: 
                start_y = int(label_y) + marge_y
            elif math.sin(angle) < -0.1: 
                start_y = int(label_y) - marge_y - total_text_height
            else: 
                start_y = int(label_y) - (total_text_height // 2)

            curr_y = start_y
            
            for s in line_surfaces:
                s_rect = s.get_rect()
                if math.cos(angle) > 0.1: s_rect.left = int(label_x) + marge_x
                elif math.cos(angle) < -0.1: s_rect.right = int(label_x) - marge_x
                else: s_rect.centerx = int(label_x)
                
                s_rect.top = curr_y
                surface.blit(s, s_rect)
                curr_y += s.get_height() + 2

            v_rect = value_surf.get_rect()
            if math.cos(angle) > 0.1: v_rect.left = int(label_x) + marge_x
            elif math.cos(angle) < -0.1: v_rect.right = int(label_x) - marge_x
            else: v_rect.centerx = int(label_x)
            
            v_rect.top = curr_y + 4
            if self.editing_index == i:
                padding = 4
                bg_rect = v_rect.inflate(padding*2, padding*2)
                pygame.draw.rect(surface, (40, 40, 50), bg_rect)
                pygame.draw.rect(surface, (255, 255, 255), bg_rect, 1)
            surface.blit(value_surf, v_rect)
            
            self.value_rects[i] = v_rect.inflate(20, 20)
    
    def handle_event(self, event):
        if self.editing_index is not None and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.input_text.strip():
                    try:
                        val = int(self.input_text)
                        val = max(self.min_values[self.editing_index], min(self.max_values[self.editing_index], val))
                        norm = (val - self.min_values[self.editing_index]) / (self.max_values[self.editing_index] - self.min_values[self.editing_index])
                        self.values[self.editing_index] = norm
                    except ValueError:
                        pass
                self.editing_index = None
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.editing_index = None
            elif event.unicode.isdigit(): 
                self.input_text += event.unicode
            return True
        return False

    def handle_mouse_down(self, pos: Tuple[int, int], button: int = 1) -> bool:
        if button == 1:
            for i, rect in enumerate(self.value_rects):
                if rect.collidepoint(pos) and self.is_constrainable[i]:
                    self.editing_index = i
                    self.input_text = ""
                    actual_val = self.min_values[i] + self.values[i] * (self.max_values[i] - self.min_values[i])
                    self.input_text = str(int(round(actual_val)))
                    return True
                    
            self.editing_index = None

            for i in range(self.num_criteria):
                if not self.is_constrainable[i]: continue
                handle_pos = self.get_handle_position(i)
                dist = math.hypot(pos[0] - handle_pos[0], pos[1] - handle_pos[1])
                if dist < self.handle_radius:
                    self.dragging_handle = i
                    self.drag_start_pos = pos
                    self.has_dragged = False
                    return True
        return False
    
    def handle_mouse_up(self):
        if self.dragging_handle is not None:
            if not getattr(self, 'has_dragged', False):
                current = self.constraint_type[self.dragging_handle]
                self.constraint_type[self.dragging_handle] = 'exact' if current == 'max' else 'max'
            self.dragging_handle = None
            
    def handle_mouse_motion(self, pos: Tuple[int, int]):
        if self.dragging_handle is not None:
            dist = math.hypot(pos[0] - self.drag_start_pos[0], pos[1] - self.drag_start_pos[1])
            if dist > 3:
                self.has_dragged = True
            angle = self.get_axis_angle(self.dragging_handle)
            axis_vec_x = math.cos(angle)
            axis_vec_y = math.sin(angle)
            projection = (pos[0] - self.center_x) * axis_vec_x + (pos[1] - self.center_y) * axis_vec_y
            self.values[self.dragging_handle] = min(max(projection / self.radius, 0.0), 1.0)

    def set_criterion_range(self, index: int, min_val: float, max_val: float):
        self.min_values[index] = min_val
        self.max_values[index] = max_val

    def get_targets_for_solver(self):
        keys = ['makespan', 'balance', 'wip', 'idle_time']
        
        targets = {}
        for i in range(min(self.num_criteria, len(keys))):
            if self.is_constrainable[i]:
                actual_value = self.min_values[i] + self.values[i] * (self.max_values[i] - self.min_values[i])
                targets[keys[i]] = {
                    'val': int(round(actual_value)),
                    'type': self.constraint_type[i]
                }
        return targets