const mongoose = require('mongoose');

const connectDB = async () => {
  try {
    // Set strict query to false to allow for more flexible queries
    mongoose.set('strictQuery', false);
    
    // Attempt to connect to MongoDB using the URI from environment variables
    const conn = await mongoose.connect(process.env.MONGO_URI, {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    });

    console.log(`MongoDB Connected: ${conn.connection.host}`);
  } catch (error) {
    // Log any errors that occur during connection and exit the process
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
};

module.exports = connectDB;
