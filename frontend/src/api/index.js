import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:8000" });

export const getFlights       = (params) => api.get("/flights", { params }).then(r => r.data);
export const getFlightById    = (id)     => api.get(`/flights/${id}`).then(r => r.data);
export const getSystemStatus  = ()       => api.get("/nodes/status").then(r => r.data);
export const getNodeMap       = ()       => api.get("/nodes/map").then(r => r.data);
export const getNearestNode   = (city)   => api.get("/nodes/nearest", { params: { city } }).then(r => r.data);
export const searchCities     = (q, limit = 10) => api.get("/nodes/cities/search", { params: { q, limit } }).then(r => r.data);
export const getLiveFlights   = ()       => api.get("/flights/live").then(r => r.data);
export const createReservation = (data)  => api.post("/reservations/", data).then(r => r.data);
export const cancelReservation = (data)  => api.delete("/reservations/", { data }).then(r => r.data);
export const getReservationsForFlight = (id) => api.get(`/reservations/flight/${id}`).then(r => r.data);
export const getSeatsForFlight        = (id) => api.get(`/reservations/flight/${id}/seats`).then(r => r.data);
export const getPassenger     = (passport) => api.get(`/passengers/${passport}`).then(r => r.data);

export default api;
