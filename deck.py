"""
CS 3050 Poker Game - deck.py
Sam Whitcomb, Jonah Harris, Owen Davis, Jake Pappas
"""


import random
import Card


class Deck:
    def __init__(self):
        suits = ["Hearts", "Diamonds", "Clubs", "Spades"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        self.cards = [Card.Card(suit, rank) for suit in suits for rank in ranks]

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self, num=1):
        dealt = [self.cards.pop() for _ in range(num)]
        return dealt

    def __len__(self):
        return len(self.cards)
