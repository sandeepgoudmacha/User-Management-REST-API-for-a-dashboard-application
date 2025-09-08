// Import required packages
const express = require('express');
const dotenv = require('dotenv');
const cors = require('cors');
const connectDB = require('./config/db');

// Load environment variables from .env file
dotenv.config();

// Initialize Express app
const app = express();

// Connect to the database
connectDB();

// --- Middlewares ---

// Enable Cross-Origin Resource Sharing (CORS)
app.use(cors());

// Enable express to parse JSON bodies from HTTP requests
app.use(express.json());

// --- API Routes ---

// Default route
app.get('/', (req, res) => {
  res.send('User Management API is running...');
});

// Mount the user routes
app.use('/api/users', require('./routes/users'));

// --- Server Initialization ---

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => console.log(`Server started on port ${PORT}`));
