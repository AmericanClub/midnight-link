import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { ThemeProvider } from "@/context/ThemeContext";
import { I18nProvider } from "@/context/I18nContext";
import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

import Landing from "@/pages/Landing";
import Pricing from "@/pages/Pricing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import Overview from "@/pages/Overview";
import LinksPage from "@/pages/LinksPage";
import LinkDetail from "@/pages/LinkDetail";
import QRPage from "@/pages/QRPage";
import ProtectionPage from "@/pages/ProtectionPage";
import BillingPage from "@/pages/BillingPage";
import SettingsPage from "@/pages/SettingsPage";
import NotFound from "@/pages/NotFound";

function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <BrowserRouter>
          <AuthProvider>
            <Toaster richColors position="top-right" />
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/pricing" element={<Pricing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/app" element={<ProtectedRoute><Overview /></ProtectedRoute>} />
              <Route path="/app/links" element={<ProtectedRoute><LinksPage /></ProtectedRoute>} />
              <Route path="/app/links/:id" element={<ProtectedRoute><LinkDetail /></ProtectedRoute>} />
              <Route path="/app/qr" element={<ProtectedRoute><QRPage /></ProtectedRoute>} />
              <Route path="/app/protection" element={<ProtectedRoute><ProtectionPage /></ProtectedRoute>} />
              <Route path="/app/billing" element={<ProtectedRoute><BillingPage /></ProtectedRoute>} />
              <Route path="/app/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </I18nProvider>
    </ThemeProvider>
  );
}

export default App;
