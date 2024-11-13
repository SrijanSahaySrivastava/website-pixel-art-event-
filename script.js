const boardElement = document.getElementById("board");
const statusElement = document.querySelector(".status");
let selectedColor = "red";
let userId = Math.random().toString(36).substring(7);  // Generate a random user ID for cooldown tracking

// WebSocket connection to backend
const socket = new WebSocket("ws://localhost:8000/ws");

socket.onopen = () => {
    console.log("Connected to WebSocket");
};

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    const pixelElement = document.querySelector(`[data-x="${data.x}"][data-y="${data.y}"]`);
    if (pixelElement) {
        pixelElement.style.backgroundColor = data.color;
    }
};

// Load the board from the backend
fetch("http://localhost:8000/board")
    .then(response => response.json())
    .then(data => {
        const board = data.board;
        Object.entries(board).forEach(([position, color]) => {
            const [x, y] = position.split(",").map(Number);
            const pixel = document.createElement("div");
            pixel.classList.add("pixel");
            pixel.dataset.x = x;
            pixel.dataset.y = y;
            pixel.style.backgroundColor = color;
            pixel.addEventListener("click", () => updatePixel(x, y));
            boardElement.appendChild(pixel);
        });
    });

// Set up color picker
document.querySelectorAll(".color").forEach(colorElement => {
    colorElement.addEventListener("click", () => {
        selectedColor = colorElement.getAttribute("data-color");
        statusElement.textContent = `Selected color: ${selectedColor}`;
    });
});

function updatePixel(x, y) {
    fetch("http://localhost:8000/update_pixel", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ x, y, color: selectedColor, user_id: userId })
    })
    .then(response => {
        if (response.status === 429) {
            return response.json().then(data => {
                alert(data.detail);
            });
        } else if (response.ok) {
            statusElement.textContent = `Pixel at (${x}, ${y}) updated to ${selectedColor}`;
        }
    })
    .catch(error => {
        console.error("Error updating pixel:", error);
    });
}
