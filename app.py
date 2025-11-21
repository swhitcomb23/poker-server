"""
CS 3050 Poker Game - app.py
Sam Whitcomb, Jonah Harris, Owen Davis, Jake Pappa's
"""


import eventlet
from flask import Flask, request
from flask_socketio import SocketIO, emit

from game import PokerGame

hand_ranking_weight_to_string = {1: "High Card", 2: "One Pair", 3: "Two Pair", 4: "Three of a Kind", 5: "Straight",
                                 6: "Flush", 7: "Full House", 8: "Four of a Kind", 9: "Straight Flush",
                                 10: "Royal Flush"}

app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    ping_interval=10,   # server pings every 10s
    ping_timeout=20,
)  # allow external connections

# Single game instance
game = PokerGame()

player_counter = 0

# Helper function for when it is a player's turn
def send_turn_prompt(player_or_uuid):
    # Accept either a Player object or a UUID string
    if isinstance(player_or_uuid, str):
        player = game.players.get(player_or_uuid)
    else:
        player = player_or_uuid

    if not player:
        print("[TURN] Tried to prompt non-existent player:", player_or_uuid)
        return

    print(f"[TURN] Prompting: {player.name} ({player.uuid})")

    # Acting player: turn message + allowed actions
    socketio.emit(
        'your_turn',
        {"message": f"It's {player.name}'s turn"},
        room=None
    )

    actions = game.get_available_actions(player.uuid)

    socketio.emit(
        'available_actions',
        {"actions": actions},
        room=player.uuid
    )

    # Everyone else: explicitly grey out buttons
    for p in game.players.values():
        if p.uuid == player.uuid:
            continue
        socketio.emit(
            'available_actions',
            {"actions": []},
            room=p.uuid
        )


# Broadcast entire game state to all players
def broadcast_game_state():
    state = game.serialize_game_state()
    emit("game_state", state, broadcast=True)


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


@socketio.on("ready_for_next_round")
def handle_ready_for_next_round(_):
    # Reset round state
    game.reset_round()

    # Start round
    game.start_round()
    print("New round started")
    emit('round_started', {}, broadcast=True)

    # Send each player their hand
    for player in game.players.values():
        socketio.emit('hand', [str(card) for card in player.hand], room=player.uuid)

    game.assign_hand_ranking()
    emit('game_state', game.serialize_game_state(), broadcast=True)

    # Notify current player it's their turn
    current_player = game.current_player()
    send_turn_prompt(current_player)


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

    # Send each player their hand
    for player in game.players.values():
        socketio.emit('hand', [str(card) for card in player.hand], room=player.uuid)

    game.assign_hand_ranking()
    emit('game_state', game.serialize_game_state(), broadcast=True)

    # Notify current player it's their turn
    current_player = game.current_player()
    send_turn_prompt(current_player)


@socketio.on('disconnect')
def handle_disconnect(_):
    sid = request.sid
    print(f"Player disconnected: {sid}")

    result = game.on_disconnect(sid)

    emit('message', "A player has disconnected.", broadcast=True)

    player_list_payload = [
        {
            "uuid": p.uuid,
            "name": p.name,
            "seat_position": getattr(p, "seat_position", None),
            "money_count": getattr(p, "chips", 0),
            "ready": getattr(p, "ready", False),
        }
        for p in game.players.values()
    ]
    emit('player_list', player_list_payload, broadcast=True)

    if result.get("ended_round"):
        emit('message', "Round ended due to disconnect (not enough players).", broadcast=True)
        for player in game.players.values():
            emit('hand', [], to=player.uuid)
        emit('community_cards', [], broadcast=True)
        emit('game_state', game.serialize_game_state(), broadcast=True)
        return

    if result.get("ended_round") is False:
        actor = game.current_player()
        if not actor or actor.folded or actor.chips == 0:
            actor = game.advance_turn()

        print(f"[DISCONNECT] Next actor after disconnect: {actor.uuid if actor else None}")
        if actor:
            send_turn_prompt(actor)

    emit('game_state', game.serialize_game_state(), broadcast=True)

@socketio.on('client_exit')
def handle_client_exit(_=None):
    handle_disconnect()


@socketio.on('player_action')
def handle_action(data):
    uuid = request.sid
    action = data.get('action')
    amount = int(data.get('amount', 0))

    if not game.round_active:
        emit('error_message', "No active round.", to=uuid)
        return

    ok, msg = game.apply_action(uuid, action, amount)
    emit('bet_message', msg, broadcast=True)

    if game.is_betting_round_complete():
        progress_betting_round()
    else:
        nxt = game.advance_turn()
        if nxt:
            send_turn_prompt(nxt)
        # Send game state on every action instead of after each deal
        broadcast_game_state()

def progress_betting_round():
    # Automatically move to next street or showdown
    if game.street != "river":
        game.move_to_next_street()
        # Send newly dealt community cards only (keeps same behavior as before)
        emit('community_cards', [str(c) for c in game.community_cards], broadcast=True)
        game.assign_hand_ranking()
        # Broadcast updated game state
        emit('game_state', game.serialize_game_state(), broadcast=True)

        # Notify first active player in new street
        current_player = game.current_player()
        send_turn_prompt(current_player)

    else:
        # Showdown logic (placeholder)
        game.assign_hand_ranking()
        best_rank, winning_players = game.rank_all_player_hands()
        print(f'BEST HAND IS {hand_ranking_weight_to_string[best_rank]} -- {[player.name for player in winning_players]}')
        if len(winning_players) < 1:
            emit('error_message', "Less than 1 winning player... A curious bug indeed.")
        if len(winning_players) == 1:
            game.pot.payout_single(winning_players[0])
        else:
            game.pot.payout_split_pot(winning_players)

        # flip over all cards visually
        all_hands = {}
        for player in game.players.values():
            if not player.folded and len(player.hand) > 0:
                all_hands[player.seat_position] = [str(card) for card in player.hand]
        emit('reveal_hands', {"hands":all_hands}, broadcast=True)


        message = f'BEST HAND IS {hand_ranking_weight_to_string[best_rank]} -- {[player.name for player in winning_players]}'
        emit('bet_message', message, broadcast=True)
        emit('message', "Round over! Showdown now.", broadcast=True)
        emit('game_state', game.serialize_game_state(), broadcast=True)

        eventlet.sleep(2.5)
        emit('round_reset', {}, broadcast=True)


@socketio.on('request_flop')
def handle_flop_request(_):
    if not game.round_active:
        emit('error_message', 'No active round.')
        return

    if len(game.community_cards) > 0:
        return  # Flop already dealt

    game.deal_flop()
    print("Flop dealt:", [str(c) for c in game.community_cards])
    print(f'BEST HAND {game.rank_all_player_hands()}')
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


if __name__ == "__main__":
    print("Starting poker server...")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
