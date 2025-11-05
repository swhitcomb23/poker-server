"""
CS 3050 Poker Game - Card.py
Sam Whitcomb, Jonah Harris, Owen Davis, Jake Pappas
"""


import arcade

ranks = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
         "7": 7, "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13}


class Card(arcade.Sprite):
    def __init__(self, suit, value, scale=1):
        self.suit = suit
        self.value = value
        self.number = ranks[value]

        # face up card
        self.image_file_name = f":resources:/images/cards/card{self.suit}{self.value}.png"

        # call parent
        super().__init__(self.image_file_name, scale, hit_box_algorithm="None")

    def __str__(self):
        return f"{self.value} of {self.suit}"

    def __value__(self):
        return f"{self.value}"

    def __suit__(self):
        return f"{self.suit}"
