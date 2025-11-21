"""
CS 3050 Poker Game - Player.py
Sam Whitcomb, Jonah Harris, Owen Davis, Jake Pappas
"""


class Player:
    def __init__(self, name, uuid, seat_position, seat_position_flag, is_ready):
        self.name = name
        self.uuid = uuid
        self.chips = 1000
        self.seat_position = seat_position
        self.hand = []  # List of Cards of length 2
        self.hand_rank = (1,0)
        self.seat_position_flag = seat_position_flag  # one of Dealer, Big Blind, Little Blind
        self.folded = False
        self.current_bet = 0
        self.is_ready = is_ready

        self.acted_this_round = False

    # returns a dictionary of the player data to pass around as json (cant pass regular python objects)
    # we should keep our eye on this to make sure that the dictionary is
    # updated correctly (when we eventually access it in a more involved way)
    def to_dict(self):
        return {
            'name': self.name,
            'uuid': self.uuid,
            'money_count': self.chips,
            'seat_position': self.seat_position,
            'hand': self.hand,
            'hand_rank': self.hand_rank,
            'seat_position_flag': self.seat_position_flag,
            'folded': self.folded,
            'current_bet': self.current_bet
        }

    def receive_card(self, card):
        self.hand += card

    def make_bet(self, current_bet):
        self.chips -= current_bet
        self.current_bet += current_bet

    def set_hand_rank(self, hand_rank):
        self.hand_rank = hand_rank

    def receive_money(self, current_bet):
        self.chips += current_bet

    def reset_for_round(self):
        self.hand = []
        self.current_bet = 0
        self.folded = False
        self.acted_this_round = False

    @property
    def ready(self):
        return bool(self.is_ready)

    @ready.setter
    def ready(self, value):
        self.is_ready = bool(value)
