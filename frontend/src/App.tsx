import { useState } from "react"
import { Sidebar } from "./components/layout/Sidebar"
import { ChatPage } from "./pages/chat/ChatPage"
import { ImagePage } from "./pages/image/ImagePage"
import { CompanionPage } from "./pages/companion/CompanionPage"
import { PlaceholderPage } from "./pages/PlaceholderPage"
import type { Page } from "./types"

export default function App() {
  const [page, setPage] = useState<Page>("chat")

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg)" }}>
      <Sidebar active={page} onChange={setPage} />
      <main className="flex-1 overflow-hidden">
        {page === "chat"      && <ChatPage />}
        {page === "companion" && <CompanionPage />}
        {page === "image"     && <ImagePage />}
        {page === "video"     && <PlaceholderPage title="video" />}
        {page === "settings"  && <PlaceholderPage title="settings" />}
      </main>
    </div>
  )
}
