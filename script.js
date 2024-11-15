document.addEventListener('DOMContentLoaded', () => {
    const BOARD_WIDTH = 100;  // Define the board width
    const BOARD_HEIGHT = 100;  // Define the board height

    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');
    const loginDiv = document.getElementById('login');
    const registerDiv = document.getElementById('register');
    const boardContainer = document.getElementById('board-container');
    const boardElement = document.getElementById('board');
    const statusElement = document.querySelector('.status');
    const colorPicker = document.getElementById('color-picker');
    let selectedColor = colorPicker.value;
    let token = '';
    let username = '';
    let userId = Math.random().toString(36).substring(7);  // Generate a random user ID for cooldown tracking


    const howToPlayButton = document.getElementById("how-to-play-button");
    const howToPlayModal = document.getElementById("how-to-play-modal");
    const closeHowToPlayButton = document.querySelector(".close-how-to-play-button");


    // Show the "How to Play" modal on first reload
    if (!localStorage.getItem('howToPlaySeen')) {
        howToPlayModal.style.display = "block";
        localStorage.setItem('howToPlaySeen', 'true');
    }

    howToPlayButton.addEventListener("click", function() {
        howToPlayModal.style.display = "block";
    });

    closeHowToPlayButton.addEventListener("click", function() {
        howToPlayModal.style.display = "none";
    });

    window.addEventListener("click", function(event) {
        if (event.target == howToPlayModal) {
            howToPlayModal.style.display = "none";
        }
    });

    // Cursor effect
    const customCursor = document.getElementById('custom-cursor');

    document.addEventListener('mousemove', (e) => {
        customCursor.style.left = `${e.pageX}px`;
        customCursor.style.top = `${e.pageY}px`;

        // Change the glow effect based on cursor position
        const red = Math.round((e.pageX / window.innerWidth) * 255);
        const green = Math.round((e.pageY / window.innerHeight) * 255);
        const blue = 255 - red;
        customCursor.style.boxShadow = `0 0 10px rgba(${red}, ${green}, ${blue}, 0.5)`;
        customCursor.style.backgroundColor = `rgb(${red}, ${green}, ${blue})`;
    });
    

    //info button
    const infoButton = document.getElementById("info-button");
    const infoModal = document.getElementById("info-modal");
    const closeButton = document.querySelector(".close-button");

    infoButton.addEventListener("click", function() {
        console.log("info button clicked");
        infoModal.style.display = "block";
    });

    closeButton.addEventListener("click", function() {
        infoModal.style.display = "none";
    });

    window.addEventListener("click", function(event) {
        if (event.target == infoModal) {
            infoModal.style.display = "none";
        }
    });

    // Show registration form
    showRegisterLink.addEventListener('click', (event) => {
        event.preventDefault();
        loginDiv.style.display = 'none';
        registerDiv.style.display = 'block';
    });

    // Show login form
    showLoginLink.addEventListener('click', (event) => {
        event.preventDefault();
        registerDiv.style.display = 'none';
        loginDiv.style.display = 'block';
    });

    // Handle login form submission
    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const usernameInput = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        const response = await fetch('http://localhost:8000/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                'username': usernameInput,
                'password': password,
            }),
        });

        const data = await response.json();
        if (response.ok) {
            token = data.access_token;
            username = usernameInput;  // Set the username
            loginDiv.style.display = 'none';
            boardContainer.style.display = 'block';
            initializeBoard();
        } else {
            alert('Login failed: ' + data.detail);
        }
    });

    // Handle registration form submission
    registerForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const username = document.getElementById('reg-username').value;
        const password = document.getElementById('reg-password').value;

        const response = await fetch('http://localhost:8000/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                'username': username,
                'password': password,
            }),
        });

        const data = await response.json();
        if (response.ok) {
            alert('Registration successful! Please log in.');
            registerDiv.style.display = 'none';
            loginDiv.style.display = 'block';
        } else {
            alert('Registration failed: ' + data.detail);
        }
    });

    // WebSocket connection to backend
    const socket = new WebSocket('ws://localhost:8000/ws');

    socket.onopen = () => {
        console.log('Connected to WebSocket');
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const pixelElement = document.querySelector(`[data-x="${data.x}"][data-y="${data.y}"]`);
        if (pixelElement) {
            pixelElement.style.backgroundColor = data.color;
        }
    };

    // Load the board from the backend
    function initializeBoard() {
        fetch('http://localhost:8000/board', {
            headers: {
                'Authorization': `Bearer ${token}`,
            },
        })
        .then(response => response.json())
        .then(data => {
            const board = data.board;
            boardElement.style.gridTemplateColumns = `repeat(${BOARD_WIDTH}, 1fr)`;
            boardElement.style.gridTemplateRows = `repeat(${BOARD_HEIGHT}, 1fr)`;
            Object.entries(board).forEach(([position, color]) => {
                const [x, y] = position.split(',').map(Number);
                const pixel = document.createElement('div');
                pixel.classList.add('pixel');
                pixel.dataset.x = x;
                pixel.dataset.y = y;
                pixel.style.backgroundColor = color;
                pixel.addEventListener('click', () => updatePixel(x, y));
                boardElement.appendChild(pixel);
            });
        });
    }

    // Handle color picker change
    colorPicker.addEventListener('input', (event) => {
        selectedColor = event.target.value;
        statusElement.textContent = `Selected color: ${selectedColor}`;
    });

    function updatePixel(x, y) {
        // Ensure coordinates are within valid range
        if (x < 0 || x >= BOARD_WIDTH || y < 0 || y >= BOARD_HEIGHT) {
            console.error(`Invalid coordinates: x=${x}, y=${y}`);
            alert(`Invalid coordinates: x=${x}, y=${y}`);
            return;
        }

        const payload = { x, y, color: selectedColor, user_id: userId, username: username };
        console.log('Sending payload:', payload);

        fetch('http://localhost:8000/update_pixel', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
        })
        .then(response => {
            if (response.status === 400) {
                return response.json().then(data => {
                    alert('Bad Request: ' + data.detail);
                });
            } else if (response.status === 429) {
                return response.json().then(data => {
                    alert(data.detail);
                });
            } else if (response.ok) {
                statusElement.textContent = `Pixel at (${x}, ${y}) updated to ${selectedColor}`;
                const pixelElement = document.querySelector(`[data-x="${x}"][data-y="${y}"]`);
                if (pixelElement) {
                    pixelElement.style.backgroundColor = selectedColor;
                }
            }
        })
        .catch(error => {
            console.error('Error updating pixel:', error);
        });
    }
});