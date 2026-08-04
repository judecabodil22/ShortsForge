import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { ToastProvider } from '@/contexts/ToastContext'
import ToastContainer from '@/components/ui/Toast'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import Graph from '@/pages/Graph'
import Scripts from '@/pages/Scripts'
import Performance from '@/pages/Performance'
import Context from '@/pages/Context'
import Settings from '@/pages/Settings'
import PromptEditor from '@/pages/PromptEditor'
import LearningDashboard from '@/pages/LearningDashboard'
import { pageVariants, pageTransition } from '@/lib/animations'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function AnimatedPage({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      className="h-full w-full overflow-auto p-6"
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={pageTransition}
    >
      {children}
    </motion.div>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <h1 className="text-6xl font-display font-bold text-40k-gold mb-4">404</h1>
      <p className="text-xl text-gray-400 mb-8">Page not found</p>
      <a
        href="/dashboard"
        className="cyber-button-primary px-6 py-3 text-sm font-medium"
      >
        Return to Dashboard
      </a>
    </div>
  )
}

function AppRoutes() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<AnimatedPage><Dashboard /></AnimatedPage>} />
        <Route path="/graph" element={<AnimatedPage><Graph /></AnimatedPage>} />
        <Route path="/scripts" element={<AnimatedPage><Scripts /></AnimatedPage>} />
        <Route path="/metrics" element={<AnimatedPage><Performance /></AnimatedPage>} />
        <Route path="/context" element={<AnimatedPage><Context /></AnimatedPage>} />
        <Route path="/settings" element={<AnimatedPage><Settings /></AnimatedPage>} />
        <Route path="/prompts" element={<AnimatedPage><PromptEditor /></AnimatedPage>} />
        <Route path="/learning" element={<AnimatedPage><LearningDashboard /></AnimatedPage>} />
        <Route path="*" element={<AnimatedPage><NotFound /></AnimatedPage>} />
      </Routes>
    </AnimatePresence>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <ToastProvider>
            <BrowserRouter>
              <Layout>
                <AppRoutes />
              </Layout>
            </BrowserRouter>
            <ToastContainer />
          </ToastProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
