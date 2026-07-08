import pygame

class TutorialManager:
    def __init__(self, screen, scale_x=1.0, scale_y=1.0):
        self.screen = screen
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.scale = min(scale_x, scale_y) # Facteur global pour les textes
        self.screen_w = self.screen.get_width()
        self.screen_h = self.screen.get_height()
    
        # Polices responsives (beaucoup plus grandes)
        self.font = pygame.font.SysFont("segoeui", int(24 * self.scale))
        self.title_font = pygame.font.SysFont("segoeui", int(32 * self.scale), bold=True)
        self.small_font = pygame.font.SysFont("segoeui", int(18 * self.scale))
        
        self.step = 0
        self.mode = "CENTER" 
        self.is_active = True
        
        self.is_validated = False
        self.validation_timer = 0
        self.validation_delay = 1000 
        
        # Bouton OK mis à l'échelle
        self.btn_ok_rect = pygame.Rect(0, 0, int(220 * self.scale_x), int(55 * self.scale_y))
        
        self.steps = [
            # PARTIE 1 : PLANNING
            {"index": 1, "id": "PLAN_TASK", "title": "1/19 : BIENVENUE !", 
             "text": "En bas de votre écran, vous trouverez 4 composants, chacun identifié par une couleur. Cliquez sur l'un d'eux pour faire apparaître la liste des tâches qui lui sont associées.\nChaque tâche est marquée d'une bande de couleur qui indique à quel type d'opérateur elle doit être confiée : une bande jaune signifie que la tâche revient à un assembleur (chargé de l'assemblage des modules), une bande bleue qu'elle revient à un contrôleur (chargé du contrôle de l'assemblage).\nLes opérateurs sont visibles en haut à gauche de votre écran. Votre mission est de glisser une tâche sur la ligne de l’un des opérateurs.", 
             "short": "Glissez une tâche vers le planning.", "block_sim": True},
            
            {"index": 2, "id": "UNPLAN_TASK", "title": "2/19 : LA DÉPLANIFICATION", 
             "text": "Il vous est possible d'annuler un placement à tout moment. Pour cela, repérez la tâche que vous souhaitez retirer dans la partie Planification en haut de votre écran. Vous avez deux façons de procéder : soit vous glissez la tâche en dehors de la zone de planning, soit vous faites un clic droit dessus et sélectionnez « Déplanifier ». Quand vous effectuez votre mission, vous pouvez à tout moment cliquer sur le cadre de la consigne en bas à droite pour la ré-ouvrir en plein écran.", 
             "short": "Déplanifiez la tâche.", "block_sim": True},
            
            {"index": 3, "id": "PLAN_EARLY", "title": "3/19 : AU PLUS TÔT", 
             "text": "Vous pouvez laisser l'outil planifier une tâche automatiquement à la date la plus proche possible. Pour cela, repérez la tâche souhaitée dans le panier en bas de votre écran, faites un clic droit dessus et sélectionnez « Placer au plus tôt ».\nCette fonctionnalité est également disponible pour un composant entier : faites un clic droit directement sur le composant pour planifier toutes ses tâches d'un coup. En faisant 'Placer sans conflit', le solveur fera des placements valides dans le planning actuel, quitte à ce que les tâches soient planifiées plus tard.", 
             "short": "Clic-droit sur une tâche > Placer au plus tôt.", "block_sim": True},
            
            {"index": 4, "id": "RIGHT_CLICK", "title": "4/19 : L'ÉPINGLE", 
             "text": "Vous pouvez fixer manuellement une tâche à un emplacement précis. Pour cela, glissez la tâche de votre choix sur la ligne d'un opérateur : elle sera automatiquement épinglée, ce qui signifie que c'est vous qui avez pris cette décision de placement. Une tâche épinglée ne pourra pas être déplacée automatiquement par le solveur.\nPour retirer l'épingle et laisser à nouveau le solveur disposer librement de cette tâche, faites un clic droit dessus et sélectionnez « Désépingler ».", 
             "short": "Déplacez une tâche puis \nClic-droit > Désepingler", "block_sim": True},
            
            {"index": 5, "id": "FORCED_OP", "title": "5/19 : LE WORKER", 
             "text": "Glissez une tâche sur la case d'un opérateur spécifique (case avec marqué 'Assembleur A/B/C' ou 'Contrôleur A/B'), pour lui assigner directement cette tâche.\nSi cette tâche était déjà planifiée chez un autre opérateur, elle sera automatiquement retirée de son planning et renvoyée dans le panier, en bas de votre écran.", 
             "short": "Assignez la tâche à un opérateur", "block_sim": True},
            
            {"index": 6, "id": "CUT_TASK", "title": "6/19 : LES CISEAUX", 
             "text": "Certaines tâches longues peuvent être découpées en deux parties pour plus de flexibilité dans la planification. Cette option est disponible uniquement pour les tâches d'une durée supérieure à 8 heures (soit une journée).\nPour découper une tâche, cliquez sur l'icône des ciseaux en bas de votre écran, puis cliquez sur la tâche concernée dans le planning.\nAstuce : vous pouvez également appuyer sur la touche ‘C’ de votre clavier pour aller plus vite !", 
             "short": "Coupez une tâche en deux.", "block_sim": True},
            
            {"index": 7, "id": "HISTORY", "title": "7/19 : L'HISTORIQUE", 
             "text": "Si vous faites une erreur, vous pouvez annuler votre dernière action à tout moment. Pour cela, cliquez sur la flèche arrière en bas à gauche de votre écran, ou utilisez le raccourci clavier Ctrl+Z.\nPour rétablir une action que vous venez d'annuler, cliquez sur la flèche avant ou utilisez Ctrl+Y.", 
             "short": "Faites Ctrl+Z, puis faites Ctrl+Y.", "block_sim": True},
            
            {"index": 8, "id": "SOLVE", "title": "8/19 : LE SOLVEUR", 
             "text": "L'algorithme peut compléter automatiquement votre planning à partir de ce que vous avez déjà planifié. Pour cela, cliquez sur 'Nouvelle solution'.\nÀ noter : lors de votre planification, il vous est possible de superposer temporairement des tâches, mais un planning contenant des chevauchements n'est pas valide. Il devra être corrigé avant de pouvoir être utilisé.", 
             "short": "Générez une nouvelle solution.", "block_sim": True},
            
            {"index": 9, "id": "SAVE", "title": "9/19 : LA SAUVEGARDE", 
             "text": "Pour retrouver rapidement une tâche déjà planifiée, cliquez dessus dans le panier en bas de votre écran : vous serez automatiquement redirigé vers son emplacement dans la timeline.\nEnregistrez maintenant votre travail en cliquant sur 'Sauvegarder'.", 
             "short": "Cliquez sur le bouton 'Sauvegarder'.", "block_sim": True},
            
            {"index": 10, "id": "RESET", "title": "10/19 : RÉINITIALISATION", 
             "text": "Le bouton 'Réinitialiser' efface l'intégralité du planning. Cliquez dessus pour vider le planning.", 
             "short": "Cliquez sur le bouton 'Réinitialiser'.", "block_sim": True},
            
            {"index": 11, "id": "LOAD", "title": "11/19 : LE CHARGEMENT", 
             "text": "Cliquez sur 'Charger' pour retrouver la sauvegarde que vous venez d'effectuer.", 
             "short": "Cliquez sur le bouton 'Charger'.", "block_sim": True},
        
            # PARTIE 3 : SUPERVISION & REPLANIFICATION (Devenue Partie 2)
            {"index": 12, "id": "GO_SUPERV", "title": "12/19 : ACCÈS AU TERRAIN", 
             "text": "Un nouvel onglet vient de se débloquer : 'Supervision'. Cliquez dessus en haut de l'écran. Dans cet onglet, votre rôle sera d'observer le déroulement du projet de construction d’un satellite. Si un imprévu survient, le temps s'arrêtera automatiquement et vous devrez replanifier pour rétablir un planning valide.", 
             "short": "Ouvrez l'onglet Supervision.", "block_sim": False},
            
            {"index": 13, "id": "PLAY_SUPERV", "title": "13/19 : LANCER LA SUPERVISION", 
             "text": "Vous avez devant vous le planning prévisionnel du projet. Cliquez sur le bouton 'Lecture' en bas de l'écran pour lancer le déroulement des jours.\nObservez la barre rouge avancer dans la timeline. Surveillez qu'aucun imprévu ne survienne. Si c'est le cas, le temps s'arrêtera automatiquement.", 
             "short": "Cliquez sur Lecture et attendez l'aléa.", "block_sim": False},
            
            {"index": 14, "id": "CLICK_REPLAN", "title": "14/19 : RÉAGIR", 
             "text": "Un problème vient de survenir ! Une fenêtre s’est affichée au centre pour vous expliquer la situation.\nLisez le message : la tâche Cataphorèse a pris du retard (cadre rouge), ce qui cause un conflit dans le planning. Cliquez sur la bouton ‘Aller replanifier’ pour corriger le problème.", 
             "short": "Cliquez sur Aller Replanifier.", "block_sim": False},
            
            {"index": 15, "id": "FIX_CATAPHORESE", "title": "15/19 : RÉPARER LE PLANNING", 
             "text": "Deux règles essentielles à respecter dans ce planning : un opérateur ne peut réaliser qu'une seule tâche à la fois, et les tâches d'un même composant (même couleur) doivent être effectuées dans l'ordre défini par la gamme.\nÀ cause du retard, la tâche 'Ctrl Cataphorèse' (mise en surbrillance) se retrouve planifiée avant la fin de la Cataphorèse elle-même, ce qui est un conflit. Déplacez 'Ctrl Cataphorèse', par exemple aux Jour 9-10, pour résoudre ce conflit.", 
             "short": "Déplacez 'Ctrl Cataphorèse' aux Jours 9-10.", "highlight_task": 316},
            
            {"index": 16, "id": "VALIDATE_TUTO", "title": "16/19 : VALIDER", 
             "text": "Bravo, le planning est de nouveau valide !\nPour confirmer vos modifications, cliquez sur le bouton orange ‘VALIDER LA REPLANIFICATION’ qui est apparu en haut de votre écran.", 
             "short": "Cliquez sur 'VALIDER LA REPLANIFICATION'.", "block_sim": False},
            
            {"index": 17, "id": "REPAIR_SOL", "title": "17/19 : NOUVEL ALÉA", 
             "text": "Un nouveau planning s'affiche. Il est fictif et a pour unique but de vous présenter la prochaine fonctionnalité de la replanification.\nCliquez sur 'Lecture' pour lancer la supervision, puis sur 'Aller replanifier'.", 
             "short": "Cliquez sur 'Lecture' puis 'Aller replanifier'.", "block_sim": False},
            
            {"index": 18, "id": "VALIDATE_TUTO_BIS", "title": "18/19 : RÉPARATION DE SOLUTION", 
             "text": "Pour vous aider à réagir correctement face aux aléas, un nouveau bouton est apparu : 'Réparer le planning'. Contrairement à 'Nouvelle solution' qui recalcule tout, ce mode tente de réparer le planning en minimisant les changements par rapport à votre planning actuelle. Ce processus peut prendre quelques secondes de plus (effet domino). À la fin, le solveur vous affichera une liste détaillée des modifications qu'il a dû effectuer. Cliquez sur 'Réparer le planning' puis validez la replanification pour continuer.", 
             "short": "Cliquez sur 'Réparer le planning' puis validez la replanification.", "block_sim": False},
            
            {"index": 19, "id": "TUTO_END", "title": "19/19 : FIN DU TUTORIEL", 
             "text": "Félicitations ! Vous maîtrisez maintenant l’ensemble de l’outil (Planification et Supervision).\nVous pouvez terminer la familiarisation pour commencer l’étude réelle.", 
             "short": "Observez les symboles d'aléas puis terminez la familiarisation.", "block_sim": False}
        ]

    def current(self):
        return self.steps[self.step] if self.step < len(self.steps) else None

    def trigger_validation(self, delay=1000):
        if not self.is_validated:
            self.is_validated = True
            self.validation_delay = delay
            self.validation_timer = pygame.time.get_ticks()

    def update(self):
        if self.is_validated:
            if pygame.time.get_ticks() - self.validation_timer > self.validation_delay:
                self.is_validated = False
                self.advance()

    def advance(self):
        if self.step < len(self.steps) - 1:
            self.step += 1
            self.mode = "CENTER"
        else:
            self.is_active = False

    def handle_events(self, event):
        if not self.is_active or not self.current(): return False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode == "CENTER":
                if self.btn_ok_rect.collidepoint(event.pos):
                    self.mode = "CORNER"
                    return True
                if getattr(self, 'btn_next_rect', pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    self.advance()
                    return True
                if getattr(self, 'btn_prev_rect', pygame.Rect(0,0,0,0)).collidepoint(event.pos) and self.step > 0:
                    self.step -= 1
                    return True
                return True 
            
            elif self.mode == "CORNER":
                if getattr(self, 'corner_rect', pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    self.mode = "CENTER"
                    return True
        return False

    def draw_multiline(self, surface, text, rect, font, color, line_height):
        y = rect.y
        for paragraph in text.split('\n'):
            words = paragraph.split(' ')
            line = ""
            for word in words:
                if font.size(line + word)[0] < rect.width: line += word + " "
                else:
                    surface.blit(font.render(line, True, color), (rect.x, y))
                    line = word + " "
                    y += line_height
            surface.blit(font.render(line, True, color), (rect.x, y))
            y += line_height

    def draw(self, surface):
        data = self.current()
        if not data or not self.is_active: return

        if self.mode == "CENTER":
            overlay = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            surface.blit(overlay, (0, 0))

            box_w = int(900 * self.scale_x)
            
            # =================================================================
            # 1. CALCUL DYNAMIQUE DE LA HAUTEUR DU TEXTE
            # =================================================================
            max_text_w = box_w - int(80 * self.scale_x)
            line_height = int(self.font.get_height() * 1.2)
            
            # On simule le découpage pour compter le nombre de lignes réelles
            nb_lines = 0
            for paragraph in data["text"].split('\n'):
                words = paragraph.split(' ')
                line = ""
                for word in words:
                    if self.font.size(line + word)[0] < max_text_w:
                        line += word + " "
                    else:
                        nb_lines += 1
                        line = word + " "
                nb_lines += 1
                
            text_total_height = nb_lines * line_height
            
            # =================================================================
            # 2. DIMENSIONNEMENT DE LA BOÎTE
            # =================================================================
            # Hauteur = Espace du Titre (90) + Hauteur du texte + Espace Boutons (120)
            box_h = int(90 * self.scale_y) + text_total_height + int(120 * self.scale_y)
            
            # Sécurité : On empêche la boîte d'être plus grande que l'écran
            box_h = min(box_h, self.screen_h - int(40 * self.scale_y))

            box_rect = pygame.Rect((self.screen_w - box_w)//2, (self.screen_h - box_h)//2, box_w, box_h)
            
            # Dessin du fond et bordure
            pygame.draw.rect(surface, (250, 250, 255), box_rect, border_radius=15)
            pygame.draw.rect(surface, (50, 100, 200), box_rect, 4, border_radius=15)

            # Titre
            surface.blit(self.title_font.render(data["title"], True, (30, 40, 80)), (box_rect.x + int(40*self.scale_x), box_rect.y + int(30*self.scale_y)))
            
            # Texte multilingue
            text_rect = pygame.Rect(box_rect.x + int(40*self.scale_x), box_rect.y + int(90*self.scale_y), max_text_w, text_total_height)
            self.draw_multiline(surface, data["text"], text_rect, self.font, (20, 20, 20), line_height=line_height)

            # =================================================================
            # 3. PLACEMENT DYNAMIQUE DES BOUTONS (En bas de la boîte)
            # =================================================================
            self.btn_ok_rect.centerx = box_rect.centerx
            self.btn_ok_rect.bottom = box_rect.bottom - int(30*self.scale_y)
            
            pygame.draw.rect(surface, (50, 200, 50), self.btn_ok_rect, border_radius=8)
            txt = self.title_font.render("J'ai compris", True, (255, 255, 255))
            surface.blit(txt, txt.get_rect(center=self.btn_ok_rect.center))

            self.small_font.set_underline(True)
            if self.step < len(self.steps) - 1: 
                self.btn_next_rect = surface.blit(self.small_font.render("Suivant", True, (50, 50, 70)), (box_rect.right - int(100*self.scale_x), box_rect.bottom - int(50*self.scale_y)))
            if self.step > 0: 
                self.btn_prev_rect = surface.blit(self.small_font.render("Précédent", True, (50, 50, 70)), (box_rect.left + int(40*self.scale_x), box_rect.bottom - int(50*self.scale_y)))
            self.small_font.set_underline(False)

        elif self.mode == "CORNER":
            box_w, box_h = int(450 * self.scale_x), int(120 * self.scale_y)
            self.corner_rect = pygame.Rect(self.screen_w - box_w - int(30*self.scale_x), self.screen_h - box_h - int(110*self.scale_y), box_w, box_h)
            
            border_color = (50, 200, 50) if self.is_validated else (255, 200, 50)
            thickness = 4 if self.is_validated else 2
            
            pygame.draw.rect(surface, (40, 45, 60), self.corner_rect, border_radius=10)
            pygame.draw.rect(surface, border_color, self.corner_rect, thickness, border_radius=10)
            
            surface.blit(self.font.render("Objectif actuel :", True, border_color), (self.corner_rect.x + int(20*self.scale_x), self.corner_rect.y + int(10*self.scale_y)))
            text_rect = pygame.Rect(self.corner_rect.x + int(20*self.scale_x), self.corner_rect.y + int(40*self.scale_y), box_w - int(40*self.scale_x), int(60*self.scale_y))
            self.draw_multiline(surface, data["short"], text_rect, self.font, (230, 230, 230), line_height = int(self.font.get_height()*1.1))