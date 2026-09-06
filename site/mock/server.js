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
  })
}

startServer().catch(console.error)
