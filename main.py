from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import random
import asyncio

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Define game state
GRID_SIZE = 5
EMPTY_CELL = None
players = {
    "P01": {"tribe": "Blue"}, "P02": {"tribe": "Grey"}, "P03": {"tribe": "Blue"},
    "P04": {"tribe": "Grey"}, "P05": {"tribe": "Blue"}, "P06": {"tribe": "Grey"},
    "P07": {"tribe": "Blue"}, "P08": {"tribe": "Grey"}, "P09": {"tribe": "Blue"},
    "P10": {"tribe": "Grey"}, "P11": {"tribe": "Blue"}, "P12": {"tribe": "Grey"},
    "P13": {"tribe": "Blue"}, "P14": {"tribe": "Grey"}, "P15": {"tribe": "Blue"},
    "P16": {"tribe": "Grey"}, "P17": {"tribe": "Blue"}
}

# Initialize random grid
cells = [(i, j) for i in range(GRID_SIZE) for j in range(GRID_SIZE)]
random.shuffle(cells)
grid = [[EMPTY_CELL for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

player_positions = {}
for player, cell in zip(players.keys(), cells[:len(players)]):
    x, y = cell
    grid[x][y] = player
    player_positions[player] = (x, y)

# Keep track of WebSocket connections
connections = []
middle_threshold = 3  # Default scenario is Scenario 2

# Utility functions
def get_neighbors(x, y):
    directions = [(-1, -1), (-1, 0), (-1, 1),
                  (0, -1),          (0, 1),
                  (1, -1),  (1, 0), (1, 1)]
    return [(x + dx, y + dy) for dx, dy in directions if 0 <= x + dx < GRID_SIZE and 0 <= y + dy < GRID_SIZE]

def count_same_tribe(player, neighbors):
    tribe = players[player]['tribe']
    count = 0
    for nx, ny in neighbors:
        neighbor_player = grid[nx][ny]
        if neighbor_player and players[neighbor_player]['tribe'] == tribe:
            count += 1
    return count

def cell_type(x, y):
    if (x in [0, GRID_SIZE-1]) and (y in [0, GRID_SIZE-1]):
        return 'corner', 3
    elif (x in [0, GRID_SIZE-1]) or (y in [0, GRID_SIZE-1]):
        return 'side', 5
    else:
        return 'middle', 8

def is_happy(player):
    x, y = player_positions[player]
    neighbors = get_neighbors(x, y)
    same_tribe_count = count_same_tribe(player, neighbors)
    ctype, total_neighbors = cell_type(x, y)
    thresholds = {'middle': middle_threshold, 'side': 2, 'corner': 1}
    return same_tribe_count >= thresholds[ctype]

# Broadcast updates to all clients
async def broadcast_state():
    board_state = {"grid": grid, "players": players, "unhappy": get_unhappy_players()}
    for connection in connections:
        await connection.send_json(board_state)

def get_unhappy_players():
    return [player for player in players if not is_happy(player)]

# Routes
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    await websocket.send_json({"grid": grid, "players": players, "unhappy": get_unhappy_players()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.remove(websocket)

@app.post("/move")
async def move_player(player: str = Form(...), target_x: int = Form(...), target_y: int = Form(...)):
    old_x, old_y = player_positions[player]
    grid[old_x][old_y] = EMPTY_CELL
    grid[target_x][target_y] = player
    player_positions[player] = (target_x, target_y)
    await broadcast_state()
    return {"status": "moved"}

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(game_loop())

async def game_loop():
    while True:
        await asyncio.sleep(5)
        await broadcast_state()

@app.post("/reset")
async def reset_game():
    global grid, player_positions
    random.shuffle(cells)
    grid = [[EMPTY_CELL for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    player_positions = {}
    for player, cell in zip(players.keys(), cells[:len(players)]):
        x, y = cell
        grid[x][y] = player
        player_positions[player] = (x, y)
    await broadcast_state()
    return {"status": "reset"}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "players": players})
@app.post("/scenario/{threshold}")
async def change_scenario(threshold: int):
    global middle_threshold
    middle_threshold = threshold
    await broadcast_state()
    return {"status": "scenario changed", "threshold": middle_threshold}


####### Prepare static and templates
import os
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Schelling Game</title>
    <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
    <link rel=\"stylesheet\" type=\"text/css\" href=\"/static/style.css\">
</head>
<body>
    <h1>Schelling Game</h1>

    <div style=\"max-width: 600px; margin: auto; text-align: left; font-size: 14px; padding: 10px; background: #f9f9f9; border: 1px solid #ddd;\">
        <p><strong>Game Instructions:</strong></p>
        <p>Each of you is non-racist. But you do want some people of your type to be around you, for ease of communication, common festivals, and so on.</p>
        <p>You have a threshold of how many people of your type should be neighbours (i.e., people in houses with an edge common with you):</p>
        <ul>
            <li><strong>Scenario 1:</strong> For middle plot residents, you want <strong>2 out of 8</strong> neighbours to be of your type.</li>
            <li><strong>Scenario 2:</strong> For middle plot residents, you want <strong>3 out of 8</strong> neighbours to be of your type.</li>
            <li><strong>Scenario 3:</strong> For middle plot residents, you want <strong>4 out of 8</strong> neighbours to be of your type.</li>
            <li>For side plots, it is <strong>2 out of 5</strong>.</li>
            <li>For corner plots, it is <strong>1 out of 3</strong>.</li>
        </ul>
        <p>If the threshold is not met, you are not happy and you move to an empty location where it is met. If there is more than one feasible location to move to, you follow the following order of preference:</p>
        <ol>
            <li>Corner location</li>
            <li>Side location</li>
            <li>Middle location</li>
        </ol>
        <p>If there is more than one choice within a preference, feel free to use your discretion.</p>
        <p><strong>Note:</strong> Cells with a <strong>red border</strong> represent <strong>unhappy players</strong> who currently do not have enough neighbours of their own type according to the rules above. These players should move to improve their happiness!</p>
    </div>

    <div>
        <label for=\"scenario-select\">Select Scenario:</label>
        <select id=\"scenario-select\" onchange=\"changeScenario()\">
            <option value=\"2\">Scenario 1 (2 out of 8)</option>
            <option value=\"3\">Scenario 2 (3 out of 8)</option>
            <option value=\"4\">Scenario 3 (4 out of 8)</option>
        </select>
    </div>

    <div id=\"game-board\"></div>

    <form id=\"move-form\">
        <label>Player:
            <select name=\"player\" id=\"player-select\">
                {% for player, info in players.items() %}
                    <option value=\"{{ player }}\">{{ player }} ({{ info['tribe'] }})</option>
                {% endfor %}
            </select>
        </label>
        <label>Target X: <input type=\"number\" name=\"target_x\" min=\"0\" max=\"4\" required></label>
        <label>Target Y: <input type=\"number\" name=\"target_y\" min=\"0\" max=\"4\" required></label>
        <button type=\"submit\">Move</button>
    </form>

    <button onclick=\"resetGame()\">Reset Game</button>

    <script src=\"/static/script.js\"></script>
    <script>
        function resetGame() {
            fetch('/reset', { method: 'POST' }).then(() => {
                location.reload();
            });
        }

        function changeScenario() {
            const selectedScenario = document.getElementById('scenario-select').value;
            fetch(`/scenario/${selectedScenario}`, { method: 'POST' }).then(() => {
                location.reload();
            });
        }
    </script>
</body>
</html>""")

with open("static/script.js", "w", encoding="utf-8") as f:
    f.write("""const gameBoard = document.getElementById('game-board');
const moveForm = document.getElementById('move-form');
const playerSelect = document.getElementById('player-select');

const ws = new WebSocket(`ws://${location.host}/ws`);

ws.onopen = function() {
    console.log('WebSocket connection established');
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Message from server', data);
    renderBoard(data.grid, data.players, data.unhappy);
};

function renderBoard(grid, players, unhappy) {
    gameBoard.innerHTML = '';
    grid.forEach((row, x) => {
        row.forEach((cell, y) => {
            const div = document.createElement('div');
            div.className = 'cell';

            if (cell) {
                const tribe = players[cell].tribe;
                div.classList.add(tribe);
                if (unhappy.includes(cell)) {
                    div.classList.add('unhappy');
                }
                div.textContent = cell;
                div.onclick = () => {
                    playerSelect.value = cell;
                };
            } else {
                div.classList.add('empty');
                div.onclick = () => {
                    document.querySelector('input[name=\"target_x\"]').value = x;
                    document.querySelector('input[name=\"target_y\"]').value = y;
                };
            }
            gameBoard.appendChild(div);
        });
    });
}
            
function resetGame() {
    fetch('/reset', { method: 'POST' }).then(() => {
        location.reload();
    });
}

moveForm.onsubmit = async function(event) {
    event.preventDefault();
    const formData = new FormData(moveForm);
    await fetch('/move', {
        method: 'POST',
        body: formData
    });
    moveForm.reset();
};
""")

with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write("""fastapi
uvicorn
jinja2
python-multipart
""")
