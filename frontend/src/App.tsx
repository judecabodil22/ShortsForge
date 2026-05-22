import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import Graph from '@/pages/Graph'
import Scripts from '@/pages/Scripts'
import Metrics from '@/pages/Metrics'
import Context from '@/pages/Context'
import Settings from '@/pages/Settings'
import Pipeline from '@/pages/Pipeline'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

const pageVariants = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
}

function AnimatedPage({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      className="h-full w-full overflow-auto p-6"
      initial="initial"
      animate="animate"
      variants={pageVariants}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.div>
  )
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<AnimatedPage><Dashboard /></AnimatedPage>} />
      <Route path="/graph" element={<AnimatedPage><Graph /></AnimatedPage>} />
      <Route path="/scripts" element={<AnimatedPage><Scripts /></AnimatedPage>} />
      <Route path="/metrics" element={<AnimatedPage><Metrics /></AnimatedPage>} />
      <Route path="/context" element={<AnimatedPage><Context /></AnimatedPage>} />
      <Route path="/settings" element={<AnimatedPage><Settings /></AnimatedPage>} />
      <Route path="/pipeline" element={<AnimatedPage><Pipeline /></AnimatedPage>} />
    </Routes>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <AppRoutes />
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App