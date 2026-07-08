import pygame

class UITheme:
    """Gestionnaire centralisé pour le scaling et les polices."""
    scale_x = 1.0
    scale_y = 1.0
    scale = 1.0
    fonts = {}

    @classmethod
    def init(cls, screen_width, screen_height):
        # Sécurité : Pygame doit être initialisé pour les polices
        if not pygame.font.get_init():
            pygame.font.init()
            
        cls.scale_x = screen_width / 1680.0
        cls.scale_y = screen_height / 945.0
        cls.scale = min(cls.scale_x, cls.scale_y)
        
        cls.fonts['title'] = pygame.font.SysFont("trebuchetms", int(36 * cls.scale), bold=True)
        cls.fonts['large'] = pygame.font.SysFont("trebuchetms", int(48 * cls.scale))
        cls.fonts['medium'] = pygame.font.SysFont("trebuchetms", int(32 * cls.scale))
        cls.fonts['normal'] = pygame.font.SysFont("trebuchetms", int(24 * cls.scale))
        cls.fonts['small'] = pygame.font.SysFont("trebuchetms", int(20 * cls.scale))
        cls.fonts['tiny'] = pygame.font.SysFont("trebuchetms", int(16 * cls.scale))

    @classmethod
    def get_font(cls, size_name='normal'):
        if not cls.fonts:
            cls.init(1680, 945)
        return cls.fonts.get(size_name, cls.fonts.get('normal'))

class NotificationManager:
    """Gestionnaire centralisé des notifications (Remplace les doublons dans les onglets)."""
    def __init__(self):
        self.notifications = []

    def show(self, text, color=(240, 50, 50)):
        self.notifications.append({
            "text": text,
            "time": pygame.time.get_ticks(),
            "color": color
        })
        if len(self.notifications) > 3:
            self.notifications = self.notifications[-3:]

    def draw(self, surface, screen_height):
        current_time = pygame.time.get_ticks()
        y_offset = screen_height - int(40 * UITheme.scale_y)
        font = UITheme.get_font('normal')
        
        # Nettoyage des vieilles notifications
        self.notifications = [n for n in self.notifications if current_time - n["time"] < 5000]
        
        for notif in reversed(self.notifications):
            age = current_time - notif["time"]
            alpha = 255
            if age > 4000:
                alpha = int(255 * (1.0 - (age - 4000) / 1000.0))
                alpha = max(0, min(255, alpha))
                
            text_surf = font.render(notif["text"], True, notif["color"])
            text_surf.set_alpha(alpha)
            
            bg_rect = pygame.Rect(
                int(15 * UITheme.scale_x), 
                y_offset - text_surf.get_height() - int(10 * UITheme.scale_y), 
                text_surf.get_width() + int(20 * UITheme.scale_x), 
                text_surf.get_height() + int(15 * UITheme.scale_y)
            )
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg_surf.fill((255, 255, 255, alpha))
            
            pygame.draw.rect(bg_surf, (*notif["color"], alpha), bg_surf.get_rect(), 2, border_radius=5)
            surface.blit(bg_surf, bg_rect.topleft)
            surface.blit(text_surf, (bg_rect.x + int(10 * UITheme.scale_x), bg_rect.y + int(8 * UITheme.scale_y)))
            
            y_offset -= (bg_rect.height + int(10 * UITheme.scale_y))

class Button:
    def __init__(self, x: int, y: int, width: int, height: int, text: str, color: tuple = (70, 130, 180), border_radius: int = 8, border_color:  tuple = (150, 200, 255)):
        # Application automatique du scaling
        self.rect = pygame.Rect(
            int(x * UITheme.scale_x), 
            int(y * UITheme.scale_y), 
            int(width * UITheme.scale_x), 
            int(height * UITheme.scale_y)
        )
        self.text = text
        self.is_hovered = False
        self.is_pressed = False
        self.color_normal = color
        self.color_hover = tuple(min(c + 30, 255) for c in color)
        self.color_pressed = tuple(max(c - 20, 0) for c in color)
        self.text_color = (255, 255, 255)
        self.border_radius = border_radius
        self.border_color = border_color

    def draw(self, surface: pygame.Surface, font=None):
        font = font or UITheme.get_font('normal')
        color = self.color_pressed if self.is_pressed else (self.color_hover if self.is_hovered else self.color_normal)
        
        pygame.draw.rect(surface, color, self.rect, border_radius=self.border_radius)
        pygame.draw.rect(surface, self.border_color, self.rect, 2, border_radius=self.border_radius)
        
        text_surf = font.render(self.text, True, self.text_color)
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.is_pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_pressed and self.rect.collidepoint(event.pos):
                self.is_pressed = False
                return True
            self.is_pressed = False
        return False

class HorizontalScrollbar:
    def __init__(self, x, y, width, height, total_content_width, visible_width):
        self.rect = pygame.Rect(
            int(x * UITheme.scale_x), 
            int(y * UITheme.scale_y), 
            int(width * UITheme.scale_x), 
            int(height * UITheme.scale_y)
        )
        self.total_content_width = total_content_width
        self.visible_width = visible_width
        self.scroll_x = 0
        self.is_dragging = False
        self.drag_start_x = 0
        self.start_scroll_x = 0
        self.update_thumb()

    def update_thumb(self):
        if self.total_content_width > self.visible_width:
            ratio = self.visible_width / self.total_content_width
            self.thumb_width = max(int(self.rect.width * ratio), int(30 * UITheme.scale_x))
            self.max_scroll = self.total_content_width - self.visible_width
        else:
            self.thumb_width = self.rect.width
            self.max_scroll = 0

    def update_content_width(self, total_width):
        self.total_content_width = total_width
        self.update_thumb()

    def draw(self, surface):
        pygame.draw.rect(surface, (220, 220, 230), self.rect, border_radius=4)
        if self.max_scroll > 0:
            scroll_ratio = self.scroll_x / self.max_scroll
            thumb_x = self.rect.x + int(scroll_ratio * (self.rect.width - self.thumb_width))
            color = (100, 100, 120) if self.is_dragging else (150, 150, 170)
            pygame.draw.rect(surface, color, (thumb_x, self.rect.y, self.thumb_width, self.rect.height), border_radius=4)

    def handle_event(self, event):
        if self.max_scroll <= 0: return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            scroll_ratio = self.scroll_x / self.max_scroll
            thumb_x = self.rect.x + int(scroll_ratio * (self.rect.width - self.thumb_width))
            thumb_rect = pygame.Rect(thumb_x, self.rect.y, self.thumb_width, self.rect.height)
            if thumb_rect.collidepoint(event.pos):
                self.is_dragging = True
                self.drag_start_x = event.pos[0]
                self.start_scroll_x = self.scroll_x
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1: 
            self.is_dragging = False
        elif event.type == pygame.MOUSEMOTION and self.is_dragging:
            delta = event.pos[0] - self.drag_start_x
            track_len = self.rect.width - self.thumb_width
            if track_len > 0:
                self.scroll_x = max(0, min(self.start_scroll_x + delta * (self.max_scroll / track_len), self.max_scroll))
            return True
        return False