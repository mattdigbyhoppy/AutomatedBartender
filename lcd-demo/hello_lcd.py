#!/usr/bin/env python3
import pygame
import time

# Initialize Pygame to use the Pi’s framebuffer (fb1)
pygame.init()
screen = pygame.display.set_mode((320,240))
pygame.mouse.set_visible(False)

# Fill screen with blue
screen.fill((0,0,255))
pygame.display.flip()

# Keep it up for 5 seconds
time.sleep(5)
