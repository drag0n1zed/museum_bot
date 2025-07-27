// static/js/visualization.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Canvas and Context Setup ---
    const staticCanvas = document.getElementById('static-canvas');
    const dynamicCanvas = document.getElementById('dynamic-canvas');
    if (!staticCanvas || !dynamicCanvas) return;
    
    const staticCtx = staticCanvas.getContext('2d');
    const dynamicCtx = dynamicCanvas.getContext('2d');

    // --- Configuration ---
    const CONFIG = {
        COLORS: {
            gridLine: '#444', open: '#cdd6f4', obstacle: '#6c7086',
            poi: '#74c7ec', poiLabel: '#ffffff', robot: '#a6e3a1',
            robotFov: 'rgba(76, 175, 80, 0.3)', path: '#fab387',
            dynamicObstacle: '#f38ba8',
        },
        PATH: { lineWidth: 5 }, // Thicker path line
    };

    // --- State Management ---
    let mapData = null;      // Holds static grid, POIs, dimensions
    let dynamicState = {     // Holds all moving/changing elements
        position: { x: 0, y: 0 },  // Will be initialized from server
        angle: 90,  // Facing South
        path: [],
        obstacles: []
    };
    let cellSize = 0;

    // --- Main Initialization ---
    async function init() {
        // Show loading message
        staticCtx.font = '16px Arial';
        staticCtx.fillStyle = 'black';
        staticCtx.textAlign = 'center';
        staticCtx.fillText('Loading Map...', staticCanvas.width / 2, staticCanvas.height / 2);

        try {
            // Fetch map data
            const mapResponse = await fetch('/api/map_data');
            mapData = await mapResponse.json();
            
            // Fetch initial robot position
            const positionResponse = await fetch('/api/robot_position');
            const positionData = await positionResponse.json();
            dynamicState.position = positionData.position;
            dynamicState.angle = positionData.angle;
            
            // Setup canvas sizes and listeners
            window.addEventListener('resize', handleResize);
            handleResize(); // Initial size calculation
            
            // Draw the non-moving parts ONCE
            drawStaticLayer();
            
            // Connect to the server for real-time updates
            connectWebSocket();

            // Start the animation loop for moving parts
            requestAnimationFrame(drawDynamicLayer);

        } catch (error) {
            console.error("Failed to initialize map:", error);
            staticCtx.clearRect(0, 0, staticCanvas.width, staticCanvas.height);
            staticCtx.fillText('Error loading map.', staticCanvas.width / 2, staticCanvas.height / 2);
        }
    }

    // --- WebSocket Event Handlers ---
    function connectWebSocket() {
        const socket = io();
        socket.on('connect', () => console.log('WebSocket connected.'));
        socket.on('disconnect', () => console.warn('WebSocket disconnected.'));

        socket.on('update_position', (data) => {
            dynamicState.position = data.position;
            dynamicState.angle = data.angle;
        });

        socket.on('new_path', (data) => {
            dynamicState.path = data.path;
        });

        socket.on('update_obstacles', (data) => {
            dynamicState.obstacles = data.obstacles;
        });
        
        // Listen for errors to show alerts (can be handled in main.js)
        socket.on('navigation_error', (data) => {
             alert(`Navigation Error: ${data.message}`);
        });
    }

    // --- Drawing Logic ---

    // Called ONCE or on resize
    function drawStaticLayer() {
        // Clear the entire canvas
        staticCtx.clearRect(0, 0, staticCanvas.width, staticCanvas.height);
        
        // Fill the background
        staticCtx.fillStyle = CONFIG.COLORS.open;
        staticCtx.fillRect(0, 0, staticCanvas.width, staticCanvas.height);
        
        // Calculate the offset to center the map
        const mapWidth = mapData.width * cellSize;
        const mapHeight = mapData.height * cellSize;
        const offsetX = (staticCanvas.width - mapWidth) / 2;
        const offsetY = (staticCanvas.height - mapHeight) / 2;
        
        // Draw Grid
        for (let y = 0; y < mapData.height; y++) {
            for (let x = 0; x < mapData.width; x++) {
                staticCtx.fillStyle = mapData.grid[y][x] === 1 ? CONFIG.COLORS.obstacle : CONFIG.COLORS.open;
                staticCtx.fillRect(offsetX + x * cellSize, offsetY + y * cellSize, cellSize, cellSize);
                staticCtx.strokeStyle = CONFIG.COLORS.gridLine;
                staticCtx.strokeRect(offsetX + x * cellSize, offsetY + y * cellSize, cellSize, cellSize);
            }
        }

        // Draw POIs
        staticCtx.font = `${Math.max(8, cellSize / 2.5)}px Arial`;
        staticCtx.textAlign = 'center';
        for (const poi of Object.values(mapData.pois)) {
            const x = offsetX + poi.coordinates.x * cellSize + cellSize / 2;
            const y = offsetY + poi.coordinates.y * cellSize + cellSize / 2;
            
            staticCtx.fillStyle = CONFIG.COLORS.poi;
            staticCtx.beginPath();
            staticCtx.arc(x, y, cellSize / 3, 0, 2 * Math.PI);
            staticCtx.fill();

            // Draw POI circle only, without name
            staticCtx.fillStyle = CONFIG.COLORS.poi;
            staticCtx.beginPath();
            staticCtx.arc(x, y, cellSize / 3, 0, 2 * Math.PI);
            staticCtx.fill();
        }
    }
    
    // Called every frame
    function drawDynamicLayer() {
        dynamicCtx.clearRect(0, 0, dynamicCanvas.width, dynamicCanvas.height);

        // Draw Path
        if (dynamicState.path && dynamicState.path.length > 0) {
            drawPath(dynamicState.path);
        }
        
        // Draw Dynamic Obstacles
        if (dynamicState.obstacles && dynamicState.obstacles.length > 0) {
            dynamicCtx.fillStyle = CONFIG.COLORS.dynamicObstacle;
            // Calculate the offset to center the map
            const mapWidth = mapData.width * cellSize;
            const mapHeight = mapData.height * cellSize;
            const offsetX = (dynamicCanvas.width - mapWidth) / 2;
            const offsetY = (dynamicCanvas.height - mapHeight) / 2;
            
            dynamicState.obstacles.forEach(obs => {
                dynamicCtx.fillRect(offsetX + obs[0] * cellSize, offsetY + obs[1] * cellSize, cellSize, cellSize);
            });
        }
        
        // Draw Robot
        drawRobot(dynamicState.position, dynamicState.angle);

        requestAnimationFrame(drawDynamicLayer);
    }
    
    function drawPath(path) {
        // Calculate the offset to center the map
        const mapWidth = mapData.width * cellSize;
        const mapHeight = mapData.height * cellSize;
        const offsetX = (dynamicCanvas.width - mapWidth) / 2;
        const offsetY = (dynamicCanvas.height - mapHeight) / 2;
        
        dynamicCtx.strokeStyle = CONFIG.COLORS.path;
        dynamicCtx.lineWidth = CONFIG.PATH.lineWidth;
        dynamicCtx.lineJoin = 'round';
        dynamicCtx.beginPath();
        path.forEach((node, index) => {
            const x = offsetX + node.x * cellSize + cellSize / 2;
            const y = offsetY + node.y * cellSize + cellSize / 2;
            if (index === 0) dynamicCtx.moveTo(x, y);
            else dynamicCtx.lineTo(x, y);
        });
        dynamicCtx.stroke();
    }
    
    function drawRobot(position, angle) {
        // Calculate the offset to center the map
        const mapWidth = mapData.width * cellSize;
        const mapHeight = mapData.height * cellSize;
        const offsetX = (dynamicCanvas.width - mapWidth) / 2;
        const offsetY = (dynamicCanvas.height - mapHeight) / 2;
        
        const x = offsetX + position.x * cellSize + cellSize / 2;
        const y = offsetY + position.y * cellSize + cellSize / 2;
        const radius = cellSize / 2; // Larger robot radius

        // Robot Body
        dynamicCtx.fillStyle = CONFIG.COLORS.robot;
        dynamicCtx.beginPath();
        dynamicCtx.arc(x, y, radius, 0, 2 * Math.PI);
        dynamicCtx.fill();

        // Direction Indicator
        dynamicCtx.save();
        dynamicCtx.translate(x, y);
        dynamicCtx.rotate((angle + 90) * Math.PI / 180); // Try adding 90 instead
        dynamicCtx.fillStyle = CONFIG.COLORS.open;
        dynamicCtx.beginPath();
        dynamicCtx.moveTo(0, -radius * 0.8);
        dynamicCtx.lineTo(-radius * 0.6, radius * 0.6);
        dynamicCtx.lineTo(radius * 0.6, radius * 0.6);
        dynamicCtx.closePath();
        dynamicCtx.fill();
        dynamicCtx.restore();
    }

    // --- Utility Functions ---
    function handleResize() {
        const container = staticCanvas.parentElement;
        const containerWidth = container.clientWidth;
        
        // Calculate height based on the actual map aspect ratio (width:height = 12:8 = 3:2)
        const containerHeight = (containerWidth * 2) / 3;
        
        staticCanvas.width = containerWidth;
        staticCanvas.height = containerHeight;
        dynamicCanvas.width = containerWidth;
        dynamicCanvas.height = containerHeight;

        if (mapData) {
            // Calculate cell size based on the actual map dimensions
            // We need to fit the map within the canvas dimensions
            const cellWidth = containerWidth / mapData.width;
            const cellHeight = containerHeight / mapData.height;
            cellSize = Math.min(cellWidth, cellHeight);
            drawStaticLayer(); // Redraw static background on resize
        }
    }

    // --- Start ---
    init();
});