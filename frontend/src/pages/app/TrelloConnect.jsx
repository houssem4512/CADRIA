import { useState } from 'react'
import api, { errorMessage } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import { Button, Card, Input, Badge, EmptyState, Alert } from '../../components/ui'
import { CheckCircle2, Plug, RefreshCw, Trash2, ExternalLink, AlertTriangle } from 'lucide-react'

export function TrelloConnect({ project, onChanged }) {
  const { data: status, refetch } = useQuery(`/trello/status/?project=${project.id}`)
  const [connecting, setConnecting] = useState(false)
  const [token, setToken] = useState('')
  const [boardId, setBoardId] = useState('')
  const [boards, setBoards] = useState([])
  const [loadingBoards, setLoadingBoards] = useState(false)
  const [error, setError] = useState(null)
  const [authUrl, setAuthUrl] = useState(null)

  const connected = status?.connected

  const getAuthUrl = async () => {
    try {
      const { data } = await api.get('/trello/auth-url/')
      setAuthUrl(data.auth_url)
      window.open(data.auth_url, '_blank')
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  const loadBoards = async () => {
    if (!token) return
    setLoadingBoards(true)
    try {
      const { data } = await api.get(`/trello/boards/?token=${token}`)
      setBoards(data.boards || [])
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoadingBoards(false)
    }
  }

  const connect = async () => {
    if (!token || !boardId) {
      setError('Token and Board ID required')
      return
    }
    setConnecting(true)
    setError(null)
    try {
      await api.post('/trello/connect/', {
        project: project.id,
        token,
        board_id: boardId,
      })
      await refetch()
      await onChanged()
      setToken('')
      setBoardId('')
      setBoards([])
      setAuthUrl(null)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setConnecting(false)
    }
  }

  const disconnect = async () => {
    try {
      await api.post('/trello/disconnect/', { project: project.id })
      await refetch()
      await onChanged()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  if (connected) {
    return (
      <Card className="border-emerald-200 bg-emerald-50">
        <div className="card-body flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500 flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="font-semibold text-emerald-900">Trello Connected</p>
              <p className="text-xs text-emerald-700">
                Board: {status?.board_name || 'Unknown'} ({status?.board_id})
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <a
              href={`https://trello.com/b/${status?.board_id}`}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-sm"
            >
              <ExternalLink size={14} /> Open Board
            </a>
            <Button variant="danger" size="sm" icon={Trash2} onClick={disconnect}>
              Disconnect
            </Button>
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="card-body space-y-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-slate-200 flex items-center justify-center">
            <Plug className="w-5 h-5 text-slate-500" />
          </div>
          <div>
            <p className="font-semibold">Connect to Trello</p>
            <p className="text-xs text-slate-500">
              Connect your Trello account to push tasks automatically
            </p>
          </div>
        </div>

        {error && (
          <Alert tone="error">
            <AlertTriangle size={14} className="inline mr-1" />
            {error}
          </Alert>
        )}

        {/* Step 1: Authorize */}
        <div>
          <p className="text-xs font-medium text-slate-600 mb-2">
            Step 1: Authorize Cadria on Trello
          </p>
          <Button variant="primary" size="sm" onClick={getAuthUrl}>
            <ExternalLink size={14} /> Authorize on Trello
          </Button>
          {authUrl && (
            <p className="text-[11px] text-slate-400 mt-1">
              A new tab opened. Authorize, then copy the token.
            </p>
          )}
        </div>

        {/* Step 2: Paste token */}
        <div>
          <p className="text-xs font-medium text-slate-600 mb-2">
            Step 2: Paste your Trello token
          </p>
          <Input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Paste token here..."
            className="font-mono text-sm"
          />
          <Button
            variant="secondary"
            size="sm"
            className="mt-2"
            onClick={loadBoards}
            disabled={!token || loadingBoards}
          >
            {loadingBoards ? 'Loading boards...' : 'List my boards'}
          </Button>
        </div>

        {/* Step 3: Select board */}
        <div>
          <p className="text-xs font-medium text-slate-600 mb-2">
            Step 3: Select or enter board ID
          </p>
          {boards.length > 0 ? (
            <select
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={boardId}
              onChange={(e) => setBoardId(e.target.value)}
            >
              <option value="">Select a board...</option>
              {boards.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          ) : (
            <Input
              value={boardId}
              onChange={(e) => setBoardId(e.target.value)}
              placeholder="Board ID (from Trello URL)"
              className="font-mono text-sm"
            />
          )}
        </div>

        {/* Connect button */}
        <Button
          variant="primary"
          onClick={connect}
          disabled={!token || !boardId || connecting}
        >
          {connecting ? 'Connecting...' : 'Connect Trello'}
        </Button>
      </div>
    </Card>
  )
}

export default TrelloConnect
