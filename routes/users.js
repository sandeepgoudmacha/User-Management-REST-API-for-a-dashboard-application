const express = require('express');
const router = express.Router();
const {
  getUsers,
  getUser,
  createUser,
  updateUser,
  deleteUser,
} = require('../controllers/userController');

// Route for getting all users and creating a new user
router.route('/')
  .get(getUsers)
  .post(createUser);

// Route for getting, updating, and deleting a single user by their ID
router.route('/:id')
  .get(getUser)
  .put(updateUser)
  .delete(deleteUser);

module.exports = router;
