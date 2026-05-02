import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import NewPage from './pages/NewPage'
import ReviewPage from './pages/ReviewPage'
import PreviewPage from './pages/PreviewPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/new" element={<NewPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/preview" element={<PreviewPage />} />
        <Route path="*" element={<Navigate to="/new" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
