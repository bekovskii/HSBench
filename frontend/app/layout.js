import "./globals.css";

export const metadata = {
  title: "TarifeLab — GTİP doğrulama",
  description: "Sınır ötesi e-ticaret için açıklanabilir HS/GTİP önizleme prototipi.",
};

export default function RootLayout({ children }) {
  return <html lang="tr"><body>{children}</body></html>;
}

