// src/api.js
import axios from "axios";

const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE || "http://localhost:8000",
  withCredentials: true, // 🔥 REQUIRED
});

export default api;
