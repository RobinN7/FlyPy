# @Author: robin

import pygame
import threading
import time
import random
import math
import numpy as np
import os

import constants
from spritesheet_functions import SpriteSheet
import maps

class Propeller(pygame.sprite.Sprite):
    """Propeller of UAV."""
    def __init__(self, UAV, prop_dia=10, prop_pitch=4.5, thrust_unit='N',):
        super(Propeller, self).__init__()
        self.dia = prop_dia # in.
        self.pitch = prop_pitch # in.
        self.thrust_unit = thrust_unit
        self.speed = 0 # RPM
        self.thrust = 0
        self.max_speed = 25000 # RPM

        self.uav = UAV

        self.rotating_frames = []
        sprite_sheet = SpriteSheet(os.path.join("data","img","propeller1.png"))
        for frame_nb in range(7):
            frame = sprite_sheet.get_image(1, frame_nb*49, 235, 49)
            frame = pygame.transform.scale(frame, (234//4, 49//4))
            self.rotating_frames.append(frame)
        # Set the image the propeller starts with
        self.image = self.rotating_frames[0]
        # Set a reference to the image rect.
        self.rect = self.image.get_rect()
        self.last_frame = {'prop_angle': 0, 'time': time.time()}

    def set_speed(self,speed):
        self.speed = np.clip(speed, -self.max_speed, self.max_speed)
        direction = np.sign(speed)
        # From http://www.electricrcaircraftguy.com/2013/09/propeller-static-dynamic-thrust-equation.html
        self.thrust = 4.392e-8 * self.speed * np.power(self.dia,3.5)/(np.sqrt(self.pitch))
        self.thrust *= (4.23e-4 * self.speed * self.pitch)
        self.thrust *= direction
        if self.thrust_unit == 'Kg':
            self.thrust = self.thrust*0.101972

    def update(self):
        elapsed_time = (time.time()-self.last_frame['time'])
        prop_angle = self.last_frame['prop_angle'] + elapsed_time*self.speed/100
        frame_nb = int(prop_angle) % len(self.rotating_frames)
        self.image = self.rotating_frames[frame_nb]
        self.last_frame['prop_angle'] = prop_angle
        self.last_frame['time'] = time.time()

        self.rect.x = self.uav.rect.x + self.uav.rect.width/2 - self.rect.width/2
        self.rect.y = self.uav.rect.y - 12



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
        self.image.fill(constants.YELLOW)
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
        self.image.fill(constants.BLACK)
        # Set a referance to the image rect.
        self.rect = self.image.get_rect()

        # Give a mass (kg) to the UAV
        self._mass = 0.25
        # Set speed and acceleration vectors of player
        self.pos_x = constants.SCREEN_WIDTH/2
        self.pos_y = constants.SCREEN_HEIGHT - self.rect.height*2
        self._x_dot = 0
        self._y_dot = 0

        # Mount a propeller on UAV
        self.propellers = pygame.sprite.Group()
        self.propellers.add(Propeller(self))
        # Control target
        self.target = Target()
        self.target.rect.x = (constants.SCREEN_WIDTH - self.target.rect.width) / 2
        self.target.rect.y = (constants.SCREEN_HEIGHT - self.target.rect.height) / 2

        # Control loop parameters
        self.control_loop_period = 0.005
        self._Kp = 4000
        self._Ki = 1000
        self._Kd = 0

        self._Pvalue = 0
        self._Ivalue = 0
        self._Dvalue = 0
        self._lastError = 0

        self.mutex = threading.Lock()

    @property
    def pos_x(self):
        return self._pos_x
    @pos_x.setter
    def pos_x(self, value):
        self._pos_x = value
        self.rect.x = value
    @property
    def pos_y(self):
        return self._pos_y
    @pos_y.setter
    def pos_y(self, value):
        self._pos_y = value
        self.rect.y = value

    def update(self):
        self.mutex.acquire()
        """ Move the player. """
        # Update target
        self.target.update()
        # Update propellers
        for prop in self.propellers:
            prop.update()
        # Move left/right
        self.pos_x += self._x_dot
        # See if we hit anything
        block_hit_list = pygame.sprite.spritecollide(self, self.level.platform_list, False)
        for block in block_hit_list:
            # If we are moving right,
            # set our right side to the left side of the item we hit
            if self._x_dot > 0:
                self.pos_x = block.rect.left - self.rect.width
            elif self._x_dot < 0:
                # Otherwise if we are moving left, do the opposite.
                self.pos_x = block.rect.right

        # Move up/down
        self.pos_y += self._y_dot
        # Check and see if we hit anything
        block_hit_list = pygame.sprite.spritecollide(self, self.level.platform_list, False)
        for block in block_hit_list:
            # Reset our position based on the top/bottom of the object.
            if self._y_dot > 0:
                self.pos_y = block.rect.top - self.rect.height
            elif self._y_dot < 0:
                self.pos_y = block.rect.bottom
            # Stop our vertical movement
            self._y_dot = 0

        # See if we are on the ground or hitting the ceiling.
        if self.pos_y >= constants.SCREEN_HEIGHT - self.rect.height and self._y_dot >= 0:
            self._y_dot = 0
            self.pos_y = constants.SCREEN_HEIGHT - self.rect.height
        elif self.pos_y <= 0 and self._y_dot <= 0:
            self._y_dot = 0
            self.pos_y = 0

        self.mutex.release()
    def control_loop(self):
        """ Calculate new propeller speed. """
        error = self.pos_y - self.target.rect.y
        self._Pvalue = error
        self._Ivalue += error * self.control_loop_period
        self._Dvalue = (error - self._lastError)/self.control_loop_period
        # Saturate values to avoid divergence
        self._Pvalue = np.clip(self._Pvalue, -1000, 1000)
        self._Ivalue = np.clip(self._Ivalue, -80, 80)
        for prop in self.propellers: # TODO create one full control loop for each prop
            prop.set_speed(self._Kp * error        +
                           self._Ki * self._Ivalue -
                           self._Kd * self._Dvalue)
        self._lastError = error
    def calc_forces(self):
        """ Calculate effect of forces exerced on uav. """
        self._y_dot = -(sum([prop.thrust for prop in self.propellers])/self._mass -
                        constants.GRAVITY_ACC)/constants.FPS

    def jump(self):
        """ Called when user hits 'jump' button. """

        # move down a bit and see if there is a platform below us.
        # Move down 2 pixels because it doesn't work well if we only move down
        # 1 when working with a platform moving down.
        self.pos_y += 2
        platform_hit_list = pygame.sprite.spritecollide(self, self.level.platform_list, False)
        self.pos_y -= 2

        # If it is ok to jump, set our speed upwards
        if len(platform_hit_list) > 0 or self.rect.bottom >= constants.SCREEN_HEIGHT:
            self._y_dot = -2

    # Player-controlled movement:
    def go_left(self):
        """ Called when the user hits the left arrow. """
        self._x_dot = -10

    def go_right(self):
        """ Called when the user hits the right arrow. """
        self._x_dot = 10

    def stop(self):
        """ Called when the user lets off the keyboard. """
        self._x_dot = 0

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
        time.sleep(np.clip(next_call - time.time(), 0, None))


def main():
    """ Main Program """
    pygame.init()
    # Set the height and width of the screen
    size = [constants.SCREEN_WIDTH, constants.SCREEN_HEIGHT]
    screen = pygame.display.set_mode(size)

    pygame.display.set_caption("FlyPy")

    # Create the player
    player = UAV()

    # Create all the levels
    level_list = []
    level_list.append(maps.Map_01(player) )

    # Set the current level
    current_level_no = 0
    current_level = level_list[current_level_no]

    active_sprite_list = pygame.sprite.Group()
    player.level = current_level

    active_sprite_list.add(player)

    player.target.rect.x = (constants.SCREEN_WIDTH - player.target.rect.width) / 2
    player.target.rect.y = (constants.SCREEN_HEIGHT - player.target.rect.height) / 2
    active_sprite_list.add(player.target)
    active_sprite_list.add(player.propellers)

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
                if event.key == pygame.K_LEFT and player._x_dot < 0:
                    player.stop()
                if event.key == pygame.K_RIGHT and player._x_dot > 0:
                    player.stop()

        if keys[pygame.K_UP]:
            player.target.rect.y -= 10
        if keys[pygame.K_DOWN]:
            player.target.rect.y += 10
        if keys[pygame.K_LEFT]:
            player.target.rect.x -= 10
        if keys[pygame.K_RIGHT]:
            player.target.rect.x += 10

        # Update the player.
        active_sprite_list.update()

        # Update items in the level
        current_level.update()

        # If the player gets near the right side, shift the world left (-x)
        if player.rect.right > constants.SCREEN_WIDTH:
            player.rect.right = constants.SCREEN_WIDTH

        # If the player gets near the left side, shift the world right (+x)
        if player.rect.left < 0:
            player.rect.left = 0

        # ALL CODE TO DRAW SHOULD GO BELOW THIS COMMENT
        current_level.draw(screen)
        active_sprite_list.draw(screen)

        # ALL CODE TO DRAW SHOULD GO ABOVE THIS COMMENT

        # Limit to 60 frames per second
        clock.tick(constants.FPS)

        # Go ahead and update the screen with what we've drawn.
        pygame.display.flip()

    # Be IDLE friendly. If you forget this line, the program will 'hang'
    # on exit.
    pygame.quit()


if __name__ == '__main__':
    main()
