# User Management REST API
This is a simple REST API for a user management dashboard application, built with Node.js, Express, and MongoDB.

## Features
* CRUD operations for users (Create, Read, Update, Delete).

* Structured and modular code.

* Proper error handling and validation.

* RESTful API design.

## Prerequisites
* Node.js (v14 or higher)

* MongoDB (either local or a cloud instance like MongoDB Atlas)

## Setup and Installation
* Clone the repository:
```bash
git clone <your-github-repo-link>
cd user-management-api
```

* Install dependencies:
```bash
npm install
```

* Set up environment variables:
Create a .env file in the root of the project by copying the example file:
```bash
cp .env.example .env
```
Open the .env file and add your MongoDB connection string:
```bash
PORT=5000
MONGO_URI=mongodb://localhost:27017/user-dashboard
```
Replace the MONGO_URI with your actual MongoDB URI.

* Start the server:
To run the server in production mode:
```bash
npm start
```
To run in development mode with automatic restarts (requires nodemon):
```bash
npm run dev
```
The API will be running at http://localhost:5000.

## API Endpoints
The base URL for all endpoints is /api/users.

### 1. Get All Users
* Endpoint: GET /api/users

* Description: Retrieves a list of all users.

* Success Response: 200 OK with a JSON object containing the list of users.

* Example curl request:

```json
curl -X GET http://localhost:5000/api/users
```
Response:
```json
{
    "success": true,
    "data": {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "123-456-7890",
        "company": "Tech Solutions Inc.",
        "address": {
            "city": "Metropolis",
            "zipcode": "12345",
            "geo": {
                "lat": "40.7128",
                "lng": "-74.0060"
            }
        },
        "_id": "68bec716d29ac27e070d41af",
        "createdAt": "2025-09-08T12:07:50.395Z",
        "updatedAt": "2025-09-08T12:07:50.395Z",
        "__v": 0
    }
}
```

### 2. Get a Single User
* Endpoint: GET /api/users/:id

* Description: Retrieves a single user by their unique ID.

* Success Response: 200 OK with the user object.

* Error Response: 404 Not Found if the user ID does not exist.

* Example curl request:
```json
curl -X GET http://localhost:5000/api/users/68bec716d29ac27e070d41af
```
Response:
```json
{
    "success": true,
    "data": {
        "_id": "68bec716d29ac27e070d41af",
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "123-456-7890",
        "company": "Tech Solutions Inc.",
        "address": {
            "city": "Metropolis",
            "zipcode": "12345",
            "geo": {
                "lat": "40.7128",
                "lng": "-74.0060"
            }
        },
        "createdAt": "2025-09-08T12:07:50.395Z",
        "updatedAt": "2025-09-08T12:07:50.395Z",
        "__v": 0
    }
}
```
### 3. Create a New User
* Endpoint: POST /api/users

* Description: Creates a new user. The request body must be a JSON object with the user's details.

* Success Response: 201 Created with the newly created user object.

* Error Response: 400 Bad Request if the request body is invalid or validation fails.

* Example curl request:
```json
curl -X POST http://localhost:5000/api/users \
-H "Content-Type: application/json" \
-d '{
  "name": "Arjun",
  "email": "Arjun.doe@example.com",
  "phone": "123-456-7890",
  "company": "ABD Solutions Inc.",
  "address": {
    "city": "Hyderabad",
    "zipcode": "50000",
    "geo": {
      "lat": "60.7128",
      "lng": "-70.0060"
    }
  }
}'
```
Response:
```json
{
    "success": true,
    "data": {
        "name": "Arjun",
        "email": "Arjun.doe@example.com",
        "phone": "123-456-7890",
        "company": "ABD Solutions Inc.",
        "address": {
            "city": "Hyderabad",
            "zipcode": "50000",
            "geo": {
                "lat": "60.7128",
                "lng": "-70.0060"
            }
        },
        "_id": "68beca64d29ac27e070d41b4",
        "createdAt": "2025-09-08T12:21:56.171Z",
        "updatedAt": "2025-09-08T12:21:56.171Z",
        "__v": 0
    }
}
```
### 4. Update a User
* Endpoint: PUT /api/users/:id

* Description: Updates an existing user's details by their ID.

* Success Response: 200 OK with the updated user object.

* Error Response: 404 Not Found if the user ID does not exist. 400 Bad Request for validation errors.

* Example curl request:
```json
curl -X PUT http://localhost:5000/api/users/68beca64d29ac27e070d41b4 \
-H "Content-Type: application/json" \
-d '{
  "name": "Johnathan Doe",
  "phone": "987-654-3210"
}'
```
Response:
```json
{
    "success": true,
    "data": {
        "_id": "68beca64d29ac27e070d41b4",
        "name": "Johnathan Doe",
        "email": "Arjun.doe@example.com",
        "phone": "987-654-3210",
        "company": "ABD Solutions Inc.",
        "address": {
            "city": "Hyderabad",
            "zipcode": "50000",
            "geo": {
                "lat": "60.7128",
                "lng": "-70.0060"
            }
        },
        "createdAt": "2025-09-08T12:21:56.171Z",
        "updatedAt": "2025-09-08T12:23:00.281Z",
        "__v": 0
    }
}
```
### 5. Delete a User
* Endpoint: DELETE /api/users/:id

* Description: Deletes a user by their ID.

* Success Response: 200 OK with an empty data object.

* Error Response: 404 Not Found if the user ID does not exist.

* Example curl request:
```json
curl -X DELETE http://localhost:5000/api/users/68beca64d29ac27e070d41b4
```
Response:
```json
{
    "success": true,
    "data": {}
}
```