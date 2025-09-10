import React, { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:51955/api/v1'
const API_KEY = 'dev-api-key'

interface Format {
  id: string
  name: string
  canonical_description: string
  created_at: string
  latest_version: string
  template_count: number
}

interface Template {
  id: string
  format_id: string
  version: string
  status: string
  created_at: string
  approved_at?: string
}

interface ProcessingJob {
  id: string
  status: string
  progress: number
  error_message?: string
}

function App() {
  const [formats, setFormats] = useState<Format[]>([])
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null)
  const [formatName, setFormatName] = useState('')
  const [formatVersion, setFormatVersion] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error' | ''>('')
  const [currentJob, setCurrentJob] = useState<ProcessingJob | null>(null)

  useEffect(() => {
    loadFormats()
  }, [])

  const loadFormats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/formats`, {
        headers: { Authorization: `Bearer ${API_KEY}` }
      })
      setFormats(response.data)
    } catch (error) {
      console.error('Error loading formats:', error)
    }
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(event.target.files)
  }

  const handleUpload = async () => {
    if (!selectedFiles || selectedFiles.length === 0) {
      setMessage('Please select files to upload')
      setMessageType('error')
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setMessage('')

    try {
      const formData = new FormData()
      
      for (let i = 0; i < selectedFiles.length; i++) {
        formData.append('files', selectedFiles[i])
      }
      
      if (formatName) formData.append('format_name', formatName)
      if (formatVersion) formData.append('format_version', formatVersion)

      const response = await axios.post(`${API_BASE}/formats/upload`, formData, {
        headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'multipart/form-data'
        }
      })

      const jobId = response.data.job_id
      setCurrentJob({ id: jobId, status: 'pending', progress: 0 })
      
      // Poll for job status
      pollJobStatus(jobId)
      
    } catch (error: any) {
      setMessage(`Upload failed: ${error.response?.data?.detail || error.message}`)
      setMessageType('error')
      setUploading(false)
    }
  }

  const pollJobStatus = async (jobId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/formats/jobs/${jobId}`, {
        headers: { Authorization: `Bearer ${API_KEY}` }
      })
      
      const job = response.data
      setCurrentJob(job)
      setUploadProgress(job.progress * 100)

      if (job.status === 'completed') {
        setMessage('Upload and processing completed successfully!')
        setMessageType('success')
        setUploading(false)
        setCurrentJob(null)
        loadFormats() // Refresh the formats list
        
        // Clear form
        setSelectedFiles(null)
        setFormatName('')
        setFormatVersion('')
        
      } else if (job.status === 'failed') {
        setMessage(`Processing failed: ${job.error_message}`)
        setMessageType('error')
        setUploading(false)
        setCurrentJob(null)
        
      } else if (job.status === 'processing' || job.status === 'pending') {
        // Continue polling
        setTimeout(() => pollJobStatus(jobId), 2000)
      }
      
    } catch (error) {
      console.error('Error polling job status:', error)
      setUploading(false)
      setCurrentJob(null)
    }
  }

  const downloadTemplate = async (templateId: string, type: string) => {
    try {
      const response = await axios.get(`${API_BASE}/templates/${templateId}/download?type=${type}`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `template_${templateId}.${type === 'json_schema' ? 'json' : type}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      
    } catch (error) {
      console.error('Error downloading template:', error)
    }
  }

  return (
    <div className="container">
      <div className="header">
        <h1>AI-Powered Documentation Ingestion Service</h1>
        <p>Upload documentation packages to generate reusable templates with full provenance tracking</p>
      </div>

      <div className="upload-section">
        <h2>Upload Documentation Package</h2>
        <p>Select a PDF specification and sample files (CSV, XML, JSON, Excel)</p>
        
        <div style={{ margin: '20px 0' }}>
          <input
            type="file"
            multiple
            accept=".pdf,.csv,.xml,.json,.xlsx,.xls"
            onChange={handleFileChange}
            disabled={uploading}
          />
        </div>

        <div style={{ margin: '20px 0' }}>
          <input
            type="text"
            placeholder="Format Name (optional)"
            value={formatName}
            onChange={(e) => setFormatName(e.target.value)}
            disabled={uploading}
            style={{ margin: '5px', padding: '8px', width: '200px' }}
          />
          <input
            type="text"
            placeholder="Version (optional)"
            value={formatVersion}
            onChange={(e) => setFormatVersion(e.target.value)}
            disabled={uploading}
            style={{ margin: '5px', padding: '8px', width: '100px' }}
          />
        </div>

        <button 
          className="btn" 
          onClick={handleUpload} 
          disabled={uploading || !selectedFiles}
        >
          {uploading ? 'Processing...' : 'Upload Package'}
        </button>

        {uploading && (
          <div>
            <div className="progress">
              <div 
                className="progress-bar" 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p>Progress: {uploadProgress.toFixed(1)}%</p>
            {currentJob && <p>Status: {currentJob.status}</p>}
          </div>
        )}

        {message && (
          <div className={messageType === 'error' ? 'error' : 'success'}>
            {message}
          </div>
        )}
      </div>

      <div className="formats-list">
        <h2>Available Formats ({formats.length})</h2>
        
        {formats.length === 0 ? (
          <p>No formats uploaded yet. Upload your first documentation package above!</p>
        ) : (
          formats.map(format => (
            <div key={format.id} className="format-card">
              <h3>{format.name}</h3>
              <p>{format.canonical_description}</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <small>
                    Latest Version: {format.latest_version} | 
                    Templates: {format.template_count} | 
                    Created: {new Date(format.created_at).toLocaleDateString()}
                  </small>
                </div>
                <div>
                  <button 
                    className="btn" 
                    onClick={() => window.open(`${API_BASE}/formats/${format.id}`, '_blank')}
                  >
                    View Details
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div style={{ marginTop: '40px', padding: '20px', background: '#f8f9fa', borderRadius: '8px' }}>
        <h3>API Information</h3>
        <p><strong>Base URL:</strong> {API_BASE}</p>
        <p><strong>Authentication:</strong> Bearer token (API Key: {API_KEY})</p>
        <p><strong>Supported File Types:</strong> PDF, CSV, XML, JSON, Excel (.xlsx, .xls)</p>
        
        <h4>Key Endpoints:</h4>
        <ul>
          <li><code>POST /formats/upload</code> - Upload documentation package</li>
          <li><code>GET /formats</code> - List all formats</li>
          <li><code>GET /templates/{{id}}</code> - Get template details</li>
          <li><code>GET /templates/{{id}}/download</code> - Download template artifacts</li>
        </ul>
      </div>
    </div>
  )
}

export default App