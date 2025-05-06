import pygame, sys
from sensors import is_glass_present, get_weight
from pumps import init_pumps, prime_all, dispense
from gui import GUI
from drinks import drink_list
import config

def main():
    pygame.init()
    screen = pygame.display.set_mode(config.SCREEN_SIZE)
    gui = GUI(screen)

    init_pumps()

    # 1. Priming prompt
    gui.draw_text("Prime pumps? Press any key", (20,100))
    pygame.display.flip()
    wait_for_key()
    prime_all()

    while True:
        # 2. Drink selection
        names = [d['name'] for d in drink_list]
        sel = menu_selection(gui, names)

        # 3. Show recipe
        recipe = next(d for d in drink_list if d['name']==names[sel])
        gui.show_recipe(recipe['name'], recipe['ingredients'])
        time.sleep(2)

        # 4. Wait for glass
        gui.draw_text("Place glass...", (20,100))
        pygame.display.flip()
        while not is_glass_present():
            time.sleep(0.2)

        # 5. Dispense with live update
        total_ml = sum(recipe['ingredients'].values())
        dispense(recipe['ingredients'],
                 update_callback=lambda poured: gui.update_during_pour(poured, total_ml))

        # 6. Finished pouring
        gui.draw_text("Done! Remove glass.", (20,100))
        pygame.display.flip()
        while is_glass_present():
            time.sleep(0.2)

def wait_for_key():
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.KEYDOWN:
                return

def menu_selection(gui, options):
    idx = 0
    gui.show_menu(options, idx)
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_UP:
                    idx = (idx-1) % len(options)
                elif ev.key == pygame.K_DOWN:
                    idx = (idx+1) % len(options)
                elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return idx
                gui.show_menu(options, idx)

if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit()
