import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
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

function AppRoutes() {
  const location = useLocation()
  
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.2 }}
        className="h-full w-full absolute inset-0 overflow-auto p-6"
      >
        <Routes location={location}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/graph" element={<Graph />} />
          <Route path="/scripts" element={<Scripts />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/context" element={<Context />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/pipeline" element={<Pipeline />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
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