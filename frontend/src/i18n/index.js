import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

const resources = {
  es: {
    translation: {
      "nav.home":    "Inicio",
      "nav.flights": "Vuelos",
      "hero.title":  "Vuela con RafaelPabón Airlines",
      "hero.subtitle": "Conectando el mundo con excelencia",
      "search.origin":      "Origen",
      "search.destination": "Destino",
      "search.date":        "Fecha",
      "search.class":       "Clase",
      "search.economy":     "Económica",
      "search.first":       "Primera clase",
      "search.button":      "Mostrar vuelos",
      "booking.title":      "Confirmar reserva",
      "booking.seat_map":   "Seleccionar asiento",
      "booking.passenger":  "Número de pasaporte",
      "booking.confirm":    "Confirmar compra",
      "booking.cancel":     "Cancelar",
      "booking.success":    "¡Reserva confirmada!",
      "booking.tx_id":      "Transaction ID",
      "booking.node":       "Nodo origen",
      "booking.vector_clock": "Vector Clock",
      "booking.selected_seat": "Asiento seleccionado",
      "error.503": "Servicio no disponible: nodo regional caído.",
      "error.generic": "Error inesperado. Intente nuevamente.",
    },
  },
  en: {
    translation: {
      "nav.home":    "Home",
      "nav.flights": "Flights",
      "hero.title":  "Fly with RafaelPabón Airlines",
      "hero.subtitle": "Connecting the world with excellence",
      "search.origin":      "From",
      "search.destination": "To",
      "search.date":        "Date",
      "search.class":       "Class",
      "search.economy":     "Economy",
      "search.first":       "First class",
      "search.button":      "Search flights",
      "booking.title":      "Confirm booking",
      "booking.seat_map":   "Select seat",
      "booking.passenger":  "Passport number",
      "booking.confirm":    "Confirm purchase",
      "booking.cancel":     "Cancel",
      "booking.success":    "Booking confirmed!",
      "booking.tx_id":      "Transaction ID",
      "booking.node":       "Origin node",
      "booking.vector_clock": "Vector Clock",
      "booking.selected_seat": "Selected seat",
      "error.503": "Service unavailable: regional node is down.",
      "error.generic": "Unexpected error. Please try again.",
    },
  },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "es",
    interpolation: { escapeValue: false },
  });

export default i18n;
