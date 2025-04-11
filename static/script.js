const gameBoard = document.getElementById('game-board');
const moveForm = document.getElementById('move-form');
const playerSelect = document.getElementById('player-select');

const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
const ws = new WebSocket(`${wsProtocol}://${location.host}/ws`);

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
                    document.querySelector('input[name="target_x"]').value = x;
                    document.querySelector('input[name="target_y"]').value = y;
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
