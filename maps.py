import pygame

import constants
import platforms

class Map(object):
    """ This is a generic super-class used to define a map.
        Create a child class for each map with map-specific
        info. """

    def __init__(self, player):
        """ Constructor. Pass in a handle to player. Needed for when moving platforms
            collide with the player. """
        self.platform_list = pygame.sprite.Group()
        self.enemy_list = pygame.sprite.Group()
        self.player = player

        # Background image
        self.background = None

    # Update everythign on this map
    def update(self):
        """ Update everything in this map."""
        self.platform_list.update()
        self.enemy_list.update()

    def draw(self, screen):
        """ Draw everything on this map. """
        # Draw the background
        screen.fill(constants.DARKTURQUOISE)
        # Draw all the sprite lists that we have
        self.platform_list.draw(screen)
        self.enemy_list.draw(screen)

# Create platforms for the map
class Map_01(Map):
    """ Definition for map 1. """

    def __init__(self, player):
        """ Create map 1. """

        # Call the parent constructor
        Map.__init__(self, player)

        # Array with width, height, x, and y of platform
        map = [[210, 70, 500, 500],
                 [210, 70, 200, 400]
                 ]

        # Go through the array above and add platforms
        for platform in map:
            block = platforms.Platform(platform[0], platform[1])
            block.rect.x = platform[2]
            block.rect.y = platform[3]
            block.player = self.player
            self.platform_list.add(block)
