"""
CS 3050 Poker Game - client.py
Sam Whitcomb, Jonah Harris, Owen Davis, Jake Pappa's
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
import tkinter as tk


def get_screen_resolution():
    root = tk.Tk()
    root.withdraw()
    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.destroy()
    return width * 0.6, height * 0.6

SCREEN_WIDTH, SCREEN_HEIGHT = 1040, 768
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

HAND_RANKING_NUM_TO_STRING = {1: "High Card", 2: "One Pair", 3: "Two Pair", 4: "Three of a Kind",
                              5: "Straight",
                              6: "Flush", 7: "Full House", 8: "Four of a Kind", 9: "Straight Flush",
                              10: "Royal Flush"}

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

        # shuffle animation state
        self.shuffle_animation_active = False
        self.shuffle_start_time = 0
        self.shuffle_duration = 2.0
        self.shuffle_complete = False
        self.pending_hand = None
        self.pending_community_cards = None

        # Background music
        self.background_music = None
        self.music_player = None
        # Card music
        self.card_flip_sound = None
        self.card_shuffle_sound = None
        self.shuffle_sound_played = False
        self.sound_enabled = True

        # Networking
        # self.sio = socketio.Client()
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # 0 = keep trying forever
            reconnection_delay=1.0,
            reconnection_delay_max=5.0,
            request_timeout=10.0,
        )
        self.server_url = "http://127.0.0.1:5000"  # Change to servers IP when flask starts running

        # GUI
        self.status_text = "Not Connected"
        self.betting_text = "No Current Bet"
        self.player_name = "Player"
        self.seat_position = 0
        self.player_list = []
        self.lobby = []
        self.all_ready = False
        self.is_ready = False
        self.game_started = False
        self.show_title_screen = True

        self.incoming_hands = []
        self.incoming_lock = threading.Lock()
        self.incoming_community_cards = []
        self.community_lock = threading.Lock()
        self.incoming_reveals = []
        self.reveal_lock = threading.Lock()

        self.ui = gui.UIManager()
        self.ready_button = None
        self.start_button = None
        self.bet_button = None
        self.fold_button = None
        self.check_button = None
        self.raise_button = None
        self.call_button = None
        self.sound_button = None
        self.placeholder_button = None
        self.placeholder_button2 = None

        self.anchor = None
        self.start_box = None
        self.action_row = None
        self.audio_row = None
        self.left_column = None
        self.right_column = None
        self.top_right_column = None

        self.phase = Phase.LOBBY

        self.current_game_state = None
        # Used for greying buttons
        self.is_my_turn = False
        # Used for custom betting
        self.bet_amount_input = None


    def setup(self):
        self.register_socket_events()
        threading.Thread(target=self.connect_to_server, daemon=True).start()
        self.setup_ui()
        self.setup_music()

    # Load and play background music
    def setup_music(self):
        try:
            # BACKGROUND
            # load in background music file
            self.background_music = arcade.load_sound("sounds/lounge-jazz-elevator-music.mp3")
            # play music on loop w/ volume
            self.music_player = arcade.play_sound(
                self.background_music,
                volume=0.1,
                loop=True
            )
            print("Background Music has started")


            # CARD FLIP
            # Load card flip sound file
            self.card_flip_sound = arcade.load_sound("sounds/flipcard1.mp3")
            # We'll play this sound later
            print("Card flip sound loaded")

            # CARD SHUFFLE
            # Load shuffle sound file
            self.card_shuffle_sound = arcade.load_sound("sounds/cards-being-shuffled.mp3")
            print("Card shuffle sound loaded")

        except Exception as e:
            print(f"Count not load music fully. Exception: {e}")

    # Cleanup for disconnects
    def on_close(self):
        try:
            # stop music if currently playing
            if self.music_player:
                arcade.stop_sound(self.music_player)

            if self.sio.connected:
                try:
                    self.sio.emit("client_exit", {})
                    time.sleep(0.1)
                except Exception:
                    pass
                self.sio.disconnect()
        finally:
            super().on_close()

    # Helper for custom betting
    def get_bet_amount(self) -> int:
        """Return a sane integer bet amount from the input box."""
        if not self.bet_amount_input:
            return 10
        try:
            amt = int(self.bet_amount_input.text)
        except ValueError:
            amt = 10
        if amt <= 0:
            amt = 10
        return amt

    # -------------------- UI --------------------
    def setup_ui(self):
        self.ui.enable()
        self.anchor = gui.UIAnchorLayout()
        self.ui.add(self.anchor)

        self.start_box = gui.UIBoxLayout(space_between=10)
        self.ready_button = gui.UIFlatButton(text="Ready", width=160)
        self.start_button = gui.UIFlatButton(text="Start Game", width=160)

        @self.ready_button.event("on_click")
        def _on_ready_click(_):
            self.sio.emit("ready", {"action": "toggle"})

        @self.start_button.event("on_click")
        def _on_start_click(_):
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
        self.audio_row = gui.UIBoxLayout()
        self.left_column = gui.UIBoxLayout(space_between=8)
        self.right_column = gui.UIBoxLayout(space_between=8)

        self.top_right_column = gui.UIBoxLayout(space_between=8)

        self.check_button = gui.UIFlatButton(text="Check", width=140)
        self.fold_button = gui.UIFlatButton(text="Fold", width=140)
        self.bet_button = gui.UIFlatButton(text="Bet", width=140)
        self.raise_button = gui.UIFlatButton(text="Raise", width=140)
        self.call_button = gui.UIFlatButton(text="Call", width=140)
        self.placeholder_button = gui.UIFlatButton(text="Place", width=140)
        self.placeholder_button2 = gui.UIFlatButton(text="Place2", width=140)

        self.sound_button = gui.UIFlatButton(text="🔉", width=60, height=60)

        # Input Text box for betting amounts
        self.bet_amount_input = gui.UIInputText(width=80, text="10")

        @self.check_button.event("on_click")
        def _on_check_click(_):
            self.sio.emit("player_action", {"action": "check"})
        @self.fold_button.event("on_click")
        def _on_fold_click(_):
            self.sio.emit("player_action", {"action": "fold"})
        @self.bet_button.event("on_click")
        def _on_bet_click(_):
            amount =  self.get_bet_amount()
            self.set_action_buttons([])
            self.sio.emit("player_action", {"action": "bet", "amount": amount})
        @self.raise_button.event("on_click")
        def _on_raise_click(_):
            amount = self.get_bet_amount()
            self.set_action_buttons([])
            self.sio.emit("player_action", {"action": "raise", "amount": amount})
        @self.call_button.event("on_click")
        def _on_call_click(_):
            self.sio.emit("player_action", {"action": "call"})
        @self.sound_button.event("on_click")
        def _on_sound_click(event):
            # switch sound_enabled T->F or F->T
            self.sound_enabled = not self.sound_enabled

            if self.sound_enabled:
                self.sound_button.text = "🔊"
                if self.background_music and not self.music_player:
                    self.music_player = arcade.play_sound(self.background_music, volume=0.1, loop=True)
            else:
                self.sound_button.text = "🔇"
                if self.music_player:
                    arcade.stop_sound(self.music_player)
                    self.music_player = None

            self.sio.emit("mute_action", {"action":"mute_or_on"})

        self.left_column.add(self.placeholder_button)
        self.left_column.add(self.placeholder_button2)
        self.left_column.add(self.check_button)
        self.left_column.add(self.fold_button)
        self.right_column.add(self.bet_button)
        self.right_column.add(self.call_button)
        self.right_column.add(self.raise_button)
        self.right_column.add(self.bet_amount_input)
        self.top_right_column.add(self.sound_button)
        self.action_row.add(self.left_column)
        self.action_row.add(self.right_column)
        self.audio_row.add(self.top_right_column)

        self.placeholder_button.visible=False
        self.placeholder_button2.visible = False

        self.ui.add(
            self.anchor.add(
                anchor_x="right",
                anchor_y="bottom",
                align_x=-10,
                align_y=10,
                child=self.action_row
            )
        )

        self.ui.add(
            self.anchor.add(
                anchor_x="right",
                anchor_y="top",
                align_x=-10,
                align_y=-10,
                child=self.audio_row
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
            # starts with all buttons greyed out on new hand
            self.set_action_buttons([])
        self.update_buttons()

    def update_buttons(self):
        self.ready_button.text = "Unready" if self.is_ready else "Ready"
        self.start_button.disabled = not (self.all_ready and len(self.lobby) >= 2)

    # Helper function for enabling and disabling buttons based off turn and round status
    def set_action_buttons(self, actions):
        # disable all buttons
        for b in [self.check_button, self.fold_button,
                  self.bet_button, self.raise_button, self.call_button]:
            b.disabled = True
            b.visible = True
        # Enable buttons based on
        allowed = set(actions or [])
        self.check_button.disabled = "check" not in allowed
        self.fold_button.disabled = "fold" not in allowed
        self.bet_button.disabled = "bet" not in allowed
        self.raise_button.disabled = "raise" not in allowed
        self.call_button.disabled = "call" not in allowed

        # Can only put custom amount if applicable
        if self.bet_amount_input:
            self.bet_amount_input.disabled = not (("bet" in allowed) or ("raise" in allowed))

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
            self.shuffle_animation(start_new=True)
            self.game_started = True
            self.show_title_screen = False
            # Grey out all buttons
            self.is_my_turn = False
            self.set_action_buttons([])

        @self.sio.on("round_reset")
        def on_round_reset(_):
            # Defer sprite clearing until next frame ON THE MAIN THREAD
            arcade.schedule_once(self.reset_round, 0)

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
            self.is_my_turn = True

        @self.sio.on("available_actions")
        def available_actions(_):
            acts = _.get("actions", [])
            self.set_action_buttons(acts)

        @self.sio.on("community_cards")
        def update_community_cards(cards: list):
            with self.community_lock:
                self.incoming_community_cards.append(cards)

        @self.sio.on("reveal_hands")
        def on_reveal_hands(data):
            hands_data = data.get("hands", {})
            with self.reveal_lock:
                self.incoming_reveals.append(hands_data)

        @self.sio.on("message")
        def post_message(message: str):
            print(message)
            self.status_text = message

        @self.sio.on("bet_message")
        def post_bet_message(message: str):
            print(message)
            self.betting_text = message

        @self.sio.on("error_message")
        def post_error(data):
            self.status_text = f"Error: {data}"

        @self.sio.on("game_state")
        def on_game_state(state):
            self.current_game_state = state

            my_uuid = self.sio.get_sid()
            current_turn = state.get("current_turn")
            self.is_my_turn = (current_turn == my_uuid)

    def connect_to_server(self):
        try:
            self.sio.connect(self.server_url)
        except Exception as e:
            print("Connection failed:", e)
            self.status_text = "Failed to connect."

    # -------------------- DRAW --------------------
    def on_draw(self):
        self.clear()

        # Title Screen
        if self.show_title_screen:
            # Simple dark background (override the table drawing)
            arcade.draw_lbwh_rectangle_filled(
                0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, arcade.color.DARK_GREEN
            )

            # Title
            arcade.draw_text(
                "CS 3050 Poker",
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2 + 80,
                arcade.color.WHITE,
                48,
                anchor_x="center",
                anchor_y="center",
            )

            # Subtitle
            arcade.draw_text(
                "Texas Hold'em",
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2 + 30,
                arcade.color.LIGHT_GRAY,
                24,
                anchor_x="center",
                anchor_y="center",
            )
            # Instructions
            arcade.draw_text(
                "Use READY to toggle your status.\n"
                "When all players are ready, click START GAME.",
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2 - 40,
                arcade.color.WHITE,
                18,
                anchor_x="center",
                anchor_y="center",
                align="center",
                width=600,
            )

            arcade.draw_text(self.status_text, 10, 20, arcade.color.WHITE, 16)

            # Draw ready and start buttons
            self.ui.draw()
            return

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
        arcade.draw_text(self.betting_text, 10, 40, arcade.color.WHITE, 16)
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

            arcade.draw_text(f"Hand rank: {HAND_RANKING_NUM_TO_STRING[my_player['hand_rank']]}",
                             10, SCREEN_HEIGHT - 90, arcade.color.BLUE_GREEN, 18)

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
    def enqueue_deal(self, sprite: arcade.Sprite, end_xy, duration=0.25, delay=0.3, play_sound=False):
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
            "play_sound": play_sound,
            "sound_played": False

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

            # Play sound when animation starts
            if anim.get("play_sound") and not anim.get("sound_played"):
                if self.card_flip_sound and self.sound_enabled:
                    arcade.play_sound(self.card_flip_sound, volume=1.0, speed=1.5)
                anim["sound_played"] = True

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

        # update shuffle anim if active
        self.shuffle_animation()

    def shuffle_animation(self, start_new=False):
        '''
        Shuffles the deck of cards at the beginning of each round (before cards handed out)
        start_new: If set to True, starts new shuffle animation
        '''
        # Start new animation
        if start_new:
            self.shuffle_animation_active = True
            self.shuffle_start_time = time.time()
            self.shuffle_complete = False
            self.shuffle_sound_played = False

        # If no active animation, stop
        if not self.shuffle_animation_active:
            return

        # Create progress to split up stages (split, combine)
        now = time.time()
        elapsed = now - self.shuffle_start_time
        progress = elapsed / self.shuffle_duration

        original_x = SCREEN_WIDTH / 2
        original_y = SCREEN_HEIGHT / 2 + 120


        # play shuffle music
        if self.card_shuffle_sound and not self.shuffle_sound_played and self.sound_enabled:
            arcade.play_sound(self.card_shuffle_sound, volume=1.0)
            self.shuffle_sound_played = True

        # three cycles, each is 1/3 of total time
        cycle_duration = 1.0 / 3.0

        if progress < 1.0:
            cycle_progress = (progress % cycle_duration) / cycle_duration

            if cycle_progress < 0.5:
                split_progress = cycle_progress / 0.5
                self.shuffle_apart(split_progress, original_x, original_y)
            else:
                combine_progress = (cycle_progress - 0.5) / 0.5
                self.shuffle_together(combine_progress, original_x, original_y)

        # we're done
        else:
            for i, sprite in enumerate(self.deck_back_sprites):
                sprite.center_x = original_x
                sprite.center_y = original_y + i * 2
                #sprite.angle=0
            self.shuffle_animation_active = False
            self.shuffle_complete = True

            if self.pending_hand is not None:
                self.display_hand(self.pending_hand)
                self.pending_hand = None
            if self.pending_community_cards is not None:
                self.display_community_cards(self.pending_community_cards)
                self.pending_community_cards = None

    def shuffle_apart(self, progress, original_x, original_y):
        """Move deck halves apart"""
        for i, sprite in enumerate(self.deck_back_sprites):
            if i % 2 == 0:#i < len(self.deck_back_sprites) / 2:
                # Left half - move left
                sprite.center_x = original_x - 60 * progress
                #sprite.angle = -10 * progress
            else:
                # Right half - move right
                sprite.center_x = original_x + 60 * progress
                #sprite.angle = 10 * progress
            sprite.center_y = original_y + i * 2

    def shuffle_together(self, progress, original_x, original_y):
        """Bring deck halves back together"""
        for i, sprite in enumerate(self.deck_back_sprites):
            if i < len(self.deck_back_sprites) / 2:
                # Left half - move from left back to center
                start_x = original_x - 60
                sprite.center_x = start_x + 60 * progress
                #sprite.angle = -10 * (1 - progress)
            else:
                # Right half - move from right back to center
                start_x = original_x + 60
                sprite.center_x = start_x - 60 * progress
                #sprite.angle = 10 * (1 - progress)
            sprite.center_y = original_y + i * 2


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

            # play card flip sound
            if self.card_flip_sound and self.sound_enabled:
                arcade.play_sound(self.card_flip_sound, volume=1.0)
            # Animate the deal from the deck to the player's hand
            end_pos = (start_x + i * 100, y + 50)
            self.enqueue_deal(card, end_pos, duration=0.25, delay=0.3)

    def reveal_all_hands(self, all_hands_data):
        cx, cy = self.table_center_x, self.table_center_y
        rx = self.table_width / 2.5
        ry = self.table_height / 2.5
        space_offset = 28

        for seat_position_str, cards in all_hands_data.items():
            # skip your own seat
            seat_position = int(seat_position_str)
            if seat_position == self.seat_position:
                continue

            # Calculate position for this seat
            theta = -2 * math.pi * (seat_position + 2 - self.seat_position) / SEAT_COUNT
            base_x = cx + rx * math.cos(theta)
            base_y = cy + ry * math.sin(theta)

            # clear face-down sprites, create face-up ones
            if seat_position in self.other_hands:
                self.other_hands[seat_position].clear()
            revealed_hand = arcade.SpriteList()

            # play card flip sound
            if self.card_flip_sound and self.sound_enabled:
                arcade.play_sound(self.card_flip_sound, volume=1.0)

            for i, card_str in enumerate(cards):
                value, _, suit = card_str.partition(" of ")
                card = Card(suit, value, CARD_SCALE)

                # Position the card
                card.center_x = base_x + i * space_offset
                card.center_y = base_y
                if i == 0:
                    card.center_y = base_y - 10

                revealed_hand.append(card)

            # Replace the face-down cards with face-up cards
            self.other_hands[seat_position] = revealed_hand

            print(f"Revealed hand for seat {seat_position}: {cards}")

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
                self.enqueue_deal(card, end_pos, duration=0.25, delay=i * 0.4, play_sound=True)
            else:
                self.enqueue_deal(card, end_pos, duration=0.25, delay=0.3, play_sound=True)

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
                if self.shuffle_animation_active and not self.shuffle_complete:
                    self.pending_hand = cards
                else:
                    self.display_hand(cards)

        # Process community cards
        with self.community_lock:
            while self.incoming_community_cards:
                cards = self.incoming_community_cards.pop(0)
                if self.shuffle_animation_active and not self.shuffle_complete:
                    self.pending_community_cards = cards
                else:
                    self.display_community_cards(cards)

        # Process revealed cards
        with self.reveal_lock:
            while self.incoming_reveals:
                hands_data = self.incoming_reveals.pop(0)
                self.reveal_all_hands(hands_data)


        self.update_animations()

    def reset_round(self, delta_time):
        print("Resetting round on main thread")

        # Clear logical data
        self.cards_dealt = False
        self.pending_hand = None
        self.pending_community_cards = None

        # Clear main sprite lists
        self.hand_cards.clear()
        self.community_cards.clear()
        self.deal_animations.clear()

        # Clear other players hands
        self.other_hands.clear()

        # Tell the server to start a new round after a few seconds
        if self.game_started:
            my_uuid = self.sio.get_sid()
            if my_uuid == self.player_list[0]['uuid']:
                arcade.schedule_once(lambda dt: self.sio.emit("ready_for_next_round", {}), 1.5)


def main():
    window = PokerGameClient()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    main()
