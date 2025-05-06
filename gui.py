import pygame
import time
import config


from drinks import drink_list


class GUI:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.Font(None, 28)

        # Pre‑load recipe images keyed by name
        self.recipe_images = {}
        for drink in drink_list:
            try:
                img = pygame.image.load(drink["image"]).convert_alpha()
                # Optionally: scale to fit half the screen width
                img = pygame.transform.smoothscale(img, (120, 120))
                self.recipe_images[drink["name"]] = img
            except Exception as e:
                print(f"Failed loading {drink['image']}: {e}")

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
        self.screen.fill((0, 0, 0))
        # Draw the image centered top‑left
        img = self.recipe_images.get(name)
        if img:
            self.screen.blit(img, (10, 10))
        # Draw ingredients list next to image
        y = 10
        for fluid, ml in ingredients.items():
            text = self.font.render(f"{fluid}: {ml}ml", True, (255, 255, 255))
            # Offset x by image width + padding
            self.screen.blit(text, (140, y))
            y += 30
        pygame.display.flip()

    def update_during_pour(self, poured, total):
        pct = int(poured/total*100)
        bar = pygame.Rect(20,200, int(280*pct/100), 20)
        pygame.draw.rect(self.screen, (0,255,0), bar)
        self.draw_text(f"{pct}%", (150, 170))
        pygame.display.flip()
