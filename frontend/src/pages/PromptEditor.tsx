import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { getScriptPrompt, saveScriptPrompt } from '@/lib/api'
import { stagger } from '@/lib/animations'

export default function PromptEditor() {
  const queryClient = useQueryClient()
  const [content, setContent] = useState('')
  const [isDirty, setIsDirty] = useState(false)
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const { isLoading, isError } = useQuery({
    queryKey: ['script-prompt'],
    queryFn: async () => {
      const res = await getScriptPrompt()
      setContent(res.content)
      return res
    },
  })

  const saveMutation = useMutation({
    mutationFn: (text: string) => saveScriptPrompt(text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['script-prompt'] })
      setIsDirty(false)
      setStatusMsg({ type: 'success', text: 'Prompt saved successfully' })
      setTimeout(() => setStatusMsg(null), 3000)
    },
    onError: (error: Error) => {
      setStatusMsg({ type: 'error', text: `Failed to save: ${error.message}` })
    },
  })

  const handleSave = () => {
    if (!content.trim()) return
    saveMutation.mutate(content)
  }

  // Cmd+S / Ctrl+S keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (isDirty && content.trim()) {
          handleSave()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isDirty, content])

  // Warn before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault()
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isDirty])

  const lineCount = content.split('\n').length
  const charCount = content.length

  return (
    <motion.div variants={stagger.container} initial="hidden" animate="show" className="space-y-6">
      <PageHeader
        accentWord="PROMPT"
        title="PROMPT EDITOR"
        subtitle="Edit the script generation template (prompts/base.j2)"
        actions={
          <div className="flex items-center gap-3">

          <span className="text-xs text-gray-500">
            {lineCount} lines &middot; {charCount} chars
          </span>

          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`cyber-button flex items-center gap-2 ${
              isDirty ? 'border-40k-gold text-40k-gold pulse-glow' : 'text-stone-500 border-40k-border'
            }`}
            disabled={!isDirty || saveMutation.isPending}
            onClick={handleSave}
          >
            {saveMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Save
          </motion.button>
          </div>
        }
      />

      {statusMsg && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm ${
            statusMsg.type === 'success'
              ? 'bg-40k-gold/10 text-40k-gold-bright border border-40k-gold/40'
              : 'bg-40k-crimson/20 text-40k-crimson-bright border border-40k-crimson-bright/50'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4" />
          ) : (
            <AlertCircle className="w-4 h-4" />
          )}
          {statusMsg.text}
        </motion.div>
      )}

      <Card notch accent>
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-40k-gold" />
          </div>
        ) : isError ? (
          <div className="flex items-center justify-center py-20 text-red-400">
            <AlertCircle className="w-6 h-6 mr-2" />
            Failed to load prompt template
          </div>
        ) : (
          <textarea
            value={content}
            onChange={(e) => {
              setContent(e.target.value)
              setIsDirty(true)
              setStatusMsg(null)
            }}
            className="w-full h-[65vh] bg-40k-black/80 border border-40k-border corner-notch p-4 text-sm font-mono text-stone-200 resize-none focus:outline-none focus:border-40k-gold/50 focus:shadow-[var(--40k-shadow-gold)] transition-colors block-cursor"
            spellCheck={false}
          />
        )}
      </Card>
    </motion.div>
  )
}
