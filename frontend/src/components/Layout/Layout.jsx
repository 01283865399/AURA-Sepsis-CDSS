import { motion } from 'framer-motion';
import { Outlet, useLocation } from 'react-router-dom';
import Footer from './Footer';
import Navbar from './Navbar';
import Sidebar from './Sidebar';
import SplineBackdrop from './SplineBackdrop';

export default function Layout() {
  const location = useLocation();
  return (
    <div className="app-shell">
      <SplineBackdrop />
      <Sidebar />
      <div className="workspace-column">
        <Navbar />
        <motion.main key={location.pathname} className="page-content" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}>
          <Outlet />
        </motion.main>
        <Footer />
      </div>
    </div>
  );
}
