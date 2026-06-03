import "./globals.css";
import type { ReactNode } from "react";
import Sidebar from "./components/Sidebar";
import AuthProvider from "./components/AuthProvider";
import Header from "./components/Header";

export const metadata = {
  title: "Recruit IQ",
  description: "Intelligence Pipeline"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        <AuthProvider>
          <div className="app-container">
            <Sidebar />

            <main className="main-content">
              <Header />
              
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
