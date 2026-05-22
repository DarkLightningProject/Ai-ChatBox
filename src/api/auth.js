import axios from "axios";

const getCsrfToken = () =>
  document.cookie.split("; ")
    .find((row) => row.startsWith("csrftoken="))
    ?.split("=")[1] || "";


const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

export const signup = (data) =>
  axios.post(`${API_BASE}/api/auth/signup/`, data, {
    withCredentials: true,
  });

export const login = (data) =>
  axios.post(`${API_BASE}/api/auth/login/`, data, {
    withCredentials: true,
  });

export const forgotPassword = (data) =>
  axios.post(`${API_BASE}/api/auth/forgot-password/`, data, {
    withCredentials: true,
  });

export const logout = () =>
  axios.post(
    `${API_BASE}/api/auth/logout/`,
    {},
    { withCredentials: true, headers: { "X-CSRFToken": getCsrfToken() } }
  );

export const deleteAccount = () =>
  axios.delete(`${API_BASE}/api/auth/delete-account/`, {
    withCredentials: true,
  });

export const verifyEmail = (uid, token) =>
  axios.get(`${API_BASE}/api/auth/verify-email/${uid}/${token}/`, {
    withCredentials: true,
  });