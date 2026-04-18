import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Navbar       from "./components/Navbar";
import RegionBanner from "./components/RegionBanner";
import Home         from "./pages/Home";
import Search       from "./pages/Search";
import Booking      from "./pages/Booking";
import FlightMap    from "./pages/FlightMap";
import PowerBI      from "./pages/PowerBI";
import { getSystemStatus } from "./api";

export default function App() {
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    const refresh = () => getSystemStatus().then(setSystemStatus).catch(() => {});
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-brand-light">
      <Navbar />
      <RegionBanner systemStatus={systemStatus} />
      {/* flex-1 + min-h-0 acota la altura para que FlightMap pueda hacer scroll interno */}
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <Routes>
          {/* Páginas que pueden superar la pantalla → scroll propio */}
          <Route path="/"            element={<div className="flex-1 overflow-y-auto"><Home /></div>} />
          <Route path="/search"      element={<div className="flex-1 overflow-y-auto"><Search /></div>} />
          <Route path="/booking/:id" element={<div className="flex-1 overflow-y-auto"><Booking /></div>} />
          {/* FlightMap y Dashboard ocupan toda la altura disponible sin scroll externo */}
          <Route path="/flightmap"   element={<FlightMap />} />
          <Route path="/dashboard"   element={<PowerBI />} />
        </Routes>
      </div>
    </div>
  );
}
