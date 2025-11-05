# Poker Game Multiplayer – Client Instructions
## Prerequisites

1. Python 3.10+ installed
2. pip install arcade python-socketio
(If not installed, run pip install -r requirements.txt where requirements.txt includes these.)
## Connecting to a Hosted Server
1. Open client.py in a text editor.
2. Set the server URL to the public URL of your hosted app:
`self.server_url = "https://your-app-name.onrender.com"`
3. Save the file.
4. Run the client: 
`python client.py`
5. The client will connect automatically and join the lobby. 
   1. You can toggle ready using the Ready button. 
   2. Once all players are ready, the Start Game button becomes active.

## Notes

- Each player must run their own client.py instance on their machine.

- Multiple players can join the same game simultaneously by connecting to the same server URL.

- The client will display:
  - Your hand cards 
  - Community cards 
  - Your chips and the total pot 
  - Action buttons: Check, Fold, Bet, Call, Raise, All-in

## Troubleshooting
- If you cannot connect, make sure the server is running and the correct public URL is set.
- Ensure any firewalls or network restrictions allow WebSocket connections.