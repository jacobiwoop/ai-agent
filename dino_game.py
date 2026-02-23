#!/usr/bin/env python3
"""
Jeu du Désert (Dino Runner)
Un clone simple du jeu du dinosaur de Chrome en Python avec Pygame.
"""

import pygame
import sys
import random

# Initialisation de Pygame
pygame.init()

# Configuration de la fenêtre
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 400
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Dino Runner - Chrome Dino Clone")

# Couleurs
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
DINO_COLOR = (50, 150, 50)
CACTUS_COLOR = (150, 50, 50)
GROUND_COLOR = (100, 100, 100)
CLOUD_COLOR = (230, 230, 230)

# Constantes du jeu
FPS = 60
GROUND_HEIGHT = 50
DINO_WIDTH = 40
DINO_HEIGHT = 45
DINO_POS_Y = SCREEN_HEIGHT - GROUND_HEIGHT - DINO_HEIGHT
GRAVITY = 0.6
JUMP_STRENGTH = -11
CACTUS_SPEED = 5
SPAWN_RATE = 90  # Frames entre les cactus

# Groupe de cactus
obstacles = []
clouds = []
score = 0
high_score = 0
game_speed = 5
frame_count = 0
game_over = False


class Dino:
    def __init__(self):
        self.width = DINO_WIDTH
        self.height = DINO_HEIGHT
        self.x = 50
        self.y = DINO_POS_Y
        self.vel_y = 0
        self.jump_count = 0
        self.is_jumping = False
        self.duck = False
        self.duck_timer = 0

    def jump(self):
        if not self.is_jumping:
            self.vel_y = JUMP_STRENGTH
            self.is_jumping = True

    def duck(self):
        self.duck = True

    def update(self):
        # Appliquer la gravité
        self.vel_y += GRAVITY
        self.y += self.vel_y

        # Atteindre le sol
        if self.y >= DINO_POS_Y:
            self.y = DINO_POS_Y
            self.vel_y = 0
            self.is_jumping = False

        # Reset du positionnement
        self.width = DINO_WIDTH
        self.height = DINO_HEIGHT

    def draw(self):
        # Corps du dinosaure
        pygame.draw.rect(SCREEN, DINO_COLOR, (self.x, self.y, self.width, self.height))
        
        # Yeux
        pygame.draw.circle(SCREEN, WHITE, (self.x + 25, self.y + 10), 3)
        
        # Bras
        if self.is_jumping:
            pygame.draw.rect(SCREEN, DINO_COLOR, (self.x + 25, self.y + 15, 10, 5))
        else:
            pygame.draw.rect(SCREEN, DINO_COLOR, (self.x + 20, self.y + 25, 15, 5))


class Cactus:
    def __init__(self):
        self.width = random.randint(20, 40)
        self.height = random.randint(30, 50)
        self.x = SCREEN_WIDTH
        self.y = SCREEN_HEIGHT - GROUND_HEIGHT - self.height
        self.marked_for_deletion = False

    def update(self):
        self.x -= game_speed
        if self.x + self.width < 0:
            self.marked_for_deletion = True

    def draw(self):
        # Tronc principal
        pygame.draw.rect(SCREEN, CACTUS_COLOR, (self.x, self.y, self.width, self.height))
        
        # Détails du cactus
        if self.width > 25:
            pygame.draw.rect(SCREEN, (120, 40, 40), (self.x + 5, self.y + 5, 3, self.height - 10))
            pygame.draw.rect(SCREEN, (120, 40, 40), (self.x + self.width - 8, self.y + 10, 3, self.height - 15))


class Cloud:
    def __init__(self):
        self.x = SCREEN_WIDTH + random.randint(0, 200)
        self.y = random.randint(20, 150)
        self.width = random.randint(40, 60)
        self.height = random.randint(20, 30)
        self.speed = random.randint(1, 2)

    def update(self):
        self.x -= self.speed
        if self.x + self.width < 0:
            self.x = SCREEN_WIDTH + random.randint(0, 100)
            self.y = random.randint(20, 150)

    def draw(self):
        pygame.draw.rect(SCREEN, CLOUD_COLOR, (self.x, self.y, self.width, self.height))
        pygame.draw.rect(SCREEN, CLOUD_COLOR, (self.x + 10, self.y - 10, self.width - 20, self.height))


def draw_ground():
    pygame.draw.rect(SCREEN, GROUND_COLOR, (0, SCREEN_HEIGHT - GROUND_HEIGHT, SCREEN_WIDTH, GROUND_HEIGHT))
    # Lignes de sol pour effet de mouvement
    offset = (frame_count * game_speed) % 50
    for i in range(0, SCREEN_WIDTH, 50):
        pygame.draw.line(SCREEN, (80, 80, 80), (i - offset, SCREEN_HEIGHT - GROUND_HEIGHT), 
                        (i - offset + 10, SCREEN_HEIGHT), 2)


def draw_score():
    font = pygame.font.Font(None, 36)
    score_text = font.render(f"Score: {int(score)}", True, BLACK)
    SCREEN.blit(score_text, (SCREEN_WIDTH - 150, 30))
    
    high_score_text = font.render(f"Best: {int(high_score)}", True, BLACK)
    SCREEN.blit(high_score_text, (SCREEN_WIDTH - 150, 60))


def draw_game_over():
    font = pygame.font.Font(None, 72)
    game_over_text = font.render("GAME OVER", True, BLACK)
    text_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    SCREEN.blit(game_over_text, text_rect)
    
    font_small = pygame.font.Font(None, 36)
    restart_text = font_small.render("Appuyez sur ESPACE pour rejouer", True, BLACK)
    text_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
    SCREEN.blit(restart_text, text_rect)


def check_collision(dino, obstacle):
    return (dino.x < obstacle.x + obstacle.width and
            dino.x + dino.width > obstacle.x and
            dino.y < obstacle.y + obstacle.height and
            dino.y + dino.height > obstacle.y)


def reset_game():
    global obstacles, clouds, score, game_speed, frame_count, game_over
    obstacles = []
    clouds = []
    score = 0
    game_speed = 5
    frame_count = 0
    game_over = False
    dino = Dino()
    return dino


def main():
    global score, high_score, game_speed, frame_count, game_over
    
    clock = pygame.time.Clock()
    dino = reset_game()
    
    # Créer quelques nuages initiaux
    for _ in range(3):
        clouds.append(Cloud())
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE or event.key == pygame.K_UP:
                    if game_over:
                        dino = reset_game()
                    else:
                        dino.jump()
        
        # Input continu pour saut (optionnel)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] or keys[pygame.K_UP]:
            if not game_over and not dino.is_jumping:
                dino.jump()
        
        SCREEN.fill(WHITE)
        
        if not game_over:
            frame_count += 1
            score += 0.1
            game_speed = 5 + (score / 500)  # Augmenter la vitesse progressivement
            
            # Créer des cactus
            if frame_count % SPAWN_RATE == 0:
                obstacles.append(Cactus())
            
            # Créer des nuages
            if frame_count % 100 == 0:
                clouds.append(Cloud())
            
            # Mettre à jour et dessiner les nuages
            for cloud in clouds:
                cloud.update()
                cloud.draw()
            
            # Mettre à jour et dessiner le sol
            draw_ground()
            
            # Mettre à jour et dessiner le dino
            dino.update()
            dino.draw()
            
            # Mettre à jour et dessiner les obstacles
            for obstacle in obstacles[:]:
                obstacle.update()
                obstacle.draw()
                
                if check_collision(dino, obstacle):
                    game_over = True
                    if score > high_score:
                        high_score = score
                
                if obstacle.marked_for_deletion:
                    obstacles.remove(obstacle)
            
            draw_score()
        else:
            draw_game_over()
        
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
