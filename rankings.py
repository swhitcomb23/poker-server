card_number_to_card_rank = {1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "J",
                            12: "Q", 13: "K"}

hand_ranking_weight_to_string = {1: "High Card", 2: "One Pair", 3: "Two Pair", 4: "Three of a Kind", 5: "Straight",
                                 6: "Flush", 7: "Full House", 8: "Four of a Kind", 9: "Straight Flush",
                                 10: "Royal Flush"}


# Note: Ace card_number is 14 if it is used as a high card

# Returns the hand ranking along with the high card of that ranking
def rank_hand(full_hand):
    if has_royal_flush(full_hand):
        return 10, 0  # only one way for a straight flush, high card doesn't matter
    straight_flush_bool, straight_flush_high_card = has_straight_flush(full_hand)
    if straight_flush_bool:
        return 9, straight_flush_high_card
    four_of_a_kind_bool, four_of_a_kind_high_card = has_four_of_a_kind(full_hand)
    if four_of_a_kind_bool:
        return 8, four_of_a_kind_high_card
    full_house_bool, full_house_cards = has_full_house(full_hand)
    if full_house_bool:
        return 7, full_house_cards
    flush_bool, flush_high_card = has_flush(full_hand)
    if flush_bool:
        return 6, flush_high_card
    straight_bool, straight_high_card = has_straight(full_hand)
    if straight_bool:
        return 5, straight_high_card
    three_of_a_kind_bool, three_of_a_kind_card = has_three_of_a_kind(full_hand)
    if three_of_a_kind_bool:
        return 4, three_of_a_kind_card
    two_pair_bool, two_pair_cards = has_two_pair(full_hand)
    if two_pair_bool:
        return 3, two_pair_cards
    one_pair_bool, one_pair_card = has_one_pair(full_hand)
    if one_pair_bool:
        return 2, one_pair_card
    return 1, high_card(full_hand)


# Returns whether there is a royal flush (there is no way to rank a royal flush further, so only return bool)
def has_royal_flush(full_hand):
    # a royal flush requires 5 cards minimum
    if len(full_hand) < 5:
        return False

    straight_flush_check = has_straight_flush(full_hand)

    # if there is a straight flush with Ace high, that's a royal flush
    if straight_flush_check[0] and straight_flush_check[1] == 14:
        return True

    # otherwise no royal flush
    return False


# Returns whether there is a straight flush and the highest card of that straight flush
def has_straight_flush(full_hand):
    # a straight flush requires 5 cards minimum
    if len(full_hand) < 5:
        return False, 0
    suit_groups = {"Hearts": [], "Diamonds": [], "Spades": [], "Clubs": []}
    # group cards by suit
    for card in full_hand:
        suit_groups[card.suit].append(card)

    # if there is a suit with a straight there is a straight flush
    for suit in suit_groups:
        straight_bool, straight_high_card = has_straight(suit_groups[suit])
        if straight_bool:
            return True, straight_high_card

    # otherwise, no straight flush
    return False, 0


# return whether there's a four of a kind and what the card_number is
# AAAA -> True, 14
def has_four_of_a_kind(full_hand):
    # a 4 of a kind requires 4 cards minimum (duh)
    if len(full_hand) < 4:
        return False, 0
    full_hand_numbers = [card.number for card in full_hand]
    for card_number in full_hand_numbers:
        if full_hand_numbers.count(card_number) == 4:
            if card_number == 1:
                card_number = 14
            return True, card_number
    return False, 0


# returns whether there's a full house and what the 3 of a kind is and the pair is in that order
# AAAKK -> True, (A,K)
def has_full_house(full_hand):
    # a full_house requires 5 cards minimum
    if len(full_hand) < 5:
        return False, (0, 0)
    three_of_a_kind = has_three_of_a_kind(full_hand)
    two_pair = has_two_pair(full_hand)
    # check equality because the high pair in the two pair could be within the 3 of a kind
    if three_of_a_kind[0] and two_pair[0] and (three_of_a_kind[1] != max(two_pair[1])):
        return True, (three_of_a_kind[1], max(two_pair[1]))
    if three_of_a_kind[0] and two_pair[0] and (three_of_a_kind[1] != min(two_pair[1])):
        return True, (three_of_a_kind[1], min(two_pair[1]))
    return False, (0, 0)


# returns whether there's a flush and what the high card of the flush is
# 2H 5H 6H 10H 7H -> True, 10
def has_flush(full_hand):
    # a flush requires 5 cards minimum
    if len(full_hand) < 5:
        return False, 0
    suit_groups = {"Hearts": [], "Diamonds": [], "Spades": [], "Clubs": []}
    # group cards by suit
    for card in full_hand:
        suit_groups[card.suit].append(card)
    for suit, cards in suit_groups.items():
        if len(cards) > 4:  # there's a flush
            return True, max([card.number for card in cards])
    return False, 0


# return whether there's a straight and what the highest card of the straight is.
# A2345 -> True, 5
# 10JQKA -> True, A
def has_straight(full_hand):
    # a straight requires 5 cards minimum
    if len(full_hand) < 5:
        return False, 0
    has_straight_bool = False
    current_high_card_number = 0
    for card in full_hand:
        high_card = check_straight_offsets(card.number, full_hand)
        if high_card > current_high_card_number:
            has_straight_bool = True
            current_high_card_number = high_card
    return has_straight_bool, current_high_card_number


# checks the offsets about a card to see if there is 5 in a row
def check_straight_offsets(card_number, full_hand):
    if card_number > 10:
        return 0
    capture = 0
    for i in range(1, 5):
        # special case for Ace high
        if card_number + i == 14:
            if not value_in_full_hand(1, full_hand):
                return 0
            return 14

        if not value_in_full_hand(card_number + i, full_hand):
            return 0
        capture = i
    return card_number + capture


# returns whether a value is within the full hand of cards
def value_in_full_hand(card_number, full_hand):
    for card in full_hand:
        if card.number == card_number:
            return True
    return False


# returns whether there's a three of a kind and the best three of a kind card
# 3335557 -> True, 5
def has_three_of_a_kind(full_hand):
    # a three of a kind requires 3 cards minimum (duh)
    if len(full_hand) < 3:
        return False, 0

    full_hand_numbers = [card.number for card in full_hand]
    current_best = 0
    for card_number in full_hand_numbers:
        if card_number > current_best or card_number == 1:
            if full_hand_numbers.count(card_number) == 3:
                current_best = card_number
                if current_best == 1:
                    return True, 14

    return current_best > 0, current_best


# returns whether there's a two pair and the best two pair
# 5522883 -> True, [5,8]
def has_two_pair(full_hand):
    # a 2 pair requires 4 cards minimum
    if len(full_hand) < 4:
        return False, 0
    full_hand_numbers = [card.number for card in full_hand]
    pairs = []
    for card_number in full_hand_numbers:
        if full_hand_numbers.count(card_number) >= 2:
            if card_number == 1:
                card_number = 14
            if card_number not in pairs:
                pairs.append(card_number)
    if len(pairs) > 2:
        pairs.remove(min(pairs))
    return len(pairs) == 2, tuple(sorted(pairs, reverse=True))   # the higher card at index 0


# returns whether there's a one pair and what the card number is
# 44786 -> True, 4
def has_one_pair(full_hand):
    full_hand_numbers = [card.number for card in full_hand]
    for card_number in full_hand_numbers:
        if full_hand_numbers.count(card_number) == 2:
            if card_number == 1:
                return True, 14
            return True, card_number
    return False, 0


# returns true (because there's always a high card if nothing else) and the card number
# 28974 -> True, 9
def high_card(full_hand):
    full_hand_numbers = [card.number for card in full_hand]
    if 1 in full_hand_numbers:  # Ace
        return 14
    return max(full_hand_numbers)
