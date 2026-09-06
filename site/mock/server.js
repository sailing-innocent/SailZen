/**
 * @file server.js
 * @brief Mock API Server for local development
 * @author sailing-innocent
 * @date 2025-08-12
 */

import express from 'express'
import cors from 'cors'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import fs from 'fs/promises'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const app = express()
const PORT = process.env.PORT || 3001

// Middleware
app.use(cors())
app.use(express.json())

// Mock data storage files
const DATA_DIR = join(__dirname, 'data')
const ACCOUNTS_FILE = join(DATA_DIR, 'accounts.json')
const TRANSACTIONS_FILE = join(DATA_DIR, 'transactions.json')
const WEIGHTS_FILE = join(DATA_DIR, 'weights.json')
const BODY_DATA_FILE = join(DATA_DIR, 'body_data.json')

// Builtin body metric registry mirror（与 site/src/lib/data/body_data.ts 及
// 后端 sail_server/application/dto/body_data.py 保持三端同步；mock 仅开发用）
const BODY_METRICS = [
  { key: 'weight', labelZh: '体重', labelEn: 'Weight', unit: 'kg', category: 'body', precision: 1, min: 20, max: 300, higherIsBetter: false, builtin: true },
  { key: 'height', labelZh: '身高', labelEn: 'Height', unit: 'cm', category: 'body', precision: 1, min: 100, max: 250, higherIsBetter: true, builtin: true },
  { key: 'chest', labelZh: '胸围', labelEn: 'Chest', unit: 'cm', category: 'body', precision: 1, min: 40, max: 200, higherIsBetter: true, builtin: true },
  { key: 'waist', labelZh: '腰围', labelEn: 'Waist', unit: 'cm', category: 'body', precision: 1, min: 40, max: 200, higherIsBetter: false, builtin: true },
  { key: 'hip', labelZh: '臀围', labelEn: 'Hip', unit: 'cm', category: 'body', precision: 1, min: 40, max: 250, higherIsBetter: false, builtin: true },
  { key: 'body_fat_pct', labelZh: '体脂率', labelEn: 'Body Fat', unit: '%', category: 'body', precision: 1, min: 1, max: 70, higherIsBetter: false, builtin: true },
  { key: 'muscle_mass', labelZh: '肌肉量', labelEn: 'Muscle Mass', unit: 'kg', category: 'body', precision: 1, min: 5, max: 150, higherIsBetter: true, builtin: true },
  { key: 'protein_powder', labelZh: '蛋白粉', labelEn: 'Protein Powder', unit: 'g', category: 'intake', precision: 0, min: 0, max: 300, higherIsBetter: true, builtin: true },
  { key: 'creatine', labelZh: '肌酸', labelEn: 'Creatine', unit: 'g', category: 'intake', precision: 1, min: 0, max: 50, higherIsBetter: true, builtin: true },
  { key: 'water', labelZh: '饮水量', labelEn: 'Water', unit: 'ml', category: 'intake', precision: 0, min: 0, max: 8000, higherIsBetter: true, builtin: true },
  { key: 'caffeine', labelZh: '咖啡因', labelEn: 'Caffeine', unit: 'mg', category: 'intake', precision: 0, min: 0, max: 1000, higherIsBetter: false, builtin: true },
]

// Ensure data directory and files exist
async function initializeData() {
  try {
    await fs.mkdir(DATA_DIR, { recursive: true })
    
    // Initialize accounts data
    try {
      await fs.access(ACCOUNTS_FILE)
    } catch {
      const defaultAccounts = [
        { id: 1, name: "现金", description: "现金账户", balance: "1000.00", state: 1, mtime: Date.now() },
        { id: 2, name: "银行卡", description: "银行储蓄卡", balance: "5000.00", state: 1, mtime: Date.now() },
        { id: 3, name: "支付宝", description: "支付宝余额", balance: "500.00", state: 1, mtime: Date.now() }
      ]
      await fs.writeFile(ACCOUNTS_FILE, JSON.stringify(defaultAccounts, null, 2))
    }
    
    // Initialize transactions data
    try {
      await fs.access(TRANSACTIONS_FILE)
    } catch {
      const defaultTransactions = [
        { 
          id: 1, 
          from_acc_id: 1, 
          to_acc_id: 2, 
          value: "100.00", 
          description: "转账测试", 
          tags: "test", 
          htime: Date.now() - 86400000 
        },
        { 
          id: 2, 
          from_acc_id: 2, 
          to_acc_id: 3, 
          value: "50.00", 
          description: "充值支付宝", 
          tags: "recharge", 
          htime: Date.now() - 43200000 
        }
      ]
      await fs.writeFile(TRANSACTIONS_FILE, JSON.stringify(defaultTransactions, null, 2))
    }
    
    // Initialize weights data
    try {
      await fs.access(WEIGHTS_FILE)
    } catch {
      const defaultWeights = [
        { id: 1, value: "70.5", htime: Date.now() - 86400000 },
        { id: 2, value: "70.2", htime: Date.now() - 43200000 },
        { id: 3, value: "70.8", htime: Date.now() }
      ]
      await fs.writeFile(WEIGHTS_FILE, JSON.stringify(defaultWeights, null, 2))
    }

    // Initialize body data (htime in Unix seconds, matching the real backend;
    // fixed timestamps consistent with the committed seed data/body_data.json)
    try {
      await fs.access(BODY_DATA_FILE)
    } catch {
      const defaultBodyData = [
        { id: 1, htime: 1754913352, data: { weight: 70.5, waist: 85.0 }, tag: '', description: '', source: 'manual', weightId: null, created_at: 1754913352 },
        { id: 2, htime: 1754956552, data: { weight: 70.2, waist: 84.5, water: 2000 }, tag: '', description: '', source: 'manual', weightId: null, created_at: 1754956552 },
        { id: 3, htime: 1754999752, data: { weight: 70.8, protein_powder: 30 }, tag: '', description: '', source: 'manual', weightId: null, created_at: 1754999752 },
      ]
      await fs.writeFile(BODY_DATA_FILE, JSON.stringify(defaultBodyData, null, 2))
    }
  } catch (error) {
    console.error('Error initializing data:', error)
  }
}

// Helper functions for data operations
async function readData(filePath) {
  try {
    const data = await fs.readFile(filePath, 'utf8')
    return JSON.parse(data)
  } catch (error) {
    console.error(`Error reading ${filePath}:`, error)
    return []
  }
}

async function writeData(filePath, data) {
  try {
    await fs.writeFile(filePath, JSON.stringify(data, null, 2))
  } catch (error) {
    console.error(`Error writing ${filePath}:`, error)
  }
}

function getNextId(data) {
  return data.length > 0 ? Math.max(...data.map(item => item.id)) + 1 : 1
}

// Health check endpoint
app.get('/api/v1/health', (req, res) => {
  res.json({ status: 'ok', message: 'Mock server is running' })
})

// ===================
// FINANCE API ROUTES
// ===================

// Account endpoints
app.get('/api/v1/finance/account/', async (req, res) => {
  try {
    const accounts = await readData(ACCOUNTS_FILE)
    res.json(accounts)
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch accounts' })
  }
})

app.get('/api/v1/finance/account/:id', async (req, res) => {
  try {
    const accounts = await readData(ACCOUNTS_FILE)
    const account = accounts.find(acc => acc.id === parseInt(req.params.id))
    
    if (!account) {
      return res.status(404).json({ error: 'Account not found' })
    }
    
    res.json(account)
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch account' })
  }
})

app.post('/api/v1/finance/account/', async (req, res) => {
  try {
    const accounts = await readData(ACCOUNTS_FILE)
    const newAccount = {
      id: getNextId(accounts),
      name: req.body.name,
      description: req.body.description || req.body.name,
      balance: "0.00",
      state: 1,
      mtime: Date.now()
    }
    
    accounts.push(newAccount)
    await writeData(ACCOUNTS_FILE, accounts)
    
    res.json(newAccount)
  } catch (error) {
    res.status(500).json({ error: 'Failed to create account' })
  }
})

app.post('/api/v1/finance/account/fix_balance/', async (req, res) => {
  try {
    const accounts = await readData(ACCOUNTS_FILE)
    const accountIndex = accounts.findIndex(acc => acc.id === req.body.id)
    
    if (accountIndex === -1) {
      return res.status(404).json({ error: 'Account not found' })
    }
    
    accounts[accountIndex].balance = req.body.balance
    accounts[accountIndex].mtime = Date.now()
    
    await writeData(ACCOUNTS_FILE, accounts)
    
    res.json(accounts[accountIndex])
  } catch (error) {
    res.status(500).json({ error: 'Failed to fix account balance' })
  }
})

app.get('/api/v1/finance/account/recalc_balance/:id', async (req, res) => {
  try {
    const accounts = await readData(ACCOUNTS_FILE)
    const transactions = await readData(TRANSACTIONS_FILE)
    const accountId = parseInt(req.params.id)
    const accountIndex = accounts.findIndex(acc => acc.id === accountId)
    
    if (accountIndex === -1) {
      return res.status(404).json({ error: 'Account not found' })
    }
    
    // Calculate balance from transactions
    let balance = 0
    transactions.forEach(transaction => {
      const value = parseFloat(transaction.value)
      if (transaction.to_acc_id === accountId) {
        balance += value
      }
      if (transaction.from_acc_id === accountId) {
        balance -= value
      }
    })
    
    accounts[accountIndex].balance = balance.toFixed(2)
    accounts[accountIndex].mtime = Date.now()
    
    await writeData(ACCOUNTS_FILE, accounts)
    
    res.json(accounts[accountIndex])
  } catch (error) {
    res.status(500).json({ error: 'Failed to recalculate account balance' })
  }
})

app.get('/api/v1/finance/account/update_balance/:id', async (req, res) => {
  try {
    // For mock, this is the same as recalc_balance
    const accounts = await readData(ACCOUNTS_FILE)
    const accountIndex = accounts.findIndex(acc => acc.id === parseInt(req.params.id))
    
    if (accountIndex === -1) {
      return res.status(404).json({ error: 'Account not found' })
    }
    
    accounts[accountIndex].mtime = Date.now()
    await writeData(ACCOUNTS_FILE, accounts)
    
    res.json(accounts[accountIndex])
  } catch (error) {
    res.status(500).json({ error: 'Failed to update account balance' })
  }
})

// Transaction endpoints
app.get('/api/v1/finance/transaction/', async (req, res) => {
  try {
    const transactions = await readData(TRANSACTIONS_FILE)
    const limit = parseInt(req.query.limit) || transactions.length
    
    // Sort by htime descending (most recent first)
    const sortedTransactions = transactions.sort((a, b) => b.htime - a.htime)
    const limitedTransactions = limit > 0 ? sortedTransactions.slice(0, limit) : sortedTransactions
    
    res.json(limitedTransactions)
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch transactions' })
  }
})

app.post('/api/v1/finance/transaction/', async (req, res) => {
  try {
    const transactions = await readData(TRANSACTIONS_FILE)
    const newTransaction = {
      id: getNextId(transactions),
      from_acc_id: req.body.from_acc_id,
      to_acc_id: req.body.to_acc_id,
      value: req.body.value,
      description: req.body.description,
      tags: req.body.tags,
      htime: req.body.htime || Date.now()
    }
    
    transactions.push(newTransaction)
    await writeData(TRANSACTIONS_FILE, transactions)
    
    res.json(newTransaction)
  } catch (error) {
    res.status(500).json({ error: 'Failed to create transaction' })
  }
})

app.delete('/api/v1/finance/transaction/:id', async (req, res) => {
  try {
    const transactions = await readData(TRANSACTIONS_FILE)
    const transactionId = parseInt(req.params.id)
    const transactionIndex = transactions.findIndex(t => t.id === transactionId)
    
    if (transactionIndex === -1) {
      return res.status(404).json({ 
        id: transactionId,
        status: 'error',
        message: 'Transaction not found' 
      })
    }
    
    transactions.splice(transactionIndex, 1)
    await writeData(TRANSACTIONS_FILE, transactions)
    
    res.json({
      id: transactionId,
      status: 'success',
      message: 'Transaction deleted successfully'
    })
  } catch (error) {
    res.status(500).json({ 
      id: parseInt(req.params.id),
      status: 'error',
      message: 'Failed to delete transaction' 
    })
  }
})

app.put('/api/v1/finance/transaction/:id', async (req, res) => {
  try {
    const transactions = await readData(TRANSACTIONS_FILE)
    const transactionId = parseInt(req.params.id)
    const transactionIndex = transactions.findIndex(t => t.id === transactionId)
    
    if (transactionIndex === -1) {
      return res.status(404).json({ error: 'Transaction not found' })
    }
    
    // Update transaction with new data while keeping the ID
    const updatedTransaction = {
      id: transactionId,
      from_acc_id: req.body.from_acc_id,
      to_acc_id: req.body.to_acc_id,
      value: req.body.value,
      description: req.body.description,
      tags: req.body.tags,
      htime: req.body.htime || transactions[transactionIndex].htime // Keep original time if not provided
    }
    
    transactions[transactionIndex] = updatedTransaction
    await writeData(TRANSACTIONS_FILE, transactions)
    
    res.json(updatedTransaction)
  } catch (error) {
    res.status(500).json({ error: 'Failed to update transaction' })
  }
})

// ===================
// HEALTH API ROUTES
// ===================

// Weight endpoints
app.get('/api/v1/health/weight/', async (req, res) => {
  try {
    const weights = await readData(WEIGHTS_FILE)
    const skip = parseInt(req.query.skip) || 0
    const limit = parseInt(req.query.limit) || -1
    const start = parseInt(req.query.start) || -1
    const end = parseInt(req.query.end) || -1
    
    let filteredWeights = weights
    
    // Filter by time range if provided
    if (start !== -1 && end !== -1) {
      filteredWeights = weights.filter(w => w.htime >= start && w.htime <= end)
    } else if (start !== -1) {
      filteredWeights = weights.filter(w => w.htime >= start)
    } else if (end !== -1) {
      filteredWeights = weights.filter(w => w.htime <= end)
    }
    
    // Sort by htime descending (most recent first)
    filteredWeights.sort((a, b) => b.htime - a.htime)
    
    // Apply skip and limit
    const startIndex = skip
    const endIndex = limit === -1 ? filteredWeights.length : startIndex + limit
    const result = filteredWeights.slice(startIndex, endIndex)
    
    res.json(result)
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch weights' })
  }
})

app.get('/api/v1/health/weight/:id', async (req, res) => {
  try {
    const weights = await readData(WEIGHTS_FILE)
    const weight = weights.find(w => w.id === parseInt(req.params.id))
    
    if (!weight) {
      return res.status(404).json({ error: 'Weight record not found' })
    }
    
    res.json(weight)
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch weight' })
  }
})

app.post('/api/v1/health/weight/', async (req, res) => {
  try {
    const weights = await readData(WEIGHTS_FILE)
    const newWeight = {
      id: getNextId(weights),
      value: req.body.value,
      htime: req.body.htime || Date.now()
    }
    
    weights.push(newWeight)
    await writeData(WEIGHTS_FILE, weights)
    
    res.json(newWeight)
  } catch (error) {
    res.status(500).json({ error: 'Failed to create weight record' })
  }
})

// ===================
// BODY DATA API ROUTES
// ===================

// NOTE: static segments (/metrics, /series, /analysis) are registered BEFORE /:id
// so express does not treat them as an id parameter.

// GET /api/v1/health/body-data/metrics — builtin + discovered custom metrics
app.get('/api/v1/health/body-data/metrics', async (req, res) => {
  try {
    const records = await readData(BODY_DATA_FILE)
    const seen = new Set(BODY_METRICS.map((m) => m.key))
    const custom = []
    for (const record of records) {
      for (const key of Object.keys(record.data || {})) {
        if (!seen.has(key)) {
          seen.add(key)
          custom.push({ key, labelZh: key, labelEn: key, unit: '', category: 'body', precision: 1, higherIsBetter: true, builtin: false })
        }
      }
    }
    custom.sort((a, b) => a.key.localeCompare(b.key))
    res.json([...BODY_METRICS, ...custom])
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch body metrics' })
  }
})

// GET /api/v1/health/body-data/series?metric=<key> — points only from records that measured the metric
app.get('/api/v1/health/body-data/series', async (req, res) => {
  try {
    const metric = req.query.metric
    if (!metric) {
      return res.status(422).json({ detail: 'metric query parameter is required' })
    }
    const records = await readData(BODY_DATA_FILE)
    const start = parseInt(req.query.start) || -1
    const end = parseInt(req.query.end) || -1
    const unit = BODY_METRICS.find((m) => m.key === metric)?.unit || ''
    const points = records
      .filter((r) => r.data && typeof r.data[metric] === 'number')
      .filter((r) => (start === -1 || r.htime >= start) && (end === -1 || r.htime <= end))
      .map((r) => ({ id: r.id, htime: r.htime, value: r.data[metric] }))
      .sort((a, b) => a.htime - b.htime)
    res.json({ metric, unit, points })
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch body series' })
  }
})

// GET /api/v1/health/body-data/analysis?metric=<key>&model_type=linear
app.get('/api/v1/health/body-data/analysis', async (req, res) => {
  try {
    const metric = req.query.metric
    if (!metric) {
      return res.status(422).json({ detail: 'metric query parameter is required' })
    }
    const records = await readData(BODY_DATA_FILE)
    const unit = BODY_METRICS.find((m) => m.key === metric)?.unit || ''
    const points = records
      .filter((r) => r.data && typeof r.data[metric] === 'number')
      .map((r) => ({ htime: r.htime, value: r.data[metric] }))
      .sort((a, b) => a.htime - b.htime)

    const zero = {
      metric,
      unit,
      model_type: req.query.model_type || 'linear',
      slope: 0,
      intercept: 0,
      r_squared: 0,
      current_value: 0,
      current_trend: 'stable',
      predicted_points: [],
    }
    if (points.length < 2) {
      return res.json(zero)
    }

    const firstTime = points[0].htime
    const x = points.map((p) => (p.htime - firstTime) / 86400)
    const y = points.map((p) => p.value)
    const n = points.length
    const sumX = x.reduce((a, b) => a + b, 0)
    const sumY = y.reduce((a, b) => a + b, 0)
    const sumXX = x.reduce((a, b) => a + b * b, 0)
    const sumXY = x.reduce((a, b, i) => a + b * y[i], 0)
    const denom = n * sumXX - sumX * sumX
    const slope = denom !== 0 ? (n * sumXY - sumX * sumY) / denom : 0
    const intercept = (sumY - slope * sumX) / n
    const meanY = sumY / n
    const ssRes = y.reduce((a, b, i) => a + (b - (slope * x[i] + intercept)) ** 2, 0)
    const ssTot = y.reduce((a, b) => a + (b - meanY) ** 2, 0)
    const rSquared = ssTot !== 0 ? 1 - ssRes / ssTot : 0

    const lastTime = points[points.length - 1].htime
    const lastDay = (lastTime - firstTime) / 86400
    const predictedPoints = points.map((p) => ({ htime: p.htime, value: p.value, is_actual: true }))
    for (let day = 1; day <= 30; day++) {
      predictedPoints.push({
        htime: lastTime + day * 86400,
        value: slope * (lastDay + day) + intercept,
        is_actual: false,
      })
    }

    const trend = slope > 1e-9 ? 'increasing' : slope < -1e-9 ? 'decreasing' : 'stable'
    res.json({
      metric,
      unit,
      model_type: req.query.model_type || 'linear',
      slope,
      intercept,
      r_squared: rSquared,
      current_value: points[points.length - 1].value,
      current_trend: trend,
      predicted_points: predictedPoints,
    })
  } catch (error) {
    res.status(500).json({ error: 'Failed to analyze body metric' })
  }
})

// GET /api/v1/health/body-data/ — list with skip/limit/start/end/metric
app.get('/api/v1/health/body-data/', async (req, res) => {
  try {
    const records = await readData(BODY_DATA_FILE)
    const skip = parseInt(req.query.skip) || 0
    const limit = parseInt(req.query.limit) || -1
    const start = parseInt(req.query.start) || -1
    const end = parseInt(req.query.end) || -1
    const metric = req.query.metric || ''

    let filtered = records
    if (metric) {
      filtered = filtered.filter((r) => r.data && typeof r.data[metric] === 'number')
    }
    if (start !== -1) {
      filtered = filtered.filter((r) => r.htime >= start)
    }
    if (end !== -1) {
      filtered = filtered.filter((r) => r.htime <= end)
    }

    // Sort by htime descending (most recent first), then apply skip/limit
    filtered.sort((a, b) => b.htime - a.htime)
    const endIndex = limit === -1 ? filtered.length : skip + limit
    res.json(filtered.slice(skip, endIndex))
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch body data list' })
  }
})

// POST /api/v1/health/body-data/ — create; dual-writes to weights.json when data.weight present
app.post('/api/v1/health/body-data/', async (req, res) => {
  try {
    const records = await readData(BODY_DATA_FILE)
    const now = Math.floor(Date.now() / 1000)
    const newRecord = {
      id: getNextId(records),
      htime: req.body.htime || now,
      data: req.body.data || {},
      tag: req.body.tag || '',
      description: req.body.description || '',
      source: req.body.source || 'manual',
      // camelCase to match the real backend DTO (BodyDataResponse.weightId)
      weightId: null,
      created_at: now,
    }

    // Dual-write to weights.json to mimic the real backend (plan/dashboard compatibility)
    if (newRecord.source === 'manual' && typeof newRecord.data.weight === 'number') {
      const weights = await readData(WEIGHTS_FILE)
      const newWeight = {
        id: getNextId(weights),
        value: newRecord.data.weight.toString(),
        htime: newRecord.htime * 1000, // weights.json uses ms timestamps in this mock
        tag: newRecord.tag,
        description: newRecord.description,
      }
      weights.push(newWeight)
      await writeData(WEIGHTS_FILE, weights)
      newRecord.weightId = newWeight.id
    }

    records.push(newRecord)
    await writeData(BODY_DATA_FILE, records)
    res.json(newRecord)
  } catch (error) {
    res.status(500).json({ error: 'Failed to create body data' })
  }
})

// GET /api/v1/health/body-data/:id
app.get('/api/v1/health/body-data/:id', async (req, res) => {
  try {
    const records = await readData(BODY_DATA_FILE)
    const record = records.find((r) => r.id === parseInt(req.params.id))
    if (!record) {
      return res.status(404).json({ error: 'Body data record not found' })
    }
    res.json(record)
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch body data' })
  }
})

// PUT /api/v1/health/body-data/:id
app.put('/api/v1/health/body-data/:id', async (req, res) => {
  try {
    const records = await readData(BODY_DATA_FILE)
    const index = records.findIndex((r) => r.id === parseInt(req.params.id))
    if (index === -1) {
      return res.status(404).json({ error: 'Body data record not found' })
    }
    const updated = { ...records[index], ...req.body, id: records[index].id }
    records[index] = updated
    await writeData(BODY_DATA_FILE, records)
    res.json(updated)
  } catch (error) {
    res.status(500).json({ error: 'Failed to update body data' })
  }
})

// DELETE /api/v1/health/body-data/:id
app.delete('/api/v1/health/body-data/:id', async (req, res) => {
  try {
    const records = await readData(BODY_DATA_FILE)
    const record = records.find((r) => r.id === parseInt(req.params.id))
    if (!record) {
      return res.status(404).json({ error: 'Body data record not found' })
    }
    await writeData(BODY_DATA_FILE, records.filter((r) => r.id !== record.id))

    // Cascade: remove the dual-written weight row (mirrors the real backend)
    if (record.weightId != null) {
      const weights = await readData(WEIGHTS_FILE)
      await writeData(WEIGHTS_FILE, weights.filter((w) => w.id !== record.weightId))
    }

    res.json({ status: 'ok' })
  } catch (error) {
    res.status(500).json({ error: 'Failed to delete body data' })
  }
})

// Start server
async function startServer() {
  await initializeData()
  
  app.listen(PORT, () => {
    console.log(`🚀 Mock API Server is running on http://localhost:${PORT}`)
    console.log(`📊 API Base URL: http://localhost:${PORT}/api/v1`)
    console.log('📋 Available endpoints:')
    console.log('  Health: GET /api/v1/health')
    console.log('  Finance:')
    console.log('    - GET    /api/v1/finance/account/')
    console.log('    - GET    /api/v1/finance/account/:id')
    console.log('    - POST   /api/v1/finance/account/')
    console.log('    - POST   /api/v1/finance/account/fix_balance/')
    console.log('    - GET    /api/v1/finance/account/recalc_balance/:id')
    console.log('    - GET    /api/v1/finance/account/update_balance/:id')
    console.log('    - GET    /api/v1/finance/transaction/')
    console.log('    - POST   /api/v1/finance/transaction/')
    console.log('    - PUT    /api/v1/finance/transaction/:id')
    console.log('    - DELETE /api/v1/finance/transaction/:id')
    console.log('  Health:')
    console.log('    - GET    /api/v1/health/weight/')
    console.log('    - GET    /api/v1/health/weight/:id')
    console.log('    - POST   /api/v1/health/weight/')
    console.log('    - GET    /api/v1/health/body-data/')
    console.log('    - POST   /api/v1/health/body-data/')
    console.log('    - GET    /api/v1/health/body-data/metrics')
    console.log('    - GET    /api/v1/health/body-data/series?metric=')
    console.log('    - GET    /api/v1/health/body-data/analysis?metric=')
    console.log('    - GET    /api/v1/health/body-data/:id')
    console.log('    - PUT    /api/v1/health/body-data/:id')
    console.log('    - DELETE /api/v1/health/body-data/:id')
  })
}

startServer().catch(console.error)
