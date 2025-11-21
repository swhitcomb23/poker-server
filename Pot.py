class Pot:
    def __init__(self):
        self.amount = 0

    def add_to_pot(self, bet_amount):
        self.amount += bet_amount

    def clear_pot(self):
        self.amount = 0

    def payout_single(self, player):
        player.receive_money(self.amount)
        self.clear_pot()

    def payout_split_pot(self, players):
        if len(players) == 0:
            return

        split_amount = self.amount // len(players)
        remainder = self.amount % len(players)

        for player in players:
            player.receive_money(split_amount)

        # Remainder goes to earliest in turn order (standard poker)
        if remainder > 0:
            players[0].receive_money(remainder)

        self.clear_pot()
