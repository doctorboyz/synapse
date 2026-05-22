import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './shared/components/Layout'
import { KnowledgeGraphPage } from './features/knowledge-graph/KnowledgeGraphPage'
import { PushPage } from './features/push/PushPage'
import { ChatPage } from './features/chat/ChatPage'
import { CommandsPage } from './features/commands/CommandsPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<KnowledgeGraphPage />} />
          <Route path="/push" element={<PushPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/commands" element={<CommandsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
