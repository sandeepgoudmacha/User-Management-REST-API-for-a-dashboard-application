const mongoose = require('mongoose');

// Define the schema for the nested 'geo' object
const GeoSchema = new mongoose.Schema({
  lat: {
    type: String,
    required: true,
  },
  lng: {
    type: String,
    required: true,
  },
}, { _id: false }); // _id is not needed for this sub-document

// Define the schema for the nested 'address' object
const AddressSchema = new mongoose.Schema({
  city: {
    type: String,
    required: [true, 'City is required'],
  },
  zipcode: {
    type: String,
    required: [true, 'Zipcode is required'],
  },
  geo: {
    type: GeoSchema,
    required: true,
  },
}, { _id: false }); // _id is not needed for this sub-document

// Define the main User schema
const UserSchema = new mongoose.Schema({
  name: {
    type: String,
    required: [true, 'Please add a name'],
    trim: true,
  },
  email: {
    type: String,
    required: [true, 'Please add an email'],
    unique: true,
    match: [
      /^\w+([.-]?\w+)*@\w+([.-]?\w+)*(\.\w{2,3})+$/,
      'Please add a valid email',
    ],
  },
  phone: {
    type: String,
    required: [true, 'Please add a phone number'],
  },
  company: {
    type: String,
    required: [true, 'Please add a company name'],
  },
  address: {
    type: AddressSchema,
    required: true,
  },
}, {
  timestamps: true, // Automatically adds createdAt and updatedAt fields
});

module.exports = mongoose.model('User', UserSchema);
