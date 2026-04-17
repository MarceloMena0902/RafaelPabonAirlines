import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Navbar       from "./components/Navbar";
import RegionBanner from "./components/RegionBanner";
import Home         from "./pages/Home";
import Search       from "./pages/Search";
import Booking      from "./pages/Booking";
import FlightMap    from "./pages/FlightMap";
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
    <div className="min-h-screen flex flex-col bg-brand-light">
      <Navbar />
      <RegionBanner systemStatus={systemStatus} />
      <div className="flex flex-col flex-1">
        <Routes>
          <Route path="/"            element={<Home />} />
          <Route path="/search"      element={<Search />} />
          <Route path="/booking/:id" element={<Booking />} />
          <Route path="/flightmap"   element={<FlightMap />} />
        </Routes>
      </div>
    </div>
  );
}
