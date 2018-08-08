# @Author: robin

import pygame
import threading
import time
import random
import math
import numpy as np
import os

###############################
# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Define Colors
WHITE =     (255, 255, 255)
BLACK =     (0, 0, 0)
RED =       (255, 0, 0)
GREEN =     (0, 255, 0)
BLUE =      (0, 0, 255)
YELLOW =    (255, 255, 0)
DARKTURQUOISE = ( 3, 54, 73)

BGCOLOR = DARKTURQUOISE

GRAVITY_ACC = 9.8
###############################

class Propeller(object):
    """Propeller of UAV."""
    def __init__(self):
        """ Constructor function """
        super(Propeller, self).__init__()
        self.radius = 0.1
        self.area = math.pi * self.radius**2
        self.speed = 0

    @property
    def force(self):
        f = self.area * self.speed
        return f #if self.speed>0 else -f


class Target(pygame.sprite.Sprite):
    """Control loop target."""
    def __init__(self):
        """ Constructor function """
        super(Target, self).__init__()
        # Create an image of the target, and fill it with a color.
        # This could also be an image loaded from the disk.
        width = 6
        height = 6
        self.image = pygame.Surface([width, height])
        self.image.fill(YELLOW)
        # Set a referance to the image rect.
        self.rect = self.image.get_rect()


class UAV(pygame.sprite.Sprite):
    """Controllable UAV."""
    def __init__(self):
        """ Constructor function """
        super(UAV, self).__init__()

        # Create an image of the block, and fill it with a color.
        # This could also be an image loaded from the disk.
        width = 10
        height = 10
        self.image = pygame.Surface([width, height])
        self.image.fill(GREEN)
        # Set a referance to the image rect.
        self.rect = self.image.get_rect()

        # Give a mass (grams) to the UAV
        self._mass = 100
        # Set speed and acceleration vectors of player
        self._speed_x = 0
        self._speed_y = 0
        self._accel_x = 0
        self._accel_y = 0

        # Mount a propeller on UAV
        self._propellers = [Propeller()]
        # Control target
        self.target = Target()

        # Control loop parameters
        self.control_loop_period = 0.01
        self._Kp = 85
        self._Ki = 0
        self._Kd = 0

        self._Pvalue = 0
        self._Ivalue = 0
        self._Dvalue = 0
        self._lastError = 0

        self.mutex = threading.Lock()

    def update(self):
        self.mutex.acquire()
        print(self._Dvalue)
        """ Move the player. """
        # Move left/right
        self.rect.x += self._speed_x

        # See if we hit anything
        block_hit_list = pygame.sprite.spritecollide(self, self.level.platform_list, False)
        for block in block_hit_list:
            # If we are moving right,
            # set our right side to the left side of the item we hit
            if self._speed_x > 0:
                self.rect.right = block.rect.left
            elif self._speed_x < 0:
                # Otherwise if we are moving left, do the opposite.
                self.rect.left = block.rect.right
        # Move up/down
        self.rect.y += self._speed_y

        # Check and see if we hit anything
        block_hit_list = pygame.sprite.spritecollide(self, self.level.platform_list, False)
        for block in block_hit_list:
            # Reset our position based on the top/bottom of the object.
            if self._speed_y > 0:
                self.rect.bottom = block.rect.top
            elif self._speed_y < 0:
                self.rect.top = block.rect.bottom
            # Stop our vertical movement
            self._speed_y = 0
        self.mutex.release()
    def control_loop(self):
        """ Calculate new propeller speed. """
        error = self.rect.y - self.target.rect.y
        self._Pvalue = error
        self._Ivalue += error * self.control_loop_period
        self._Dvalue = (error - self._lastError)/self.control_loop_period
        # Saturate values to avoid divergence
        self._Pvalue = np.clip(self._Pvalue, -1000, 1000)
        self._Ivalue = np.clip(self._Ivalue, -10000, 10000)
        self._propellers[0].speed = (self._Kp * error        +
                                    self._Ki * self._Ivalue  -
                                    self._Kd * self._Dvalue
                                    )
        self._lastError = error
    def calc_forces(self):
        """ Calculate effect of forces exerced on uav. """
        self._speed_y -= (sum([prop.force for prop in self._propellers])/self._mass -
                          GRAVITY_ACC)/FPS

        # See if we are on the ground or hitting the ceiling.
        if self.rect.y >= SCREEN_HEIGHT - self.rect.height and self._speed_y >= 0:
            self._speed_y = 0
            self.rect.y = SCREEN_HEIGHT - self.rect.height
        elif self.rect.y <= 0 and self._speed_y <= 0:
            self._speed_y = 0
            self.rect.y = 0

    def jump(self):
        """ Called when user hits 'jump' button. """

        # move down a bit and see if there is a platform below us.
        # Move down 2 pixels because it doesn't work well if we only move down
        # 1 when working with a platform moving down.
        self.rect.y += 2
        platform_hit_list = pygame.sprite.spritecollide(self, self.level.platform_list, False)
        self.rect.y -= 2

        # If it is ok to jump, set our speed upwards
        if len(platform_hit_list) > 0 or self.rect.bottom >= SCREEN_HEIGHT:
            self._speed_y = -2

    # Player-controlled movement:
    def go_left(self):
        """ Called when the user hits the left arrow. """
        self._speed_x = -6

    def go_right(self):
        """ Called when the user hits the right arrow. """
        self._speed_x = 6

    def stop(self):
        """ Called when the user lets off the keyboard. """
        self._speed_x = 0


class Platform(pygame.sprite.Sprite):
    """ Platform the user can jump on """

    def __init__(self, width, height):
        """ Platform constructor. Assumes constructed with user passing in
            an array of 5 numbers like what's defined at the top of this
            code. """
        super().__init__()

        self.image = pygame.Surface([width, height])
        self.image.fill(RED)

        self.rect = self.image.get_rect()


class Level(object):
    """ This is a generic super-class used to define a level.
        Create a child class for each level with level-specific
        info. """

    def __init__(self, player):
        """ Constructor. Pass in a handle to player. Needed for when moving platforms
            collide with the player. """
        self.platform_list = pygame.sprite.Group()
        self.enemy_list = pygame.sprite.Group()
        self.player = player

        # Background image
        self.background = None

    # Update everythign on this level
    def update(self):
        """ Update everything in this level."""
        self.platform_list.update()
        self.enemy_list.update()

    def draw(self, screen):
        """ Draw everything on this level. """
        # Draw the background
        screen.fill(DARKTURQUOISE)
        # Draw all the sprite lists that we have
        self.platform_list.draw(screen)
        self.enemy_list.draw(screen)

# Create platforms for the level
class Level_01(Level):
    """ Definition for level 1. """

    def __init__(self, player):
        """ Create level 1. """

        # Call the parent constructor
        Level.__init__(self, player)

        # Array with width, height, x, and y of platform
        level = [[210, 70, 500, 500],
                 [210, 70, 200, 400]
                 ]

        # Go through the array above and add platforms
        for platform in level:
            block = Platform(platform[0], platform[1])
            block.rect.x = platform[2]
            block.rect.y = platform[3]
            block.player = self.player
            self.platform_list.add(block)

def control_loop_callback(uav):
    next_call = time.time()
    while True:
        uav.mutex.acquire()
        # Control loop
        uav.control_loop()
        # Gravity
        uav.calc_forces()
        uav.mutex.release()
        next_call += uav.control_loop_period
        time.sleep(next_call - time.time())


def main():
    """ Main Program """
    pygame.init()
    # Set the height and width of the screen
    size = [SCREEN_WIDTH, SCREEN_HEIGHT]
    screen = pygame.display.set_mode(size)

    pygame.display.set_caption("Platformer Jumper")

    # Create the player
    player = UAV()

    # Create all the levels
    level_list = []
    level_list.append( Level_01(player) )

    # Set the current level
    current_level_no = 0
    current_level = level_list[current_level_no]

    active_sprite_list = pygame.sprite.Group()
    player.level = current_level

    player.rect.x = 340
    player.rect.y = SCREEN_HEIGHT - player.rect.height
    active_sprite_list.add(player)

    player.target.rect.x = (SCREEN_WIDTH - player.target.rect.width) / 2
    player.target.rect.y = (SCREEN_HEIGHT - player.target.rect.height) / 2
    active_sprite_list.add(player.target)

    # Loop until the user clicks the close button.
    done = False

    # Used to manage how fast the screen updates
    clock = pygame.time.Clock()

    # Start UAV control loop
    timerThread = threading.Thread(target=control_loop_callback, args=(player,))
    timerThread.daemon = True
    timerThread.start()
    # -------- Main Program Loop -----------
    while not done:
        keys=pygame.key.get_pressed()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    player.go_left()
                if event.key == pygame.K_RIGHT:
                    player.go_right()
                if event.key == pygame.K_SPACE:
                    player.jump()

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT and player._speed_x < 0:
                    player.stop()
                if event.key == pygame.K_RIGHT and player._speed_x > 0:
                    player.stop()

        if keys[pygame.K_UP]:
            player.target.rect.y -= 4
        if keys[pygame.K_DOWN]:
            player.target.rect.y += 4
        if keys[pygame.K_LEFT]:
            player.target.rect.x -= 4
        if keys[pygame.K_RIGHT]:
            player.target.rect.x += 4

        # Update the player.
        active_sprite_list.update()

        # Update items in the level
        current_level.update()

        # If the player gets near the right side, shift the world left (-x)
        if player.rect.right > SCREEN_WIDTH:
            player.rect.right = SCREEN_WIDTH

        # If the player gets near the left side, shift the world right (+x)
        if player.rect.left < 0:
            player.rect.left = 0

        # ALL CODE TO DRAW SHOULD GO BELOW THIS COMMENT
        current_level.draw(screen)
        active_sprite_list.draw(screen)

        # ALL CODE TO DRAW SHOULD GO ABOVE THIS COMMENT

        # Limit to 60 frames per second
        clock.tick(FPS)

        # Go ahead and update the screen with what we've drawn.
        pygame.display.flip()

    # Be IDLE friendly. If you forget this line, the program will 'hang'
    # on exit.
    pygame.quit()


if __name__ == '__main__':
    main()
