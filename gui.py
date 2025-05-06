import pygame
import time

class GUI:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.Font(None, 28)

        # Pre‑load recipe images
        self.icons = {
            d['name']: pygame.image.load(f"assets/{d['name'].lower().replace(' ','_')}.png")
            for d in drink_list
        }

    def draw_text(self, text, pos):
        surf = self.font.render(text, True, (255,255,255))
        self.screen.blit(surf, pos)

    def show_menu(self, options, selected):
        self.screen.fill((0,0,0))
        for i, opt in enumerate(options):
            color = (255,255,0) if i == selected else (255,255,255)
            surf = self.font.render(opt, True, color)
            self.screen.blit(surf, (20, 20 + 40*i))
        pygame.display.flip()

    def show_recipe(self, name, ingredients):
        self.screen.fill((0,0,0))
        icon = self.icons[name]
        self.screen.blit(icon, (10,10))
        y = 10
        for fluid, ml in ingredients.items():
            self.draw_text(f"{fluid}: {ml}ml", (100, y))
            y += 30
        pygame.display.flip()

    def update_during_pour(self, poured, total):
        pct = int(poured/total*100)
        bar = pygame.Rect(20,200, int(280*pct/100), 20)
        pygame.draw.rect(self.screen, (0,255,0), bar)
        self.draw_text(f"{pct}%", (150, 170))
        pygame.display.flip()
