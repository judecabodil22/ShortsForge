import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Trash2, Palette, Settings as SettingsIcon, Cpu, Wrench, Subtitles, Shuffle, Mic, Gauge } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { useTheme, themes } from '@/contexts/ThemeContext'
import { useToast } from '@/contexts/ToastContext'
import { getConfig, updateConfig, cleanupFiles, getGames } from '@/lib/api'
import { stagger, slideLeft, springGentle } from '@/lib/animations'

type TabId = 'general' | 'subtitles' | 'variety' | 'system' | 'voice'

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: 'general',   label: 'General',   icon: <SettingsIcon className="w-4 h-4" /> },
  { id: 'subtitles', label: 'Subtitles', icon: <Subtitles className="w-4 h-4" /> },
  { id: 'variety',   label: 'Variety',   icon: <Shuffle className="w-4 h-4" /> },
  { id: 'voice',     label: 'Voice',     icon: <Mic className="w-4 h-4" /> },
  { id: 'system',    label: 'System',    icon: <Wrench className="w-4 h-4" /> },
]

export default function Settings() {
  const queryClient = useQueryClient()
  const { theme, setTheme } = useTheme()
  const { toast } = useToast()
  const [formData, setFormData] = useState({
    GAME_TITLE: '',
    TTS_VOICE: '',
    CLIPS_PER_HOUR: '4',
    PARENT_FRANCHISE: '',
    SRT_MAX_WORDS: '5',
    SRT_FONT_SIZE: '22',
    SRT_FONT_COLOR: '',
    SRT_MARGIN_V: '60',
    SRT_FONT_NAME: 'Open Sans',
    SRT_FONT_OUTLINE: '2',
    SRT_FONT_SHADOW: '1',
    SRT_OUTLINE_COLOR: '',
    SRT_SUB_GAP: '0.5',
    SRT_MIN_DURATION: '1.0',
    SRT_MAX_DURATION: '6.0',
    SRT_BORDER_STYLE: 'outline',
    SRT_ALIGNMENT: 'center',
    CLIP_ORDER: 'sequential',
    VARIETY_SEED: '42',
    TTS_EMOTION: 'default',
    TTS_SPEED: '1.0',
  })

  const [isFranchise, setIsFranchise] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('general')

  const { data: gamesData } = useQuery({
    queryKey: ['games'],
    queryFn: getGames,
  })

  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })

  useEffect(() => {
    if (config) {
      const clean = (v: string) => v.replace(/[^0-9a-fA-F]/g, '');
      setFormData({
        GAME_TITLE: config.GAME_TITLE || '',
        TTS_VOICE: config.TTS_VOICE || '',
        CLIPS_PER_HOUR: config.CLIPS_PER_HOUR || '4',
        PARENT_FRANCHISE: config.PARENT_FRANCHISE || '',
        SRT_MAX_WORDS: config.SRT_MAX_WORDS || '5',
        SRT_FONT_SIZE: config.SRT_FONT_SIZE || '22',
        SRT_FONT_COLOR: clean(config.SRT_FONT_COLOR || ''),
        SRT_MARGIN_V: config.SRT_MARGIN_V || '60',
        SRT_FONT_NAME: config.SRT_FONT_NAME || 'Open Sans',
        SRT_FONT_OUTLINE: config.SRT_FONT_OUTLINE || '2',
        SRT_FONT_SHADOW: config.SRT_FONT_SHADOW || '1',
        SRT_OUTLINE_COLOR: clean(config.SRT_OUTLINE_COLOR || ''),
        SRT_SUB_GAP: config.SRT_SUB_GAP || '0.5',
        SRT_MIN_DURATION: config.SRT_MIN_DURATION || '1.0',
        SRT_MAX_DURATION: config.SRT_MAX_DURATION || '6.0',
        SRT_BORDER_STYLE: config.SRT_BORDER_STYLE || 'outline',
        SRT_ALIGNMENT: config.SRT_ALIGNMENT || 'center',
        CLIP_ORDER: config.CLIP_ORDER || 'sequential',
        VARIETY_SEED: config.VARIETY_SEED || '42',
        TTS_EMOTION: config.TTS_EMOTION || 'default',
        TTS_SPEED: config.TTS_SPEED || '1.0',
      })
      if (config.PARENT_FRANCHISE) setIsFranchise(true)
    }
  }, [config])

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => updateConfig(data),
    onSuccess: (data: any) => {
      if (data?.status === 'error') {
        toast('error', `Validation errors: ${data.errors?.join(', ')}`)
        return
      }
      queryClient.invalidateQueries({ queryKey: ['config'] })
      toast('success', 'Configuration saved successfully!')
    },
    onError: (error: any) => {
      if (error?.response?.data?.errors) {
        toast('error', `Validation errors: ${error.response.data.errors.join(', ')}`)
      } else {
        toast('error', `Failed to save config: ${error.message}`)
      }
    }
  })

  const cleanupMutation = useMutation({
    mutationFn: cleanupFiles,
    onSuccess: () => toast('success', 'Generated files cleaned up successfully!'),
    onError: (error: Error) => toast('error', `Failed to cleanup files: ${error.message}`)
  })

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    const finalData = { ...formData }
    if (!isFranchise) finalData.PARENT_FRANCHISE = ''
    saveMutation.mutate(finalData)
  }

  return (
    <motion.div variants={stagger.container} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={slideLeft} className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-40k-gold">SYSTEM</span> SETTINGS
          </h1>
          <p className="text-gray-400 mt-1">Configure Cogitator core parameters</p>
        </div>
      </motion.div>

      {/* Tab Navigation */}
      <div className="flex gap-1 bg-40k-card border border-40k-border p-1 rounded-lg">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
              activeTab === tab.id
                ? 'bg-40k-gold/15 text-40k-gold border border-40k-gold/30'
                : 'text-stone-400 hover:text-stone-200 hover:bg-40k-dark/50'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6">
        {isLoading ? (
          <Card>
            <motion.div className="space-y-3" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {[1, 2, 3, 4].map((i) => (
                <motion.div key={i} className="h-10 bg-40k-dark rounded animate-pulse" style={{ animationDelay: `${i * 0.1}s` }} />
              ))}
            </motion.div>
          </Card>
        ) : (
          <form onSubmit={handleSave}>
            {/* ──────── GENERAL TAB ──────── */}
            {activeTab === 'general' && (
              <Card accent="gold" notch className="space-y-4">
                <SectionHeader title="Target Game" subtitle="Primary game title for context extraction" icon={<SettingsIcon className="w-4 h-4" />} terminal />

                <div>
                  <label className="terminal-label mb-1 block">Target Game Title</label>
                  <input
                    type="text"
                    value={formData.GAME_TITLE}
                    onChange={e => setFormData({ ...formData, GAME_TITLE: e.target.value })}
                    className="cyber-input"
                    placeholder="e.g. Cyberpunk 2077"
                  />
                </div>

                <motion.label className="flex items-center gap-2 cursor-pointer pt-2" whileHover={{ scale: 1.01 }}>
                  <input
                    type="checkbox"
                    checked={isFranchise}
                    onChange={(e) => setIsFranchise(e.target.checked)}
                    className="form-checkbox h-4 w-4 text-40k-gold bg-40k-dark border-40k-border rounded"
                  />
                  <span className="text-sm text-stone-300">Part of a Franchise/Series?</span>
                </motion.label>

                {isFranchise && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={springGentle}>
                    <label className="terminal-label mb-1 block">Parent Franchise Context</label>
                    <select
                      value={formData.PARENT_FRANCHISE}
                      onChange={e => setFormData({ ...formData, PARENT_FRANCHISE: e.target.value })}
                      className="cyber-input"
                    >
                      <option value="">Select a Franchise Context...</option>
                      {(gamesData?.games || []).filter((game: any) => game.is_series).map((game: any) => (
                        <option key={game.name} value={game.name}>{game.display_name || game.name}</option>
                      ))}
                    </select>
                    <p className="text-[10px] text-stone-500 mt-1">This game will read from and write to the Franchise context.</p>
                  </motion.div>
                )}

                <div className="pt-2">
                  <label className="terminal-label mb-1 block">TTS Voice Model</label>
                  <select
                    value={formData.TTS_VOICE}
                    onChange={e => setFormData({ ...formData, TTS_VOICE: e.target.value })}
                    className="cyber-input"
                  >
                    <option value="">Let system handle (learning-weighted round-robin)</option>
                    {["Vindemiatrix", "Puck", "Aoede", "Charon", "Kore", "Fenrir", "Orus", "Enceladus", "Iapetus", "Nereus", "Zephyr", "Atlas", "Callirhoe", "Ceres"].map(voice => (
                      <option key={voice} value={voice}>{voice}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="terminal-label mb-1 block">Target Clips Per Hour</label>
                  <input
                    type="text"
                    value={formData.CLIPS_PER_HOUR}
                    onChange={e => setFormData({ ...formData, CLIPS_PER_HOUR: e.target.value })}
                    className="cyber-input"
                    placeholder="e.g. 1"
                  />
                </div>
              </Card>
            )}

            {/* ──────── SUBTITLES TAB ──────── */}
            {activeTab === 'subtitles' && (
              <Card accent="gold" notch>
                <SectionHeader title="Subtitle Preview" icon={<Subtitles className="w-4 h-4" />} terminal className="mb-3" />
                {(() => {
                  const fc = formData.SRT_FONT_COLOR || 'FFFFFF';
                  const oc = formData.SRT_OUTLINE_COLOR || '000000';
                  const ow = parseInt(formData.SRT_FONT_OUTLINE) || 2;
                  const sd = parseInt(formData.SRT_FONT_SHADOW) || 1;
                  const fs = parseInt(formData.SRT_FONT_SIZE) || 22;
                  const shadowX = Math.round(sd * 1.5);
                  const shadowY = Math.round(sd * 1.5);
                  const shadowBlur = Math.max(sd, 1);
                  return (
                    <div className="bg-black/70 rounded overflow-hidden border border-40k-border/50 mb-4" style={{ minHeight: 100 }}>
                      <div className="flex items-center justify-center h-full py-6 px-4">
                        <span
                          style={{
                            fontFamily: formData.SRT_FONT_NAME || 'Open Sans',
                            fontSize: `${Math.min(fs * 1.5, 48)}px`,
                            color: `#${fc}`,
                            WebkitTextStroke: ow > 0 ? `${ow}px #${oc}` : undefined,
                            textShadow: sd > 0 ? `${shadowX}px ${shadowY}px ${shadowBlur}px rgba(0,0,0,0.8)` : undefined,
                            paintOrder: 'stroke fill',
                            textAlign: 'center',
                            lineHeight: 1.3,
                          }}
                        >
                          The Cogitator processes sacred data
                        </span>
                      </div>
                    </div>
                  );
                })()}

                <SectionHeader title="Timing" terminal className="mb-3" />
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {[
                    { key: 'SRT_SUB_GAP', label: 'Gap (s)', placeholder: '0.5', min: 0.1, max: 5, step: 0.1, hint: 'Pause between subtitle chunks.' },
                    { key: 'SRT_MIN_DURATION', label: 'Min (s)', placeholder: '1.0', min: 0.5, max: 10, step: 0.1, hint: 'Minimum subtitle on-screen time.' },
                    { key: 'SRT_MAX_DURATION', label: 'Max (s)', placeholder: '6.0', min: 1, max: 30, step: 0.5, hint: 'Prevents very long chunks.' },
                  ].map(({ key, label, placeholder, min, max, step, hint }) => (
                    <div key={key}>
                      <label className="terminal-label mb-1 block">{label}</label>
                      <input type="number" min={min} max={max} step={step} value={(formData as any)[key]}
                        onChange={e => setFormData({ ...formData, [key]: e.target.value })} className="cyber-input" placeholder={placeholder} />
                      <p className="text-[10px] text-stone-500 mt-1">{hint}</p>
                    </div>
                  ))}
                </div>

                <SectionHeader title="Styling" terminal className="mb-3" />
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                  {[
                    { key: 'SRT_MAX_WORDS', label: 'Words/Subtitle', placeholder: '5', min: 1, max: 20, hint: 'Words per subtitle line.' },
                    { key: 'SRT_FONT_SIZE', label: 'Font Size', placeholder: '22', min: 8, max: 48 },
                    { key: 'SRT_FONT_OUTLINE', label: 'Outline Width', placeholder: '2', min: 0, max: 8, hint: 'Black border around text.' },
                    { key: 'SRT_FONT_SHADOW', label: 'Shadow Depth', placeholder: '1', min: 0, max: 5, hint: 'Drop shadow below text.' },
                    { key: 'SRT_MARGIN_V', label: 'Vertical Margin', placeholder: '60', min: 10, max: 200 },
                    { key: 'SRT_FONT_NAME', label: 'Font Family', placeholder: 'Open Sans' },
                  ].map(({ key, label, placeholder, min, max, hint }) => (
                    <div key={key}>
                      <label className="terminal-label mb-1 block">{label}</label>
                      <input type={min !== undefined ? 'number' : 'text'} min={min} max={max}
                        value={(formData as any)[key]} onChange={e => setFormData({ ...formData, [key]: e.target.value })}
                        className="cyber-input" placeholder={placeholder} />
                      {hint && <p className="text-[10px] text-stone-500 mt-1">{hint}</p>}
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-2 gap-3 mb-4">
                  {[
                    { key: 'SRT_FONT_COLOR', label: 'Font Color (hex)', placeholder: 'FFFFFF', maxLength: 6, mono: true },
                    { key: 'SRT_OUTLINE_COLOR', label: 'Outline Color (hex)', placeholder: '000000', maxLength: 6, mono: true },
                  ].map(({ key, label, placeholder, maxLength, mono }) => (
                    <div key={key}>
                      <label className="terminal-label mb-1 block">{label}</label>
                      <input type="text" maxLength={maxLength}
                        value={(formData as any)[key]}
                        onChange={e => {
                          let val = e.target.value.replace(/[^0-9a-fA-F]/g, '');
                          setFormData({ ...formData, [key]: val });
                        }}
                        className={`cyber-input ${mono ? 'font-mono' : ''}`} placeholder={placeholder} />
                    </div>
                  ))}
                </div>

                <SectionHeader title="Border & Alignment" terminal className="mb-3" />
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="terminal-label mb-1 block">Border Style</label>
                    <select value={formData.SRT_BORDER_STYLE} onChange={e => setFormData({ ...formData, SRT_BORDER_STYLE: e.target.value })} className="cyber-input">
                      <option value="outline">Outline</option>
                      <option value="glow">Glow</option>
                      <option value="box">Box</option>
                    </select>
                    <p className="text-[10px] text-stone-500 mt-1">Glow uses outline color; Box has opaque background.</p>
                  </div>
                  <div>
                    <label className="terminal-label mb-1 block">Alignment</label>
                    <select value={formData.SRT_ALIGNMENT} onChange={e => setFormData({ ...formData, SRT_ALIGNMENT: e.target.value })} className="cyber-input">
                      <option value="center">Center</option>
                      <option value="bottom-left">Bottom Left</option>
                      <option value="bottom-right">Bottom Right</option>
                      <option value="top-left">Top Left</option>
                      <option value="top-right">Top Right</option>
                    </select>
                    <p className="text-[10px] text-stone-500 mt-1">Position of subtitles on screen.</p>
                  </div>
                </div>
              </Card>
            )}

            {/* ──────── VARIETY TAB ──────── */}
            {activeTab === 'variety' && (
              <Card accent="gold" notch className="space-y-4">
                <SectionHeader title="Clip Variety" subtitle="Control randomness and ordering of generated clips" icon={<Shuffle className="w-4 h-4" />} terminal />

                <div>
                  <label className="terminal-label mb-1 block">Clip Order</label>
                  <select value={formData.CLIP_ORDER} onChange={e => setFormData({ ...formData, CLIP_ORDER: e.target.value })} className="cyber-input">
                    <option value="sequential">Sequential — play clips in order</option>
                    <option value="shuffle">Shuffle — randomize clip order per hour</option>
                  </select>
                  <p className="text-[10px] text-stone-500 mt-1">Shuffle uses the Variety Seed for deterministic randomization.</p>
                </div>

                <div>
                  <label className="terminal-label mb-1 block">Variety Seed</label>
                  <input type="number" min={0} max={999999} value={formData.VARIETY_SEED}
                    onChange={e => setFormData({ ...formData, VARIETY_SEED: e.target.value })}
                    className="cyber-input" placeholder="42" />
                  <p className="text-[10px] text-stone-500 mt-1">Integer seed for deterministic shuffle. Different seed = different clip order.</p>
                </div>
              </Card>
            )}

            {/* ──────── VOICE TAB ──────── */}
            {activeTab === 'voice' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card accent="gold" notch>
                  <SectionHeader title="Emotion Control" icon={<Mic className="w-4 h-4" />} terminal />
                  <div className="space-y-3 mt-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">TTS Emotion</label>
                      <select
                        value={formData.TTS_EMOTION || 'default'}
                        onChange={(e) => setFormData({...formData, TTS_EMOTION: e.target.value})}
                        className="w-full px-3 py-2 bg-40k-dark border border-40k-border rounded text-white focus:outline-none focus:border-40k-gold"
                      >
                        <option value="default">Default</option>
                        <option value="happy">Happy</option>
                        <option value="sad">Sad</option>
                        <option value="excited">Excited</option>
                        <option value="calm">Calm</option>
                        <option value="angry">Angry</option>
                        <option value="fearful">Fearful</option>
                        <option value="whisper">Whisper</option>
                      </select>
                      <p className="text-[10px] text-stone-500 mt-1">Emotional tone applied to TTS audio (Kokoro provider).</p>
                    </div>
                  </div>
                </Card>

                <Card accent="gold" notch>
                  <SectionHeader title="Speed Control" icon={<Gauge className="w-4 h-4" />} terminal />
                  <div className="space-y-3 mt-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">
                        TTS Speed: {formData.TTS_SPEED || '1.0'}x
                      </label>
                      <input
                        type="range"
                        min="0.5"
                        max="2.0"
                        step="0.1"
                        value={formData.TTS_SPEED || '1.0'}
                        onChange={(e) => setFormData({...formData, TTS_SPEED: e.target.value})}
                        className="w-full h-2 bg-40k-border rounded-full appearance-none cursor-pointer slider"
                      />
                      <div className="flex justify-between text-[10px] text-stone-500 mt-1">
                        <span>0.5x (Slow)</span>
                        <span>1.0x (Normal)</span>
                        <span>2.0x (Fast)</span>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>
            )}

            {/* ──────── SYSTEM TAB ──────── */}
            {activeTab === 'system' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card accent="crimson" notch>
                  <SectionHeader title="UI Theme" icon={<Palette className="w-4 h-4" />} terminal />
                  <div className="grid grid-cols-1 gap-2 mt-4">
                    {themes.map((t, idx) => (
                      <motion.button
                        key={t.id}
                        onClick={() => setTheme(t.id)}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.06, ...springGentle }}
                        whileHover={theme !== t.id ? { scale: 1.02, x: 4 } : {}}
                        whileTap={{ scale: 0.98 }}
                        className={`flex items-center gap-3 px-4 py-3 rounded border transition-all duration-300 text-left ${
                          theme === t.id
                            ? 'border-40k-gold bg-40k-gold/10 text-white shadow-[0_0_15px_rgb(var(--40k-gold-rgb)/0.2)]'
                            : 'border-40k-border bg-40k-card text-gray-400 hover:border-40k-gold/50 hover:text-gray-200'
                        }`}
                      >
                        <span className="text-xl">{t.icon}</span>
                        <div>
                          <div className="font-medium text-sm">{t.name}</div>
                          <div className="text-xs opacity-70">{t.description}</div>
                        </div>
                        {theme === t.id && (
                          <motion.span className="ml-auto text-40k-gold text-xs font-bold"
                            initial={{ scale: 0 }} animate={{ scale: 1 }}
                            transition={{ type: 'spring', stiffness: 200, damping: 10 }}>
                            ACTIVE
                          </motion.span>
                        )}
                      </motion.button>
                    ))}
                  </div>
                </Card>

                <div className="space-y-4">
                  <Card accent="crimson" notch>
                    <SectionHeader title="System Tools" icon={<Wrench className="w-4 h-4" />} terminal />
                    <div className="space-y-3 mt-4">
                      {[
                        { title: 'Cleanup Generated Files', desc: 'Deletes media, shorts, TTS, and transcripts. Keeps scripts.', icon: Trash2, color: 'text-40k-red-bright', border: 'border-40k-red-bright/50', hover: 'hover:bg-40k-red-bright/10', action: () => { if (window.confirm('Are you sure?')) cleanupMutation.mutate() }, mutation: cleanupMutation },
                      ].map(({ title, desc, icon: Icon, color, border, hover, action, mutation }) => (
                        <div key={title} className="p-3 bg-40k-dark rounded border border-40k-border flex justify-between items-center">
                          <div>
                            <h4 className="text-white text-sm font-medium">{title}</h4>
                            <p className="text-xs text-gray-400">{desc}</p>
                          </div>
                          <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                            onClick={action} disabled={mutation.isPending}
                            className={`cyber-button flex items-center gap-2 text-xs ${color} ${border} ${hover}`}>
                            <Icon className={`w-3.5 h-3.5 ${mutation.isPending ? 'animate-spin' : ''}`} />
                            {mutation.isPending ? 'Cleaning...' : 'Cleanup'}
                          </motion.button>
                        </div>
                      ))}
                    </div>
                  </Card>

                  <Card className="bg-40k-gold/10 border-40k-gold/30">
                    <div className="flex items-center gap-4">
                      <motion.div animate={{ rotate: [0, 5, -5, 0] }} transition={{ duration: 5, repeat: Infinity }}>
                        <Cpu className="w-8 h-8 text-40k-gold" />
                      </motion.div>
                      <div>
                        <h4 className="text-white font-display font-bold">Cogitator v2.0.0</h4>
                        <p className="text-xs text-40k-gold">Cyberpunk Edition • System Online</p>
                      </div>
                    </div>
                  </Card>
                </div>
              </div>
            )}

            {/* Always visible Save button */}
            <motion.div className="pt-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <motion.button
                whileHover={{ scale: 1.02, boxShadow: '0 0 20px rgb(var(--40k-gold-rgb) / 0.35)' }}
                whileTap={{ scale: 0.98 }}
                type="submit"
                disabled={saveMutation.isPending}
                className="cyber-button-primary flex items-center gap-2 w-full justify-center"
              >
                <motion.div animate={saveMutation.isPending ? { rotate: 360 } : {}} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
                  <Save className="w-4 h-4" />
                </motion.div>
                {saveMutation.isPending ? 'Saving...' : 'Save Configuration'}
              </motion.button>
            </motion.div>
          </form>
        )}
      </div>
    </motion.div>
  )
}
