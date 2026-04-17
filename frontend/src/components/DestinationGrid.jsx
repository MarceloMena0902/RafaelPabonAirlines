/**
 * DestinationGrid.jsx
 * Fotos reales de Unsplash (CDN público, sin API key).
 */
import { useNavigate } from "react-router-dom";

const DESTINATIONS = [
  {
    code: "DXB", city: "Dubái",     country: "EAU",
    photo: "https://images.unsplash.com/photo-1582672060674-bc2bd808a8b5?w=400&h=520&fit=crop&q=80",
    price: "desde $850",
  },
  {
    code: "PAR", city: "París",     country: "Francia",
    photo: "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=400&h=520&fit=crop&q=80",
    price: "desde $620",
  },
  {
    code: "TYO", city: "Tokio",     country: "Japón",
    photo: "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=400&h=520&fit=crop&q=80",
    price: "desde $980",
  },
  {
    code: "LON", city: "Londres",   country: "Reino Unido",
    photo: "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=400&h=520&fit=crop&q=80",
    price: "desde $590",
  },
  {
    code: "SIN", city: "Singapur",  country: "Singapur",
    photo: "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=400&h=520&fit=crop&q=80",
    price: "desde $760",
  },
  {
    code: "SAO", city: "São Paulo", country: "Brasil",
    photo: "https://images.unsplash.com/photo-1543059080-f9b1272213d5?w=400&h=520&fit=crop&q=80",
    price: "desde $410",
  },
  {
    code: "MAD", city: "Madrid",    country: "España",
    photo: "https://images.unsplash.com/photo-1539037116277-4db20889f2d4?w=400&h=520&fit=crop&q=80",
    price: "desde $580",
  },
  {
    code: "PEK", city: "Pekín",     country: "China",
    photo: "https://images.unsplash.com/photo-1508804185872-d7badad00f7d?w=400&h=520&fit=crop&q=80",
    price: "desde $870",
  },
  {
    code: "ATL", city: "Atlanta",   country: "EE.UU.",
    photo: "https://images.unsplash.com/photo-1575917649705-5b59aaa12e6b?w=400&h=520&fit=crop&q=80",
    price: "desde $320",
  },
  {
    code: "IST", city: "Estambul",  country: "Turquía",
    photo: "https://images.unsplash.com/photo-1524231757912-21f4fe3a7200?w=400&h=520&fit=crop&q=80",
    price: "desde $490",
  },
  {
    code: "AMS", city: "Ámsterdam", country: "Países Bajos",
    photo: "https://images.unsplash.com/photo-1534351590666-13e3e96b5017?w=400&h=520&fit=crop&q=80",
    price: "desde $610",
  },
  {
    code: "FRA", city: "Fráncfort", country: "Alemania",
    photo: "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=400&h=520&fit=crop&q=80",
    price: "desde $570",
  },
];

export default function DestinationGrid({ onDestinationSelect }) {
  const navigate = useNavigate();

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900">
          Lugares que creemos le enamorarán
        </h2>
        <p className="text-gray-500 mt-1 text-sm">
          Descubra destinos extraordinarios con RafaelPabón Airlines
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {DESTINATIONS.map((dest) => (
          <button
            key={dest.code}
            onClick={() =>
              onDestinationSelect
                ? onDestinationSelect(dest.code)
                : navigate(`/search?destination=${dest.code}&cabin_class=ECONOMY`)
            }
            className="group relative overflow-hidden rounded-2xl aspect-[3/4] text-left focus:outline-none focus:ring-2 focus:ring-brand-wine"
          >
            {/* Foto real */}
            <img
              src={dest.photo}
              alt={dest.city}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
              loading="lazy"
            />

            {/* Overlay degradado */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />

            {/* Badge IATA */}
            <div className="absolute top-3 right-3 bg-white/20 backdrop-blur-sm text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {dest.code}
            </div>

            {/* Texto inferior */}
            <div className="absolute bottom-0 left-0 right-0 p-4">
              <p className="text-white font-bold text-base leading-tight">{dest.city}</p>
              <p className="text-white/70 text-xs">{dest.country}</p>
              <p className="text-brand-gold font-semibold text-sm mt-1">{dest.price}</p>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
