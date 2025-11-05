"""
CS 3050 Poker Game - client.py
Sam Whitcomb, Jonah Harris, Owen Davis, Jake Pappas
"""


from enum import Enum
import threading
import math
import time
import arcade
import socketio
import arcade.gui as gui
from Card import Card
from game import PokerGame


SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
SCREEN_TITLE = "Poker"

# Constants for sizing
CARD_SCALE = 0.6
CARD_WIDTH = 140 * CARD_SCALE
CARD_HEIGHT = 190 * CARD_SCALE

MAT_PERCENT_OVERSIZE = 1.25
MAT_HEIGHT = int(CARD_HEIGHT * MAT_PERCENT_OVERSIZE)
MAT_WIDTH = int(CARD_WIDTH * MAT_PERCENT_OVERSIZE)

BOTTOM_Y = MAT_HEIGHT / 2 + MAT_HEIGHT * 0.10
START_X = MAT_WIDTH / 2 + MAT_WIDTH * 0.10

SEAT_COUNT = 8
STOOL_RADIUS = 25
STOOL_COLOR = arcade.color.SADDLE_BROWN
STOOL_RING_COLOR = arcade.color.BEIGE
STOOL_RING_THICKNESS = 3
SEAT_CLEARANCE = 35

CARD_BACK_ASSET = ":resources:images/cards/cardBack_red2.png"

game = PokerGame()

class Phase(Enum):
    LOBBY = 0
    IN_HAND = 1

class PokerGameClient(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        self.background_color = arcade.color.CAL_POLY_GREEN

        self.table_center_x = SCREEN_WIDTH // 2
        self.table_center_y = SCREEN_HEIGHT // 2
        self.table_width = 800
        self.table_height = 500
        self.table_color = arcade.color.CAPUT_MORTUUM

        # Card storage for each hand and the deck
        self.hand_cards = arcade.SpriteList()
        self.other_hands = {}
        self.community_cards = arcade.SpriteList()
        # track if cards are dealt
        self.cards_dealt = False

        # Deck variables
        self.deck = []
        self.deck_back_sprites = arcade.SpriteList()

        # Make the deck visable
        deck_sprite = arcade.Sprite(CARD_BACK_ASSET, CARD_SCALE)
        deck_sprite.center_x = SCREEN_WIDTH / 2
        deck_sprite.center_y = SCREEN_HEIGHT / 2 + 120  # match your deck_y offset
        # self.deck_back_sprites.append(deck_sprite)
        for i in range(10):
            deck_sprite = arcade.Sprite(CARD_BACK_ASSET, CARD_SCALE)
            deck_sprite.center_x = SCREEN_WIDTH / 2
            deck_sprite.center_y = SCREEN_HEIGHT / 2 + 120 + i * 2  # small offset for thickness
            self.deck_back_sprites.append(deck_sprite)

        # List for dealing animations
        self.deal_animations = []

        # Networking
        self.sio = socketio.Client()
        self.server_url = "https://poker-server-yv2b.onrender.com"  # Change to servers IP when flask starts running

        # GUI
        self.status_text = "Not Connected"
        self.player_name = "Player"
        self.seat_position = 0
        self.player_list = []
        self.lobby = []
        self.all_ready = False
        self.is_ready = False

        self.incoming_hands = []
        self.incoming_lock = threading.Lock()
        self.incoming_community_cards = []
        self.community_lock = threading.Lock()

        self.ui = gui.UIManager()
        self.ready_button = None
        self.start_button = None
        self.bet_button = None
        self.fold_button = None
        self.check_button = None
        self.raise_button = None
        self.call_button = None

        self.anchor = None
        self.start_box = None
        self.action_row = None
        self.left_column = None
        self.right_column = None

        self.phase = Phase.LOBBY

        self.current_game_state = None

    def setup(self):
        self.register_socket_events()
        threading.Thread(target=self.connect_to_server, daemon=True).start()
        self.setup_ui()

    # -------------------- UI --------------------
    def setup_ui(self):
        self.ui.enable()
        self.anchor = gui.UIAnchorLayout()
        self.ui.add(self.anchor)

        self.start_box = gui.UIBoxLayout(space_between=10)
        self.ready_button = gui.UIFlatButton(text="Ready", width=160)
        self.start_button = gui.UIFlatButton(text="Start Game", width=160)

        @self.ready_button.event("on_click")
        def _on_ready_click(event):
            self.sio.emit("ready", {"action": "toggle"})

        @self.start_button.event("on_click")
        def _on_start_click(event):
            if self.all_ready and len(self.lobby) >= 2:
                self.sio.emit("start_game", {})
            else:
                self.status_text = "Waiting for everyone to be ready..."

        self.start_box.add(self.ready_button)
        self.start_box.add(self.start_button)

        self.ui.add(
            self.anchor.add(
                anchor_x="right",
                anchor_y="bottom",
                align_x=-10,
                align_y=10,
                child=self.start_box
            )
        )

        # Action buttons
        self.action_row = gui.UIBoxLayout(vertical=False, space_between=20)
        self.left_column = gui.UIBoxLayout(space_between=8)
        self.right_column = gui.UIBoxLayout(space_between=8)

        self.check_button = gui.UIFlatButton(text="Check", width=140)
        self.fold_button = gui.UIFlatButton(text="Fold", width=140)
        self.bet_button = gui.UIFlatButton(text="Bet", width=140)
        self.raise_button = gui.UIFlatButton(text="Raise", width=140)
        self.call_button = gui.UIFlatButton(text="Call", width=140)

        @self.check_button.event("on_click")
        def _on_check_click(event):
            self.sio.emit("player_action", {"action": "check"})
        @self.fold_button.event("on_click")
        def _on_fold_click(event):
            self.sio.emit("player_action", {"action": "fold"})
        @self.bet_button.event("on_click")
        def _on_bet_click(event):
            self.sio.emit("player_action", {"action": "bet", "amount": 10})
        @self.raise_button.event("on_click")
        def _on_raise_click(event):
            self.sio.emit("player_action", {"action": "raise", "amount": 10})
        @self.call_button.event("on_click")
        def _on_call_click(event):
            self.sio.emit("player_action", {"action": "call"})

        self.left_column.add(self.check_button)
        self.left_column.add(self.fold_button)
        self.right_column.add(self.bet_button)
        self.right_column.add(self.call_button)
        self.right_column.add(self.raise_button)
        self.action_row.add(self.left_column)
        self.action_row.add(self.right_column)

        self.ui.add(
            self.anchor.add(
                anchor_x="right",
                anchor_y="bottom",
                align_x=-10,
                align_y=10,
                child=self.action_row
            )
        )

        self.apply_phase(Phase.LOBBY)

    def set_group_visible(self, container, visible: bool):
        container.visible = visible
        for child in container.children:
            child.visible = visible
            child.enabled = visible

    def apply_phase(self, phase: Phase):
        self.phase = phase
        if phase == Phase.LOBBY:
            self.set_group_visible(self.start_box, True)
            self.set_group_visible(self.action_row, False)
        else:
            self.set_group_visible(self.start_box, False)
            self.set_group_visible(self.action_row, True)
        self.update_buttons()

    def update_buttons(self):
        self.ready_button.text = "Unready" if self.is_ready else "Ready"
        self.start_button.disabled = not (self.all_ready and len(self.lobby) >= 2)

    # Helper function for enabling and disabling buttons based off turn and round status
    def set_action_buttons(self, actions):
        # disable all buttons
        for b in [self.check_button, self.fold_button, self.bet_button, self.raise_button, self.call_button]:
            b.disabled = True
            b.visible = True
        # Enable buttons based on
        allowed = set(actions or [])
        self.check_button.disabled = "check" not in allowed
        self.fold_button.disabled = "fold" not in allowed
        self.bet_button.disabled = "bet" not in allowed
        self.raise_button.disabled = "raise" not in allowed
        self.call_button.disabled = "call" not in allowed

    # -------------------- SOCKET --------------------
    def register_socket_events(self):
        @self.sio.event
        def connect():
            print("Connected to server.")
            self.status_text = "Connected!"
            self.sio.emit("set_name", {"player_name": self.player_name})

        @self.sio.on("lobby_state")
        def on_lobby_state(data):
            self.lobby = data or []
            self.all_ready = len(self.lobby) > 0 and all(p.get("ready", False) for p in self.lobby)
            names = [f"{p['name']}{' [x]' if p.get('ready') else ' [ ]'}" for p in self.lobby]
            self.status_text = f"Lobby: {', '.join(names)} | All ready: {self.all_ready}"
            self.update_buttons()

        @self.sio.on("player_list")
        def update_player_list(player_dictionaries: list):
            print("Player list", player_dictionaries)
            self.status_text = f"Players: {', '.join([player['name'] for player in player_dictionaries])}"
            self.player_list = player_dictionaries

        @self.sio.on("seat_position")
        def set_seat_position(seat_position: int):
            self.seat_position = seat_position

        @self.sio.on("round_started")
        def on_round_started(_data):
            self.apply_phase(Phase.IN_HAND)

        @self.sio.on("round_reset")
        def on_round_reset(_data):
            self.apply_phase(Phase.LOBBY)

        @self.sio.on("hand")
        def update_hand(hand_cards: list):
            print("Received hand", hand_cards)
            self.cards_dealt = True
            # Store in thread-safe queue
            with self.incoming_lock:
                self.incoming_hands.append(hand_cards)

        @self.sio.on("your_turn")
        def your_turn(data):
            self.status_text = data["message"]

        @self.sio.on("available_actions")
        def available_actions(_):
            acts = _.get("actions", [])
            self.set_action_buttons(acts)

        @self.sio.on("community_cards")
        def update_community_cards(cards: list):
            with self.community_lock:
                self.incoming_community_cards.append(cards)

        @self.sio.on("message")
        def post_message(message: str):
            print(message)
            self.status_text = message

        @self.sio.on("error_message")
        def post_error(data):
            self.status_text = f"Error: {data['message']}"

        @self.sio.on("game_state")
        def on_game_state(state):
            self.current_game_state = state

    def connect_to_server(self):
        try:
            self.sio.connect(self.server_url)
        except Exception as e:
            print("Connection failed:", e)
            self.status_text = "Failed to connect."

    # -------------------- DRAW --------------------
    def on_draw(self):
        self.clear()
        cx, cy = self.table_center_x, self.table_center_y
        arcade.draw_ellipse_filled(cx, cy, self.table_width, self.table_height, arcade.color.CAPUT_MORTUUM)

        self.draw_stools_around_table()
        self.draw_players_around_table()

        self.deck_back_sprites.draw()
        self.community_cards.draw()
        self.hand_cards.draw()
        for hand in self.other_hands.values():
            hand.draw()

        arcade.draw_text(self.status_text, 10, 20, arcade.color.WHITE, 16)
        self.ui.draw()

        # players chip amount and pot amount
        if self.current_game_state:
            # Find client player
            my_uuid = self.sio.get_sid()
            my_player = next((p for p in self.current_game_state["players"] if p["uuid"] == my_uuid), None)
            my_chips = my_player["chips"] if my_player else 0
            pot_amount = self.current_game_state.get("pot", 0)

            arcade.draw_text(f"My Chips: {my_chips}", 10, SCREEN_HEIGHT - 30, arcade.color.YELLOW, 18)
            arcade.draw_text(f"Pot: {pot_amount}", 10, SCREEN_HEIGHT - 60, arcade.color.ORANGE, 18)

    # render the player name at each stool with the client player localized to the bottom.
    def draw_players_around_table(self):
        cx, cy = self.table_center_x, self.table_center_y
        rx = self.table_width / 2 + SEAT_CLEARANCE
        ry = self.table_height / 2 + SEAT_CLEARANCE

        for player in self.player_list:
            theta = -2 * math.pi * (player['seat_position'] + 2 - self.seat_position) / SEAT_COUNT

            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)
            # Draw Player
            arcade.draw_text(player["name"], x - 30, y - 50, arcade.color.WHITE, 16)  # positioning could use some work
            # arcade.draw_text(player["money_count"], x - 30, y - 70, arcade.color.WHITE, 16)


    # helper function for update_player_list to draw facedown cards
    def create_facedown_hand_for_player(self, seat_position):
        # essentially a copy from draw_players_around_table
        cx, cy = self.table_center_x, self.table_center_y
        rx = self.table_width / 2.5
        ry = self.table_height / 2.5

        theta = -2 * math.pi * (seat_position + 2 - self.seat_position) / SEAT_COUNT
        base_x = cx + rx * math.cos(theta)
        base_y = cy + ry * math.sin(theta)
        print(f"Facedown cards for seat {seat_position} at ({base_x}, {base_y})")

        hand_sprites = arcade.SpriteList()

        space_offset = 28

        # for two facedown cards
        for i in range(2):
            card_back = arcade.Sprite(CARD_BACK_ASSET, CARD_SCALE)
            card_back.center_x = base_x + i * space_offset
            card_back.center_y = base_y
            # offset top card's y - allows for more space on board
            if i == 0:
                card_back.center_y = base_y + 70
            hand_sprites.append(card_back)

            end_pos = (base_x + i * space_offset, base_y + i * 10)
            self.enqueue_deal(card_back, end_pos, duration=0.25, delay=0.3)

            print(f"  Card {i}: position ({card_back.center_x}, {card_back.center_y})")

        self.other_hands[seat_position] = hand_sprites
        print(f"  Total other_hands: {len(self.other_hands)}")

    def draw_stools_around_table(self):
        cx, cy = self.table_center_x, self.table_center_y
        rx = self.table_width / 2 + SEAT_CLEARANCE
        ry = self.table_height / 2 + SEAT_CLEARANCE

        for i in range(SEAT_COUNT):
            theta = 2 * math.pi * i / SEAT_COUNT
            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)

            # Stool top
            arcade.draw_circle_filled(x, y, STOOL_RADIUS, STOOL_COLOR)
            # Light ring
            arcade.draw_circle_outline(x, y, STOOL_RADIUS, STOOL_RING_COLOR, STOOL_RING_THICKNESS)

            # Cast shadow
            leg_len = 8
            leg_dx = math.cos(theta) * -1
            leg_dy = math.sin(theta) * -1
            arcade.draw_line(x, y, x + leg_dx * leg_len, y + leg_dy * leg_len, STOOL_COLOR, 4)

    # -------------------- ANIMATION --------------------
    def enqueue_deal(self, sprite: arcade.Sprite, end_xy, duration=0.25, delay=0.3):
        start_x, start_y = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 120
        sprite.center_x, sprite.center_y = start_x, start_y

        anim = {
            "sprite": sprite,
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_xy[0],
            "end_y": end_xy[1],
            "start_time": time.time() + delay,
            "duration": duration,
            "done": False,
        }
        self.deal_animations.append(anim)


    def update_animations(self):
        """Advance and apply any active deal animations. Call this from on_update()."""
        now = time.time()
        still_running = []

        for anim in self.deal_animations:
            # not started yet
            if now < anim["start_time"]:
                still_running.append(anim)
                continue

            # already finished
            if anim.get("done"):
                continue

            elapsed = now - anim["start_time"]
            dur = anim["duration"]
            progress = min(1.0, elapsed / dur) if dur > 0 else 1.0

            sx, sy = anim["start_x"], anim["start_y"]
            ex, ey = anim["end_x"], anim["end_y"]

            # Interpolate
            anim["sprite"].center_x = sx + (ex - sx) * progress
            anim["sprite"].center_y = sy + (ey - sy) * progress

            if progress >= 1.0:
                anim["done"] = True
            else:
                still_running.append(anim)

        # keep only running animations
        self.deal_animations = still_running


    # -------------------- DISPLAY CARDS --------------------
    def display_hand(self, cards):
        # Display cards received from server
        self.hand_cards = arcade.SpriteList()
        start_x = SCREEN_WIDTH // 2 - (len(cards) * 50) // 2
        y = 100
        deck_x, deck_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2  # deck position (adjust as needed)

        for i, card_str in enumerate(cards):
            value, _, suit = card_str.partition(" of ")
            card = Card(suit, value, CARD_SCALE)
            card.center_x = deck_x
            card.center_y = deck_y

            self.hand_cards.append(card)

            # Animate the deal from the deck to the player's hand
            end_pos = (start_x + i * 100, y + 50)
            self.enqueue_deal(card, end_pos, duration=0.25, delay=0.3)


    # Card dealing animation
    def display_community_cards(self, cards):
        gap = 18
        y = self.table_center_y
        deck_x, deck_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2  # SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 120 #deck origin point

        for i, card_str in enumerate(cards):
            value, _, suit = card_str.partition(" of ")
            card = Card(suit, value, CARD_SCALE)
            card.center_x = deck_x
            card.center_y = deck_y

            already_dealt = any(c.value + " of " + c.suit == card_str for c in self.community_cards)
            if already_dealt:
                continue
            self.community_cards.append(card)

            end_pos = (308 + i * (CARD_WIDTH + gap), y)
            if i <= 2:
                self.enqueue_deal(card, end_pos, duration=0.25, delay=i * 0.3)
            else:
                self.enqueue_deal(card, end_pos, duration=0.25, delay=0.3)


    # -------------------- UPDATE --------------------
    def on_update(self, delta_time):
        # Process facedown cards when player list changes
        if self.cards_dealt:
            current_seats = set(self.other_hands.keys())
            expected_seats = {p['seat_position'] for p in self.player_list if p['seat_position'] != self.seat_position}
            if current_seats != expected_seats:
                self.other_hands.clear()
                for player in self.player_list:
                    seat = player['seat_position']
                    if seat != self.seat_position:
                        self.create_facedown_hand_for_player(seat)

        # Process hands received from server
        with self.incoming_lock:
            while self.incoming_hands:
                cards = self.incoming_hands.pop(0)
                self.display_hand(cards)

        # Process community cards
        with self.community_lock:
            while self.incoming_community_cards:
                cards = self.incoming_community_cards.pop(0)
                self.display_community_cards(cards)

        self.update_animations()

def main():
    window = PokerGameClient()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    main()
