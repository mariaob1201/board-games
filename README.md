## chess_duel

Two GPT-5 personas — **The Aggressor** (White) and **The Strategist**
(Black) — play a full game of chess against each other. `python-chess` owns
the board and enforces legality; each model only ever chooses among the
legal moves it's handed, with a short in-character comment per move.

```
chess_duel/
  duel.py        game loop: prompts each persona, validates/retries illegal
                  replies, falls back to a random legal move after repeated
                  invalid output, writes PGN + a JSON move log
  viewer.html     self-contained replay artifact: steps through the game
                  move by move with board, captured pieces, and commentary
  games/          generated game_NNN.json / game_NNN.pgn output
```

### Run

```bash
source .venv/bin/activate
python chess_duel/duel.py
```

Produces `chess_duel/games/game_001.json` and `game_001.pgn`. Open
`chess_duel/viewer.html` (or publish it as an artifact) with that game's
JSON embedded to replay the match.

## league-of-legends

Exploratory notebook, not yet built out.
