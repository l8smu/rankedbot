import { Router } from 'express';
import { storage } from './storage.js';
import { insertUserSchema, insertExpenseSchema, insertApprovalSchema } from '../shared/schema.js';

const router = Router();

// User routes
router.get('/api/users', async (req, res) => {
  try {
    const users = await storage.getAllUsers();
    res.json(users);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

router.get('/api/users/:id', async (req, res) => {
  try {
    const user = await storage.getUser(req.params.id);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch user' });
  }
});

router.post('/api/users', async (req, res) => {
  try {
    const userData = insertUserSchema.parse(req.body);
    const user = await storage.createUser(userData);
    res.status(201).json(user);
  } catch (error) {
    res.status(400).json({ error: 'Invalid user data' });
  }
});

// Expense routes
router.get('/api/expenses', async (req, res) => {
  try {
    const { userId, status, managerId } = req.query;
    
    let expenses;
    if (userId) {
      expenses = await storage.getExpensesByUser(userId as string);
    } else if (status) {
      expenses = await storage.getExpensesByStatus(status as string);
    } else if (managerId) {
      expenses = await storage.getExpensesByManager(managerId as string);
    } else {
      expenses = await storage.getAllExpenses();
    }
    
    res.json(expenses);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch expenses' });
  }
});

router.get('/api/expenses/:id', async (req, res) => {
  try {
    const expense = await storage.getExpense(req.params.id);
    if (!expense) {
      return res.status(404).json({ error: 'Expense not found' });
    }
    res.json(expense);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch expense' });
  }
});

router.post('/api/expenses', async (req, res) => {
  try {
    const expenseData = insertExpenseSchema.parse(req.body);
    const expense = await storage.createExpense(expenseData);
    res.status(201).json(expense);
  } catch (error) {
    res.status(400).json({ error: 'Invalid expense data' });
  }
});

router.patch('/api/expenses/:id', async (req, res) => {
  try {
    const updates = req.body;
    const expense = await storage.updateExpense(req.params.id, updates);
    res.json(expense);
  } catch (error) {
    res.status(400).json({ error: 'Failed to update expense' });
  }
});

// Approval routes
router.post('/api/expenses/:id/approve', async (req, res) => {
  try {
    const { approverId, reason } = req.body;
    const expenseId = req.params.id;
    
    // Create approval record
    const approval = await storage.createApproval({
      expenseId,
      approverId,
      action: 'approve',
      reason,
    });
    
    // Update expense status
    const expense = await storage.updateExpense(expenseId, {
      status: 'approved',
      approvedAt: new Date().toISOString(),
      approvedBy: approverId,
    });
    
    res.json({ expense, approval });
  } catch (error) {
    res.status(400).json({ error: 'Failed to approve expense' });
  }
});

router.post('/api/expenses/:id/reject', async (req, res) => {
  try {
    const { approverId, reason } = req.body;
    const expenseId = req.params.id;
    
    // Create approval record
    const approval = await storage.createApproval({
      expenseId,
      approverId,
      action: 'reject',
      reason,
    });
    
    // Update expense status
    const expense = await storage.updateExpense(expenseId, {
      status: 'rejected',
      rejectedAt: new Date().toISOString(),
      rejectedBy: approverId,
      rejectionReason: reason,
    });
    
    res.json({ expense, approval });
  } catch (error) {
    res.status(400).json({ error: 'Failed to reject expense' });
  }
});

// Dashboard stats
router.get('/api/dashboard/stats', async (req, res) => {
  try {
    const { userId } = req.query;
    const stats = await storage.getDashboardStats(userId as string);
    res.json(stats);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch dashboard stats' });
  }
});

// Export routes
router.get('/api/export/expenses', async (req, res) => {
  try {
    const { startDate, endDate, format = 'json' } = req.query;
    
    if (!startDate || !endDate) {
      return res.status(400).json({ error: 'Start date and end date are required' });
    }
    
    const expenses = await storage.getExpensesInDateRange(startDate as string, endDate as string);
    const users = await storage.getAllUsers();
    
    const exportData = {
      expenses,
      users,
      totalAmount: expenses.reduce((sum, expense) => sum + expense.amount, 0),
      dateRange: {
        start: startDate as string,
        end: endDate as string,
      },
    };
    
    if (format === 'csv') {
      // Convert to CSV format
      const csvHeader = 'ID,User,Title,Description,Amount,Category,Status,Submitted Date,Approved Date,Approved By\n';
      const csvRows = expenses.map(expense => {
        const user = users.find(u => u.id === expense.userId);
        const approver = expense.approvedBy ? users.find(u => u.id === expense.approvedBy) : null;
        return [
          expense.id,
          user?.name || 'Unknown',
          expense.title,
          expense.description.replace(/,/g, ';'),
          expense.amount,
          expense.category,
          expense.status,
          expense.submittedAt,
          expense.approvedAt || '',
          approver?.name || ''
        ].join(',');
      });
      
      const csvData = csvHeader + csvRows.join('\n');
      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', `attachment; filename="expenses-${startDate}-${endDate}.csv"`);
      res.send(csvData);
    } else {
      res.json(exportData);
    }
  } catch (error) {
    res.status(500).json({ error: 'Failed to export expenses' });
  }
});

export default router;