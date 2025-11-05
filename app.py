"""
CS 3050 Poker Game - app.py
Sam Whitcomb, Jonah Harris, Owen Davis, Jake Pappas
"""


import os
from flask import Flask, request
from flask_socketio import SocketIO, emit

from game import PokerGame

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")  # allow external connections

# Single game instance
game = PokerGame()

player_counter = 0

# Helper function for when it is a player's turn
def send_turn_prompt(player):
    emit('your_turn', {"message": "It's your turn!"}, to=player.uuid)
    # Decides what buttons can and can't be pressed
    emit('available_actions', {"actions": game.get_available_actions(player.uuid)}, to=player.uuid)


# Broadcast entire game state to all players
def broadcast_game_state():
    state = game.serialize_game_state()
    emit("game_state", state)


# Event handlers

# When someone connects
@socketio.on('connect')
def handle_connect():
    print(f"Player connected: {request.sid}")
    emit('connected', 'Connected to server!')


# When a player sets their name
@socketio.on('set_name')
def handle_set_name(data):
    global player_counter
    player_counter += 1  # incrementing the counter each time a player joins
    name = f"Player {player_counter}"

    # name = data.get('player_name', 'Anonymous')
    uuid = request.sid
    emit('seat_position', player_counter)
    game.add_player(name, uuid, seat_position=data.get('seat_position', player_counter),
                    seat_position_flag=data.get('seat_position_flag', 0), is_ready=False)

    print(f"Added player: {name}, SID={uuid}")
    print(f"Current players: {[p.name for p in game.players.values()]}")

    # Notify all players of player list
    emit('player_list', [player.to_dict() for player in game.players.values()], broadcast=True)


@socketio.on('ready')
def handle_ready(data):
    uuid = request.sid
    if data is None:
        data = {}

    action = data.get('action')
    if action == 'toggle' or ('ready' not in data):
        # Default: toggle if ready not explicitly provided
        new_val = game.toggle_ready(uuid)
    else:
        new_val = game.set_ready(uuid, bool(data.get('ready', True)))

    print(f"Player {uuid} ready set to {new_val}")
    # Broadcast updated player list AND ready state
    lobby_state = [{
        "uuid": p.uuid,
        "name": p.name,
        "ready": getattr(p, "ready", False)
    } for p in game.players.values()]

    emit("lobby_state", lobby_state, broadcast=True)


# Start a new round
@socketio.on('start_game')
def handle_start_game(_):
    if game.round_active:
        emit('error_message', 'A round is already in progress!')
        return

    if len(game.players) < 2:
        emit('error_message', 'You must have at least 2 players!')
        return

    if not game.all_ready():
        emit('error_message', 'Everyone must be ready!')
        return

    game.start_round()
    print("New round started")

    emit('round_started', {}, broadcast=True)
    emit('game_state', game.serialize_game_state(), broadcast=True)

    # Send each player their hand
    for player in game.players.values():
        emit('hand', [str(card) for card in player.hand], to=player.uuid)

    # Notify current player it's their turn
    current_player = game.current_player()
    send_turn_prompt(current_player)


@socketio.on('player_action')
def handle_action(data):
    uuid = request.sid
    action = data.get('action')
    amount = int(data.get('amount', 0))

    if not game.round_active:
        emit('error_message', {"message": "No active round."}, to=uuid)
        return

    # Apply the action in game logic
    success, message = game.apply_action(uuid, action, amount)
    if not success:
        emit('error_message', message, to=uuid)
        return

    # Broadcast game state to all players
    emit('message', message, broadcast=True)

    print("DEBUG: Action received:", action)
    print("DEBUG: Betting round complete?", game.is_betting_round_complete())
    print("DEBUG: Current street:", game.street)

    # Check if betting round is complete
    if game.is_betting_round_complete():
        progress_betting_round()
    else:
        # Move to next active player
        next_player = game.advance_turn()
        if next_player:
            send_turn_prompt(next_player)


def progress_betting_round():
    # Automatically move to next street or showdown
    if game.street != "showdown":
        game.move_to_next_street()
        # Send newly dealt community cards only (keeps same behavior as before)
        emit('community_cards', [str(c) for c in game.community_cards], broadcast=True)

        # Broadcast updated game state
        emit('game_state', game.serialize_game_state(), broadcast=True)

        # Notify first active player in new street
        current_player = game.current_player()
        send_turn_prompt(current_player)

    else:
        # Showdown logic (placeholder)
        emit('message', "Round over! Showdown now.", broadcast=True)
        emit('game_state', game.serialize_game_state(), broadcast=True)



@socketio.on('request_flop')
def handle_flop_request(_):
    if not game.round_active:
        emit('error_message', 'No active round.')
        return

    if len(game.community_cards) > 0:
        return  # Flop already dealt

    game.deal_flop()
    print("Flop dealt:", [str(c) for c in game.community_cards])
    emit("community_cards", [str(card) for card in game.community_cards], broadcast=True)


@socketio.on('request_turn')
def handle_turn_request(_):
    if len(game.community_cards) != 3:
        emit('error_message', 'Flop must be dealt first.')
        return
    game.deal_turn()
    emit("community_cards", [str(card) for card in game.community_cards], broadcast=True)


@socketio.on('request_river')
def handle_river_request(_):
    if len(game.community_cards) != 4:
        emit('error_message', 'Turn must be dealt first.')
        return
    game.deal_river()
    emit("community_cards", [str(card) for card in game.community_cards], broadcast=True)


@socketio.on('reset_round')
def handle_reset_round(_):
    game.reset_round()
    print("Round has been reset.")

    # Notify all clients to clear hands and community cards
    for player in game.players.values():
        emit('hand', [], to=player.uuid)
    emit('community_cards', [], broadcast=True)


if __name__ == "__main__":
    print("Starting poker server...")
    socketio.run(app,
                 host="0.0.0.0",
                 port = int(os.environ.get("PORT", 5000)),
                 debug=True,
                 allow_unsafe_werkzeug=True)
